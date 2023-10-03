import os
import sys
import json

import requests

import markdown
import markdown.extensions.fenced_code

from google.cloud import ndb

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file
from flask import current_app as app

import flask_login
from flask_login import current_user

from SlothAI.lib.util import random_string
from SlothAI.lib.ai import ai
from SlothAI.lib.tasks import list_tasks
from SlothAI.lib.database import table_exists

from SlothAI.web.models import Pipeline, Node, Models

site = Blueprint('site', __name__)

# client connection
client = ndb.Client()

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')

@site.route('/tasks')
@site.route('/jobs')
@flask_login.login_required
def get_all_tasks():
	_tasks = list_tasks(current_user.uid)
	username = current_user.name
	return render_template(
		'pages/tasks.html', tasks=_tasks, username=username
	)

# main route
@site.route('/settings', methods=['GET'])
@flask_login.login_required
def settings():
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid

	return render_template(
		'pages/settings.html', username=username, api_token=api_token, dbid=dbid
	)


@site.route('/models', methods=['GET'])
@flask_login.login_required
def models():
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid
	models = Models.get_all()

	return render_template(
		'pages/models.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, models=models
	)


@site.route('/animate', methods=['GET'])
def serve_markdown():
	# Get the directory containing the script (one level above)
	script_directory = os.path.dirname(os.path.abspath(__file__))
	parent_directory = os.path.abspath(os.path.join(script_directory, '../static/'))

	# Define the relative path to your Markdown file
	relative_file_path = 'animate.mmd'


	readme_file = open(os.path.join(parent_directory, relative_file_path), "r")
	md_template_string = markdown.markdown(
		readme_file.read(), extensions=["fenced_code"]
	)

	return md_template_string


@site.route('/', methods=['GET'])
@site.route('/pipelines', methods=['GET'])
@flask_login.login_required
def pipelines():
	# get the user and their tables
	username = current_user.name
	hostname = request.host
	pipelines = Pipeline.get_all_by_uid(uid=current_user.uid)
	models = Models.get_all()

	return render_template('pages/pipelines.html', username=username, hostname=hostname, pipelines=pipelines)

@site.route('/tables/<tid>', methods=['GET'])
@flask_login.login_required
def table_view(tid):
	# get the user and their tables
	username = current_user.name
	token = current_user.api_token

	hostname = request.host

	# hack the _table (pipeline) up with the model info 
	_table = Table.get_by_uid_tid(uid=current_user.uid, tid=tid)

	if not _table:
		return redirect(url_for('site.tables'))

	# (rest of your code remains unchanged...)
	mermaid_string = "graph TD\n"
	mermaid_string += "A[Input Data] -->|JSON| B[Ingest POST]\n"
	mermaid_string += "B -->|Response| G[JSON]\n"
	mermaid_string += "G -->|job_id: int| H[User]\n"
	mermaid_string += "B -->|JSON| J[schemer]\n"
	mermaid_string += "J -->|schema: auto| F{FeatureBase\n%s}\n" % _table.get("name")

	# check if models are present
	if _table and _table.get('models'):
		previous_model = 'B'  # initially, Ingest POST

		output = "|text: string|"
		for idx, model in enumerate(_table['models']):
			current_model = chr(67 + idx)  # 67 is ASCII for 'C'
			model_name = model['name']
			model_kind = model['kind']

			mermaid_string += f"{previous_model} -->{output}{current_model}[{model_kind}\n{model_name}]\n"

			# define the specific output based on model 'kind'
			if model['kind'] == 'keyterms':
				output = "|keyterms: stringset|"
			elif model['kind'] == 'embedding':
				output = "|embedding: vector|"
			elif model['kind'] == 'form_question':
				output = "|question: string|"
			else:
				output = "|text: string|"  # default case
			previous_model = current_model


		# After the loop ends, link the last model to the FeatureBase
		mermaid_string += f"{current_model} -->{output}F\n"

	return render_template('pages/table.html', username=username, dbid=current_user.dbid, token=token, hostname=hostname, table=_table, mermaid_string=mermaid_string)


