import os
import json
from datetime import datetime, timedelta

from flask import url_for

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

import config

# Set your Google Cloud Project ID
project_id = config.project_id

def delete_task(name):
	pass

def create_task(document):
	# Create a Cloud Tasks client
	client = tasks_v2.CloudTasksClient()

	# Define the target URL where the task will be sent
	target_url = f"/tasks/process/{config.cron_key}"

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
