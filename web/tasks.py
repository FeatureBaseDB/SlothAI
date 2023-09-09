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

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)
	
	try:
		document = json.loads(task_payload)
	except json.JSONDecodeError as e:
		# Handle JSON decoding error.
		return f"Error decoding JSON payload: {e}", 400
	except Exception as e:
		# Handle other exceptions that may occur during processing.
		return f"Error processing task: {e}", 500

	if active_sloths:
		# If there are active boxes, select one at random
		selected_box = random.choice(active_sloths)
	else:
		# no boxes to run task

		# pick a random box
		selected_box_name = random.choice(other_boxes).get('box_id')

		# start a box
		box_start(selected_box_name)
		return "starting a box", 503 # exit old task

	document['ip_address'] = selected_box.get('ip_address')
	
	try:
		# get the dbid's token
		user = User.get_by_uid(document.get('uid'))

		if "instructor" in document.get('model'):
			ai_document = ai("instructor", document)
			if 'error' in ai_document:
				raise Exception("AI error")


	except Exception as ex:
		print(ex)
		return ex, 503 # return error to requeue

	"""

	document = ai("chatgpt_complete_dict", {"text": sentence})
	print(document.get('keyterms'))
	from lib.database import featurebase_query, create_table
	auth = {"dbid": current_user.dbid, "token": current_user.db_token}
	create_table('sample', f'(_id string, keyterm stringset, sentence string, embedding vector(768))', auth)

	sql = f"INSERT INTO sample VALUES('{random_string(6)}', {document.get('keyterms')}, '{sentence}', {embeddings[0]});"
	result = featurebase_query({"sql": sql, "dbid": current_user.dbid, "token": current_user.db_token})

	sql = f"select _id, sentence, keyterm, cosine_distance(select embedding from sample where sentence = '{sentence}', embedding) AS distance FROM sample ORDER BY distance ASC;"

	result = featurebase_query({"sql": sql, "dbid": current_user.dbid, "token": current_user.db_token})
	results = result.get('results')

	# Return a response, redirect, or render a template as needed
		
	return render_template('pages/home.html', results=results)
	"""
	
	# create table
	err = create_table(document.get('name'), "(_id string, keyterms stringset, text string, embedding vector(768))", {"dbid": user.get('dbid'), "db_token": user.get('db_token')})
	# TODO: unhandled error

	values = ""
	for i, text in enumerate(ai_document.get('text')):
		_id = random_string(6)
		try:
			values = values + f"('{_id}', [], '{text}', {ai_document.get('embeddings')[i]}),"
		except Exception as ex:
			print(ex)
			values = values + f"('{_id}', [], '{text}', []),"

	values = values.rstrip(',')
	sql = f"INSERT INTO {document.get('name')} VALUES {values};"
	
	document = {"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')}
	resp, err = featurebase_query(document)
	# TODO: unhandled error

	return "success", 200