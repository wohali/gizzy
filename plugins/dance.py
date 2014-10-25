"""\
A trivial example plugin that makes people laugh.
"""

@command(["dance"])
def dance(msg):
    "Do a little dance."
    for a in ":D|-< :D\-< :D/-< :D>-<".split():
        msg.do(a)
