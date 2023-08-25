import datetime
import json
import random

from google.cloud import ndb

import flask_login

from lib.util import random_name, random_string, generate_token

import config

# client connection
client = ndb.Client()

timestring = "%Y-%m-%dT%H:%M:%SZ"

# transactions secure queries
class Transaction(ndb.Model):
	uid = ndb.StringProperty() # owner
	tid = ndb.StringProperty()
	created = ndb.DateTimeProperty()

	@classmethod
	def get_old(cls, timestamp):
		with client.context():
			return cls.query(cls.created < timestamp)

	@classmethod
	def get_by_tid(cls, tid):
		with client.context():
			return cls.query(cls.tid == tid).get()

	@classmethod
	def create(cls, tid=None, uid=None):
		with client.context():
			cls(
				tid = tid,
				uid = uid,
				created = datetime.datetime.utcnow()
			).put()
			return cls.query(cls.tid == tid).get()

# user inherits from flask_login and ndb
class User(flask_login.UserMixin, ndb.Model):
	uid = ndb.StringProperty() # user_id
	name = ndb.StringProperty() # assigned name
	created = ndb.DateTimeProperty()
	updated = ndb.DateTimeProperty()
	expires = ndb.DateTimeProperty()

	# auth settings and log
	dbid = ndb.StringProperty()
	db_token = ndb.StringProperty()
	admin = ndb.BooleanProperty()

	# status
	authenticated = ndb.BooleanProperty(default=False)
	active = ndb.BooleanProperty(default=True)
	anonymous = ndb.BooleanProperty(default=False)

	# API use
	api_token = ndb.StringProperty()

	# flask-login
	def is_active(self): # all accounts are active
		return self.active

	def get_id(self):
		return self.uid

	def is_authenticated(self):
		return self.authenticated

	def is_anonymous(self):
		return self.anonymous


	@classmethod
	def token_reset(cls, uid=uid):
		with client.context():
			user = cls.query(cls.uid == uid).get()
			user.api_token = generate_token()
			user.put()
			return user

	@classmethod
	def create(cls, dbid="", db_token=""):
		name = random_name(3)
		uid = random_string(size=17)
		with client.context():
			cls(
				uid = uid,
				name = name,
				created = datetime.datetime.utcnow(),
				updated = datetime.datetime.utcnow(),
				expires = datetime.datetime.utcnow() + datetime.timedelta(days=15),
				admin = False,
				dbid = dbid,
				db_token = db_token,
				api_token = generate_token()
			).put()

			return cls.query(cls.dbid == dbid).get()

	@classmethod
	def get_by_name(cls, name):
		with client.context():
			return cls.query(cls.name == name).get()

	@classmethod
	def get_by_dbid(cls, dbid):
		with client.context():
			return cls.query(cls.dbid == dbid).get()

	@classmethod
	def get_by_uid(cls, uid):
		with client.context():
			return cls.query(cls.uid == uid).get()

	@classmethod
	def get_by_token(cls, api_token):
		with client.context():
			return cls.query(cls.api_token == api_token).get()
