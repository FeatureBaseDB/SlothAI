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


class Template(ndb.Model):
    template_id = ndb.StringProperty()
    name = ndb.StringProperty()
    uid = ndb.StringProperty()
    text = ndb.StringProperty()
    created = ndb.DateTimeProperty()

    @classmethod
    @ndb_context_manager
    def create(cls, name, uid, text):
        current_utc_time = datetime.datetime.utcnow()
        existing_template = cls.query(cls.name == name, cls.uid == uid).get()

        if not existing_template:
            template_id = random_string(13)
            template = cls(
                template_id=template_id,
                name=name,
                uid=uid,
                text=text,
                created=current_utc_time,
            )
            template.put()
            return template.to_dict()
        else:
            return template.to_dict()

    @classmethod
    @ndb_context_manager
    def fetch(cls, **kwargs):
        query_conditions = []

        if 'template_id' in kwargs:
            query_conditions.append(cls.template_id == kwargs['template_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            entities = cls.query(query).fetch()
        else:
            entities = None

        templates = []
        for entity in entities:
            templates.append(entity.to_dict())

        return templates

    @classmethod
    @ndb_context_manager
    def get(cls, **kwargs):
        query_conditions = []

        if 'template_id' in kwargs:
            query_conditions.append(cls.template_id == kwargs['template_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            template = cls.query(query).get()
 
        if query_conditions and template:
            return template.to_dict()
        else:
            return None


class Node(ndb.Model):
    node_id = ndb.StringProperty()
    name = ndb.StringProperty()
    uid = ndb.StringProperty()
    input_keys = ndb.JsonProperty()
    output_keys = ndb.JsonProperty()
    extras = ndb.JsonProperty()  # auth, flavor, service, method, template, sql, etc.
    created = ndb.DateTimeProperty()
    method = ndb.StringProperty()
    template_id = ndb.StringProperty()
    
    @classmethod
    @ndb_context_manager
    def create(cls, name, uid, extras, input_keys, output_keys, method, template_id):
        current_utc_time = datetime.datetime.utcnow()
        node = cls.query(cls.name == name, cls.uid == uid).get()

        if not node:
            if template_id:
                # ensure we have the template
                template = Template.query(Template.template_id == template_id).get()
                if not template:
                    template_id = None
            else:
                template_id = None

            node_id = random_string(13)
            node = cls(
                node_id=node_id,
                name=name,
                uid=uid,
                input_keys=input_keys,
                output_keys=output_keys,
                extras=extras,
                created=current_utc_time,
                method=method,
                template_id=template_id
            )
            node.put()

        return node.to_dict()

    @classmethod
    @ndb_context_manager
    def update(cls, node_id, name, extras, input_keys, output_keys, method, template_id):
        node = cls.query(cls.node_id == node_id).get()
        if not node:
            return None

        if template_id:
            template = Template.query(Template.template_id == template_id).get()
            if not template:
                template_id = None
        else:
            template_id = None

        node.name = name
        node.input_keys = input_keys
        node.output_keys = output_keys
        node.extras = extras
        node.method = method
        node.template_id = template_id

        node.put()

        return node.to_dict()

    @classmethod
    @ndb_context_manager
    def get(cls, **kwargs):
        query_conditions = []

        if 'node_id' in kwargs:
            query_conditions.append(cls.node_id == kwargs['node_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            node = cls.query(query).get()
        
        if query_conditions and node:
            return node.to_dict()
        else:
            return None

    @classmethod
    @ndb_context_manager
    def fetch(cls, **kwargs):
        query_conditions = []

        if 'node_id' in kwargs:
            query_conditions.append(cls.node_id == kwargs['node_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            entities = cls.query(query).fetch()
        else:
            entities = []

        nodes = []
        for entity in entities:
            _entity = entity.to_dict()
            nodes.append(_entity)
        return nodes

    @classmethod
    @ndb_context_manager
    def delete(cls, **kwargs):
        query_conditions = []

        if 'node_id' in kwargs:
            query_conditions.append(cls.node_id == kwargs['node_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            entities = cls.query(query).get()
        else:
            entities = None

        if entities:
            entities.key.delete()
            return True
        else:
            return False


class Pipeline(ndb.Model):
    pipe_id = ndb.StringProperty()
    uid = ndb.StringProperty()
    name = ndb.StringProperty()
    node_ids = ndb.JsonProperty()
    created = ndb.DateTimeProperty()

    @classmethod
    @ndb_context_manager
    def create(cls, uid, name, node_ids):
        current_utc_time = datetime.datetime.utcnow()
        pipeline = cls.query(cls.uid == uid, cls.name == name).get()

        # TODO check the node IDs are good...

        if not pipeline:
            pipe_id = random_string(13)
            pipeline = cls(
                pipe_id=pipe_id,
                uid=uid,
                name=name,
                node_ids=node_ids,
                created=current_utc_time
            )
            pipeline.put()

        return pipeline.to_dict()

    @classmethod
    @ndb_context_manager
    def get(cls, **kwargs):
        query_conditions = []

        if 'pipe_id' in kwargs:
            query_conditions.append(cls.pipe_id == kwargs['pipe_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            pipeline = cls.query(query).get()

        if query_conditions and pipeline:
            return pipeline.to_dict()
        else:
            return None

    @classmethod
    @ndb_context_manager
    def fetch(cls, **kwargs):
        query_conditions = []

        if 'pipe_id' in kwargs:
            query_conditions.append(cls.node_id == kwargs['pipe_id'])
        if 'name' in kwargs:
            query_conditions.append(cls.name == kwargs['name'])
        if 'uid' in kwargs:
            query_conditions.append(cls.uid == kwargs['uid'])

        if query_conditions:
            query = ndb.AND(*query_conditions)
            entities = cls.query(query).fetch()
        else:
            entities = None

        pipelines = []
        for entity in entities:
            _entity = entity.to_dict()
            pipelines.append(_entity)

        return pipelines

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

