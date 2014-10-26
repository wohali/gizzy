#!/usr/bin/env python


import copy
import datetime
import functools
import logging
import inspect
import json
import optparse as op
import os
import Queue
import re
import socket
import StringIO
import sys
import threading
import time
import traceback


TRACE = 1
log = logging.getLogger("main")


STYLES = {
    "bold": "\x02",
    "reset": "\x0F",
    "italic": "\x26",
    "reverse": "\x26",
    "underline": "\x37",
    "white": "\x0300",
    "black": "\x0301",
    "dark_blue": "\x0302",
    "dblue": "\x0302",
    "dark_green": "\x0303",
    "dgreen": "\x0303",
    "dark_red": "\x0304",
    "dred": "\x0304",
    "brownish": "\x0305",
    "brown": "\x0305",
    "dark_purple": "\x0306",
    "dpurple": "\x0306",
    "orange": "\x0307",
    "yellow": "\x0308",
    "light_green": "\x0309",
    "lgreen": "\x0309",
    "dark_teal": "\x0310",
    "dteal": "\x0310",
    "light_teal": "\x0311",
    "lteal": "\x0311",
    "light_blue": "\x0312",
    "lblue": "\x0312",
    "light_purple": "\x0313",
    "lpurple": "\x0313",
    "dark_gray": "\x0314",
    "dgray": "\x0314",
    "light_gray": "\x0315",
    "lgray": "\x0315"
}


class Config(object):
    def __init__(self):
        self.data = {
            "logfile": None,
            "host": "irc.freenode.net",
            "port": 6667,
            "nick": "gizzy-{0:06d}".format(os.getpid()),
            "name": "GizzyBot {0:06d}".format(os.getpid()),
            "user": "gizzy-{0:06d}".format(os.getpid()),
            "serverpass": None,
            "nickpass": None,
            "channels": [],
            "owners": [],
            "plugins": "./plugins",
            "command_prefix": "."
        }

    def load(self, fname):
        if not os.path.exists(fname):
            log.error("Missing config file: {0}".format(fname))
            exit(1)
        try:
            execfile(fname, self.data)
        except Exception, e:
            log.error("Error loading: {0}".format(fname))
            log.error("{0}".format(e))
            exit(1)

    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(name)

    def _get_channels(self):
        ret = []
        for c in self.data["channels"]:
            if isinstance(c, basestring):
                chname = c
                pwd = None
            elif isinstance(c, tuple) and len(c) == 2:
                (chname, pwd) = c
            else:
                raise ValueError("Invalid channel: {0}".format(c))
            if chname[:1] != "#":
                chname = "#{0}".format(chname.strip())
            ret.append((chname, pwd))
        return ret

    channels = property(_get_channels)


class Message(object):
    SOURCE_RE = re.compile(r'([^!]*)!?([^@]*)@?(.*)')

    def __init__(self, client, line):
        self.client = client
        self.raw = line
        self.source = None
        self.nick = None
        self.user = None
        self.host = None
        self.args = None
        self.sender = None
        self.target = None
        self.event = None
        self.text = None
        self.owner = False
        self.match = None
        self.groups = None
        self.group = None

        if line[:1] == u":":
            self.source, line = line[1:].split(u" ", 1)
            match = self.SOURCE_RE.match(self.source)
            self.nick, self.user, self.host = match.groups()
        else:
            self.source = None

        if u" :" in line:
            argstr, self.text = line.split(u" :", 1)
        else:
            argstr, self.text = line, u""
        self.args = argstr.split()

        if len(self.args) > 0:
            self.event = self.args.pop(0)
        if len(self.args) > 0:
            self.target = self.args.pop(0)

        if self.target == self.client.cfg.nick:
            self.sender = self.nick
        else:
            self.sender = self.target

        if self.nick in self.client.cfg.owners:
            self.owner = True

    def __str__(self):
        parts = {
            "sender": self.sender,
            "target": self.target,
            "event": self.event,
            "text": self.text
        }
        parts = ["%r=%r" % kv for kv in parts.items()]
        return "<Message %s>" % " ".join(sorted(parts))

    def do(self, text):
        self.client.action(self.sender, text)

    def reply(self, text):
        self.client.msg(self.sender, text)

    def respond(self, text):
        self.client.msg(self.sender, u"{0}: {1}".format(self.nick, text))

    def notify(self, text):
        self.client.notify(self.sender, text)


class Action(object):
    def __init__(self, event='PRIVMSG', require_owner=False):
        self.event = event
        self.require_owner = require_owner
        self.func = None
        self.docs = None
        self.regexps = []
        self.name = None

    def __call__(self, func):
        if func.__doc__:
            self.docs = func.__doc__.splitlines()[0].strip()
        args = inspect.getargspec(func)
        if len(args[0]) == 1:
            self.func = lambda m, s: func(m)
        elif len(args[0]) == 2:
            self.func = func
        else:
            raise ValueError("Invalid action argspec")
        return self

    def compile(self, cfg):
        raise NotImplemented

    def handle(self, msg, state):
        if msg.event != self.event and self.event != '*':
            return
        msg = copy.copy(msg)
        for regexp in self.regexps:
            match = regexp.search(msg.text)
            if not match:
                continue
            if self.require_owner and not msg.owner:
                msg.respond("You are not an owner of this bot.")
                raise StopIteration
            args = (self.name, msg.text, regexp.pattern)
            log.debug("Action triggered: {0} {1} {2}".format(*args))
            msg.match = match
            msg.groups = match.groups()
            msg.group = match.group
            self.func(msg, state)


class Command(Action):
    ARG_PATTERN = "^<(?P<name>[_a-zA-Z][_a-zA-Z0-9]*)(?P<pattern>:[^>]+)?>$"
    ARG_RE = re.compile(ARG_PATTERN)

    def __init__(self, cmd, **kwargs):
        super(Command, self).__init__(**kwargs)
        self.cmd = cmd
        self.name = " ".join(cmd)

    def compile(self, cfg):
        prefixes = [
            "^$nick[,:]?\s+",
            "^" + re.escape(cfg.command_prefix)
        ]
        parts = []
        for c in self.cmd:
            match = self.ARG_RE.match(c)
            if not match:
                parts.append(re.escape(c))
            else:
                name, pattern = match.groups()
                if pattern:
                    assert pattern[:1] == ":"
                    parts.append("(?P<{0}>{1})".format(name, pattern[1:]))
                else:
                    parts.append("(?P<{0}>\S+)".format(name))
        cmd = "\s+".join(parts)
        for p in prefixes:
            pattern = (p + cmd + "$").replace("$nick", re.escape(cfg.nick))
            self.regexps.append(re.compile(pattern.decode("utf-8")))


class Rule(Action):
    def __init__(self, pattern, name=None, **kwargs):
        super(Rule, self).__init__(**kwargs)
        self.pattern = pattern
        if name is None:
            self.name = self.pattern

    def compile(self, cfg):
        self.pattern = self.pattern.replace("$nick", re.escape(cfg.nick))
        self.pattern = self.pattern.decode("utf-8")
        self.regexps.append(re.compile(self.pattern))


class Plugin(object):
    def __init__(self, cfg, cli, plugin_mgr, fname):
        self.cfg = cfg
        self.fname = fname
        self.state = None
        self.actions = []
        self.data = copy.copy(globals())
        self.data.update({
            "irc": cli,
            "plugin_manager": plugin_mgr,
            "log": self._get_logger(),
            "config": self.cfg,
            "command": Command,
            "rule": Rule
        })
        if not os.path.exists(self.fname):
            raise ValueError("Plugin not found: {0}".format(self.fname))

    def load(self):
        execfile(self.fname, self.data)
        if callable(self.data.get("load")):
            self.state = self.data["load"]()
        for (k, v) in self.data.iteritems():
            if isinstance(v, Action):
                v.compile(self.cfg)
                self.actions.append(v)

    def unload(self):
        if callable(self.data.get("unload")):
            self.data["unload"](self.state)

    def handle(self, msg):
        for a in self.actions:
            try:
                a.handle(msg, self.state)
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise
            except StopIteration:
                raise
            except:
                log.exception("Error handling msg: {0}".format(msg))

    @property
    def name(self):
        name = os.path.relpath(self.fname, self.cfg.plugins)
        return os.path.splitext(name)[0]

    def _get_logger(self):
        base = os.path.basename(self.fname)
        name = os.path.splitext(base)[0]
        return logging.getLogger(name)


class PluginManager(object):
    def __init__(self, config, client):
        self.cfg = config
        self.cli = client
        self.plugins = []

    def load(self):
        if len(self.plugins):
            self.unload()
        for dpath, dnames, fnames in os.walk(self.cfg.plugins):
            for fname in fnames:
                if fname[-3:] != ".py":
                    continue
                fname = os.path.join(dpath, fname)
                p = Plugin(self.cfg, self.cli, self, fname)
                try:
                    p.load()
                    log.info("Loaded: {0}".format(p.fname))
                    self.plugins.append(p)
                except:
                    log.exception("Error loading: {0}".format(p.fname))

    def unload(self):
        while len(self.plugins):
            p = self.plugins.pop(0)
            try:
                p.unload()
                log.info("Unloaded: {0}".format(p.fname))
            except:
                log.exception("Error unloading: {0}".format(p.fname))

    def handle(self, msg):
        try:
            for p in self.plugins:
                p.handle(msg)
        except StopIteration:
            pass


class Reader(object):
    def __init__(self, client, sock):
        self.client = client
        self.sock = sock
        self.buf = StringIO.StringIO()
        self.q = Queue.Queue()
        self.t = threading.Thread(target=self.run, args=tuple())
        self.t.setDaemon(True)
        self.t.start()

    def is_alive(self):
        return self.t.is_alive()

    def next(self, timeout=None):
        return self.q.get(True, timeout)

    def run(self):
        while True:
            try:
                self.recv()
            except:
                log.exception("Error receiving data")
                return

    def recv(self):
        data = self.sock.recv(4096)
        while data.find("\n") > 0:
            (msg, data) = data.split("\n", 1)
            self.handle(msg)
        self.buf.write(data)

    def handle(self, msg):
        log.log(TRACE, "RECV: %r" % msg)
        if self.buf.tell() > 0:
            self.buf.write(msg)
            msg = self.buf.getvalue()
            self.buf = StringIO.StringIO()
        msg = msg.rstrip("\r")
        try:
            msg = self.parse(msg)
        except:
            log.exception(u"Error parsing line: %s" % msg)
        log.log(TRACE, msg)
        self.q.put(msg)

    def parse(self, line):
        decoded = False
        for enc in ("utf-8", "iso-8859-1"):
            try:
                line = line.decode(enc)
                decoded = True
                break
            except UnicodeDecodeError:
                pass
        if not decoded:
            line = line.decode("utf-8", "replace")
        return Message(self.client, line)


class Writer(object):
    def __init__(self, client, sock):
        self.client = client
        self.sock = sock
        self.sent = []
        self.q = Queue.Queue()
        self.t = threading.Thread(target=self.run, args=tuple())
        self.t.setDaemon(True)
        self.t.start()

    def is_alive(self):
        return self.t.is_alive()

    def action(self, recip, text):
        msg = "\001ACTION {0}\001".format(text)
        self.msg(recip, msg)

    def msg(self, recip, text):
        self.write(('PRIVMSG', recip), text)

    def notice(self, recip, text):
        self.write(('NOTICE', recip), text)

    def write(self, args, text=None):
        msg = u" ".join(self.fmt(a) for a in args)
        if text is not None:
            msg += u" :" + self.fmt(text)
        msg = msg[:510] + u"\r\n"
        self.q.put(msg)

    def run(self):
        while True:
            try:
                self.send()
            except:
                log.exception("Error sending message")
                return

    def send(self):
        msg = self.q.get()
        assert isinstance(msg, unicode), ("Invalid unicode message", msg)
        msg = msg.encode("utf-8")
        log.log(TRACE, "SEND: %r" % msg)
        self.rate_limit(msg)
        if self.is_looping(msg):
            log.log(TRACE, "DROP: %r" % msg)
            return
        self.sent.append((time.time(), msg))
        self.sent = self.sent[-10:]
        self.sock.sendall(msg)

    def rate_limit(self, msg):
        if not self.sent:
            return
        penalty = float(max(0, len(msg) - 50)) / 70.0
        wait = min(3.0, 0.4 + penalty)
        elapsed = time.time() - self.sent[-1][0]
        if elapsed < wait:
            log.log(TRACE, "SLEEP: %f" % (wait - elapsed))
            time.sleep(wait - elapsed)

    def is_looping(self, new_msg):
        count = 0
        for (when, old_msg) in reversed(self.sent):
            if time.time() - when > 5.0:
                return False
            if new_msg == old_msg:
                count += 1
            if count >= 3:
                return True
        return False

    def fmt(self, data):
        if not isinstance(data, unicode):
            data = data.decode("utf-8", "replace")
        for c in u"\r\n\x00":
            data = data.replace(c, u" ")
        return data


class Client(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.sock = None
        self.reader = None
        self.writer = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.cfg.host, self.cfg.port))
        self.reader = Reader(self, self.sock)
        self.writer = Writer(self, self.sock)

        if self.cfg.serverpass is not None:
            self.write(('PASS', self.cfg.serverpass))
        self.write(('NICK', self.cfg.nick))
        self.write(('USER', self.cfg.user, '+iw', self.cfg.nick), self.cfg.name)

        if self.cfg.nickpass:
            self.msg('NickServ', 'IDENTIFY {0}'.format(self.cfg.nickpass))
            time.sleep(5)

        # drain the queue to deal with potential PONG request
        try:
            for msg in self.messages(drain=True):
                continue
        except Queue.Empty:
            pass

        for (chname, pwd) in self.cfg.channels:
            if pwd is not None:
                self.write(('JOIN', chname, pwd))
            else:
                self.write(('JOIN', chname))
            time.sleep(0.5)

    def messages(self, drain=False):
        while True:
            if not self.reader.is_alive():
                return
            if not self.writer.is_alive():
                return
            try:
                msg = self.reader.next(timeout=2)
                msg.client = self
                if msg.event == u"PING":
                    self.writer.write(("PONG", msg.text))
                yield msg
            except Queue.Empty:
                if drain:
                   raise
                else:
                    continue

    def action(self, recip, text):
        self.writer.action(recip, text)

    def msg(self, recip, text):
        self.writer.msg(recip, text)

    def notice(self, recip, text):
        self.writer.notice(recip, text)

    def write(self, args, text=None):
        self.writer.write(args, text)

    def style(self, name=None):
        if name is None:
            return STYLES
        return STYLES[name]

    def format(self, data, *args, **kwargs):
        style_kwargs = STYLES.copy()
        style_kwargs.update(kwargs)
        return data.format(*args, **style_kwargs)

    def human_time(self, time=False, utc=False):
        """
        Based on:
        http://stackoverflow.com/questions/1551382/user-friendly-time-format-in-python
        """
        if utc:
            now = datetime.datetime.utcnow()
        else:
            now = datetime.datetime.now()

        if type(time) is int:
            if utc:
                parsed = datetime.datetime.utcfromtimestamp(time)
            else:
                parsed = datetime.datetime.fromtimestamp(time)
            diff = now - parsed
        elif isinstance(time, datetime.datetime):
            diff = now - time
        elif not time:
            diff = now - now
        second_diff = diff.seconds
        day_diff = diff.days

        if day_diff < 0:
            return 'in the future?'
        elif day_diff == 0:
            if second_diff < 10:
                return "just now"
            if second_diff < 60:
                return str(second_diff) + " seconds ago"
            if second_diff < 120:
                return  "a minute ago"
            if second_diff < 3600:
                return str( second_diff / 60 ) + " minutes ago"
            if second_diff < 7200:
                return "an hour ago"
            if second_diff < 86400:
                return str( second_diff / 3600 ) + " hours ago"
        elif day_diff == 1:
            return "Yesterday"
        elif day_diff < 7:
            return str(day_diff) + " days ago"
        elif day_diff < 31:
            return str(day_diff/7) + " weeks ago"
        elif day_diff < 365:
            return str(day_diff/30) + " months ago"
        else:
            return str(day_diff/365) + " years ago"


def options():
    return [
        op.make_option('-v', '--verbose', dest='verbose', default=False,
            action="store_true",
            help="Display verbose logging"),
        op.make_option('--trace', dest='trace', default=False,
            action="store_true",
            help="Enable message tracing"),
        op.make_option('-c', '--config', dest='config', default=None,
            metavar="FILE",
            help="Path to config file"),
        op.make_option('--check', dest='check', default=False,
            action="store_true",
            help="Try loading each plugin and then exit.")
    ]


def main():
    cfg = Config()

    usage = "usage: %prog [options]"
    p = op.OptionParser(usage=usage, option_list=options())
    (opts, args) = p.parse_args()

    if len(args):
        p.error("Unknown arguments: {0}".format(" ".join(args)))

    logfmt = "[%(levelname)s] (%(name)s) %(message)s"

    level = logging.INFO
    if opts.verbose:
        level = logging.DEBUG
    if opts.trace:
        level = TRACE

    if opts.config is not None:
        cfg.load(opts.config)

    logging.basicConfig(
            level=level,
            format=logfmt,
            filename=cfg.logfile
        )

    cli = Client(cfg)
    pm = PluginManager(cfg, cli)
    pm.load()

    if opts.check:
        log.info("Finished check.")
        return

    cli.connect()

    for msg in cli.messages():
        pm.handle(msg)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

