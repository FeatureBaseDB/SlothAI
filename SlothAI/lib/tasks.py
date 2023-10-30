import os
import json
import random
from SlothAI.lib.schemar import Schemar
from datetime import datetime, timedelta

from ping3 import ping
from SlothAI.lib.util import check_webserver_connection

from typing import List, Tuple, Dict

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from SlothAI.lib.gcloud import box_start
from SlothAI.web.models import Box
from SlothAI.web.models import Task as TaskModel
from SlothAI.lib.util import random_string, handle_quotes
from SlothAI.lib.schemar import string_to_datetime, datetime_to_string, FBTypes

from flask import current_app as app

from enum import Enum

class TaskState(Enum):
	RUNNING = 'running'
	COMPLETED = 'completed'
	FAILDED = 'failed'

	@classmethod
	def state_from_string(self, state_as_string):
		if state_as_string == "running":
			return self.RUNNING
		elif state_as_string == "complete":
			return self.COMPLETED
		elif state_as_string == "failed":
			return self.FAILDED
		else:
			raise Exception("invalid state_as_string")

class Task:
	def __init__(self, id: str, user_id: str, pipe_id: str, nodes: List[str], document: dict, created_at: datetime, retries: int, error: str, state: TaskState):
		self.id = id
		self.user_id = user_id
		self.pipe_id = pipe_id
		self.nodes = nodes
		self.document = document
		self._created_at = created_at
		self.retries = retries
		self.error = error
		self.state = state

	@property
	def created_at(self):
		return self._created_at

	def to_dict(self) -> dict:
		"""
		Convert a Task object to a dictionary.
		"""
		return {
			"id": self.id,
			"user_id": self.user_id,
			"pipe_id": self.pipe_id,
			"nodes": self.nodes,
			"document": self.document,
			"created_at": self.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
			"retries": self.retries,
			"error": self.error,
			"state": self.state.value,
		}

	@classmethod
	def from_dict(cls, task_dict: dict) -> 'Task':
		"""
		Create a Task object from a dictionary.
		"""
		return cls(
			id=task_dict["id"],
			user_id=task_dict["user_id"],
			pipe_id=task_dict["pipe_id"],
			nodes=task_dict["nodes"],
			document=task_dict["document"],
			created_at= datetime.strptime(task_dict["created_at"], '%Y-%m-%dT%H:%M:%SZ'),
			retries=task_dict['retries'],
			error=task_dict['error'],
			state=TaskState.state_from_string(task_dict['state']),
		)

	def to_json(self) -> str:
		"""
		Convert a Task object to a JSON string.
		"""
		task_dict = self.to_dict()
		return json.dumps(task_dict, indent=4)

	@classmethod
	def from_json(cls, json_str: str) -> 'Task':
		"""
		Create a Task object from a JSON string.
		"""
		task_dict = json.loads(json_str)
		return cls.from_dict(task_dict)

	def queue(self):
		project_id = app.config['PROJECT_ID']
		client = tasks_v2.CloudTasksClient()
		queue = client.queue_path(project_id, "us-east1", app.config['SLOTH_QUEUE'])
		encoding = self.to_json().encode()

		if app.config['DEV'] == "True":
			task = {
				"http_request": {
					"url": f"{app.config['NGROK_URL']}/tasks/process/{app.config['CRON_KEY']}",
					"headers": {"Content-type": "application/json"},
					"http_method": tasks_v2.HttpMethod.POST
				}
			}
			task["http_request"]["body"] = encoding
		else:
			task = {
				"app_engine_http_request": {
					"http_method": tasks_v2.HttpMethod.POST,
					"app_engine_routing": {"version": os.environ['GAE_VERSION']},
					"relative_uri": f"/tasks/process/{app.config['CRON_KEY']}",
					"headers": {"Content-type": "application/json"}
				}
			}
			task["app_engine_http_request"]["body"] = encoding


		# Create a timestamp
		timestamp = timestamp_pb2.Timestamp()

		# Calculate the time 15 seconds from now
		if self.document.get('run_in', None):
			future_time = datetime.utcnow() + timedelta(seconds=int(self.document.get('run_in')))
		else:
			delay = random.randint(500, 3000)
			future_time = datetime.utcnow() + timedelta(milliseconds=delay)

		# Set the timestamp using the calculated future time
		timestamp.FromDatetime(future_time)

		task["schedule_time"] = timestamp

		# Send the task to the Cloud Tasks queue
		response = client.create_task(parent=queue, task=task)

		# self.id = response.name.split('/')[-1]

		# todo so error handling
		_ = self.update_store(
			state=self.state,
			retries=self.retries,
			error=self.error,
			current_node_id=self.next_node()
		)


	def next_node(self):
		if len(self.nodes) == 0:
			return None
		return self.nodes[0]
	
	def remove_node(self):
		if len(self.nodes) > 1:
			node = self.nodes[0]
			self.nodes = self.nodes[1:]
			return node
		else:
			node = self.nodes[0]
			self.nodes = []
			return node

	def retry(self):
		if self.retriable():
			self.retries += 1
			self.queue()
			return True
		else:
			self.drop()

	def drop(self):
		self.update_store(error=self.error, retries=self.retries, current_node_id=self.next_node(), state=TaskState.FAILDED)

	def retriable(self):
		if self.retries >= 5:
			return False
		return True

	def store(self):
		task = TaskModel.create(
			task_id=self.id,
			user_id=self.user_id,
			current_node_id=self.next_node(),
			pipe_id=self.pipe_id,
			created_at=self._created_at,
			state=self.state,
			error=self.error,
			retries=self.retries,
		)

		return task

	def update_store(self, state=None, retries=None, error=None, current_node_id=None):
		update_args = {}

		if state is not None:
			update_args['state'] = state
		if retries is not None:
			update_args['retries'] = retries
		if error is not None:
			update_args['error'] = error
		if current_node_id is not None:
			update_args['current_node_id'] = current_node_id

		task = TaskModel.update(self.id, **update_args)

		return task

	@classmethod
	def tasks_by_user(self, user_id):
		return TaskModel.fetch(user_id=user_id)

	def create(self):
		self.store()
		self.queue()

def delete_task(name):
	# don't forget to add a delete task button in the UI!
	pass

# probaby not the best place for this, so welcome to agile!
def box_required(pipeline_models):
	from ping3 import ping
	from SlothAI.lib.util import check_webserver_connection

	# get all boxes
	boxes = Box.get_boxes() # change this to use the Box model TODO

	_box_required = False

	# get the models in the pipeline
	for model in pipeline_models:
		# get the model name by the pipeline kind (we only do two kinds right now)
		_model = Models.get_by_name(model['name'])

		if _model.get('gpu') == "t4":
			active_t4s = []
			halted_t4s = []
			if boxes:
				for box in boxes:
					# if the box is START, PROVISIONING, STAGING, RUNNING
					if box.get('status') == "RUNNING" or box.get('status') == "START" or box.get('status') == "PROVISIONING" or box.get('status') == "STAGING":
						# can we ping it?
						response_time = ping(box.get('ip_address'), timeout=2.0)  # Set a 2-second timeout

						if response_time and check_webserver_connection(box.get('ip_address'), 9898):
							print("pinging", box.get('ip_address'), response_time, box.get('status'))
							# ping worked and the server responded
							active_t4s.append(box)
						else:
							print("box is not running")
							halted_t4s.append(box)
					else:
						# box wasn't RUNNING or at START
						halted_t4s.append(box)

			if active_t4s:
				# If there are active boxes, select one at random
				selected_box = random.choice(active_t4s)
				_box_required = False
				break
			else:
				# pick a random startable box
				alternate_box = random.choice(halted_t4s)

				# start the box and set the new status
				if box.get('status') != "START":
					print("starting box ", box.get('box_id'))
					box_start(alternate_box.get('box_id'), alternate_box.get('zone'))
					Box.start_box(alternate_box.get('box_id'), "START") # sets status to 'START'
				
				selected_box = None
				_box_required = True
				
				# return to ensure we don't start multiple boxes
				break

	else:
		selected_box = None

	return _box_required, selected_box

def get_task_schema(data: Dict[str, any]) -> Tuple[Dict[str, str], str]:
	'''
	Populate with schema dict
	'''

	if not data:
		return dict(), None

	try:
		schema = Schemar(data=data).infer_schema()
	except Exception as ex:
		return dict(), f"in get_task_schema: {ex}"

	return schema, None

def get_values_by_json_paths(json_paths, document):
    results = {}
    
    for json_path in json_paths:
        path_components = json_path.split('.')
        current_location = document
        
        for key in path_components:
            if key in current_location:
                current_location = current_location[key]
            else:
                # If a key is not found, skip this path
                break
        else:
            # This block executes if the loop completed without a 'break'
            results[path_components[-1]] = current_location
    
    return results

def process_data_dict_for_insert(data, column_type_map, table):
	"""
	Process data from a dictionary for insertion into a database table.

	This function takes data in the form of a dictionary, a mapping of column types,
	and the target table name. It generates records suitable for insertion into
	the specified table and returns the list of columns and records.

	Parameters:
	- data (dict): A dictionary containing data to be inserted into the table.
	- column_type_map (dict): A dictionary mapping column names to their data types.
	- table (str): The name of the target database table.

	Returns:
	- columns (list): A list of column names including '_id'.
	- records (list): A list of records, each formatted as a tuple for insertion.

	Example:
	data = {
		'text': ['Record 1', 'Record 2'],
		'value': [42, 57]
	}
	column_type_map = {
		'_id': 'string',
		'text': 'string',
		'value': 'int'
	}
	table = 'my_table'
	columns, records = process_data_dict_for_insert(data, column_type_map, table)
	# columns = ['_id', 'text', 'value']
	# records = ["('abc123','Record 1',42)", "('def456','Record 2',57)"]
	"""
    
	records = []
	columns = list(data.keys())

	if "_id" not in columns:
		columns = ["_id"] + columns

	# build insert tuple for each record
	for i, _ in enumerate(data[list(data.keys())[0]]):
		record = ""
		for column in columns:
			col_type = column_type_map[column]
			if column == '_id':
				if column not in list(data.keys()):
					record += f"'{random_string(6)}'," if col_type == "string" else f"identifier('{table}'),"
					continue
			value = data[column][i]
			if FBTypes.TIMESTAMP in col_type:
				value = f"'{datetime_to_string(string_to_datetime(value))}'"
			if col_type == FBTypes.STRING:
				value = f"'{handle_quotes(value)}'"
			if col_type == FBTypes.STRINGSET:
				value = "['" + "','".join(handle_quotes(value)) + "']"	
			record += f"{value},"
		records.append(f"({record[:-1]})")

	return columns, records


def validate_dict_structure(keys_list, input_dict):
    for key in keys_list:
        keys = key.get('name').split('.')
        current_dict = input_dict

        for k in keys:
            if k not in current_dict:
                return key
            current_dict = current_dict[k]

    return None


def transform_data(output_keys, data):
    out = {}

    if len(output_keys) == 1 and output_keys[0] == 'data':
        # Special case: If the output key is 'data', wrap the data in a single key
        out['data'] = data
    else:
        for key_name in output_keys:
            if key_name in data:
                out[key_name] = data[key_name]
            else:
                raise KeyError(f"Key not found: {key_name}")

    return out


def box_required():
	box_required = False
	selected_box = None

	boxes = Box.get_boxes()
	active_t4s = []
	halted_t4s = []
	if boxes:
		for box in boxes:
			# if the box is START, PROVISIONING, STAGING, RUNNING
			if box.get('status') == "RUNNING" or box.get('status') == "START" or box.get('status') == "PROVISIONING" or box.get('status') == "STAGING":
				# can we ping it?
				response_time = ping(box.get('ip_address'), timeout=2.0)  # Set a 2-second timeout

				if response_time and check_webserver_connection(box.get('ip_address'), 9898):
					print("pinging", box.get('ip_address'), response_time, box.get('status'))
					# ping worked and the server responded
					active_t4s.append(box)
				else:
					print("box is not running")
					halted_t4s.append(box)
			else:
				# box wasn't RUNNING or at START
				halted_t4s.append(box)

	if active_t4s:
		# If there are active boxes, select one at random
		selected_box = random.choice(active_t4s)
		box_required = False
	else:
		# pick a random startable box
		alternate_box = random.choice(halted_t4s)

		# start the box and set the new status
		if box.get('status') != "START":
			print("starting box ", box.get('box_id'))
			box_start(alternate_box.get('box_id'), alternate_box.get('zone'))
			Box.start_box(alternate_box.get('box_id'), "START") # sets status to 'START'
		
		selected_box = None
		box_required = True

	return box_required, selected_box


class RetriableError(Exception):
	def __init__(self, message):
		super().__init__(message)
class NonRetriableError(Exception):
	def __init__(self, message):
		super().__init__(message)
class ResourceNotFoundError(NonRetriableError):
	def __init__(self, message):
		super().__init__(message)
class PipelineNotFoundError(ResourceNotFoundError):
	def __init__(self, pipeline_id):
		super().__init__(f"pipeline with id {pipeline_id} not found.")
class UserNotFoundError(ResourceNotFoundError):
	def __init__(self, user_id):
		super().__init__(f"user with id {user_id} not found.")

class NodeNotFoundError(ResourceNotFoundError):
	def __init__(self, node_id):
		super().__init__(f"node with id {node_id} not found")

class TemplateNotFoundError(ResourceNotFoundError):
	def __init__(self, template_id):
		super().__init__(f"node with id {template_id} not found")

class MissingFieldError(NonRetriableError):
	def __init__(self, message):
		super().__init__(message)
class MissingInputFieldError(MissingFieldError):
	def __init__(self, field, node):
		super.__init__(f"task document is missing required input field {field} for node {node}")

class MissingOutputFieldError(MissingFieldError):
	def __init__(self, field, node):
		super.__init__(f"task document is missing required output field {field} for node {node}")
