Gizzy
=====

A simple, easily extendable IRC bot.


Configuration
-------------
Copy config.py.dist to config.py and edit all the things.

Running gizzy
-------------
python /path/to/gizzy.py -c /path/to/config.py

Writing Plugins
---------------

Plugins are a single Python file dropped into the plugins directory. Each file is loaded by gizzy automatically scanning the directory so there's no config required to enable new plugins.

Plugins have a normal Python namespace with six extra variables available:

  * `config` - Gizzy's configuration object
  * `log` - A logging.Logger configured for the plugin
  * `irc` - The global IRC client instance useful for messaging from threads
  * `command` - A function decorator for command style functions
  * `rule` - A function decorator for rule based functions
  * `plugin_manager` - A reference to the plugin for anything that might
    need to access other pugins (not a common requirement).

<h3>Plugin Lifecycle</h3>

Plugins have a load/unload life cycle. If a load function instantiates any
permanent resource it should be removed when unloaded. A good example of
this is to stop any threads that were started.

Each plugin has two top level functions. `load` takes a single argument which is a reference to the IRC client object. If the plugin needs to alert IRC based
on some external event (ie, sensu or pagerduty notifications) then it should
store a reference to this object.

Any value returned from `load` is stored as the plugin's state.

	# An optional function to load plugin state
    def load():
        return new_plugin_state()

There's also a corresponding `unload` function which takes a single argument
which is the value returned from `load`.

    # An optional function to unload plugin state
    def unload(state):
        release_state_resources(state)

_Neither `load` or `unload` are required to exist_.

<h3>Message Objects</h3>

All message handling functions defined in a plugin get an instance of the `Message` class which has a number of variables extracted from the message. The popular subset of useful messages is
listed below:

  * `client` -  A reference to the main IRC client object
  * `raw` - The raw, unparsed IRC message
  * `source` - The message sender in full `Nick!User@Host` format. May be `None` for some message
    types.
  * `nick`, `user`, `host` - Extracted fields from the `source` value.
  * `sender` - The entity that generated the message. May be `None` for some message types.
  * `target` - The target of the message. May be `None` for some message types.
  * `text` - The text of the IRC message if it was a PRIVMSG (ie, channel message or PM)
  * `owner` - A boolean indicating if the message sender owns the bot. Useful to restrict
    access for commands.
  * `match` - The regular expression match object.
  * `groups` - The output of `match.groups()`
  * `group` - An alias to `match.group()`

Along with the instance variables there are a number of utility functions for generating IRC messages:

  * `msg.do(text)` - Generates an action style message (ie, "* gizzy does a thing")
  * `msg.reply(text)` - Sends a reply to the channel or user that sent the message.
  * `msg.respond(text)` - Same as `reply` except `$nick: ` is prepended to the message.
  * `msg.notify(text)` - Sends a `NOTIFY` message to the channel or user that sent the message.

<h3>Command Style Functions</h3>

Each plugin can define as many `command` and `rule` functions as it desires. A `command` function looks like such:

    @command(["dance"])
    def dance(msg):
        for a in ":D|-< :D\-< :D/-< :D>-<".split():
            msg.do(a)

This is the entire implementation of the `dance` plugin. Using the `command` decorator tells gizzy to respond to either of the two following IRC messages:

    gizzy: dance
    .dance

Commands can be specified with multiple items in the chain. For instance:

    @command(["pd", "oncall"])

Which will match either of:

    gizzy: pd oncall
    .pd oncall

The items in the command chain can also be used to generate named patterns like such:

    @command(["pd", "oncall", "<schedule>"])
    def oncall(msg):
        msg.reply("Schedule: {0}".format(msg.group("schedule")))


Will then match anything like:

    gizzy: pd oncall ops-ait
    .pd oncall ops-ait

In the function you can access the regular expression match object on the
message variable passed to the function as `msg.match`. For
convenience there's also an alias from `msg.match.group(name)` to
`msg.group(name)`.

Regular expressions are matched against the entire message using the `^` and
`$` operators so you'll need to be careful in what you expect users to add. If
you wan't to accept a "and all the rest" argument, specify the last named
parameter as such:

    @comand(["pd", "wakeup", "<service>", "<message:.*>"])
    def wakeup(msg, cli):
        do_wakeup(msg, cli)

<h3>Rule Style Functions</h3>

Rule based functions on the other hand are specified as a single regexp that
will fire the function any time the regexp matches an IRC message. This is
useful for things like the FogBugz plugin which links to tickets and shows
their subject anytime it sees something that looks like `fb \d+`. For example:

    @rule("(?i)[ .](bugzid|fb)(:|\s+)(?P<id>\d+)")
    def link_fb(msg):
        msg.reply(do_link_stuff(msg))


<h3>Other Function Arguments</h3>

Both `command` and `rule` take these extra arguments beyond the first required
argument:

  * `event` - Only run commands on specific IRC events (uncommon)
  * `require_owner` - Only run commands if it was issued by a bot owner

`rule` style functions also accept a `name` parameter that is used to
refer to the function for things like `.help` and so on.

Credit
------
gizzy was originally written by Paul Davis (@davisp) for Cloudant.

This release contains the original framework but removes all of the
internal Cloudant-only plugins.

The core IRC protocol was reverse engineered by looking at the source
to Phenny written by Sean B. Palmer. Phenny was released under the
Eiffel Forum License v2.0.

https://github.com/sbp/phenny
