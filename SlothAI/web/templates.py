import re
import ast

from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request

import flask_login
from flask_login import current_user

from SlothAI.lib.util import random_name
from SlothAI.web.models import Template, Node

template = Blueprint('template', __name__)

# check if extras arrays of dicts are same same
def are_arrays_of_dicts_equivalent(array1, array2):
    def are_dicts_equivalent(dict1, dict2):
        return sorted(dict1.items()) == sorted(dict2.items())

    array2_copy = list(array2)

    for dict2 in array2:
        dict2_copy = dict2.copy()

        for key, value in dict2.items():
            if value is None or (isinstance(value, str) and value.startswith('[') and value.endswith(']')):
                del dict2_copy[key]
                for dict1 in array1:
                    if key in dict1:
                        del dict1[key]

        dict2.clear()
        dict2.update(dict2_copy)

    if len(array1) != len(array2):
        return False

    for dict1 in array1:
        found_equivalent = False
        for dict2 in array2_copy:
            if are_dicts_equivalent(dict1, dict2):
                found_equivalent = True
                break
        if not found_equivalent:
            return False

    return True


# API HANDLERS
@template.route('/templates/list', methods=['GET'])
@flask_login.login_required
def templates_list():
    # get the user and their tables
    username = current_user.name
    api_token = current_user.api_token
    dbid = current_user.dbid
    templates = Template.fetch(uid=current_user.uid)
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

                # Initialize empty lists for input_fields and output_fields
                input_fields = []
                output_fields = []
                extras = []

                # Regular expressions to match lines defining input and output fields and extras
                input_fields_regex = re.compile(r"\s*input_fields\s*=\s*(\[.*\])")
                output_fields_regex = re.compile(r"\s*output_fields\s*=\s*(\[.*\])")
                extras_regex = re.compile(r"\s*extras\s*=\s*(\[.*\])")

                # Search for input_fields, output_fields, and extras lines and extract data
                for line in template_data.get('text').split('\n'):
                    input_match = input_fields_regex.search(line)
                    output_match = output_fields_regex.search(line)
                    extras_match = extras_regex.search(line)

                    if input_match:
                        # Extract the input_fields list as a string and then safely evaluate it as Python code
                        input_fields_str = input_match.group(1)
                        input_fields = ast.literal_eval(input_fields_str)
                    elif output_match:
                        # Extract the output_fields list as a string and then safely evaluate it as Python code
                        output_fields_str = output_match.group(1)
                        output_fields = ast.literal_eval(output_fields_str)
                    elif extras_match:
                        # Extract the extras dictionary as a string and then safely evaluate it as Python code
                        extras_str = extras_match.group(1)
                        extras = ast.literal_eval(extras_str)


                # Call the update function with the data from 'template' dictionary
                updated_template = Template.update(
                    template_id=template_id,
                    uid=current_user.uid,
                    name=template_data.get('name', template.get('name')),
                    text=template_data.get('text', template.get('text')),
                    input_fields=input_fields,
                    output_fields=output_fields,
                    extras=extras,
                    processor=template_data.get('processor', template.get('processor'))
                )

                # find the nodes using this and update the extras
                nodes = Node.fetch(template_id=template_id)

                for node in nodes:
                    print(node.get('extras'), extras)
                    if not are_arrays_of_dicts_equivalent(node.get('extras'), extras):
                        return jsonify({"error": "Update failed", "message": "Extras may not be changed while in use by a node."}), 500

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


@template.route('/templates/generate_name', methods=['GET'])
@flask_login.login_required
def generate_name():
    return jsonify({"name": random_name(2)})


@template.route('/templates', methods=['POST'])
@template.route('/templates/create', methods=['POST'])
@flask_login.login_required
def template_create():
    uid = current_user.uid

    if request.is_json:
        json_data = request.get_json()
       
        if 'template' in json_data and isinstance(json_data['template'], dict):
            template_data = json_data['template']

            # Initialize empty lists for input_fields and output_fields
            input_fields = []
            output_fields = []
            extras = []

            # Regular expressions to match lines defining input and output fields with flexible spacing
            input_fields_regex = re.compile(r"\s*input_fields\s*=\s*(\[.*\])")
            output_fields_regex = re.compile(r"\s*output_fields\s*=\s*(\[.*\])")
            extras_regex = re.compile(r"\s*extras\s*=\s*(\[.*\])")

            # Search for input_fields and output_fields lines and extract data
            for line in template_data.get('text').split('\n'):
                input_match = input_fields_regex.search(line)
                output_match = output_fields_regex.search(line)
                extras_match = extras_regex.search(line)

                try:
                    if input_match:
                        # Extract the input_fields list as a string and then safely evaluate it as Python code
                        input_fields_str = input_match.group(1)
                        input_fields = ast.literal_eval(input_fields_str)
                    elif output_match:
                        # Extract the output_fields list as a string and then safely evaluate it as Python code
                        output_fields_str = output_match.group(1)
                        output_fields = ast.literal_eval(output_fields_str)
                    elif extras_match:
                        # Extract the extras dictionary as a string and then safely evaluate it as Python code
                        extras_str = extras_match.group(1)
                        extras = ast.literal_eval(extras_str)
                except Exception as ex:
                    return jsonify({"error": f"Invalid syntax {ex}", "message": "Syntax error on input, output or extras. Check your syntax."}), 400
            
            for extra in extras:
                if extra.get('processor'):
                    processor = extra.get('processor')
                    break
            else:
                processor = template_data.get('processor', "jinja2")

            created_template = Template.create(
                name=template_data.get('name'),
                uid=uid,
                text=template_data.get('text'),
                input_fields=input_fields,
                output_fields=output_fields,
                extras=extras,
                processor=processor
            )

            if created_template:
                flash("Template created.")
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
        nodes = Node.fetch(uid=current_user.uid)

        # Check if the template is used in any node
        is_in_node = any(node.get('template_id') == template_id for node in nodes if 'template_id' in node)

        if is_in_node:
            return jsonify({"error": "Template is in use in a node.", "message": "This template cannot be deleted until it's removed from the nodes using it."}), 409

        # delete template
        result = Template.delete(template_id=template.get('template_id'))
        return jsonify({"response": "success", "message": "Template deleted successfully!"}), 200
    else:
        return jsonify({"error": f"Unable to delete template with id {template_id}"}), 501
