import os
import markdown
import markdown.extensions.fenced_code

from google.cloud import ndb

from flask import Blueprint, render_template
from flask import redirect, url_for
from flask import request
from flask import current_app as app

import flask_login
from flask_login import current_user

from SlothAI.lib.tasks import list_tasks

from SlothAI.web.models import Pipeline, Node
from SlothAI.lib.nodes import initilize_nodes

site = Blueprint('site', __name__)

# client connection
client = ndb.Client()

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')


@site.route('/', methods=['GET'])
@site.route('/pipelines', methods=['GET'])
@flask_login.login_required
def pipelines():
	# get the user and their tables
	username = current_user.name
	hostname = request.host
	pipelines = Pipeline.get(uid=current_user.uid)
	nodes = Node.fetch(uid=current_user.uid)
	
	initilize_nodes(current_user.uid)
	
	return render_template('pages/pipelines.html', username=username, hostname=hostname, pipelines=pipelines, nodes=nodes)


@site.route('/pipelines/<pipe_id>', methods=['GET'])
@flask_login.login_required
def pipeline_view(pipe_id):
	# get the user and their tables
	username = current_user.name
	token = current_user.api_token

	hostname = request.host

	pipelines = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)
	if not pipelines:
		return redirect(url_for('site.pipelines'))

	# (rest of your code remains unchanged...)
	mermaid_string = "graph TD\n"
	mermaid_string += "A[Input Data] -->|JSON| B[Ingest POST]\n"
	mermaid_string += "B -->|Response| G[JSON]\n"
	mermaid_string += "G -->|job_id: int| H[User]\n"
	mermaid_string += "B -->|JSON| J[schemer]\n"
	mermaid_string += "J -->|schema: auto| F{FeatureBase\n%s}\n" % pipelines.get("name")

	# check if models are present
	if pipelines and pipelines.get('models'):
		previous_model = 'B'  # initially, Ingest POST

		output = "|text: string|"
		for idx, model in enumerate(pipelines['models']):
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

	return render_template('pages/pipeline.html', username=username, dbid=current_user.dbid, token=token, hostname=hostname, table=_table, mermaid_string=mermaid_string)


@site.route('/nodes', methods=['GET'])
@flask_login.login_required
def nodes():
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid
	nodes = Node.fetch(uid=current_user.uid)

	return render_template(
		'pages/nodes.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, nodes=nodes
	)


@site.route('/nodes/<node_id>', methods=['GET'])
@flask_login.login_required
def node_detail(node_id):
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid
	node = Node.get(uid=current_user.uid,node_id=node_id)[0]

	return render_template(
		'pages/node.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, node=node
	)


@site.route('/templates')
@flask_login.login_required
def templates():
	username = current_user.name
	templates = Template.get(uid=current_user.uid)
	
	return render_template(
		'pages/templates.html', templates=templates
	)


@site.route('/tasks')
@flask_login.login_required
def get_all_tasks():
	tasks = list_tasks(current_user.uid)
	username = current_user.name
	return render_template(
		'pages/tasks.html', tasks=tasks, username=username
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


