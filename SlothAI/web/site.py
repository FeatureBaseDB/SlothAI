from google.cloud import ndb

from flask import Blueprint, render_template
from flask import redirect, url_for
from flask import request
from flask import current_app as app

import flask_login
from flask_login import current_user

from SlothAI.lib.tasks import list_tasks
from SlothAI.lib.util import random_name
from SlothAI.web.models import Pipeline, Node, Template
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
    pipelines = Pipeline.fetch(uid=current_user.uid)
    nodes = Node.fetch(uid=current_user.uid)
    
    print(nodes)
    return render_template('pages/pipelines.html', username=username, hostname=hostname, pipelines=pipelines, nodes=nodes)


@site.route('/pipelines/<pipe_id>', methods=['GET'])
@flask_login.login_required
def pipeline_view(pipe_id):
	# get the user and their tables
	username = current_user.name
	token = current_user.api_token
	hostname = request.host

	pipeline = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)
	if not pipeline:
		return redirect(url_for('site.pipelines'))

	mermaid_string = "graph TD\n"
	mermaid_string += "A -->|JSON| G[Response]\n"
	mermaid_string += "G --> H[User]\n"

	# check if nodes are present
	if pipeline and pipeline.get('node_ids'):
		previous_node = None
		for i, n in enumerate(pipeline['node_ids']):
			node = Node.get(uid=current_user.uid, name=n)
			current_node = chr(65 + i)  # 65 is ASCII for 'A'
			if previous_node:
				mermaid_string += f"{previous_node} -->{output}{current_node}[{node.get('method')}\n{node.get('name')}]\n"
			else:
				# initilize mermaid string
				if node.get('method') == 'data_source' and node.get('extras').get('model', None) == 'endpoint':
					mermaid_string += f"{current_node}[POST /pipeline/{pipe_id}/task]\n"


			# define the specific output based on model 'kind'
			if node.get('method') == 'keyterm':
				output = "|keyterms: stringset|"
			elif node.get('method') == 'embedding':
				output = "|embedding: vector|"
			elif node.get('method') == 'form_question':
				output = "|question: string|"
			elif node.get('method') == 'data_source':
				output = "| JSON |"
			elif node.get('method') == 'write':
				output = "| SQL INSERT | "
			else:
				output = "|text: string|"  # default case
			previous_node = current_node

		if node.get('method') == 'write':
			mermaid_string += f"{current_node} -->{output}F[FeatureBase\n{pipeline.get('name')}]\n"

	return render_template('pages/pipeline.html', username=username, dbid=current_user.dbid, token=token, hostname=hostname, pipeline=pipeline, mermaid_string=mermaid_string)


@site.route('/nodes', methods=['GET'])
@flask_login.login_required
def nodes():
    # get the user and their tables
    username = current_user.name

    api_token = current_user.api_token
    dbid = current_user.dbid
    nodes = Node.fetch(uid=current_user.uid)

    templates = Template.fetch(uid=current_user.uid)

    template_lookup = {template['template_id']: template['name'] for template in templates}

    name_random = random_name(2).split('-')[1]

    # update the template names
    _nodes = []
    for node in nodes:
        if node.get('template_id'):
            template = Template.get(template_id=node.get('template_id'))
            node['template'] = template
        else:
            node['template'] = {}
        _nodes.append(node)

    return render_template(
        'pages/nodes.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, nodes=_nodes, name_random=name_random
    )


@site.route('/templates')
@flask_login.login_required
def templates():
    username = current_user.name
    templates = Template.fetch(uid=current_user.uid)
    print(templates)
    if not templates:
        return redirect(url_for('site.template_detail'))  # Adjust 'template_detail' to your route name

    return render_template(
        'pages/templates.html', username=username, templates=templates
    )


@site.route('/templates/new')
@site.route('/templates/<template_id>', methods=['GET'])
@flask_login.login_required
def template_detail(template_id="new"):
    # get the user and their tables
    username = current_user.name
    api_token = current_user.api_token
    dbid = current_user.dbid
    template = Template.get(uid=current_user.uid,template_id=template_id)
    hostname = request.host

    name_random = random_name(2)

    return render_template(
        'pages/template.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, template=template, hostname=hostname, name_random=name_random
    )


@site.route('/tasks')
@flask_login.login_required
def tasks():
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


