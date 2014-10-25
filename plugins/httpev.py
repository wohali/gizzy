"""\
This plugin merely enables other plugins to accept data over HTTP. If
a plugin defines a module level function named "httpev" it will be
invoked for POST requests to the url http://$hostname/event/$pluginname.
The function is invoked from the thread in the web.py request context
and as such has access to the full web.py API.
"""


import base64
import json

import web


web.config.debug = False


class Event(object):
    def POST(self, plugin):
        self.check_authorized()
        func = self.find_handler(plugin)
        try:
            func()
        except web.webapi.HTTPError:
            raise
        except:
            log.exception("Plugin '%s' broke handling HTTP event" % plugin)
            raise web.webapi.internalerror()

    def check_authorized(self):
        auth = web.ctx.env.get('HTTP_AUTHORIZATION')
        if auth is None:
            raise web.webapi.unauthorized()
        if not auth.startswith("Basic "):
            raise web.webapi.unauthorized()
        try:
            auth = auth.split(None, 1)[1]
            raw = base64.decodestring(auth)
            if tuple(raw.split(":", 1)) == config.httpev["auth"]:
                return
        except:
            raise web.webapi.badrequest("Invalid Authorization header")
        raise web.webapi.unauthorized()

    def find_handler(self, name):
        for p in plugin_manager.plugins:
            if p.name == name:
                func = p.data.get("httpev")
                if callable(func):
                    return func
        raise web.webapi.notfound()


class Server(threading.Thread):
    def __init__(self):
        super(Server, self).__init__()
        self.setDaemon(True)
        self.urls = ("/event/(.+)", "Event")
        self.app = web.application(self.urls, {"Event": Event})
        self.addr = ('0.0.0.0', config.httpev["port"])
        self.srv = web.httpserver.WSGIServer(self.addr, self.app.wsgifunc())

    def stop(self):
        self.srv.stop()

    def run(self):
        self.srv.start()


def load():
    s = Server()
    s.start()
    return s


def unload(s):
    s.stop()
