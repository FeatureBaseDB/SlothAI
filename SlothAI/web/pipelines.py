from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request
from flask import current_app as app

from datetime import datetime

import flask_login
from flask_login import current_user

from SlothAI.lib.tasks import create_task, get_task_schema, Task
from SlothAI.web.models import Pipeline, Node
from SlothAI.lib.util import random_string

pipeline = Blueprint('pipeline', __name__)

# client connection
client = ndb.Client()


# API HANDLERS
@pipeline.route('/pipelines/list', methods=['GET'])
@flask_login.login_required
def pipelines_list():
    # get the user and their tables
    username = current_user.name
    pipelines = Pipeline.fetch(uid=current_user.uid)

    return jsonify(pipelines)

@pipeline.route('/pipeline', methods=['POST'])
@flask_login.login_required
def pipeline_add():
	user_id = current_user.uid
	pipelines = Pipeline.fetch(uid=user_id)

	# Make sure request is valid JSON
	if request.is_json:
		json_data = request.get_json()
		print(json_data)

		# Make sure request JSON contains name and node_ids keys
		name = json_data.get('pipelineName', None)
		nodes = json_data.get('nodes', None)
		nodes = [node.split(" ")[0] for node in nodes]

		if not name or not nodes:
			return jsonify({"error": "Invalid JSON Object", "message": "The request body must be valid JSON data and contain a 'name' and 'nodess' key."}), 400
		
		if not isinstance(nodes, list):
			return jsonify({"error": "Invalid JSON Object", "message": f"The value of the 'node_ids' key must be a list or node ids. Got: {type(nodes)}"}), 400

		# Make sure pipeline name is avaliable
		if pipelines:
			for pipeline in pipelines:
				if pipeline.get('name') == name:
					return jsonify({"error": "Invalid Pipeline Name", "message": f"A pipeline already exists with name {name}"}), 400
 
		# Make sure all nodes exist
		for node in nodes:
			print(f"name: {node}")
			print(f"user_id: {user_id}")
			
			node = Node.fetch(name=node, uid=user_id)
			print(node)
			if not node:
				return jsonify({"error": "Invalid Node ID", "message": f"Unable to find a node with name {node}"}), 400


		pipeline = Pipeline.create(user_id, name, nodes)
		if not pipeline:
			return jsonify({"error": "Unable to create pipeline in repository"}), 501
		
		return jsonify(pipeline), 200

	return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400

@pipeline.route('/pipeline/<pipe_id>', methods=['DELETE'])
@flask_login.login_required
def pipeline_delete(pipe_id):
	pipe = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)
	if pipe:
		# delete table
		Pipeline.delete_by_pipe_id(pipe.get('pipe_id'))
		flash(f"Deleted pipeline `{pipe.get('name')}`.")
		return jsonify({"response": "success", "message": "Table deleted successfully!"}), 200
	else:
		return jsonify({"error": f"Unable to delete pipeline with id {pipe_id}"}), 501

@pipeline.route('/pipeline/<pipeline_id>/task', methods=['POST'])
@flask_login.login_required
def ingest_post(pipeline_id):
	pipeline = Pipeline.get(uid=current_user.uid, pipe_id=pipeline_id)

	task = Task(
		id=random_string(),
		user_id=current_user.uid,
		pipe_id=pipeline.get('pipe_id'),
		nodes_to_visit=pipeline.get('node_ids'),
		document=dict(),
		created_at=datetime.utcnow()
	)

	if pipeline:
		try:
			json_data = request.get_json()
		except Exception as ex:
			return jsonify({"response": f"Check your JSON! {ex}"}), 400

		if not json_data.get('text', None):
			return jsonify({"response": "'text' field is required"}), 406 # todo get error code

		# move to data
		task.document = {"data": json_data}
		if 'text' in json_data: # TODO: make this configurable by the user
			text_value = json_data['text']
			if not isinstance(text_value, list):
				# If 'text' is not an array, convert it to a single-element list
				json_data['text'] = [text_value]
		else:
			return jsonify({"response": "need 'text' field..."})


		# this populates the model object in the document
		# map table document to document (includes uid, etc.)
		task.document['retries'] = 0
		task.document['openai_token'] = app.config['OPENAI_TOKEN'] # should be a model thing not a app config thing

		# write to the job queue
		job_id = task.queue()
		task.document['job_id'] = job_id

		# pop secure info
		task.document.pop('openai_token')

		return jsonify(task.to_dict()), 200
	else:
		return jsonify({"response": f"pipeline with id {pipeline_id} not found"}), 404