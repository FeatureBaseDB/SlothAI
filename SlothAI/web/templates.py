from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request

import flask_login
from flask_login import current_user

from SlothAI.web.models import Template, Pipeline

template = Blueprint('template', __name__)

# API HANDLERS
@template.route('/templates/list', methods=['GET'])
@flask_login.login_required
def templates_list():
    # get the user and their tables
    username = current_user.name
    api_token = current_user.api_token
    dbid = current_user.dbid
    templates = template.fetch(uid=current_user.uid)

    return jsonify(templates)


@template.route('/templates/<template_id>/detail', methods=['GET'])
@flask_login.login_required
def get_template(template_id):
    # Get the user and their tables
    username = current_user.name
    
    # Fetch the template by template_id
    template = Template.get(uid=current_user.uid, template_id=template_id)

    if template:
        return jsonify(template)
    else:
        return jsonify({"error": "Not found", "message": "The requested template was not found."}), 404


@template.route('/templates/<template_id>', methods=['POST'])
@template.route('/templates/<template_id>/update', methods=['POST'])
@flask_login.login_required
def template_update(template_id):
    template = Template.get(uid=current_user.uid, template_id=template_id)

    if template:
        if request.is_json:
            json_data = request.get_json()

            # Check if 'template' key exists in json_data and use it to update the template
            if 'template' in json_data and isinstance(json_data['template'], dict):
                template_data = json_data['template']

                # Call the update function with the data from 'template' dictionary
                updated_template = Template.update(
                    template_id=template_id,
                    uid=current_user.uid,
                    name=template_data.get('name', template.get('name')),
                    text=template_data.get('text', template.get('text'))
                )

                if updated_template:
                    return jsonify(updated_template)
                else:
                    return jsonify({"error": "Update failed", "message": "Failed to update the template."}), 500
            else:
                return jsonify({"error": "Invalid JSON", "message": "'template' key with dictionary data is required in the request JSON."}), 400
        else:
            return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400
    else:
        return jsonify({"error": "Not found", "message": "The requested template was not found."}), 404


@template.route('/templates', methods=['POST'])
@template.route('/templates/create', methods=['POST'])
@flask_login.login_required
def template_create():
    uid = current_user.uid

    if request.is_json:
        json_data = request.get_json()
       
        if 'template' in json_data and isinstance(json_data['template'], dict):
            template_data = json_data['template']

            created_template = Template.create(
                name=template_data.get('name'),
                uid=uid,
                text=template_data.get('text')
            )

            if created_template:
                return jsonify(created_template), 201
            else:
                return jsonify({"error": "Creation failed", "message": "Failed to create the template."}), 500
        else:
            return jsonify({"error": "Invalid JSON", "message": "'template' key with dictionary data is required in the request JSON."}), 400
    else:
        return jsonify({"error": "Invalid JSON", "message": "The request body must be valid JSON data."}), 400



@template.route('/templates/<template_id>', methods=['DELETE'])
@template.route('/templates/<template_id>/delete', methods=['DELETE'])
@flask_login.login_required
def template_delete(template_id):
    template = Template.get(uid=current_user.uid, template_id=template_id)
    if template:
        # fetch all nodes
        nodes = Pipeline.fetch(uid=current_user.uid)

        # Check if the node is in any pipeline
        is_in_node = any(template_id in node.get('node_id', None) for node in nodes)

        if is_in_node:
            return jsonify({"error": "Template is in use in a node.", "message": "This template cannot be deleted until it's removed from the node."}), 400

        # delete table
        Template.delete(template_id=template.get('template_id'))
        flash(f"Deleted template `{template.get('name')}`.")
        return jsonify({"response": "success", "message": "Template deleted successfully!"}), 200
    else:
        return jsonify({"error": f"Unable to delete template with id {template_id}"}), 501