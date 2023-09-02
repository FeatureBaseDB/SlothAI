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

from web.models import Table, Jobs

table = Blueprint('table', __name__)

import config

# client connection
client = ndb.Client()

@table.route('/tables/list', methods=['GET'])
@flask_login.login_required
def table_list():
	return None

@table.route('/ingest/<tid>', methods=['POST'])
@flask_login.login_required
def ingest_post(tid):
	table = Table.get_by_uid_tid(current_user.uid, tid)
	print(table)
	if table:
		# test document size is greater than 1MB (todo)
		json_data = request.get_json()

		document = {"text": json_data.get('text'), "table": table.get('tid')}

		# write to the job queue
		job = Jobs.create(current_user.uid, document)

		return jsonify(json_data), 200
	else:
		return jsonify({"response": "error"}), 501
	

@table.route('/tables', methods=['GET'])
@flask_login.login_required
def tables():
	# get the user and their tables
	username = current_user.name
	tables = Table.get_all_by_uid(uid=current_user.uid)
	_tables = []
	with client.context():
		for table in tables:
			_tables.append(table)

	return render_template('pages/tables.html', username=username, tables=_tables)


@table.route('/tables', methods=['POST'])
@flask_login.login_required
def tables_post():
	username = current_user.name
	tables = Table.get_all_by_uid(uid=current_user.uid)

	# Check if the request contains JSON data
	if request.is_json:
			json_data = request.get_json()

			if 'yes' in json_data.get('keyTermsOptions'):
				extract = True
			else:
				extract = False

			_table = Table.create(current_user.uid, json_data.get('tableName'), json_data.get('modelSelect'), extract, json_data.get('openaiToken'))
			
			with client.context():
				print(_table)
			# Process the JSON data as needed
			print("Received JSON data:", json_data)
			flash("got data")
			return jsonify(json_data), 200
	else:
		return "error", 501
