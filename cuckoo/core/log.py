# Copyright (C) 2016-2017 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import copy
import json
import logging
import logging.handlers
import thread
import time

from cuckoo.common.colors import red, yellow, cyan
from cuckoo.core.database import Database
from cuckoo.misc import cwd

_tasks = {}
_loggers = {}

class DatabaseHandler(logging.Handler):
    """Logging to database handler.
    Used to log errors related to tasks in database.
    """

    def emit(self, record):
        if hasattr(record, "task_id"):
            db = Database()
            db.add_error(self.format(record), int(record.task_id))

class TaskHandler(logging.Handler):
    """Per-task logger.
    Used to log all task specific events to a per-task cuckoo.log log file.
    """

    def emit(self, record):
        task_id = _tasks.get(thread.get_ident())
        if not task_id:
            return

        with open(cwd("cuckoo.log", analysis=task_id), "a+b") as f:
            f.write("%s\n" % self.format(record))

class ConsoleHandler(logging.StreamHandler):
    """Logging to console handler."""

    def emit(self, record):
        colored = copy.copy(record)

        if record.levelname == "WARNING":
            colored.msg = yellow(record.msg)
        elif record.levelname == "ERROR" or record.levelname == "CRITICAL":
            colored.msg = red(record.msg)
        else:
            if "analysis procedure completed" in record.msg:
                colored.msg = cyan(record.msg)
            else:
                colored.msg = record.msg

        logging.StreamHandler.emit(self, colored)

class JsonFormatter(logging.Formatter):
    """Logging Cuckoo logs to JSON."""

    def format(self, record):
        action = record.__dict__.get("action")
        status = record.__dict__.get("status")
        task_id = _tasks.get(
            thread.get_ident(), record.__dict__.get("task_id")
        )
        return json.dumps({
            "action": action,
            "task_id": task_id,
            "status": status,
            "time": int(time.time()),
            "message": logging.Formatter.format(self, record),
            "level": record.levelname.lower(),
        })

    def filter(self, record):
        action = record.__dict__.get("action")
        status = record.__dict__.get("status")
        return action and status

def task_log_start(task_id):
    """Associate a thread with a task."""
    _tasks[thread.get_ident()] = task_id

def task_log_stop(task_id):
    """Disassociate a thread from a task."""
    _tasks.pop(thread.get_ident(), None)

def init_logger(root, name):
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    if name == "cuckoo.log":
        l = logging.handlers.WatchedFileHandler(cwd("log", "cuckoo.log"))
        l.setFormatter(formatter)
        root.addHandler(l)

    if name == "cuckoo.json":
        j = JsonFormatter()
        l = logging.handlers.WatchedFileHandler(cwd("log", "cuckoo.json"))
        l.setFormatter(j)
        l.addFilter(j)
        root.addHandler(l)

    if name == "console":
        l = ConsoleHandler()
        l.setFormatter(formatter)
        root.addHandler(l)

    if name == "database":
        l = DatabaseHandler()
        l.setLevel(logging.ERROR)
        root.addHandler(l)

    if name == "task":
        l = TaskHandler()
        l.setFormatter(formatter)
        root.addHandler(l)

    _loggers[name] = l

def logger(name, message, *args, **kwargs):
    """Log a message to specific logger instance."""
    record = logging.LogRecord(
        _loggers[name].name, logging.INFO, None,
        None, message, args, None, None
    )
    record.__dict__.update(kwargs)
    _loggers[name].handle(record)