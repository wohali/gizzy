#===============================================================================
# converter.py - converts McGuffey's Readers to internal format
#                i.e., one paragraph per line 
#===============================================================================
import os
import re

from docopt import docopt


def parse(f=None, of=None):
    if not f or not of:
        return

    # states
    # TODO Add support for story grouping
    OUTSIDE = 1
    INSIDE = 2
    
    # regexes
    FIRST_RE = re.compile("^([0-9]+\.) (.*)$")
    BLANK_RE = re.compile("^\s*$")

    state = OUTSIDE
    buff = ""
   
    for line in f:
        line = line.strip()
        if state == OUTSIDE:
            # look for the start of a paragraph, e.g.
            # 1. There were, in very ancient times...
            m = FIRST_RE.match(line)
            if m:
                buff = m.group(2)
                state = INSIDE
        elif state == INSIDE:
            # look for end of paragraph, a blank line
            m = BLANK_RE.match(line)
            if m:
                print(buff, file=of, flush=True)
                state = OUTSIDE
            else:
                buff += " {}".format(line)
        else:
            raise "Reached unknown state {} in parser!".format(state)

usage="""
McGuffey Converter.

Usage:
  convert.py FILE ...
  convert.py --output=FILE FILE ...
  
Options:
  -h --help                Show this screen.
  --version                Show version.
  -o FILE --output=FILE    Output file [default: out.txt]
"""

if __name__ == '__main__':
    arguments = docopt(usage, version="McGuffey Converter 0.1")
    
    of = open(arguments['--output'], 'w')

    for fn in arguments['FILE']:
        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                parse(f, of)
    
    of.close()