"""\
The Mad Libs gaming bot.
"""

from __future__ import unicode_literals
import os
import random
import sys
import threading

from collections import defaultdict
from gizzylib import nlp
from itertools import repeat
from math import ceil, floor
from numpy import dot
from numpy.linalg import norm

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
    line = None
    while not line:
        if not state['corpus']:
            if state['options']['corpus'] == "None":
                name = None
            else:
                name = state['options']['corpus']
            if state['options']['corporaset'] == "None":
                set = None
            else:
                set = state['options']['corporaset']
    
            # will raise IOError if corpus invalid
            if name:
                state['corpus'] = nlp.corpus(set=set, name=name)
            else:
                state['corpus'] = nlp.random_corpus(set=set)
    
        try:
            line = nlp.random_line(state['corpus'])
        except UnicodeDecodeError:
            state['corpus'] == None

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
            line += sent + " "
        doc = nlp.nlp(line)
        
    ddict = defaultdict(list)

    for (index, token) in enumerate(doc):
        if token.pos_ in ['ADJ', 'ADV', 'NOUN', 'VERB']:
            ddict[token].append(index)

    slist = sorted(ddict, key=lambda t: t.prob)

    # build list of tokens+whitespace from parsed output
    words = map(lambda x: x.string, list(doc))

    # 2 subs + 1 more per word wrap line
    limit = min(len(line) / 80 + 2, 6)

    slots = []
    for t in slist[:limit]:
        for ctr in ddict[t]:
            words[ctr] = underline + u"  " + t.pos_ + "  " +\
                    underline + t.whitespace_
            slots.append(ctr)

    slots.sort()

    state['doc'] = doc
    state['text'] = "".join(words)
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
    state['skippers'] = set()

    try:
        generate_madlib(state)
    except IOError as e:
        msg.reply("Unable to locate corpus. Aborting game.")
        log.error("Corpus open failed: " + str(e))
        killgame(state)

    # give 10s more time for each add'l 80-char line
    entrytime = int(state['options']['entrytime'] + \
            (floor(len(state['text']) / 80) - 1) * 10)

    msg.reply("======= Starting Round {0}/{1} =======".format(
            int(state['round']), state['options']['numrounds']
    ))
    log.info("======= Starting Round {0}/{1} =======".format(
            int(state['round']), state['options']['numrounds']
    ))

    if state['options']['hidesentence']:
        poslist = []
        for idx in state['textshape']:
            poslist.append(state['doc'][idx].pos_)
        text = "Hidden sentence! Give me: "
        text += ", ".join(poslist)

    else:
        text = state['text']
    msg.reply(text)
    log.info(text)
    msg.reply("Entries should be of the form " + underline + 
            "word word ..." + underline)
    msg.reply("--> Send your entries to me VIA MESSAGE, you have " +\
            "{} seconds".format(entrytime)
    )

    t = threading.Timer(
            entrytime,
            voteround,
            args=(msg, state)
    )
    t.start()
    state['threads'][t.ident] = t
    t2 = threading.Timer(
            entrytime - state['options']['warntime'],
            warntime,
            args=(msg, state)
    )
    t2.start()
    state['threads'][t2.ident] = t2
    if not state['options']['botplays']:
        return
    t3 = threading.Thread(
            target=botentry,
            args=(msg, state)
    )
    t3.start()
    state['threads'][t3.ident] = t3

def processentry(msg, state):
    "Process a submitted Mad Lib word list entry."
    try:
        if msg.text.strip().lower() == "!skip":
            state['skippers'].add(msg.nick)
        if len(state['skippers']) == 3:
            msg.reply("OK, you don't like that one! " +\
                    bold + "Restarting round.")
            killgame(state, reset=False)
            round -= 0.5
            startround(msg, state)

        if msg.sender[0] == '#':
            # ignore public statements other than !skip
            return

        entry = msg.text.strip()
        words = [x.strip() for x in entry.split()]


        # search for stopwords
        stopwords = [x for x in words \
                if x.lower() in state['options']['stopwords']]
        if stopwords:
            msg.reply("Entry " + bold + "rejected" + bold +\
                    ", stopword(s) found: " + ", ".join(stopwords)
            )
            return

        if len(words) == len(state['textshape']):
            resp = "Entry accepted."
            # remove any previous entry
            for ent in state['entries']:
                if ent[0] == msg.nick:
                    state['entries'].remove(ent)
                    resp = "Entry changed."
                    break
            state['entries'].append((msg.nick, words, 0))
            log.info("{0} entry: {1}".format(msg.nick, ", ".join(words)))
            state['votes'][msg.nick] = -1
            msg.reply(resp)

        else:
            msg.reply("Entry " + bold + "rejected" + bold +\
                    ", expected {1} words and got {0}".format(
                    len(words), len(state['textshape'])
            ))

    except Exception as e:
        msg.reply("Entry " + bold + "rejected" + bold + \
                ", unexpected error")
        log.error(str(e))

@gamethread
def botentry(msg, state):
    """Generate a response based on the original text.
    Warning, may take 30-60s to complete. Do not set entrytime
    very low!"""
    if 'words' not in state:
        # expensive initialization, do ALAP
        log.info("Loading word corpus...")
        state['words'] = [w for w in nlp.nlp.vocab if w.has_vector]
    #cosine = lambda v1, v2: dot(v1, v2) / (norm(v1) * norm(v2))

    entry = []
    for t in state['textshape']:
        log.debug("Searching for replacement for {0} ({1})".format(
            state['doc'][t], state['doc'][t].pos_
        ))
        try:
            state['words'].sort(key=lambda w: 
                    w.similarity(state['doc'][t]),
                    reverse=True
            )
                    #cosine(w.vector, state['doc'][t].vector)
            state['words'].reverse
        except TypeError:
            # perhaps our word lacks a vector?
            pass

        if state['options']['matchpos']:
            sent = [x.string for x in list(state['doc'])]
            pos = state['doc'][t].pos_
            for ctr in range(10):
                # TODO: Parametrize the bounds on random here
                newword = state['words'][random.randint(50, 500)]
                log.debug("Trying " + newword.orth_.lower())
                sent[t] = newword.orth_.lower() + " "
                newsent = nlp.nlp("".join(sent))
                if newsent[t].pos_ == pos:
                    break
            entry.append(newword.orth_.lower())
            log.debug("Word found: {0} ({1})".format(
                entry[-1], newsent[t].pos_
            ))
        else:
            entry.append(
                state['words'][random.randint(50, 500)].orth_.lower()
            )
            log.debug("Word found: " + entry[-1])

    log.info("Bot enters: " + ", ".join(entry))
    state['entries'].append((config.nick, entry, 0))
    # no entry in state['votes']

@gamethread
def voteround(msg, state):
    "Start the voting portion of a Mad Libs round."
    state['round'] += 0.5

    if len(state['entries']) == 0 \
            or (state['options']['botplays'] and \
            len(state['entries']) == 1):
        msg.reply(bold + "ACHTUNG! No entries received! Ending game.")
        killgame(state)
        return

    # give 10s more vote time for >3 entries
    votetime = int(state['options']['votetime'] + \
        (len(state['entries']) - 3) * 10)

    random.shuffle(state['entries'])

    msg.reply("=======  Entries Received  =======")
    for num, ent in enumerate(state['entries'], start=1):
        doc = [x.string for x in list(state['doc'])]
        # substitute words keeping original trailing whitespace
        for idx, word in enumerate(ent[1]):
            wordidx = state['textshape'][idx]
            doc[wordidx] = bold + word + bold + \
                    state['doc'][wordidx].whitespace_
        text = "".join(doc)

        msg.reply("Entry {0}: {1}".format(num, text))

    msg.reply("=======  Voting Time!!!!!  =======")
    msg.reply("Send your vote (number) to me VIA MESSAGE, you have " +
            "{} seconds".format(votetime)
    )

    t = threading.Timer(
            votetime,
            endround,
            args=(msg, state)
    )
    t.start()
    state['threads'][t.ident] = t
    t2 = threading.Timer(
            votetime - state['options']['warntime'],
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
        log.info("{0} voting for {1}".format(msg.sender,
                state['entries'][voted][0]))

    except Exception as e:
        msg.reply("Vote " + bold + "rejected" + bold + \
                ", unexpected error"
        )
        log.error(str(e))

@gamethread
def endround(msg, state):
    "End a round of Mad Libs."
    state['round'] += 0.25
    state['doc'] = None
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
    log.info("=======   Voting Results   =======")
    for num, ent in enumerate(state['entries']):
        msg.reply("Entry {0}: {1}: {2} => {3}".format(
                num+1, ent[0], ", ".join(ent[1]), ent[2]
        ))
        log.info("Entry {0}: {1}: {2} => {3}".format(
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
                state['options']['intertime']
        ))
        t = threading.Timer(
                state['options']['intertime'],
                startround,
                args=(msg, state)
        )
        t.start()
        state['threads'][t.ident] = t

def endgame(msg, state):
    "End a game of Mad Libs."
    slist = sorted(iter(state['scores'].items()),
            key=lambda k: k[1],
            reverse=True
    )

    winners = [slist[0]]
    for player in slist[1:]:
        if player[1] == slist[0][1]:
            winners.append(player[0])
        else:
            break

    msg.reply(bold + "=======     GAME OVER!     =======" + bold)
    log.info(bold + "=======     GAME OVER!     =======" + bold)
    msg.reply("Winner" + ("s" if len(winners) > 1 else "") + \
            " with a score of " + slist[0][1] + ": " +\
            bold + ", ".join(winners[:-1]) + \
            (" and " if len(winners) > 1 else "") + \
            winners[-1] + "!"
    )

    while slist:
        if len(slist) >= 3:
            msg.reply(
                    "{:>15}: {:>2} {:>15}: {:>2} {:>15}: {:>2}".format(
                    slist[0][0], slist[0][1],
                    slist[1][0], slist[1][1],
                    slist[2][0], slist[2][1]
            ))
            log.info(
                    "{:>15}: {:>2} {:>15}: {:>2} {:>15}: {:>2}".format(
                    slist[0][0], slist[0][1],
                    slist[1][0], slist[1][1],
                    slist[2][0], slist[2][1]
            ))
            del slist[0:3]
        elif len(slist) == 2:
            msg.reply(
                    "{:>15}: {:>2} {:>15}: {:>2}".format(
                    slist[0][0], slist[0][1],
                    slist[1][0], slist[1][1]
            ))
            log.info(
                    "{:>15}: {:>2} {:>15}: {:>2}".format(
                    slist[0][0], slist[0][1],
                    slist[1][0], slist[1][1]
            ))
            del slist[0:2]
        else:
            msg.reply("{:>15}: {:>2}".format(slist[0][0], slist[0][1]))
            log.info("{:>15}: {:>2}".format(slist[0][0], slist[0][1]))
            del slist[0]
        
    # be safe, kill any lingering threads
    killgame(state)

def killgame(state, reset=True):
    if state['round'] == 0:
        return
    for t in state['threads'].itervalues():
        try:
            t.cancel()
        except AttributeError:
            continue
    if reset:
        resetstate(state)
    log.info("Game killed.")

def resetstate(state):
    state.update({
	    # Round number, 0=no game running
        'round': 0,
        # Round's game text and shape of removed words
        'doc': None,
        'text': '',
        'textshape': [],
        # Pending entries: [(nick, [words], votes), ...]
        'entries': [],
        # Pending votes: { nick: voteentry, ... } # 0-indexed
        'votes': defaultdict(constant_factory(-1)),
        # Scores: { nick: score, ... }
        'scores': defaultdict(int),
        # Threads on timers, keyed by thread ident
        'threads': {},
        # Absolute path to corpus file
        'corpus': None,
        # set of skippers
        'skippers': set()
    })


@command(["madlibs", "startgame"], require_owner=True)
def startgame(msg, state):
    "Start a game of Mad Libs."
    msg.reply("Welcome to super duper amazing Mad Libs game!")
    msg.reply("Round 1/{0} starts in {1} seconds.".format(
            state['options']['numrounds'],
            state['options']['intertime']
    ))
    state['round'] = 0.75
    t = threading.Timer(
            state['options']['intertime'],
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
    # intertime 0.75 state falls through with no action

def load():
    statedict = {
        # Default game options
        'options': {
            # game length and timing options
            'numrounds': 8,
            'entrytime': 90,
            'votetime': 80,
            'warntime': 15,
            'intertime': 15,
            # gameplay options
            'hidesentence': False,
            'botplays': True,
            'corporaset': 'McGuffey',
            'corpus': 'None',
            'linemaxlen': 400,
            'shame': True,
            'matchpos': True,
            'stopwords': ["cosby", "urkel", "huxtable", "arvid",
                    "imhotep", "shumway", "dodonga"]
        }
    }
    resetstate(statedict)
    return statedict

def unload(state):
    killgame(state)
