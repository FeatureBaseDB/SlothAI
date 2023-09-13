import os
import json
import random
from datetime import datetime, timedelta

from flask import url_for

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from lib.util import random_string
from lib.gcloud import box_start
from web.models import Models, Box

import config

# Set your Google Cloud Project ID
project_id = config.project_id


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
	queue_name = client.queue_path(project_id, "us-east1", "sloth-line")

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

def create_task(document):
	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Define the target URL where the task will be sent
	target_url = f"/tasks/process/{config.cron_key}/{document.get('uid')}"

	# Create a task
	parent = client.queue_path(project_id, "us-east1", f"sloth-line")

	task = {
		"app_engine_http_request": {
			"http_method": tasks_v2.HttpMethod.POST,
			"relative_uri": target_url,
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
		future_time = datetime.utcnow() + timedelta(seconds=15)

	# Set the timestamp using the calculated future time
	timestamp.FromDatetime(future_time)

	task["schedule_time"] = timestamp

	# Send the task to the Cloud Tasks queue
	response = client.create_task(parent=parent, task=task)
	task_id = response.name.split('/')[-1]

	# return the task ID
	return task_id
