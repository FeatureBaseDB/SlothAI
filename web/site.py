import os
import sys

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login
from flask_login import current_user

from lib.util import random_string

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


from flask import request

@site.route('/', methods=['POST'])
@flask_login.login_required
def index_post():
	import requests
	import json

	url = "http://34.30.174.61:8888/embed"  # Replace with your actual server URL

	headers = {
		"Content-Type": "application/json"
	}

	data = {
		"sentence": request.form.get('text')  # Replace with the text you want to send
	}
	sentence = data.get('sentence')

	response = requests.post(url, headers=headers, json=data)

	if response.status_code == 200:
		print("Request successful")
		print("Response:", response.text)
	else:
		print("Request failed")
		print("Status Code:", response.status_code)
	
	response_data = json.loads(response.text)
	embeddings = response_data.get('embeddings', [])

	from lib.database import featurebase_query, create_database
	auth = {"dbid": current_user.dbid, "token": current_user.db_token}
	create_database('sample', f'(_id string, keyterm stringset, sentence string, embedding vector(768))', auth)

	sql = f"INSERT INTO sample VALUES('{random_string(6)}', ['none','some', 'all'], '{sentence}', {embeddings[0]});"
	result = featurebase_query({"sql": sql, "dbid": current_user.dbid, "token": current_user.db_token})
	print(result)
	# Return a response, redirect, or render a template as needed
		
	return render_template('pages/home.html', embeddings=embeddings)

