"A utility plugin to fetch tweet links."


import urlparse

try:
    import HTMLParser as htmlparser
except ImportError:
    import html.parser as htmlparser

import BeautifulSoup
import requests


# John Gruber's URL regular expression
# http://daringfireball.net/2010/07/improved_regex_for_matching_urls
URL_RE = re.compile(u"""
(?xi)
\\b
(
  (?:
    [a-z][\w-]+:
    (?:
      /{1,3}
      |
      [a-z0-9%]

    )
    |
    www\d{0,3}[.]
    |
    [a-z0-9.\-]+[.][a-z]{2,4}/
  )
  (?:
    [^\s()<>]+
    |
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)
  )+
  (?:
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)
    |
    [^\s`!()\[\]{};:'".,<>?]
  )
)
""", re.VERBOSE)


@rule("twitter.com")
def twitterize(msg):
    "Fetch and display any linked tweets."
    match = URL_RE.search(msg.text)
    if not match:
        return
    url = match.group(0)

    parsed = urlparse.urlparse(url)
    if parsed.netloc not in ("twitter.com", "www.twitter.com"):
        return
    user = filter(None, parsed.path.split("/"))[0]
    tweet = get_tweet(match.group(0))
    if not msg:
        log.info("Failed to get tweet")
        return

    msg.reply(u"@{0} - {1}".format(user, tweet))


def get_tweet(url):
    r = requests.get(url)
    if r.status_code > 299:
        return
    soup = BeautifulSoup.BeautifulSoup(r.text)
    elem = soup.find("p", "tweet-text")
    if elem:
        return htmlparser.HTMLParser().unescape(elem.text)
