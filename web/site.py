import os
import sys
import json

import requests

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login
from flask_login import current_user

from lib.util import random_string
from lib.ai import ai


site = Blueprint('site', __name__)

import config

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')

# main route
@site.route('/', methods=['GET'])
@flask_login.login_required
def index():
	return render_template(
		'pages/home.html'
	)


@site.route('/api/<zone>/<instance_name>/status', methods=['GET'])
def box_status(zone, instance_name):
    url = f"http://{config.sloth_controller_username}:{config.sloth_token}@{config.sloth_controller_ip}:8787/api/instance/{zone}/{instance_name}/status?token={config.sloth_token}"

    response = requests.get(url)

    # Print the status code
    print("Status Code:", response.status_code)

    if 400 <= response.status_code < 500:
        error_response = {'error': 'Client error'}
        return json.dumps(error_response), response.status_code

    return response.json()

if __name__ == "__main__":
    app.run()



@site.route('/dash', methods=['GET'])
@flask_login.login_required
def dash():
	username = current_user.name
	return render_template('pages/tables.html', username=username)


@site.route('/tables', methods=['POST'])
@flask_login.login_required
def index_post():
	import requests
	import json

	# needs to be abstracted into "box" and made to use token from config.py (which is the network tag)
	url = "http://35.225.127.157:8888/embed"  # Replace with your actual server URL

	headers = {
		"Content-Type": "application/json"
	}

	# instruction = request.form.getlist('instruction')[0]

	sentence = request.form.get('text').replace("\n", " ").replace("\r", " ").replace("'", "''")

	data = {
		"sentences": [sentence]
	}
	print("getting vectors")
	response = requests.post(url, headers=headers, json=data)

	if response.status_code == 200:
		print("Request successful")
		# print("Response:", response.text)
	else:
		print("Request failed")
		print("Status Code:", response.status_code)
	
	response_data = json.loads(response.text)
	embeddings = response_data.get('embeddings', [])

	document = ai("chatgpt_complete_dict", {"text": sentence})
	print(document.get('keyterms'))
	from lib.database import featurebase_query, create_database
	auth = {"dbid": current_user.dbid, "token": current_user.db_token}
	create_database('sample', f'(_id string, keyterm stringset, sentence string, embedding vector(768))', auth)

	sql = f"INSERT INTO sample VALUES('{random_string(6)}', {document.get('keyterms')}, '{sentence}', {embeddings[0]});"
	result = featurebase_query({"sql": sql, "dbid": current_user.dbid, "token": current_user.db_token})

	sql = f"select _id, sentence, keyterm, cosine_distance(select embedding from sample where sentence = '{sentence}', embedding) AS distance FROM sample ORDER BY distance ASC;"

	result = featurebase_query({"sql": sql, "dbid": current_user.dbid, "token": current_user.db_token})
	results = result.get('results')

	# Return a response, redirect, or render a template as needed
		
	return render_template('pages/home.html', results=results)

