"""\
A trivial example plugin that makes Seahawks fans laugh.
"""

@command(["SEA"])
def sea(msg):
    "GO HAWKS"
    msg.do("HAWKS!!")
