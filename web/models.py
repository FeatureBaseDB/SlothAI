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


class Box(ndb.Model):
		box_id = ndb.StringProperty()
		ip_address = ndb.StringProperty()
		status = ndb.StringProperty(default='available')
		
		@classmethod
		def create(cls, box_id, ip_address):
				with ndb.Client().context():
						box = cls(box_id=box_id, ip_address=ip_address)
						box.put()
						return cls.query(cls.box_id == box_id).get()
		
		@classmethod
		def get_available_box(cls):
				with ndb.Client().context():
						available_box = cls.query(cls.status == 'available').get()
						if available_box:
								available_box.status = 'busy'
								available_box.put()
						return available_box
		
		@classmethod
		def release_box(cls, box_id):
				with ndb.Client().context():
						box = cls.query(cls.box_id == box_id).get()
						if box:
								box.status = 'available'
								box.put()
								
		def start_box(self):
				# Code to start the box or spot instance
				self.status = 'running'
				self.put()
				
		def stop_box(self):
				# Code to stop the box or spot instance
				self.status = 'stopped'
				self.put()


class Jobs(ndb.Model):
		jid = ndb.StringProperty()
		uid = ndb.StringProperty()
		created = ndb.DateTimeProperty()
		expires = ndb.DateTimeProperty()
		document = ndb.JsonProperty()  # document object (contains the model mid)
		status = ndb.StringProperty(default='pending')  # Adding a status field
		running_at = ndb.StringProperty(default='nowhere')  # Reference to the Box where the model is running

		@classmethod
		def create(cls, uid, document):
				with ndb.Client().context():
						jid = generate_token(size=10)  # Assuming generate_token is defined elsewhere
						current_utc_time = datetime.datetime.utcnow()
						expiration_time = current_utc_time + datetime.timedelta(hours=1)  # Expiry in 1 hours
						
						job = cls(
								jid=jid,
								uid=uid,
								created=current_utc_time,
								expires=expiration_time,
								document=document
						)
						job.put()
						return cls.query(cls.jid == jid).get()

		@classmethod
		def select_next_scheduled_job(cls):
				with ndb.Client().context():
						current_utc_time = datetime.datetime.utcnow()

						# Check if there's another job already processing
						processing_job = cls.query(cls.status == 'processing').get()
						if processing_job:
								return None  # Another job is already processing
						
						# Remove expired jobs
						expired_jobs = cls.query(cls.expires < current_utc_time).fetch(keys_only=True)
						ndb.delete_multi(expired_jobs)
						
						# Select the next pending job
						next_job = cls.query(cls.status == 'pending', cls.expires >= current_utc_time).order(cls.expires).get()
						if next_job:
								next_job.status = 'processing'
								next_job.put()
						return next_job

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
