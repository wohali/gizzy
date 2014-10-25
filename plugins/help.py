"""\
This plugin implements a help system based on module and
function doc strings. Any plugin, command, or rule that has
a docstring is automatically part of the help system.
"""

import os


def plugins():
    return dict((p.name, p) for p in plugin_manager.plugins)


@command(["help"])
def help(msg):
    "List plugins and provide tips for other help commands."
    if msg.sender != msg.nick:
        msg.reply("Use private messaging for help.")
        return
    msg.reply("Installed plugins:")
    for name in sorted(plugins().keys()):
        msg.reply("  {0}".format(name))
    msg.reply("For help on a plugin: .help <name>")
    msg.reply("To list all commands: .commands")
    msg.reply("To list all rules: .rules")


@command(["help", "<name>"])
def help_plugin(msg):
    "Display the docstring for the specified plugin."
    if msg.sender != msg.nick:
        msg.reply("Use private messaging for help.")
        return
    name = msg.group("name")
    p = plugins().get(name)
    if p is None:
        msg.reply("Unknown plugin: {0}".format(name))
        return
    doc = p.data.get("__doc__")
    if isinstance(doc, basestring):
        msg.reply("{0}:".format(name))
        for line in doc.splitlines():
            msg.reply(line)
    cmds = [c for c in p.actions if isinstance(c, command)]
    rules = [r for r in p.actions if isinstance(r, rule)]
    if len(cmds):
        msg.reply("Commands:")
        for c in cmds:
            parts = [" ", c.name]
            if c.docs:
                parts.extend((': ', c.docs))
            msg.reply(" ".join(parts))
    if len(rules):
        msg.reply("Rules:")
        for r in rules:
            parts = [" ", r.name]
            if r.docs:
                parts.extend((': ', r.docs))
            msg.reply(" ".join(parts))


@command(["commands"])
def list_commands(msg):
    "List all installed commands"
    list_actions(msg, command)


@command(["rules"])
def list_rules(msg):
    "List all installed rules"
    list_actions(msg, rule)


def list_actions(msg, klass):
    "List all known commands"
    if msg.sender != msg.nick:
        msg.reply("Use private messaging for help.")
        return
    reply = []
    for p in plugins().values():
        for a in p.actions:
            if not isinstance(a, klass):
                continue
            parts = ["  ", a.name]
            if a.docs:
                parts.extend((": ", a.docs))
            reply.append(" ".join(parts))
    if len(reply):
        hdr = klass.__name__.capitalize() + "s:"
        msg.reply(hdr)
        for r in sorted(reply):
            msg.reply(r)
    else:
        msg.reply("No {0} installed.".format(klass.__name__ + "s"))
