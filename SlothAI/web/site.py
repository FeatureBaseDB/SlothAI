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

# hard coded, for now
processors = [
    {"value": "jinja2", "label": "Jinja2 Processor"},
    {"value": "callback", "label": "Callback Processor"},
    {"value": "read_file", "label": "Read Processor (File)"},
    {"value": "read_uri", "label": "Read Processor (URI)"},
    {"value": "read_featurebase", "label": "Read Processor (FeatureBase)"},
    {"value": "write_featurebase", "label": "Write Processor (FeatureBase)"},
    {"value": "aidict", "label": "Generative Completion Processor"},
    {"value": "aichat", "label": "Generative Chat Processor"},
    {"value": "embedding", "label": "Embedding Vectors Processor"},
    {"value": "aivision", "label": "Vision Processor"},
    {"value": "aiaudio", "label": "Audio Processor"}
]

# template examples
template_examples = [
    {"name": "Get started with a callback", "template_name": "get_started_callback", "processor_type": "callback"},
    {"name": "Generate random words", "template_name": "get_started_random_word", "processor_type": "jinja2"},
    {"name": "Read PDF and convert to text", "template_name": "pdf_to_text", "processor_type": "read_file"},
    {"name": "Read image and convert objects to labels", "template_name": "image_to_labels", "processor_type": "read_file"},
    {"name": "Read from a URI and convert to text", "template_name": "uri_to_text", "processor_type": "read_uri"},
    {"name": "Extract keyterms from text", "template_name": "text_to_keyterms", "processor_type": "aidict"},
    {"name": "Create a question from text and keyterms", "template_name": "text_and_keyterms_to_question", "processor_type": "aidict"},
    {"name": "Generate a summary from text", "template_name": "text_to_summary", "processor_type": "aidict"},
    {"name": "Convert text to stringset", "template_name": "text_to_stringset", "processor_type": "aidict"},
    {"name": "Analyze text sentiment", "template_name": "text_to_sentiment", "processor_type": "aidict"},
    {"name": "Generate answers from texts and keyterms", "template_name": "texts_and_keyterms_to_answer", "processor_type": "aidict"},
    {"name": "Converse and answer questions from texts and keyterms", "template_name": "texts_and_keyterms_to_answer", "processor_type": "aichat"},
    {"name": "Convert text to vector", "template_name": "text_to_vector", "processor_type": "embedding"},
    {"name": "Convert text to an OpenAI ada-similarity vector", "template_name": "text_to_ada_vector", "processor_type": "embedding"},
    {"name": "Convert text and keyterms to vector", "template_name": "text_keyterms_to_vector", "processor_type": "embedding"},
    {"name": "Find similar texts using a vector", "template_name": "vector_to_texts", "processor_type": "read_featurebase"},
    {"name": "Query table for records", "template_name": "query_table", "processor_type": "read_featurebase"},
    {"name": "Write to table", "template_name": "write_table", "processor_type": "write_featurebase"},
]


@site.route('/', methods=['GET'])
@site.route('/pipelines', methods=['GET'])
@flask_login.login_required
def pipelines():
    # get the user and their tables
    username = current_user.name
    hostname = request.host
    pipelines = Pipeline.fetch(uid=current_user.uid)
    nodes = Node.fetch(uid=current_user.uid)
    
    _nodes = []
    for node in nodes:
        template = Template.get(template_id=node.get('template_id'))
        node['template_name'] = template.get('name')
        node['input_fields'] = template.get('input_fields')
        node['output_fields'] = template.get('output_fields')
        _nodes.append(node)

    return render_template('pages/pipelines.html', username=username, hostname=hostname, pipelines=pipelines, nodes=_nodes)


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

	return render_template('pages/pipeline.html', username=username, dbid=current_user.dbid, token=token, hostname=hostname, pipeline=pipeline)


@site.route('/nodes', methods=['GET'])
@flask_login.login_required
def nodes():
    # get the user and their tables
    username = current_user.name

    api_token = current_user.api_token
    dbid = current_user.dbid
    nodes = Node.fetch(uid=current_user.uid)

    templates = Template.fetch(uid=current_user.uid)
    
    templates_exist = True
    if not templates:
        templates_exist = False

    template_lookup = {template['template_id']: template['name'] for template in templates}

    name_random = random_name(2).split('-')[1]

    # hide the tokens and passwords
    for node in nodes:
        for extra_dict in node['extras']:
            for key in extra_dict.keys():
                if 'token' in key or 'password' in key:
                    extra_dict[key] = '[secret]'

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
        'pages/nodes.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, nodes=_nodes, name_random=name_random, templates_exist=templates_exist, processors=processors
    )


@site.route('/templates')
@flask_login.login_required
def templates():
    username = current_user.name
    templates = Template.fetch(uid=current_user.uid)
    
    if not templates:
        return redirect(url_for('site.template_detail'))  # Adjust 'template_detail' to your route name

    return render_template(
        'pages/templates.html', username=username, templates=templates, processors=processors
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
    
    # test if there are more templates
    has_templates = False
    templates = Template.fetch(uid=current_user.uid)
    if templates:
        has_templates = True

    hostname = request.host

    name_random = random_name(2)

    return render_template(
        'pages/template.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, template=template, has_templates=has_templates, hostname=hostname, name_random=name_random,  template_examples=template_examples
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


