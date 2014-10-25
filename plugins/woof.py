"""\
Show cute pictures of Gizzy's namesake.
"""

import random

import requests


TREE_URL = "https://api.github.com/repos/davisp/gizzy-woof/git/trees/master"
IMG_BASE_URL = "https://raw.githubusercontent.com/davisp/gizzy-woof/master/{0}"


def load():
    r = requests.get(TREE_URL)
    if not r.ok:
        log.debug("Error getting Gizzy pictures :(")
        return []
    log.debug("gizzy-woof tree: {0}".format(r.text))
    ret = []
    for fobj in r.json()["tree"]:
        if fobj["mode"] != "100644":
            log.debug("Bad mode: {0}".format(fobj["mode"]))
            continue
        if fobj["path"][-4:] != ".jpg":
            log.debug("Bad extension: {0}".format(fobj["path"][-4:]))
            continue
        ret.append(fobj["path"])
    return ret


@command(["<blah:(?i)woof!?>"])
def woof(msg, paths):
    "Link to pictures of Gizzy"
    if not paths:
        msg.respond("Unfortunately, I don't have any images to show you.")
    else:
        msg.respond(IMG_BASE_URL.format(random.choice(paths)))
