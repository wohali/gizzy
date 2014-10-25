"""\
Dynamically change Gizzy's log level
"""

import logging


LEVELS = {
    "ALL": logging.NOTSET,
    "TRACE": 1,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


@command(["log", "<level>"], require_owner=True)
def loglevel(msg, client):
    level = msg.group("level").upper()
    if level in LEVELS:
        logging.getLogger().setLevel(LEVELS[level])
        msg.respond("Log level set to: {0}".format(level))
    else:
        msg.respond("Unknown log level: {0}".format(msg.group(level)))
