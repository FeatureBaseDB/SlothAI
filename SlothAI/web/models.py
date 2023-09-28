import datetime

from google.cloud import ndb

import flask_login

from SlothAI.lib.util import random_name, random_string, generate_token

import config as config

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


class Models(ndb.Model):
	mid = ndb.StringProperty()
	name = ndb.StringProperty()
	kind = ndb.StringProperty()
	ai_model = ndb.StringProperty()
	field = ndb.StringProperty()
	gpu = ndb.StringProperty()

	@classmethod
	def get_by_mid(cls, mid):
		with client.context():
			return cls.query(cls.mid == mid).get().to_dict()

	@classmethod
	def get_by_kind(cls, kind):
		with client.context():
			entities = cls.query(cls.kind == kind).fetch()
			return [entity.to_dict() for entity in entities]
	@classmethod
	def get_all(cls):
		with client.context():
			entities = cls.query().fetch()
			return [entity.to_dict() for entity in entities]

	@classmethod
	def get_by_name(cls, name):
		if not name:
			return None
		with client.context():
			return cls.query(cls.name == name).get().to_dict()
			
	@classmethod
	def get_by_name_ai_model(cls, name, ai_model):
		if not name or ai_model:
			return None
		with client.context():
			return cls.query(cls.name == name, cls.ai_model == ai_model).get().to_dict()


class Table(ndb.Model):
	tid = ndb.StringProperty()
	uid = ndb.StringProperty()
	name = ndb.StringProperty()
	models = ndb.JsonProperty()
	schema = ndb.JsonProperty()
	openai_token = ndb.StringProperty()

	@classmethod
	def create(cls, uid, name, models, openai_token):
		with ndb.Client().context():
			print(models)
			print("in create")
			current_utc_time = datetime.datetime.utcnow()
			table = cls.query(cls.uid == uid,cls.name == name).get()
			if not table:
				tid = random_string(size=17)
				table = cls(tid=tid, uid=uid, name=name, models=models, openai_token=openai_token)
				table.put()

			return table.to_dict()

	@classmethod
	def delete(cls, tid):
		with ndb.Client().context():
			table = cls.query(cls.tid == tid).get()
			if table:
				table.key.delete()
				return True
			else:
				return False

	@classmethod
	def remove_by_uid(cls, uid):
		with ndb.Client().context():
			tables = cls.query(cls.uid == uid).fetch()
			for table in tables:
				table.key.delete() 
			
			return True
			
	@classmethod
	def get_all_by_uid(cls, uid):
		_tables = []
		with ndb.Client().context():
			tables = cls.query(cls.uid == uid).fetch()

			for table in tables:
				_tables.append(table.to_dict())

			if tables:
				return _tables
			else:
				return False

	@classmethod
	def get_by_uid_name(cls, uid, name):
		with ndb.Client().context():
			table = cls.query(cls.uid == uid, cls.name == name).get()
		if table:
			return table.to_dict()
		else:
			return False

	@classmethod
	def get_by_uid_tid(cls, uid, tid):
		with ndb.Client().context():
			table = cls.query(cls.uid == uid, cls.tid == tid).get()
		if table:
			return table.to_dict()
		else:
			return False


class Box(ndb.Model):
	box_id = ndb.StringProperty()
	ip_address = ndb.StringProperty()
	zone = ndb.StringProperty()
	status = ndb.StringProperty(default='available')
	expires = ndb.DateTimeProperty()
	runs_models = ndb.JsonProperty() # models it runs

	@classmethod
	def create(cls, box_id, ip_address, zone, status):
		with ndb.Client().context():
			# update or create box
			current_utc_time = datetime.datetime.utcnow()
			expiration_time = current_utc_time + datetime.timedelta(days=7)  # Expiry in 7 days
			box = cls.query(cls.box_id == box_id).get()
			if not box:
				box = cls(box_id=box_id, ip_address=ip_address, zone=zone, status=status, expires=expiration_time)
			else:
				box.ip_address = ip_address
				box.status = status

			box.put()

			return cls.query(cls.box_id == box_id).get()

	@classmethod
	def delete(cls, box_id):
		with ndb.Client().context():
			box = cls.query(cls.box_id == box_id).get()
			if box:
				box.key.delete()
				return True
			else:
				return False

	@classmethod
	def get_boxes(cls):
		with ndb.Client().context():
			entities = cls.query().fetch()
			return [entity.to_dict() for entity in entities]
							
	def start_box(self):
		# Code to start the box or spot instance
		self.status = 'running'
		self.put()
			
	def stop_box(self):
		# Code to stop the box or spot instance
		self.status = 'stopped'
		self.put()


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
			return user.to_dict()

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

			return cls.query(cls.dbid == dbid).get().to_dict()

	@classmethod
	def remove_by_uid(cls, uid):
		with ndb.Client().context():
			user = cls.query(cls.uid == uid).get()
			if user:
				user.key.delete() 
			else:
				return False
			return True

	@classmethod
	def authenticate(cls, uid):
		with client.context():
			user = cls.query(cls.uid == uid).get()
			user.authenticated = True
			user.put()
			return user

	@classmethod
	def get_by_name(cls, name):
		with client.context():
			result = cls.query(cls.name == name).get()
			if result:
				return result.to_dict()
			else:
				return None

	@classmethod
	def get_by_dbid(cls, dbid):
		with client.context():
			result = cls.query(cls.dbid == dbid).get()
			if result:
				return result.to_dict()
			else:
				return None

	@classmethod
	def get_by_uid(cls, uid):
		with client.context():
			result = cls.query(cls.uid == uid).get()
			if result:
				return result.to_dict()
			else:
				return None

	@classmethod
	def get_by_token(cls, api_token):
		with client.context():
			result = cls.query(cls.api_token == api_token).get()
			if result:
				return result.to_dict()
			else:
				return None
