from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request

import flask_login
from flask_login import current_user

from SlothAI.web.models import Node, Pipeline

node = Blueprint('node', __name__)

# API HANDLERS
@node.route('/nodes/list', methods=['GET'])
@flask_login.login_required
def nodes_list():
    # get the user and their tables
    username = current_user.name
    api_token = current_user.api_token
    dbid = current_user.dbid
    nodes = Node.fetch(uid=current_user.uid)

    return jsonify(nodes)


@node.route('/nodes/<node_id>/detail', methods=['GET'])
@flask_login.login_required
def get_node(node_id):
    # Get the user and their tables
    username = current_user.name
    
    # Fetch the node by node_id
    node = Node.get(uid=current_user.uid, node_id=node_id)

    if node:
        return jsonify(node)
    else:
        return jsonify({"error": "Not found", "message": "The requested node was not found."}), 404


@node.route('/nodes/<node_id>', methods=['POST'])
@node.route('/nodes/<node_id>/update', methods=['POST'])
@flask_login.login_required
def node_update(node_id):
    user_id = current_user.uid
    node = Node.get(uid=current_user.uid, node_id=node_id)

    if node:
        if request.is_json:
            json_data = request.get_json()

            # Check if 'node' key exists in json_data and use it to update the node
            if 'node' in json_data and isinstance(json_data['node'], dict):
                node_data = json_data['node']


                # Call the update function with the data from 'node' dictionary
                updated_node = Node.update(
                    node_id=node_id,
                    name=node_data.get('name', node.get('name')),
                    extras=node_data.get('extras', node.get('extras')),
                    input_keys=node_data.get('input_keys', node.get('input_keys')),
                    output_keys=node_data.get('output_keys', node.get('output_keys')),
                    method=node_data.get('method', node.get('method')),
                    template_id=node_data.get('template_id', node.get('template_id'))
                )

                if updated_node:
                    return jsonify(updated_node)
                else:
                    return jsonify({"error": "Update failed", "message": "Failed to update the node."}), 500
            else:
                return jsonify({"error": "Invalid JSON", "message": "'node' key with dictionary data is required in the request JSON."}), 400
        else:
            return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400
    else:
        return jsonify({"error": "Not found", "message": "The requested node was not found."}), 404


@node.route('/nodes', methods=['POST'])
@node.route('/nodes/create', methods=['POST'])
@flask_login.login_required
def node_create():
    uid = current_user.uid

    if request.is_json:
        json_data = request.get_json()
       
        if 'node' in json_data and isinstance(json_data['node'], dict):
            node_data = json_data['node']

            created_node = Node.create(
                name=node_data.get('name'),
                uid=uid,
                extras=node_data.get('extras'),
                input_keys=node_data.get('input_keys'),
                output_keys=node_data.get('output_keys'),
                method=node_data.get('method'),
                template_id=node_data.get('template_id')
            )

            if created_node:
                return jsonify(created_node), 201
            else:
                return jsonify({"error": "Creation failed", "message": "Failed to create the node."}), 500
        else:
            return jsonify({"error": "Invalid JSON", "message": "'node' key with dictionary data is required in the request JSON."}), 400
    else:
        return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400


@node.route('/nodes/<node_id>', methods=['DELETE'])
@node.route('/nodes/<node_id>/delete', methods=['DELETE'])
@flask_login.login_required
def node_delete(node_id):
    node = Node.get(uid=current_user.uid, node_id=node_id)
    if node:
        # Fetch all pipelines
        pipelines = Pipeline.fetch(uid=current_user.uid)

        # Check if the node is in any pipeline
        is_in_pipeline = any(node_id in pipeline.get('node_ids', []) for pipeline in pipelines)

        if is_in_pipeline:
            return jsonify({"error": "Node is in a pipeline", "message": "This node cannot be deleted until it's removed from the pipeline."}), 400

        # If the node is not in any pipeline, proceed with deletion
        Node.delete(node_id=node.get('node_id'))
        flash(f"Deleted node `{node.get('name')}`.")
        return jsonify({"response": "success", "message": "Node deleted successfully!"}), 200
    else:
        return jsonify({"error": f"Unable to delete node with id {node_id}"}), 501
