from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request
from flask import current_app as app

from datetime import datetime

import flask_login
from flask_login import current_user

from SlothAI.lib.tasks import create_task, get_task_schema, Task, validate_dict_structure
from SlothAI.web.models import Pipeline, Node, Template
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
		name = json_data.get('name', None)
		nodes = json_data.get('nodes', None)

		if not name or not nodes:
			return jsonify({"error": "Invalid JSON Object", "message": "The request body must be valid JSON data and contain a 'name' and 'nodess' key."}), 400
		
		if not isinstance(nodes, list):
			return jsonify({"error": "Invalid JSON Object", "message": f"The value of the 'nodes' key must be a list of node_ids. Got: {type(nodes)}"}), 400

		# Make sure pipeline name is avaliable
		if pipelines:
			for pipeline in pipelines:
				if pipeline.get('name') == name:
					return jsonify({"error": "Invalid Pipeline Name", "message": f"A pipeline already exists with name {name}"}), 400
 
		# Make sure all nodes exist
		for node in nodes:
			node = Node.fetch(node_id=node, uid=user_id)
			if not node:
				return jsonify({"error": "Invalid Node ID", "message": f"Unable to find a node with name {node}"}), 400

		pipeline = Pipeline.create(user_id, name, nodes)
		if not pipeline:
			return jsonify({"error": "Create failed", "message": "Unable to create pipeline."}), 501
		
		return jsonify(pipeline), 200

	return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400


@pipeline.route('/pipeline/<pipe_id>', methods=['DELETE'])
@flask_login.login_required
def pipeline_delete(pipe_id):
	pipe = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)

	if pipe:
		# delete table
		Pipeline.delete_by_pipe_id(pipe.get('pipe_id'))

		return jsonify({"response": "success", "message": "Table deleted successfully!"}), 200
	else:
		return jsonify({"error": f"DELETE failed", "message": "Can't delete the pipeline."}), 501


@pipeline.route('/pipeline/<pipeline_id>/task', methods=['POST'])
@flask_login.login_required
def ingest_post(pipeline_id):
	pipeline = Pipeline.get(uid=current_user.uid, pipe_id=pipeline_id)
	if not pipeline:
		return jsonify({"response": f"pipeline with id {pipeline_id} not found"}), 404

	task = Task(
		id=random_string(),
		user_id=current_user.uid,
		pipe_id=pipeline.get('pipe_id'),
		nodes_to_visit=pipeline.get('node_ids'),
		document=dict(),
		created_at=datetime.utcnow(),
		retries=0
	)

	try:
		json_data = request.get_json()
	except Exception as ex:
		return jsonify({"error": f"issue getting request JSON data: {ex}"}), 400

	node_id = task.next_node() # initial node
	node = Node.get(uid = task.user_id, node_id = node_id)
	if not node:
		return f"response: node with id {node_id} not found", 500 
	template = Template.get(template_id=node.get('template_id'))
	if not template:
		return f"response: template with id {node.get('template_id')} not found", 500 

	task.document = json_data
	task.queue()

	return jsonify(task.to_dict()), 200

