import os
import sys
import json
import random
import requests
import traceback

from flask import Blueprint, render_template, flash, jsonify
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login

from lib.util import random_string
from lib.gcloud import box_status, box_start
from lib.ai import ai
from lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from lib.tasks import create_task, list_tasks, box_required

from web.models import Box, User, Table, Models

tasks = Blueprint('tasks', __name__)

import config

# called from tasks in cloud tasks
@tasks.route('/tasks/process/<cron_key>/<uid>', methods=['POST'])
def process_tasks(cron_key, uid):
	# validate call with a key
	if cron_key != config.cron_key:
		return "error auth", 401

	# verify user
	user = User.get_by_uid(uid)
	if not user:
		return f"Not authenticated. Flushing request.", 200

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)

	# grab the document and data
	try:
		document = json.loads(task_payload)
		data = None
		if "data" not in document.keys():
			return 'tasks payload must contain a "data" key', 400
		data = document['data']
		if "text" not in data.keys():
			return 'tasks payload must contain a "text" key in the data object', 400
	except json.JSONDecodeError as e:
		# Handle JSON decoding error.
		return f"Error decoding JSON payload: {e}", 400
	except Exception as e:
		# Handle other exceptions that may occur during processing.
		return f"Error processing task: {e}", 500

	# check we have the table still (user could delete since ingestion)
	table = Table.get_by_uid_tid(uid, document.get('tid'))
	if not table:
		return f"Can't find the table specified. Flushing request.", 200

	# models requiring boxes get deferred
	defer, selected_box = box_required(table.get('models'))
	if defer:
		return f"Starting GPUs...", 418 # return resource starting 

	# grab the IP for locally run models and stuff it into the document
	if selected_box:
		document['ip_address'] = selected_box.get('ip_address')

	#  (੭｡╹▿╹｡)੭
	# popping ai methods called by name from document.embedding -> lib/ai.py
	for kind in ['embedding', 'keyterms']:

		model = Models.get_by_name(document.get('models').get(kind))

		if model:
			# finally, simple
			print(model)
			ai_document = ai(model.get('ai_model'), document)

			if 'error' in ai_document:
				print(f"got error in {kind}")
				print(ai_document)
				return f"{kind} error", 400
			else:
				# chaining document FTW
				document.update(ai_document)
				document.get('models').pop(kind) # pop the run model off the document
				if config.dev != "True":
					create_task(document)
					return f"finished {kind}", 200
				else:
					print(document)

	auth = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	tbl_exists, err = table_exists(document.get('name'), auth)
	if err:
		return err, 500
	if "_id" not in data.keys():
		data['_id'] = "string"
	
	ai_document = ai("chatgpt_table_schema", document)
	if "error" in document.keys():
		return document['error'], 500
	
	if not tbl_exists:
		err = create_table(document.get('name'), document['create_schema_string'], auth)
		if err:
			return err, 500
	else:
		cols, err = get_columns(document.get('name'), auth)
		if err:
			return err, 500
		
		for k,v in ai_document['create_schema_dict'].items():
			if k not in cols.keys():
				err = add_column(document.get('name'), {'name': k, 'type':v}, auth)
				if err:
					return err, 500

	values = []
	for i in range(len(data['text'])):
		value = "("
		for column in ai_document['insert_schema_list']:
			if column == "_id":
				value += f"'{random_string(6)}'"
			else:
				v = data[column][i]
				if isinstance(v, str):
					v = f"'{v}'"
				value += f"{v}"
			value += ", "
		values.append(value[:-2] + ")")

	sql = f"INSERT INTO {document.get('name')} {ai_document['insert_schema_string']} VALUES {','.join(values)};"

	_, err = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})

	if err:
		return f"failed to insert data: {err}", 500
	else:
		return "success", 200