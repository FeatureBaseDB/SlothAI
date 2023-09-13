import os
import sys
import json
import random

import requests

from flask import Blueprint, render_template, flash, jsonify
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login

from lib.util import random_string
from lib.gcloud import box_status, box_start
from lib.ai import ai
from lib.database import featurebase_query, create_table
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

	# grab the document from the request
	try:
		document = json.loads(task_payload)
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

	print("done with AI crap")
	### SCHEMING WITH SCHEMER

	"""
	sql = f"select _id, sentence, keyterm, cosine_distance(select embedding from sample where sentence = '{sentence}', embedding) AS distance FROM sample ORDER BY distance ASC;"

	"""
	try:
		embedding_length = len(document.get('data').get('embedding')[0])
	except:
		embedding_length = 768

	# create table
	err = create_table(document.get('name'), f"(_id string, keyterms stringset, text string, embedding vector({embedding_length}))", {"dbid": user.get('dbid'), "db_token": user.get('db_token')})
	# TODO: unhandled error

	keyterms = document.get('data').get('keyterms', [])
	if keyterms == []:
		for _text in document.get('data').get('text'):
			keyterms.append([])

	embeddings = document.get('data').get('embedding', [])
	if embeddings == []:
		for _text in document.get('data').get('text'):
			embeddings.append([])

	values = ""

	for i, text in enumerate(document.get('data').get('text')):
		_id = random_string(6)
		try:
			values = values + f"('{_id}', {keyterms[i]}, '{text}', {embeddings[i]}),"
		except Exception as ex:
			# dump the text into the table because something went wrong
			print(ex)
			values = values + f"('{_id}', [], '{text}', []),"

	values = values.rstrip(',')
	sql = f"INSERT INTO {document.get('name')} VALUES {values};"

	document = {"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')}
	resp, err = featurebase_query(document)
	print(err)
	# TODO: unhandled error
	if err:
		return "failed to insert data", 500
	else:
		return "success", 200