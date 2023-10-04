import os
import json
import random
from SlothAI.lib.schemar import Schemar
from datetime import datetime, timedelta

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from SlothAI.lib.gcloud import box_start
from SlothAI.web.models import Box
from SlothAI.lib.util import random_string, handle_quotes
from SlothAI.lib.schemar import string_to_datetime, datetime_to_string, FBTypes

from flask import current_app as app

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


def list_tasks(uid):
	# Set your Google Cloud Project ID
	project_id = app.config['PROJECT_ID']
	
	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Define the queue name
	queue_name = client.queue_path(project_id, "us-east1", app.config['SLOTH_QUEUE'])

	# List tasks in the specified queue
	tasks = client.list_tasks(parent=queue_name)

	_tasks = []
	# Iterate through the tasks and print task information
	for task in tasks:
		if app.config['DEV'] == "True":
			url = task.http_request.url
		else:
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

def create_task(document):

	# Set your Google Cloud Project ID
	project_id = app.config['PROJECT_ID']

	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Create a task
	parent = client.queue_path(project_id, "us-east1", app.config['SLOTH_QUEUE'])
	converted_payload = json.dumps(document).encode()

	if app.config['DEV'] == "True":
		task = {
			"http_request": {
				"url": f"{app.config['NGROK_URL']}/tasks/process/{app.config['CRON_KEY']}/{document.get('uid')}",
				"headers": {"Content-type": "application/json"},
				"http_method": tasks_v2.HttpMethod.POST
			}
		}
		task["http_request"]["body"] = converted_payload
	else:
		task = {
			"app_engine_http_request": {
				"http_method": tasks_v2.HttpMethod.POST,
				"app_engine_routing": {"version": os.environ['GAE_VERSION']},
				"relative_uri": f"/tasks/process/{app.config['CRON_KEY']}/{document.get('uid')}",
				"headers": {"Content-type": "application/json"}
			}
		}
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

def get_task_schema(document):
	'''
	Populate with schema dict
	'''
	data = document.get('data', None)
	if not data:
		document['schema'] = {}
	else:		
		try:
			document['schema'] = Schemar(data=data).infer_schema()
		except Exception as ex:
			document['schema'] = {}
			document['error'] = f"in get_task_schema: {ex}"

	return document

def retry_task(document):
	document['retries'] += 1
	if document['retries'] > 4:
		print(f"ERROR: {document['error']}. {document['retries']} total retries. dropping.")
		return
	
	print(f"ERROR: {document['error']}. {document['retries']} total retries. retrying.")
	del document['error']
	create_task(document)


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
	columns = ['_id'] + list(data.keys())

	# build insert tuple for each record
	for i, _ in enumerate(data['text']):
		record = ""
		for column in columns:
			col_type = column_type_map[column]
			if column == '_id':
				value = f"'{random_string(6)}'" if col_type == "string" else f"identifier('{table}')"
			else:
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
	