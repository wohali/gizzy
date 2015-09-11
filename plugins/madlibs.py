"""\
The Mad Libs gaming bot.
"""

# TODO: Bot should play as well!

from __future__ import unicode_literals
import os
import random
import sys
import threading

from collections import defaultdict
from gizzylib import nlp
from itertools import repeat
from math import ceil

bold = irc.style("bold")
underline = irc.style("underline")

def constant_factory(value):
    """Helper to construct constant value defaultdicts"""
    return repeat(value).next

def gamethread(func):
    """Decorator for functions that are Timer game threads.
    Thread removes self from registry of threads in module state."""
    def new_func(*args, **kwargs):
        state = args[1]
        state['threads'].pop(threading.current_thread().ident, None)
        func(*args, **kwargs)
    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__dict__.update(func.__dict__)
    return new_func

def generate_madlib(state):
    """Generates a Mad Lib from a line out of the chosen corpus."""
    corpus = nlp.corpus(state['options']['corpus'])
    with open(corpus, 'r') as f:
        line = nlp.random_line(f)

    doc = nlp.nlp(line)

    # truncate line if too long
    maxlen = state['options']['linemaxlen']
    if len(line) > maxlen:
        line = ""
        for span in doc.sents:
            sent = ''.join(doc[i].string for i in range(
                    span.start, span.end
            )).strip()
            if len(line) + len(sent) > maxlen:
                break
            line += sent
        doc = nlp.nlp(line)
        
    ddict = defaultdict(list)

    for (index, token) in enumerate(doc):
        if token.pos_ not in ['PUNCT']:
            ddict[token].append(index)

    slist = sorted(ddict, key=lambda t: t.prob)

    # build list of tokens+whitespace from parsed output
    sents = map(lambda x: x.string, list(doc))

    # 2 subs + 1 more per word wrap line
    limit = min(len(line) / 80 + 2, 6)

    slots = []
    for t in slist[:limit]:
        for ctr in ddict[t]:
            sents[ctr] = u"__" + t.pos_ + "__" + t.whitespace_
            slots.append(ctr)

    slots.sort()

    state['text'] = "".join(sents)
    state['textshape'] = slots


@gamethread
def warntime(msg, state):
    msg.reply(bold + "*** {} second warning! ***".format(
            state['options']['warntime']) + bold
    )

@gamethread
def startround(msg, state):
    "Start a round of Mad Libs. "
    state['round'] += 0.25
    state['votes'] = { k: -1 for k, v in state['votes'].items() }
    state['entries'] = []

    generate_madlib(state)

    msg.reply("======= Starting Round {0}/{1} =======".format(
            int(state['round']), state['options']['numrounds']
    ))
    msg.reply(state['text'])
    msg.reply("Entries should be of the form " + underline + 
            "word word ..." + underline)
    msg.reply("--> Send your entries to me VIA MESSAGE, you have " +\
            "{} seconds".format(state['options']['roundlen'])
    )

    t = threading.Timer(
            state['options']['roundlen'],
            voteround,
            args=(msg, state)
    )
    t.start()
    state['threads'][t.ident] = t
    t2 = threading.Timer(
            state['options']['roundlen'] - state['options']['warntime'],
            warntime, args=(msg, state)
    )
    t2.start()
    state['threads'][t2.ident] = t2

def processentry(msg, state):
    "Process a submitted Mad Lib word list entry."
    try:
        if msg.sender[0] == '#':
            # ignore public statements
            return

        entry = msg.text.strip()
        words = [x.strip() for x in entry.split()]

        if len(words) == len(state['textshape']):
            state['entries'].append((msg.nick, words, 0))
            state['votes'][msg.nick] = -1
            msg.reply("Entry accepted.")
        else:
            msg.reply("Entry " + bold + "rejected" + bold +\
                    ", expected {1} words and got {0}".format(
                    len(words), len(state['textshape'])
            ))

    except Exception as e:
        msg.reply("Entry " + bold + "rejected" + bold + \
                ", unexpected error")
        log.debug(str(e))

@gamethread
def voteround(msg, state):
    "Start the voting portion of a Mad Libs round."
    state['round'] += 0.5

    if len(state['entries']) == 0:
        msg.reply(bold + "ACHTUNG! No entries received! Ending game.")
        killgame(msg, state)

    random.shuffle(state['entries'])

    msg.reply("=======  Entries Received  =======")
    for num, ent in enumerate(state['entries'], start=1):
        msg.reply("Entry {0}: {1}".format(num, ', '.join(ent[1])))

    msg.reply("=======  Voting Time!!!!!  =======")
    msg.reply("Send your vote (number) to me VIA MESSAGE, you have " +
            "{} seconds".format(state['options']['votetime'])
    )

    t = threading.Timer(
            state['options']['votetime'],
            endround,
            args=(msg, state)
    )
    t.start()
    state['threads'][t.ident] = t
    t2 = threading.Timer(
            state['options']['votetime'] - state['options']['warntime'],
            warntime,
            args=(msg, state)
    )
    t2.start()
    state['threads'][t2.ident] = t2

def processvote(msg, state):
    "Process a vote for a Mad Libs entry."
    try:
        if msg.sender[0] == '#':
            # ignore public statements
            return

        # Entries are numbered from 1, list is numbered from 0
        voted = int(msg.text) - 1

        if voted >= len(state['entries']) or voted < 0:
             raise ValueError
        if msg.sender == state['entries'][voted][0]:
            msg.reply("You cannot vote for yourself!")
            return
        if state['votes'][msg.sender] == -1:
            msg.reply("Vote accepted.")
        else:
            msg.reply("Vote changed.")

        state['votes'][msg.sender] = voted
        log.debug("{0} voting for {1}".format(msg.sender,
                state['entries'][voted][0]))

    except Exception as e:
        msg.reply("Vote " + bold + "rejected" + bold + \
                ", unexpected error"
        )
        log.debug(str(e))

@gamethread
def endround(msg, state):
    "End a round of Mad Libs."
    state['round'] += 0.25
    state['text'] = ""
    state['textshape'] = []

    shame = []

    for nick, vote in state['votes'].items():
        if vote == -1:
            shame.append(nick)
        else:
            ent = state['entries'][vote]
            state['entries'][vote] = ( ent[0], ent[1], ent[2]+1 )

    msg.reply("=======   Voting Results   =======")
    for num, ent in enumerate(state['entries']):
        msg.reply("Entry {0}: {1}: {2} => {3}".format(
                num+1, ent[0], ", ".join(ent[1]), ent[2]
        ))
        state['scores'][ent[0]] += ent[2]
    if state['options']['shame'] and shame:
        msg.reply("These users did not vote: " + 
                ", ".join(shame)
        )

    log.debug("Scores so far: " + str(state['scores']))

    if state['round'] > state['options']['numrounds']:
       endgame(msg, state)
    else:
        msg.reply("Round {0}/{1} starts in {2} seconds.".format(
                int(ceil(state['round'])),
                state['options']['numrounds'],
                state['options']['interround']
        ))
        t = threading.Timer(
                state['options']['interround'],
                startround,
                args=(msg, state)
        )
        t.start()
        state['threads'][t.ident] = t

def endgame(msg, state):
    "End a game of Mad Libs."
    slist = []
    for key, value in sorted(state['scores'].iteritems(),
            key=lambda (k,v): (v,k),
            reverse=True):
        slist.append((key, value))

    msg.reply(bold + "=======     GAME OVER!     =======" + bold)
    if len(slist):
        msg.reply("Winner with a score of {1}: {0}!".format(
                slist[0][0], slist[0][1]
        ))
        for player in slist:
            msg.reply("{0}: {1}".format(player[0], player[1]))

    # be safe, kill any lingering threads
    killgame(state)

def killgame(state):
    if state['round'] == 0:
        return
    for t in state['threads'].itervalues():
        try:
            t.cancel()
        except AttributeError:
            continue
    reset(state)

def reset(state):
    state.update({
	    # Round number, 0=no game running
        'round': 0,
        # Round's game text and shape of removed words
        'text': '',
        'textshape': [],
        # Pending entries: [(nick, [words], votes), ...]
        'entries': [],
        # Pending votes: { nick: voteentry, ... } # 0-indexed
        'votes': defaultdict(constant_factory(-1)),
        # Scores: { nick: score, ... }
        'scores': defaultdict(int),
        # Threads on timers, keyed by thread ident
        'threads': {}
    })


@command(["madlibs", "startgame"], require_owner=True)
def startgame(msg, state):
    "Start a game of Mad Libs."
    msg.reply("Welcome to super duper amazing Mad Libs game!")
    msg.reply("Round 1/{0} starts in {1} seconds.".format(
            state['options']['numrounds'],
            state['options']['interround']
    ))
    state['round'] = 0.75
    t = threading.Timer(
            state['options']['interround'],
            startround,
            args=(msg, state)
    )
    t.start()
    state['threads'][t.ident] = t

@command(["madlibs", "state"], require_owner=True)
def dumpstate(msg, state):
    "Dump current module state"
    log.debug(str(state))
    msg.reply("State dumped to logfile.")

@command(["madlibs", "option"], require_owner=True)
def showoptions(msg, state):
    "Show all configurable options"
    msg.reply("Mad Libs options:")
    for k, v in state['options'].items():
        msg.reply("  {0}: {1}".format(k, v))

@command(["madlibs", "option", "<key>", "<value>"], require_owner=True)
def setoption(msg, state):
    "Set option <key> to <value>"
    key = msg.group("key")
    value = msg.group("value")
    if key in state['options']:
        if isinstance(state['options'][key], bool):
            if value.lower() in ['true', '1', 'yes', 't']:
                state['options'][key] = True
                value = True
            else:
                state['options'][key] = False
                value = False
        elif isinstance(state['options'][key], int):
            state['options'][key] = int(value)
        elif isinstance(state['options'][key], str):
            state['options'][key] = value
        # only Python 2 defines the unicode type
        elif sys.version_info[0] == 2 and \
                isinstance(state['options'][key], unicode):
            state['options'][key] = unicode(value)
        else:
            # ???
            return
        msg.reply("Mad Libs option {0} set to {1}.".format(key, value))

@command(["<blah:madlibs (stop|kill)game>"], require_owner=True)
def stopgame(msg, state):
    "Stop a game in progress."
    if state['round'] != 0:
        killgame(state)
        msg.reply(bold + "Game halted by request." + bold)

@rule(".*")
def process(msg, state):
    "Handle entry and vote submissions."
    if msg.sender[0] == "#" or state['round'] == 0:
        # ignore if no game running or if public utterance
        return
    if state['round'] % 1 == 0:
        # Entry submission phase
        processentry(msg, state)
    elif state['round'] % 1 == 0.5:
        # Voting phase
        processvote(msg, state)
    # interround 0.75 state falls through with no action

def load():
    statedict = {
        # Default game options
        'options': {
            'interround': 20,
            'roundlen': 120,
            'votetime': 75,
            'warntime': 15,
            'numrounds': 8,
            'linemaxlen': 400,
            'corpus': 'mcguffey',
            'botplays': False,
            'shame': True
        }
    }
    reset(statedict)
    return statedict

def unload(state):
    killgame(state)
