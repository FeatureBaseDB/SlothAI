import sys
import json
import random
from datetime import datetime, timedelta

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from lib.util import random_string
from lib.gcloud import box_start
from web.models import Models, Box, User, Table
from web.kafka import Kafka
import enum

import config

from lib.database import featurebase_query, table_exists

# Set your Google Cloud Project ID
project_id = config.project_id

class TaskStatus(enum.Enum):
	CREATING = "creating"
	RUNNING = "running"
	COMPLETE = "complete"
	FAILED = "failed"

class Task:

	def __init__(self, data, pipeline, user):
		self.data = data
		self.pipeline = pipeline
		self.user = user
		self.status = TaskStatus.CREATING
		self.retries = 0
		self.id = ""

	def _get_id(self):
		return self.__id
	
	def _set_data(self, value):
		if not isinstance(value, str):
			raise TypeError("id must be set to a str")
		self.__id = value
	
	def _get_data(self):
		return self.__data
	
	def _set_data(self, value):
		if not isinstance(value, dict):
			raise TypeError("data must be set to a dict")
		self.__data = value

	def _get_pipeline(self):
		return self.__pipeline
	
	def _set_pipeline(self, value):
		if not isinstance(value, Pipeline):
			raise TypeError("user must be set to a Pipeline")
		self.__pipeline = value

	def _get_user(self):
		return self.__user
	
	def _set_user(self, value):
		if not isinstance(value, User):
			raise TypeError("user must be set to a Pipeline")
		self.__user = value

	def _get_status(self):
		return self.__status
	
	def _set_status(self, value):
		if not isinstance(value, TaskStatus):
			raise TypeError("status must be set to a TaskStatus")
		self.__status = value

	def _get_retries(self):
		return self.__status
	
	def _set_retries(self, value):
		if not isinstance(value, int):
			raise TypeError("retries must be set to a int")
		self.__status = value

	data = property(_get_data, _set_data)
	pipeline = property(_get_pipeline, _set_pipeline)
	user = property(_get_user, _set_user)
	status = property(_get_status, _set_status)
	retries = property(_get_retries, _set_retries)

	def to_dict(self):
		return {
            "data": self.data,
            "pipeline": self.pipeline.to_dict(),
            "user": self.user.to_dict(),
            "status": str(self.status),
            "retries": self.retries,
            "id": self.id,
        }

class Model:

	def __init__(self, type, name):
		self.type = type
		self.name = name

	def _get_type(self):
		return self.__type

	def _set_type(self, value):
		if not isinstance(value, str):
			raise TypeError("type must be set to a str")
		self.__type = value

	def _get_name(self):
		return self.__name
	
	def _set_name(self, value):
		if not isinstance(value, str):
			raise TypeError("name must be set to a str")
		self.__id = value

	id = property(_get_type, _set_type)
	name = property(_get_name, _set_name)

	def to_dict(self):
		return {
            "id": self.id,
            "name": self.name,
        }

class Pipeline:

	def __init__(self, name, id, models, openai_token):
		self.name = name
		self.id = id
		self.models = models
		self.openai_token = openai_token

	def _get_name(self):
		return self.__name

	def _set_name(self, value):
		if not isinstance(value, str):
			raise TypeError("name must be set to a dict")
		self.__name = value

	def _get_id(self):
		return self.__id
	
	def _set_id(self, value):
		if not isinstance(value, str):
			raise TypeError("id must be set to a dict")
		self.__id = value

	def _get_models(self):
		return self.__models
	
	def _set_models(self, value):
		typeErr = TypeError("models must be set to a list of Models")
		if not isinstance(value, list):
			raise typeErr
		for el in value:
			if not isinstance(el, Model):
				raise typeErr
		self.__models = value

	def _get_openai_token(self):
		return self.__openai_token
	
	def _set_openai_token(self, value):
		if not isinstance(value, str):
			raise TypeError("id must be set to a dict")
		self.__openai_token = value

	id = property(_get_id, _set_id)
	name = property(_get_name, _set_name)
	models = property(_get_models, _set_models)
	openai_token = property(_get_openai_token, _set_openai_token)

	def to_dict(self):
		models = []
		for m in self.models:
			models.append(m.to_dict())

		return {
            "id": self.id,
            "name": self.name,
            "models": self.models.to_dict(),
            "openai_token": self.openai_token,
        }

class User:

	def __init__(self, name, id):
		self.name = name
		self.id = id

	def _get_id(self):
		return self.__id
	
	def _set_id(self, value):
		if not isinstance(value, str):
			raise TypeError("id must be set to a dict")
		self.__id = value

	def _get_name(self):
		return self.__name

	def _set_name(self, value):
		if not isinstance(value, str):
			raise TypeError("name must be set to a dict")
		self.__name = value

	id = property(_get_id, _set_id)
	name = property(_get_name, _set_name)


	def to_dict(self):
		return {
            "id": self.id,
            "name": self.name,
            "models": self.models.to_dict(),
            "openai_token": self.openai_token,
        }


def delete_task(name):
	# don't forget to add a delete task button in the UI!
	pass

# probaby not the best place for this, so welcome to agile!
def box_required(pipeline_models):
	# get all boxes
	boxes = Box.get_boxes() # change this to use the Box model TODO

	_box_required = False

	# get the models in the pipeline
	for kind in ["embedding", "keyterms"]:
		# get the model name by the pipeline kind (we only do two kinds right now)
		_model = Models.get_by_name(pipeline_models.get(kind))

		if _model.get('gpu') == "t4":
			active_t4s = []
			other_t4s = []
			if boxes:
				for box in boxes:
					if box.get('status') == 'RUNNING':
						active_t4s.append(box)
					else:
						other_t4s.append(box)

			if active_t4s:
				# If there are active boxes, select one at random
				selected_box = random.choice(active_t4s)
				_box_required = False
				break
			else:
				# pick a random startable box
				alternate_box = random.choice(other_t4s)

				# start a box
				box_start(alternate_box.get('box_id'), alternate_box.get('zone'))
				selected_box = None
				_box_required = True
	else:
		selected_box = None

	return _box_required, selected_box

def list_tasks(uid):
	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Define the queue name
	queue_name = client.queue_path(project_id, "us-east1", config.sloth_queue)

	# List tasks in the specified queue
	tasks = client.list_tasks(parent=queue_name)

	_tasks = []
	# Iterate through the tasks and print task information
	for task in tasks:
		url = task.app_engine_http_request.relative_uri
		task_uid = url.split('/')[-1]
		
		_task = {
			"name": task.name.split('/')[-1],
			"dispatch_count": task.dispatch_count,
			"schedule_time": task.schedule_time.strftime("%d/%m/%Y %H:%M:%SZ"),
			"log": task.last_attempt.response_status.message
		}
		if uid == task_uid:
			_tasks.append(_task)
			
	return _tasks

# Optional per-message delivery callback (triggered by poll() or flush())
# when a message has been successfully delivered or permanently
# failed delivery (after retries).
def delivery_callback(err, msg):
	msg_str = f"key: {msg.key()}" # , value: {msg.value()}"
	if err:
		try:
			doc = json.loads(msg.value())
			create_task(doc)
			sys.stderr.write(f"ERROR: task delivery failed: {msg_str}: {err}: requeuing\n")
		except Exception as e:
			sys.stderr.write(f"ERROR: task delivery failed: {msg_str}: {err}: {e}: killing task\n")
	else:
		sys.stderr.write(f"INFO: task delivered to kafka queue successfully: {msg_str}\n")

def create_task(document):
	if not isinstance(document['task'], Task):
		return 0
	# user = User.get_by_uid(document.get('uid', None))
	# if not user:
	# 	document['error'] = "user not found"
	# 	return

	# table = Table.get_by_uid_tid(document.get('uid', None), document.get('tid', None))
	# if not table:
	# 	document['error'] = "table not found"
	# 	return

	if hasattr(config, 'task_queue') and config.task_queue == "kafka":
		task_id =  create_task_kafka(document)
	else:
		task_id = create_task_appengine(document)

	# if table_exists(config.task_store, {'dbid'})
	# featurebase_query({
	# 	'sql': f'INSERT INTO {config.task_store} VALUES'
	# })
	

def create_dead_letter(document):
	if hasattr(config, 'task_queue') and config.task_queue == "kafka":
		return create_dead_letter_kafka(document)
	else:
		return create_dead_letter_appengine(document)

def create_task_kafka(document):
	return send_message_kafka(document, queue=Kafka().task_topic)

def create_task_appengine(document):
	return send_message_appengine(document, queue=config.sloth_queue, target=f"/tasks/process/{config.cron_key}/{document.get('uid')}")

def create_dead_letter_kafka(document):
	return send_message_kafka(document, queue=Kafka().dead_letter_topic)

def create_dead_letter_appengine(document):
	return send_message_appengine(document, queue=config.sloth_queue + "-dlq", target=f"/tasks/dead-letter/{config.cron_key}/{document.get('uid')}")

def send_message_kafka(document, queue):
	k = Kafka() # get singleton obj
	doc_task_id = document.get('task_id', None)
	task_id = random_string(16) if not doc_task_id else doc_task_id
	document['task_id'] = task_id
	p = k.getProducer()
	doc = json.dumps(document).encode()
	p.produce(queue, value=doc, key=task_id, callback=delivery_callback)
	p.flush()
	# producer is garbage collected when out of scope
	return task_id

def send_message_appengine(document, queue, target):
	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Create a task
	parent = client.queue_path(project_id, "us-east1", queue)

	task = {
		"app_engine_http_request": {
			"http_method": tasks_v2.HttpMethod.POST,
			"relative_uri": target,
			"headers": {"Content-type": "application/json"}
		}
	}

	# add the document
	converted_payload = json.dumps(document).encode()
	task["app_engine_http_request"]["body"] = converted_payload

	# Create a timestamp
	timestamp = timestamp_pb2.Timestamp()

	# Calculate the time 15 seconds from now
	if document.get('run_in', None):
		future_time = datetime.utcnow() + timedelta(seconds=int(document.get('run_in')))
	else:
		delay = random.randint(500, 3000)
		future_time = datetime.utcnow() + timedelta(milliseconds=delay)

	# Set the timestamp using the calculated future time
	timestamp.FromDatetime(future_time)

	task["schedule_time"] = timestamp

	# Send the task to the Cloud Tasks queue
	response = client.create_task(parent=parent, task=task)
	task_id = response.name.split('/')[-1] if not document.get('task_id', None) else document['task_id']

	# return the task ID
	return task_id