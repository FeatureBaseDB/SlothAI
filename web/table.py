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
from lib.tasks import create_task

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
		json_data = request.get_json()
		
		if not json_data.get('text', None):
			return jsonify({"response": "'text' field is required"}), 406 # todo get error code

		# converts string to list of strings
		if not isinstance(json_data.get('text', None), list):
			json_data['text'] = [json_data.get('text', None)]

		# move to data
		document = {"data": json_data}

		# map table document to document (includes uid, etc.)
		document.update(table)

		# write to the job queue
		job_id = create_task(document)
		document['job_id'] = job_id

		# pop secure info
		document.pop('openai_token')
		document.pop('uid')

		return jsonify(document), 200
	else:
		return jsonify({"response": "not found"}), 404


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

			models = {"embedding": json_data.get('embeddingModel'),"keyterms": json_data.get('keytermModel')}

			_table = Table.create(
				current_user.uid, 
				json_data.get('tableName'), 
				models,
				json_data.get('openaiToken')
			)
		
			if _table:
				return jsonify(_table), 200
	
	return "error", 501
