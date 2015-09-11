"Commands related to reloading parts of Gizzy"

import subprocess as sp


@command(["sync"], require_owner=True)
def sync(msg):
    "Synchronize Gizzy with GitHub"
    cmd = ["/usr/bin/git", "pull", "-q", "--ff-only", "origin", "master"]
    try:
        p = sp.Popen(cmd,
                stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT)
        (stdout, _) = p.communicate()
        if p.returncode == 0:
            cmd = ["/usr/bin/git", "log", "--oneline", "-n1"]
            p = sp.Popen(cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT)
            (stdout, _) = p.communicate()
            msg.respond("synced: {0}".format(stdout.strip()))
        else:
            rcode = "Exited: {0}".format(p.returncode)
            err = " ".join(stdout.split())
            msg.respond(rcode + " " + err)
    except Exception, e:
        err = "Sync error: " + " ".join(str(e).split())
        msg.respond(err)


@command(["reload"], require_owner=True)
def reload(msg):
    "Reload all plugins"
    msg.respond("reloading...")
    plugin_manager.load()
    msg.respond("reloaded")
    raise StopIteration


@command(["restart"], require_owner=True)
def restart(msg):
    "Restart to pick up a new config and/or kernel"
    exit(0)

