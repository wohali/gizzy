"""Natural Language Processing library"""

import codecs
import os
import random
import sys

from spacy.en import English

nlp = English()

corporadir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "corpora"
)
def_set = "McGuffey"
def_text = "fourth_reader.txt"

def random_line(fname):
    while True:
        with codecs.open(fname, 'r', 'utf-8') as afile:
            # thanks to http://stackoverflow.com/questions/3540288
            line = next(afile)
            for num, aline in enumerate(afile):
                if random.randrange(num + 2): continue
                line = aline

            # We want lines long enough to be useful.
            if len(line) < 80:
                continue

            return line

def corpus(set=def_set, name=def_text):
    "Return abspath of selected corpus"
    corpuspath = os.path.join(corporadir, set, name)
    if os.path.isfile(corpuspath):
        return corpuspath
    else:
        raise IOError ("File not found: " + corpuspath)

def random_corpus(set=def_set):
    "Return randomly selected corpus from chosen corpora set."
    target = os.path.join(corporadir, set)
    if os.path.isdir(target):
        # select random file
        files = os.listdir(target)
        while True:
            picked = os.path.join(
                    target,
                    files.pop(random.randrange(len(files)))
            )
            if os.path.isfile(picked):
                return picked
    else:
        raise IOError("Corpora set invalid: " + target)
