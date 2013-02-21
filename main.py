import os
import webapp2
import jinja2
import logging
import json
from google.appengine.ext import ndb
from google.appengine.api import channel

TEMPLATE_PATH = os.path.dirname(__file__) + '/views'

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_PATH, encoding='utf8'),
    autoescape=True)

class ClientToken(ndb.Model):
    boardname = ndb.StringProperty()
    token = ndb.StringProperty()
    connected = ndb.BooleanProperty()
    created = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def getToken(cls, boardname):
        return cls.query(cls.boardname==boardname).get()

    @classmethod
    def getConnectedToken(cls, boardname):
        return cls.query(cls.boardname==boardname, cls.connected==True).get()

class CurrentMessage(ndb.Model):
    boardname = ndb.StringProperty()
    message = ndb.TextProperty()

    @classmethod
    def getMessage(cls, boardname):
        return cls.query(cls.boardname==boardname).get()

    @classmethod
    def setMessage(cls, boardname, message):
        cm = cls.getMessage(boardname)
        if cm is None:
            cm = CurrentMessage()
            cm.boardname = boardname

        cm.message = message
        cm.put()

class BaseHandler(webapp2.RequestHandler):
    def getBaseTemplateValues(self):
        btVal = {}
        return btVal
    
    def getRenderedTemplate(self, filename, **template_args):
        """ Render template with template values """
        template = jinja_env.get_template(filename)
        template_values = self.getBaseTemplateValues()
        template_values.update(template_args)
        return template.render(template_values)

    def responseTemplate(self, filename, **template_args):
        """ Response rendered template """
        self.response.out.write(self.getRenderedTemplate(filename, **template_args))

class TokenHandler(webapp2.RequestHandler):
    def get(self, boardname):
        if(boardname == '' ):
            self.response.out.write('Board name is required.')
            return;

        ct = ClientToken.getToken(boardname)
        if ct is None:
            ct = ClientToken()
            ct.boardname = boardname

        ct.connected = False
        ct.token = channel.create_channel( boardname )
        ct.put()

        json_data = { "token" : ct.token }

        self.response.content_type = "application/json"
        json.dump(json_data, self.response.out)

class TokenStatusHandler(webapp2.RequestHandler):
    def get(self, boardname):
        if(boardname == '' ):
            self.response.out.write('Board name is required.')
            return;

        connected = False
        ct = ClientToken.getToken(boardname)
        if ct is not None:
            connected = ct.connected

        json_data = { "connected" : connected }

        self.response.content_type = "application/json"
        json.dump(json_data, self.response.out)

class ConnectedHandler(webapp2.RequestHandler):
    def post(self):
        boardname = self.request.get('from')
        logging.info("Connected:" + boardname)
        ct = ClientToken.getToken(boardname)
        ct.connected = True
        ct.put()

        message = ""
        cm = CurrentMessage.getMessage(boardname)
        if cm is not None:
            message = cm.message

        send_data = { "message": message }
        channel.send_message(boardname, json.dumps(send_data))

class DisconnectedHandler(webapp2.RequestHandler):
    def post(self):
        boardname = self.request.get('from')
        logging.info("Disconnected:" + boardname)
        ct = ClientToken.getToken(boardname)
        ct.connected = False
        ct.put()

class MessageHandler(webapp2.RequestHandler):
    def post(self, boardname):
        logging.info(boardname)
        
        result = "Board is not connected";
        
        message = self.request.get('message')
        
        ct = ClientToken.getConnectedToken(boardname)
        if ct is not None:
            send_data = { "message": message }
            channel.send_message(boardname, json.dumps(send_data))
            result = "Sent message successfully"
            CurrentMessage.setMessage(boardname, message)

        json_data = { "result" : result }

        self.response.content_type = "application/json"        
        json.dump(json_data, self.response.out)

class ConsoleHandler(BaseHandler):
    def get(self):
        self.responseTemplate("console.html")

class MainHandler(BaseHandler):
    def get(self):
        self.responseTemplate("board.html")

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/console', ConsoleHandler),
    ('/message/(.*)', MessageHandler),
    ('/token/status/(.*)', TokenStatusHandler),
    ('/token/(.*)', TokenHandler),
    ('/_ah/channel/connected/', ConnectedHandler),
    ('/_ah/channel/disconnected/', DisconnectedHandler)
], debug=True)
