import os
import sys
import json

import requests

from google.cloud import ndb

from flask import Blueprint, render_template, flash, jsonify
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login
from flask_login import current_user

from lib.util import random_string
from lib.gcloud import box_status
from lib.tasks import create_task, get_task_schema

from web.models import Table, Models

table = Blueprint('table', __name__)

import config

# client connection
client = ndb.Client()

# API HANDLERS
@table.route('/tables/list', methods=['GET'])
@flask_login.login_required
def tables_list():
	return None

# API INGEST
@table.route('/tables/<tid>/ingest', methods=['POST'])
@flask_login.login_required
def ingest_post(tid):
	table = Table.get_by_uid_tid(current_user.uid, tid)

	if table:
		try:
			json_data = request.get_json()
		except Exception as ex:
			return jsonify({"response": f"Check your JSON! {ex}"}), 400

		if not json_data.get('text', None):
			return jsonify({"response": "'text' field is required"}), 406 # todo get error code

		# move to data
		document = {"data": json_data}
		if 'text' in json_data: # TODO: make this configurable by the user
			text_value = json_data['text']
			if not isinstance(text_value, list):
				# If 'text' is not an array, convert it to a single-element list
				json_data['text'] = [text_value]
		else:
			return jsonify({"response": "need 'text' field..."})

		# don't create a task if there is going to be an issue converting user
		# data to a valid schema.
		document = get_task_schema(document)
		if document.get('error', None):
			return jsonify({"error": document['error']}), 400

		# this populates the model object in the document
		# map table document to document (includes uid, etc.)
		document.update(table)
		document['retries'] = 0

		# write to the job queue
		job_id = create_task(document)
		document['job_id'] = job_id

		# pop secure info
		document.pop('openai_token')
		document.pop('uid')

		return jsonify(document), 200
	else:
		return jsonify({"response": f"table with id {tid} not found"}), 404


# API DELETE
@table.route('/tables/<tid>', methods=['DELETE'])
@flask_login.login_required
def table_delete(tid):
	# find the user's table
	table = Table.get_by_uid_tid(current_user.uid, tid)

	# Prepare JSON response data
	json_data = {"response": "success", "message": "Table deleted successfully!"}

	if table:
		# delete table
		Table.delete(table.get('tid'))
		flash(f"Deleted table `{table.get('name')}`.")
		return jsonify(json_data), 200
	else:
		json_data['response'] = "error"
		json_data['message'] = "Error deleting table."
		return jsonify(json_data), 501


# API ADD
@table.route('/tables', methods=['POST'])
@flask_login.login_required
def tables_add():
	tables = Table.get_all_by_uid(uid=current_user.uid)

	# Check if the request contains JSON data
	if request.is_json:
			json_data = request.get_json()

			_models = []
			for _model in json_data.get('mids'):
				model = Models.get_by_mid(_model)
				_models.append(model)

			_table = Table.create(
				current_user.uid, 
				json_data.get('tableName'), 
				_models,
				json_data.get('openaiToken')
			)

			if _table:
				return jsonify(_table), 200
	
	return "error", 501
