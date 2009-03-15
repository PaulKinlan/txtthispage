#!/usr/bin/env python

import wsgiref.handlers
import re # Regular expressions
import random

import os
import datetime
import time

import md5
import base64
import urllib

import logging

from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import urlfetch

defaultTwitterName = ""
defaultTwitterPassword = ""

class User(db.Model):
	username = db.StringProperty()
	msisdn = db.StringProperty()
	password = db.StringProperty('67352')
	message_count = db.IntegerProperty( default = 0)
	profile_picture = db.BlobProperty()
	profile_message = db.TextProperty()
	password_fails = db.IntegerProperty( default = 0)
	twitter_username = db.StringProperty()
	twitter_password = db.StringProperty()
	
    
class Message(db.Model):
	service_id = db.IntegerProperty()
	msisdn = db.StringProperty()
	shortcode = db.StringProperty()
	mno = db.StringProperty()
	text = db.TextProperty()
	country = db.StringProperty()
	lang = db.StringProperty()
	msg_id = db.IntegerProperty()
	market_id = db.IntegerProperty()
	tac = db.StringProperty()
	user_reference = db.StringProperty()
	timestamp = db.DateTimeProperty()
	added_on = db.DateTimeProperty(auto_now_add = True)
	user = db.ReferenceProperty(User)
	user_id = db.IntegerProperty() # use as a quick reference.
	is_admin = db.BooleanProperty()
	debug_QueryString = db.TextProperty()
	parent_of_reply = db.SelfReferenceProperty(collection_name = 'replies')
	reply_count = db.IntegerProperty(default = 0)
	
class TextFormatter():
	def format(self, text):
		# change @digits into a link.
		text = re.sub("@(\d+)", "<a href=\"/u/\\1\">@\\1</a>", text) # link the uid
		text = re.sub("\*\*(.*?)\*\*", "<strong>\\1</strong>", text) # make strong the text
		text = re.sub("__(.*?)__", "<em>\\1</em>", text) # italicise the text
		#text = re.sub("\[(http://|https://)(.*?)\]", "<a href=\"\\1\\2\">\\2</a>", text)
		text = re.sub("\!(\d+)", "<a href=\"/msg/\\1\">!\\1</a>", text)
		return text

class InputEncoder():
	def encode(self, text):
		
		if not isinstance(text, unicode):
			text = unicode(text, "latin-1")
		
		return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	
class Index(webapp.RequestHandler):
    def get(self):
		path = os.path.join(os.path.dirname(__file__),"template", "index.html")
		
		latestQuery = db.Query(Message).order("-added_on").fetch(50)
		
		formatter = TextFormatter()
		
		for msg in latestQuery:
			msg.text = formatter.format(msg.text)
			msg.id = msg.key().id()
		
		latest = latestQuery[0]
		therest = latestQuery[1:50]
		
		self.response.out.write(template.render(path, {"latest": latest, "therest": therest} ))


		
class FacebookIndex(webapp.RequestHandler):
    def get(self):
		path = os.path.join(os.path.dirname(__file__),"template", "facebookindex.html")
		
		latestQuery = db.Query(Message).order("-added_on").fetch(50)
		
		formatter = TextFormatter()
		
		for msg in latestQuery:
			msg.text = formatter.format(msg.text)
			msg.id = msg.key().id()
		
		latest = latestQuery[0]
		therest = latestQuery[1:50]
		
		self.response.out.write(template.render(path, {"latest": latest, "therest": therest} ))		

class Latest(webapp.RequestHandler):
    def get(self):
		path = os.path.join(os.path.dirname(__file__),"template", "json.txt")
		
		latest = db.Query(Message).order("-added_on").fetch(50)	
		
		self.response.out.write(self.response.out.write(template.render(path, {"messages": latest} )))

class AdminResponseHandler(webapp.RequestHandler):
	def get(self, text):
		msg = self.createMessage(text)
		
		msg.put()	
		
		self.response.out.write("Admin Sent Message:" + msg.text)
	
	def createMessage(self,text):
		cleaner = TxtCleaner()
		encoder = InputEncoder()
	
		service_id = self.request.get('service_id', -1)
		msisdn = self.request.get('msisdn', '')
		shortcode = self.request.get('shortcode', '')
		mno = self.request.get('mno', '')
		text = urllib.unquote(self.request.get('text', text))
		country = self.request.get('country', 'uk')
		lang = self.request.get('lang', 'en-gb')		
		msg_id = self.request.get('msg_id', -1)		
		market_id = self.request.get('market_id', -1)		
		tac = self.request.get('tac', '')
		user_reference = self.request.get('user_reference', '')
		timestamp = self.request.get('timestamp', '')
		
		#get the user
		usr = db.Query(User).filter("msisdn =", msisdn).get()
		
		if usr is None:
			usr = User()
			usr.name = "txtthispage"
			usr.msisdn = msisdn
			usr.put()
		
		msg = Message()
		
		msg.service_id = int(service_id)
		msg.msisdn = msisdn
		msg.shortcode = shortcode
		msg.mno = mno
		msg.text = encoder.encode(cleaner.clean(text))
		msg.country = country
		msg.lang = lang
		msg.msg_id = int(msg_id)
		msg.market_id = int(market_id)
		msg.tac = tac
		msg.user_reference = user_reference
		msg.user = usr
		msg.user_id = usr.key().id()
				
		return msg


class MessageController():
	def process(self, request):
		text = request.request.get('text', '')
		
		txtPage = re.match("textpage|txtpage", text, re.I)
		txtReply = re.match("textreply|txtreply", text, re.I)
		handler = None
		if txtPage is not None:
			handler = MessageHandler()			
		elif txtReply is not None:
			handler = ReplyHandler()
			
		return handler.process(request)
		
class MessageHandler():
	def process(self, request):
		
		
		msg = self.createMessage(request.request)
		
		msg.put()
		
		return msg
		
		
	def createMessage(self, request):
		cleaner = TxtCleaner()
		encoder = InputEncoder()
	
		service_id = request.get('service_id', '')
		msisdn = request.get('msisdn', '')
		shortcode = request.get('shortcode', '')
		mno = request.get('mno', '')
		text = urllib.unquote(request.get('text', ''))
		country = request.get('country', '')
		lang = request.get('lang', '')		
		msg_id = request.get('msg_id', '')		
		market_id = request.get('market_id', '')		
		tac = request.get('tac', '')
		user_reference = request.get('user_reference', '')
		timestamp = request.get('timestamp', '')
		
		#get the user
		usr = db.Query(User).filter("msisdn =", msisdn).get()
		
		if usr is None:
			usr = User()
			usr.msisdn = msisdn
			usr.password = str(self.createPassword())
			usr.put()
		
		if usr.password is None:
			usr.password = str(self.createPassword())
			usr.put()
		
		
		msg = Message()
		
		msg.service_id = int(service_id)
		msg.msisdn = msisdn
		msg.shortcode = shortcode
		msg.mno = mno
		msg.text = encoder.encode(cleaner.clean(text))
		msg.country = country
		msg.lang = lang
		msg.msg_id = int(msg_id)
		msg.market_id = int(market_id)
		msg.tac = tac
		msg.user_reference = user_reference
		msg.user = usr
		msg.user_id = usr.key().id()
		msg.debug_QueryString = request.query_string
				
		return msg
		
	def createPassword(self):
		return random.randint(1,999999)

class ReplyHandler():
	'A reply has come in.'
	def process(self, request):
		
		msg = self.createMessage(request.request)
		
		msg.put()
		
		return msg
		
	def createMessage(self, request):
		cleaner = TxtCleaner()
		encoder = InputEncoder()
	
		service_id = request.get('service_id', '')
		msisdn = request.get('msisdn', '')
		shortcode = request.get('shortcode', '')
		mno = request.get('mno', '')
		text = urllib.unquote(request.get('text', ''))
		country = request.get('country', '')
		lang = request.get('lang', '')		
		msg_id = request.get('msg_id', '')		
		market_id = request.get('market_id', '')		
		tac = request.get('tac', '')
		user_reference = request.get('user_reference', '')
		timestamp = request.get('timestamp', '')
		
		#get the user
		usr = db.Query(User).filter("msisdn =", msisdn).get()
		
		#get the message id.
		subjectMsgId = self.getSubjectMessageId(text)
		#get the message that this is intended for.
		subjectMsg = Message.get_by_id(subjectMsgId)
		
		if subjectMsg is None:
			return
		
		if usr is None:
			usr = User()
			usr.msisdn = msisdn
			usr.password = str(self.createPassword())
			usr.put()
		else:
			if usr.message_count is None:
				usr.message_count = 0			
			usr.message_count = usr.message_count + 1
			usr.put()
		
		msg = Message()
		
		msg.service_id = int(service_id)
		msg.msisdn = msisdn
		msg.shortcode = shortcode
		msg.mno = mno
		msg.text = encoder.encode(cleaner.clean(text))
		msg.country = country
		msg.lang = lang
		msg.msg_id = int(msg_id)
		msg.market_id = int(market_id)
		msg.tac = tac
		msg.user_reference = user_reference
		msg.user = usr
		msg.user_id = usr.key().id()
		msg.parent_of_reply = subjectMsg
		msg.debug_QueryString = request.query_string
		msg.reply_count = 0
		
		#  increment the subject message counters.
		if subjectMsg.reply_count is None:
			subjectMsg.reply_count = 0
		
		subjectMsg.reply_count = subjectMsg.reply_count + 1		
		subjectMsg.put()
		
		# send a message to twitter
		twitterUn = usr.twitter_username
		
		if twitterUn is None:
			twitterUn = defaultTwitterName
		
		twitterPwd = usr.twitter_password
		
		if twitterPwd is None:
			twitterPwd = defaultTwitterPassword
		
		
		base64string = base64.encodestring('%s:%s' % (twitterUn, twitterPwd))[:-1]
		payload= {'status' : msg.text, 'source': 'txtthispage'}
		payload= urllib.urlencode(payload)

		headers = {'Authorization': "Basic %s" % base64string} 
		
		try:
			result = urlfetch.fetch('http://twitter.com/statuses/update.json', method = urlfetch.POST, headers = headers, payload = payload)
			content = result.content
		except:
			pass # there has been an error ignore it.
				
		return msg
		
	def getSubjectMessageId(self, text):
		
		msgIdMatch = re.search("!(\d+)", text, re.I)
		
		if msgIdMatch is not None:
			val = int(msgIdMatch.group(1))
			return val
		else:
			return 0
	
	def createPassword(self):
		return random.randint(1,999999)


		
class TxtResponseHandler(webapp.RequestHandler):
	def get(self):
		controller = MessageController()
		msg = controller.process(self)		
			
		path = os.path.join(os.path.dirname(__file__),"template", "response.xml")
		self.response.out.write(self.response.out.write(template.render(path, {"msg": msg} )))
		
		usr = msg.user
		
		twitterUn = usr.twitter_username
		
		if twitterUn is None:
			twitterUn = defaultTwitterName
		
		twitterPwd = usr.twitter_password
		
		if twitterPwd is None:
			twitterPwd = defaultTwitterPassword
		
		
		base64string = base64.encodestring('%s:%s' % (twitterUn, twitterPwd))[:-1]
		payload= {'status' : msg.text, 'source': 'txtthispage'}
		payload= urllib.urlencode(payload)

		headers = {'Authorization': "Basic %s" % base64string} 
		
		try:
			result = urlfetch.fetch('http://twitter.com/statuses/update.json', method = urlfetch.POST, headers = headers, payload = payload)
			content = result.content
		except:
			pass # there has been an error ignore it.
		
	def processMessage(self, msg):
		userid = re.match("@(\d+)", msg.text)
		#There is a user id. make sure that we add the message to that users queue.
		
	
	def post(self):		
		msg =  self.createMessage()
		
		msg.put()
		
	def createMessage(self):
		cleaner = TxtCleaner()
		encoder = InputEncoder()
	
		service_id = self.request.get('service_id', '')
		msisdn = self.request.get('msisdn', '')
		shortcode = self.request.get('shortcode', '')
		mno = self.request.get('mno', '')
		text = urllib.unquote(self.request.get('text', ''))
		country = self.request.get('country', '')
		lang = self.request.get('lang', '')		
		msg_id = self.request.get('msg_id', '')		
		market_id = self.request.get('market_id', '')		
		tac = self.request.get('tac', '')
		user_reference = self.request.get('user_reference', '')
		timestamp = self.request.get('timestamp', '')
		
		#get the user
		usr = db.Query(User).filter("msisdn =", msisdn).get()
		
		if usr is None:
			usr = User()
			usr.msisdn = msisdn
			usr.password = self.createPassword()
			usr.put()
		
		msg = Message()
		
		msg.service_id = int(service_id)
		msg.msisdn = msisdn
		msg.shortcode = shortcode
		msg.mno = mno
		msg.text = encoder.encode(cleaner.clean(text))
		msg.country = country
		msg.lang = lang
		msg.msg_id = int(msg_id)
		msg.market_id = int(market_id)
		msg.tac = tac
		msg.user_reference = user_reference
		msg.user = usr
		msg.user_id = usr.key().id()
		msg.debug_QueryString = self.request.query_string
				
		return msg
		
	def createPassword(self):
		return random.randint(1,99999)
	


class Twitter(webapp.RequestHandler):
	def get(self):
				
		# send a message to twitter
		base64string = base64.encodestring('%s:%s' % (defaultTwitterName, defaultTwitterPassword))[:-1]
		payload= {'status' : 'Hello', 'source': 'txtthispage'}
		payload= urllib.urlencode(payload)

		headers = {'Authorization': "Basic %s" % base64string} 
		
		try:
			fetch = urlfetch.fetch('http://twitter.com/statuses/update.json', method = urlfetch.POST, headers = headers, payload = payload)
			self.response.out.write(fetch.content)
		except:
			self.response.out.write("Ouch and Error")
			pass # there has been an error ignore it.
		
	
class Msg(webapp.RequestHandler):
	def get(self, msg = 1):
		path = os.path.join(os.path.dirname(__file__),"template", "message.html")
		message = Message.get_by_id(int(msg))
		
		if message is None:
			path = os.path.join(os.path.dirname(__file__),"template", "nomessage.html")
			self.response.out.write(self.response.out.write(template.render(path, {} )))
			return
		
		formatter = TextFormatter()
		message.unencodedtext = message.text
		message.text = formatter.format(message.text)
		
		message.id = message.key().id()
		
		replies = message.replies
		
		for rep in replies:
			rep.unencodedtext = rep.text
			rep.text = formatter.format(rep.text)
		
		self.response.out.write(self.response.out.write(template.render(path, {"message": message, "replies": replies} )))
		
class AddReply(webapp.RequestHandler):
	'Adds a reply from the web'
	def post(self, msg = 0):
		user_id = self.request.get('user_id', 0)
		reply = self.request.get('reply', '')
		password = self.request.get('password', '')
		
		# get the msg that the user is replying to.
		message = Message.get_by_id(int(msg))
		user = User.get_by_id(int(user_id))
		
		if user is None:
			#no user no message stored.
			return

		if user.password != password:
			# the password is wrong
			logging.info('wrong password: ' + password)
			self.error(401)
			return
		
		formatter = TextFormatter();
		
		newmsg = Message()		
		newmsg.service_id = 1
		newmsg.msisdn = user.msisdn
		newmsg.user = user
		newmsg.user_id = user.key().id()
		newmsg.text =  formatter.format(reply)		
		newmsg.parent_of_reply = message
		
		
		if message.reply_count is None:
			message.reply_count = 0
		
		message.reply_count = message.reply_count + 1
		
		message.put()		
		newmsg.put()
		
		if user.message_count is None:
			user.message_count = 0
			
		user.message_count = user.message_count + 1
		user.put()
		
		twitterUn = user.twitter_username
		
		if twitterUn is None:
			twitterUn = defaultTwitterName
		
		twitterPwd = user.twitter_password
		
		if twitterPwd is None:
			twitterPwd = defaultTwitterPassword		
		
		base64string = base64.encodestring('%s:%s' % (twitterUn, twitterPwd))[:-1]
		payload= {'status' : newmsg.text, 'source': 'txtthispage'}
		payload= urllib.urlencode(payload)

		headers = {'Authorization': "Basic %s" % base64string} 
		
		try:
			result = urlfetch.fetch('http://twitter.com/statuses/update.json', method = urlfetch.POST, headers = headers, payload = payload)
			content = result.content
		except:
			pass # there has been an error ignore it.
		
		self.redirect('/msg/' + msg)

class AddMsg(webapp.RequestHandler):
	'Adds a msg from the web'
	def post(self, usr = 0):
		user_id =  int(usr)
		reply = self.request.get('reply', '')
		password = self.request.get('password', '')
		
		# get the msg that the user is replying to.
		user = User.get_by_id(int(user_id))
		
		if user is None:
			#no user no message stored.
			return

		if user.password != password:
			# the password is wrong
			logging.info('wrong password: ' + password)
			self.error(401)
			return
		
		formatter = TextFormatter();
		
		newmsg = Message()		
		newmsg.service_id = 1
		newmsg.msisdn = user.msisdn
		newmsg.user = user
		newmsg.user_id = user.key().id()
		newmsg.text =  formatter.format(reply)
					
		newmsg.put()
		
		if user.message_count is None:
			user.message_count = 0
			
		user.message_count = user.message_count + 1
		user.put()
		
		twitterUn = user.twitter_username
		
		if twitterUn is None:
			twitterUn = defaultTwitterName
		
		twitterPwd = user.twitter_password
		
		if twitterPwd is None:
			twitterPwd = defaultTwitterPassword
		
		
		base64string = base64.encodestring('%s:%s' % (twitterUn, twitterPwd))[:-1]
		payload= {'status' : newmsg.text, 'source': 'txtthispage'}
		payload= urllib.urlencode(payload)

		headers = {'Authorization': "Basic %s" % base64string} 
		
		try:
			result = urlfetch.fetch('http://twitter.com/statuses/update.json', method = urlfetch.POST, headers = headers, payload = payload)
			content = result.content
		except:
			pass # there has been an error ignore it.
		
		self.redirect('/u/' + usr)
		
class UserHandler(webapp.RequestHandler):
	def get(self, user = 1):
	
		userObj = User.get_by_id(int(user))
		
		if userObj is None:
			path = os.path.join(os.path.dirname(__file__),"template", "nouser.html")
			self.response.out.write(self.response.out.write(template.render(path, {} )))
			return
		
		userObj.id = userObj.key().id()
		
		messages = db.Query(Message).filter("user =",userObj).order("-added_on").fetch(100)
		
		formatter = TextFormatter()
		
		for msg in messages:		
			msg.text = formatter.format(msg.text)
			msg.id = msg.key().id()
					
		path = os.path.join(os.path.dirname(__file__),"template", "userhtml.html")
		self.response.out.write(self.response.out.write(template.render(path, {"messages": messages, "user": userObj} )))

class UserRssHandler(webapp.RequestHandler):
	def get(self, user = 1):
	
		userObj = User.get_by_id(int(user))
		userObj.id = userObj.key().id()
		
		messages = db.Query(Message).filter("user =",userObj).order("-added_on").fetch(100)
		
		latest = messages[0]
		
		formatter = TextFormatter()
		
		for msg in messages:		
			msg.text = formatter.format(msg.text)
			msg.id = msg.key().id()
					
		path = os.path.join(os.path.dirname(__file__),"template", "userrss.xml")
		self.response.out.write(self.response.out.write(template.render(path, {"messages": messages, "latest": latest,"user": userObj} )))
		
class AllHtml(webapp.RequestHandler):
	def get(self):
		recent = db.Query(Message).order("-added_on").fetch(200)
		
		for msg in recent:
			msg.id = msg.key().id()
		
		path = os.path.join(os.path.dirname(__file__),"template", "allhtml.html")
		self.response.out.write(self.response.out.write(template.render(path, {"messages": recent} )))

	
class AllRSS(webapp.RequestHandler):
	def get(self):
		recent = db.Query(Message).order("-added_on").fetch(200)
		
		for msg in recent:
			msg.id = msg.key().id()
		
		path = os.path.join(os.path.dirname(__file__),"template", "allrss.xml")
		self.response.out.write(self.response.out.write(template.render(path, {"messages": recent, "latest": recent[0]} )))
		
class TxtCleaner():
	def clean(self, txt):		
		return re.sub("^textpage|^textreply|^text|^txtpage|^txtreply|^txt", "", txt.lower(), re.I)
		
def main():
    application = webapp.WSGIApplication([(r'/', Index),(r'/facebook', FacebookIndex), (r'/test',Twitter), (r'/AdminResponseAdd/(.+)', AdminResponseHandler), (r'/all', AllHtml), (r'/u/(\d+)\.rss', UserRssHandler), (r'/u/(\d+)', UserHandler), (r'/msg/(\d+)', Msg), (r'/u/(\d+?)/add', AddMsg), (r'/msg/(\d+?)/reply', AddReply), (r'/rss/all.rss', AllRSS), (r'/Latest', Latest), (r'/TxtResponseHandler', TxtResponseHandler)], debug=False)
    wsgiref.handlers.CGIHandler().run(application);

if __name__ == '__main__':
  main()