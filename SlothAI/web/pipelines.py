import os
import json

from datetime import datetime

from google.cloud import ndb

from flask import Blueprint, jsonify, request
from flask import current_app as app

import flask_login
from flask_login import current_user

from werkzeug.utils import secure_filename

from SlothAI.lib.tasks import Task, TaskState
from SlothAI.web.models import Pipeline, Node, Template
from SlothAI.lib.util import random_string, upload_to_storage, deep_scrub

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


# API HANDLERS
@pipeline.route('/pipelines/<pipe_id>/download', methods=['GET'])
@flask_login.login_required
def pipelines_download(pipe_id):
    # Get the user and their tables
    username = current_user.name

    # Retrieve the pipeline by pipe_id (you need to implement your Pipeline class)
    pipeline = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)

    if pipeline is None:
        return jsonify({"error": "Pipeline not found"})

    # Retrieve nodes for the pipeline (you need to implement your Nodes class)
    node_ids = pipeline.get('node_ids')  # Assuming 'nodes' is a list of node IDs

    nodes = []
    for node_id in node_ids:
        node = Node.get(uid=current_user.uid, node_id=node_id)

        # Retrieve the template for each node
        template_id = node.get('template_id')
        template = Template.get(uid=current_user.uid, template_id=template_id)

        # Append the node and its associated template to the nodes list
        nodes.append({
            "node": node,
            "template": template,
        })

    # Create a dictionary containing pipeline information, including pipe_id
    pipeline_data = {
        "pipe_id": pipe_id,
        "name": pipeline.get('name'),
        "nodes": nodes,
    }

    deep_scrub(pipeline_data)

    # Create a JSON response
    response = jsonify(pipeline_data)

    # Set the headers to force a file download
    response.headers["Content-Disposition"] = f"attachment; filename=pipeline_{pipeline.get('name')}.json"
    response.headers["Content-Type"] = "application/json"

    return response


@pipeline.route('/pipeline', methods=['POST'])
@flask_login.login_required
def pipeline_add():
    user_id = current_user.uid
    pipelines = Pipeline.fetch(uid=user_id)

    # Make sure request is valid JSON
    if request.is_json:
        json_data = request.get_json()

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

    # start looking for uploaded files in the payload
    file_field_names = request.files.keys()

    # if we find any, we take the first one only and stick it in cloud storage
    for field_name in file_field_names:
        uploaded_file = request.files[field_name]
        filename = secure_filename(uploaded_file.filename)
        bucket_uri = upload_to_storage(current_user.uid, filename, uploaded_file)
        break

    # Check if we have a file upload
    if file_field_names:
        try:
            json_data = request.form.get('json')
            if not json_data:
                return jsonify({"error": "When using mixed mode POSTs, you must supply a 'json' key with a JSON object."}), 400
            json_data_dict = json.loads(json_data)

            if not isinstance(json_data_dict, dict):
                return jsonify({"error": "The 'json' data is not a dictionary"}), 400

            json_data_dict['filename'] = filename
            json_data_dict['content_type'] = uploaded_file.content_type
        except Exception as ex:
            return jsonify({"error": f"Error getting JSON data: {ex}"}), 400
    else:
        # If it's not a file upload, try to read JSON data
        try:
            json_data_dict = request.get_json()

            if not isinstance(json_data_dict, dict):
                return jsonify({"error": "The JSON data is not a dictionary"}), 400
        except Exception as ex:
            return jsonify({"error": f"Error getting JSON data: {ex}"}), 400


    # now we create the task
    task = Task(
        id=random_string(),
        user_id=current_user.uid,
        pipe_id=pipeline.get('pipe_id'),
        nodes=pipeline.get('node_ids'),
        document=dict(),
        created_at=datetime.utcnow(),
        retries=0,
		error=None,
		state=TaskState.RUNNING,
    )

    # store and queue
    task.document = json_data_dict
    task.create()

    return jsonify(task.to_dict()), 200

