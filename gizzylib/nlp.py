"""Natural Language Processing library"""

import os
import random
import sys

from spacy.en import English

nlp = English()

# thanks to http://stackoverflow.com/questions/3540288
def random_line(afile):
    line = next(afile)
    for num, aline in enumerate(afile):
        if random.randrange(num + 2): continue
        line = aline
    if sys.version_info[0] == 2:
        return unicode(line)
    else:
        return line

def corpus(name):
    "Return abspath of selected corpus"
    mydir = os.path.dirname(os.path.abspath(__file__))
    corporadir = os.path.join(mydir, "corpora")
    corpuspath = os.path.join(corporadir, name + ".txt")
    if os.path.isfile(corpuspath):
        return corpuspath
    else:
        raise IOError ("File not found: " + corpuspath)


