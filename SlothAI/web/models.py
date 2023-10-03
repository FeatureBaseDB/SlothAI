import datetime

from google.cloud import ndb

import flask_login

from SlothAI.lib.util import random_name, random_string, generate_token

import config as config

# client connection
client = ndb.Client()

# Create a context manager decorator
def ndb_context_manager(func):
	def wrapper(*args, **kwargs):
		with ndb.Client().context():
			result = func(*args, **kwargs)
		return result  # Return the result outside the context
	return wrapper

class Transaction(ndb.Model):
	uid = ndb.StringProperty()
	tid = ndb.StringProperty()
	created = ndb.DateTimeProperty()

	@classmethod
	@ndb_context_manager
	def get_old(cls, timestamp):
		entities = cls.query(cls.created < timestamp).fetch()
		return [entity.to_dict() for entity in entities]

	@classmethod
	@ndb_context_manager
	def get_by_tid(cls, tid):
		entity = cls.query(cls.tid == tid).get()
		return entity.to_dict() if entity else None

	@classmethod
	@ndb_context_manager
	def create(cls, tid=None, uid=None):
		table = cls(
			tid=tid,
			uid=uid,
			created=datetime.datetime.utcnow()
		)
		table.put()
		return table.to_dict()


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


class Node(ndb.Model):
	node_id = ndb.StringProperty()
	name = ndb.StringProperty()
	uid = ndb.StringProperty()
	input_keys = ndb.JsonProperty()
	output_keys = ndb.JsonProperty()
	extras = ndb.JsonProperty()  # auth, flavor, service, method, template, sql, etc.
	created = ndb.DateTimeProperty()

	@classmethod
	@ndb_context_manager
	def create(cls, name, uid, extras, input_keys, output_keys):
		current_utc_time = datetime.datetime.utcnow()
		existing_node = cls.query(cls.name == name, cls.uid == uid).get()

		if not existing_node:
			node_id = cls.random_string(13)
			node = cls(
				node_id=node_id,
				name=name,
				uid=uid,
				input_keys=input_keys,
				output_keys=output_keys,
				extras=extras,
				created=current_utc_time
			)
			node.put()
			return node.to_dict()
		else:
			return existing_node.to_dict()

	@classmethod
	@ndb_context_manager
	def get_by_node_id(cls, node_id, uid):
		entity = cls.query(cls.node_id == node_id, cls.uid == uid).get()
		
		if entity:
			return entity.to_dict()
		else:
			return None

	@classmethod
	def get_all_by_uid(cls, uid):
		with client.context():
			entities = cls.query(cls.uid == uid).fetch()
		
		if not entities:
			# Begin creating new ones for the user
			from SlothAI.lib.nodes import nodes
			
			for node in nodes:
				# Generate a random name with 2 characters
				name = random_name(2)
				
				# Create a new node and add it to the database
				extras = {}
				for extra_name in node['extras']:
					if extra_name in node:
						extras[extra_name] = node[extra_name]
					else:
						extras[extra_name] = None
				
				Node.create(
					name=name,
					uid=uid,
					extras=extras,
					input_keys=node['input_keys'],
					output_keys=node['output_keys']
				)

		result = []
		for entity in entities:
			entity_dict = entity.to_dict()
			result.append(entity_dict)
		return result

	@classmethod
	@ndb_context_manager
	def get_by_name_uid(cls, name, uid):
		entity = cls.query(cls.name == name, cls.uid == uid).get()
		if entity:
			entity_dict = entity.to_dict()
			return entity_dict
		else:
			return None

	@classmethod
	@ndb_context_manager
	def delete_by_node_id(cls, node_id):
		entity = cls.query(cls.node_id == node_id, cls.uid == uid).get()
		if entity:
			entity.key.delete()
			return True
		else:
			return False


class Pipeline(ndb.Model):
	pipe_id = ndb.StringProperty()
	uid = ndb.StringProperty()
	name = ndb.StringProperty()
	nodes = ndb.KeyProperty(kind=Node, repeated=True)
	created = ndb.DateTimeProperty()

	@classmethod
	@ndb_context_manager
	def create(cls, uid, name, node_ids):
		current_utc_time = datetime.datetime.utcnow()
		existing_pipeline = cls.query(cls.uid == uid, cls.name == name).get()

		if not existing_pipeline:
			nodes = [Node.query(Node.node_id == node_id).get() for node_id in node_ids if Node.query(Node.node_id == node_id).get()]
			pipe_id = cls.random_string(13)
			pipe = cls(
				pipe_id=pipe_id,
				uid=uid,
				name=name,
				nodes=nodes,
				created=current_utc_time
			)
			pipe.put()

			node_ids = [node.node_id for node in nodes]
			delattr(pipe, 'nodes')
			response_dict = pipe.to_dict()
			response_dict["nodes"] = node_ids

			return response_dict
		else:
			return existing_pipeline.to_dict()

	@classmethod
	@ndb_context_manager
	def get_by_pipe_id(cls, pipe_id):
		pipe = cls.query(cls.pipe_id == pipe_id).get()
		if pipe:
			nodes = [Node.query(Node.node_id == node_id).get() for node_id in node_ids if Node.query(Node.node_id == node_id).get()]

			node_ids = [node.node_id for node in nodes]
			delattr(pipe, 'nodes')
			response_dict = pipe.to_dict()
			response_dict["nodes"] = node_ids

			return response_dict
		else:
			return None

	@classmethod
	@ndb_context_manager
	def get_all_by_uid(cls, uid):
		pipes = cls.query(cls.uid == uid).fetch()
		result = []
		
		for pipe in pipes:
			node_ids = [node.node_id for node in pipe.nodes]
			delattr(pipe, 'nodes')
			pipe_dict = pipe.to_dict()
			pipe_dict['nodes'] = node_ids
			result.append(pipe_dict)

		return result

	@classmethod
	@ndb_context_manager
	def delete_by_pipe_id(cls, pipe_id):
		pipe = cls.query(cls.pipe_id == pipe_id).get()
		if pipe:
			pipe.key.delete()
			return True
		return False


class Box(ndb.Model):
	box_id = ndb.StringProperty()
	ip_address = ndb.StringProperty()
	zone = ndb.StringProperty()
	status = ndb.StringProperty(default='NEW')  # PROVISIONING, STAGING, RUNNING, STOPPING, SUSPENDING, SUSPENDED, REPAIRING, and TERMINATED
	created = ndb.DateTimeProperty()
	runs = ndb.JsonProperty()  # models it runs

	@classmethod
	@ndb_context_manager
	def create(cls, box_id, ip_address, zone, status):
		current_utc_time = datetime.datetime.utcnow()
		expiration_time = current_utc_time + datetime.timedelta(days=7)  # Expiry in 7 days

		box = cls.query(cls.box_id == box_id).get()
		if not box:
			box = cls(box_id=box_id, ip_address=ip_address, zone=zone, status=status, created=current_utc_time)
		else:
			box.ip_address = ip_address
			box.status = status

		box.put()
		return box.to_dict()

	@classmethod
	@ndb_context_manager
	def delete(cls, box_id):
		box = cls.query(cls.box_id == box_id).get()
		if box:
			box.key.delete()
			return True
		return False

	@classmethod
	@ndb_context_manager
	def get_boxes(cls):
		boxes = cls.query().fetch()
		return [box.to_dict() for box in boxes]

	@classmethod
	@ndb_context_manager
	def start_box(cls, box_id, status="START"):
		box = cls.query(cls.box_id == box_id).get()
		if box:
			box.status = status
			box.put()
			return box.to_dict()
		return None

	@classmethod
	@ndb_context_manager
	def stop_box(cls, box_id, status="STOP"):
		box = cls.query(cls.box_id == box_id).get()
		if box:
			box.status = status
			box.put()
			return box.to_dict()
		return None


class User(flask_login.UserMixin, ndb.Model):
	uid = ndb.StringProperty()  # user_id
	name = ndb.StringProperty()  # assigned name
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
	def is_active(self):  # all accounts are active
		return self.active

	def get_id(self):
		return self.uid

	def is_authenticated(self):
		return self.authenticated

	def is_anonymous(self):
		return self.anonymous

	@classmethod
	@ndb_context_manager
	def token_reset(cls, uid):
		user = cls.query(cls.uid == uid).get()
		user.api_token = generate_token()
		user.put()
		return user.to_dict()

	@classmethod
	@ndb_context_manager
	def create(cls, dbid="", db_token=""):
		name = random_name(3)
		uid = random_string(size=17)
		user = cls(
			uid=uid,
			name=name,
			created=datetime.datetime.utcnow(),
			updated=datetime.datetime.utcnow(),
			expires=datetime.datetime.utcnow() + datetime.timedelta(days=15),
			admin=False,
			dbid=dbid,
			db_token=db_token,
			api_token=generate_token()
		)
		user.put()
		return cls.query(cls.dbid == dbid).get().to_dict()

	@classmethod
	@ndb_context_manager
	def remove_by_uid(cls, uid):
		user = cls.query(cls.uid == uid).get()
		if user:
			user.key.delete()
			return True
		return False

	@classmethod
	@ndb_context_manager
	def authenticate(cls, uid):
		user = cls.query(cls.uid == uid).get()
		user.authenticated = True
		user.put()
		return user

	@classmethod
	@ndb_context_manager
	def get_by_name(cls, name):
		result = cls.query(cls.name == name).get()
		return result.to_dict() if result else None

	@classmethod
	@ndb_context_manager
	def get_by_dbid(cls, dbid):
		result = cls.query(cls.dbid == dbid).get()
		return result.to_dict() if result else None

	@classmethod
	@ndb_context_manager
	def get_by_uid(cls, uid):
		result = cls.query(cls.uid == uid).get()
		return result.to_dict() if result else None

	@classmethod
	@ndb_context_manager
	def get_by_token(cls, api_token):
		result = cls.query(cls.api_token == api_token).get()
		return result.to_dict() if result else None

