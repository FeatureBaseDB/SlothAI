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
from lib.tasks import create_task, list_tasks

from web.models import Box, User

tasks = Blueprint('tasks', __name__)

import config

# called from tasks in cloud tasks
@tasks.route('/tasks/process/<cron_key>/<uid>', methods=['POST'])
def process_tasks(cron_key, uid):
	if cron_key != config.cron_key:
		return "error auth", 401

	# TOTO check the uid exists

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)

	# grab the document
	try:
		document = json.loads(task_payload)
	except json.JSONDecodeError as e:
		# Handle JSON decoding error.
		return f"Error decoding JSON payload: {e}", 400
	except Exception as e:
		# Handle other exceptions that may occur during processing.
		return f"Error processing task: {e}", 500

	# hardcode models requiring boxes
	box_required = False

	# test if we need to run the model (TODO make this non-hardcoded)
	if "instructor" in document.get('model') or "BERTable" in document.get('keyterm_model'):
		box_required = True

	if box_required:
		boxes = Box.get_boxes()

		# Check if there are any active boxes
		active_sloths = []
		other_boxes = []
		if boxes:
			for box in boxes:
				if box.to_dict().get('status') == 'RUNNING':
					active_sloths.append(box.to_dict())
				else:
					other_boxes.append(box.to_dict())

		if active_sloths:
			# If there are active boxes, select one at random
			selected_box = random.choice(active_sloths)
		else:
			# no boxes to run task

			# pick a random startable box
			selected_box = random.choice(other_boxes)

			# start a box
			box_start(selected_box.get('box_id'), selected_box.get('zone'))
			return "starting a box", 503 # requeue


	document['ip_address'] = selected_box.get('ip_address')

	try:
		# get the dbid's token
		user = User.get_by_uid(document.get('uid'))
		if not user:
			return "auth error", 403

		if "instructor" in document.get('model'):
			ai_document = ai("instructor", document)
			if 'error' in ai_document:
				print("got error in embedding")
				raise Exception("embedding error")
			else:
				# horrible chaining, for now
				document.update(ai_document)

		if "gpt" in document.get('keyterm_model'):
			ai_document = ai("chatgpt_extract_keyterms", document)

			document.update(ai_document)
			if 'error' in document:
				print("error in keyterm")
				raise Exception("keyterm extraction error")

	except Exception as ex:
		import traceback
		print(traceback.format_exc())
		print(ex)
		return ex, 503 # return error to requeue

	"""
	sql = f"select _id, sentence, keyterm, cosine_distance(select embedding from sample where sentence = '{sentence}', embedding) AS distance FROM sample ORDER BY distance ASC;"

	"""

	# create table
	err = create_table(document.get('name'), "(_id string, keyterms stringset, text string, embedding vector(768))", {"dbid": user.get('dbid'), "db_token": user.get('db_token')})
	# TODO: unhandled error

	keyterms = document.get('keyterms')
	embeddings = document.get('embeddings')
	values = ""

	for i, text in enumerate(document.get('text')):
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

	# TODO: unhandled error
	if err:
		return "failed to insert data", 500
	else:
		return "success", 200