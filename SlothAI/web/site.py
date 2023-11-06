import json

from google.cloud import ndb

from flask import Blueprint, render_template, jsonify
from flask import redirect, url_for
from flask import request
from flask import current_app as app

import flask_login
from flask_login import current_user

from SlothAI.lib.util import random_name, gpt_dict_completion, build_mermaid, load_template
from SlothAI.web.models import Pipeline, Node, Template, Log
from SlothAI.lib.tasks import Task

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
    {"value": "read_fb", "label": "Read Processor (FeatureBase)"},
    {"value": "split_task", "label": "Split Task Processor"},
    {"value": "write_fb", "label": "Write Processor (FeatureBase)"},
    {"value": "aidict", "label": "Generative Completion Processor"},
    {"value": "aichat", "label": "Generative Chat Processor"},
    {"value": "aiimage", "label": "Generative Image Processor"},
    {"value": "embedding", "label": "Embedding Vectors Processor"},
    {"value": "aivision", "label": "Vision Processor"},
    {"value": "aiaudio", "label": "Audio Processor"}
]

# template examples
template_examples = [
    {"name": "Start with a callback", "template_name": "get_started_callback", "processor_type": "callback"},
    {"name": "Generate random words", "template_name": "get_started_random_word", "processor_type": "jinja2"},
    {"name": "Convert text to embedding", "template_name": "text_to_embedding", "processor_type": "embedding"},
    {"name": "Convert text to an OpenAI embedding", "template_name": "text_to_ada_embedding", "processor_type": "embedding"},
    {"name": "Write to table", "template_name": "write_table", "processor_type": "write_fb"},
    {"name": "Write file chunks to a table", "template_name": "chunks_embeddings_pages_to_table", "processor_type": "write_fb"},
    {"name": "Read from table", "template_name": "read_table", "processor_type": "read_fb"},
    {"name": "Read embedding distance from a table", "template_name": "read_embedding_from_table", "processor_type": "read_fb"},
    {"name": "Read PDF or text file and convert to text", "template_name": "pdf_to_text", "processor_type": "read_file"},
    {"name": "Download file from URI with GET", "template_name": "uri_to_file", "processor_type": "read_uri"},
    {"name": "POST data to URI", "template_name": "json_to_uri", "processor_type": "read_uri"},
    {"name": "Convert page text into chunks", "template_name": "text_filename_to_chunks", "processor_type": "jinja2"},
    {"name": "Split tasks", "template_name": "split_tasks", "processor_type": "split_task"},
    {"name": "Read image and convert objects to labels", "template_name": "image_to_labels", "processor_type": "read_file"},
    {"name": "Read from a URI and convert to text", "template_name": "uri_to_text", "processor_type": "read_uri"},
    {"name": "Generate keyterms from text", "template_name": "text_to_keyterms", "processor_type": "aidict"},
    {"name": "Generate a question from text and keyterms", "template_name": "text_keyterms_to_question", "processor_type": "aidict"},
    {"name": "Generate a summary from text", "template_name": "text_to_summary", "processor_type": "aidict"},
    {"name": "Generate an image prompt from words", "template_name": "words_to_prompt", "processor_type": "aidict"},
    {"name": "Generate an image prompt from chunks and a query.", "template_name": "query_chunks_to_prompt", "processor_type": "aidict"},
    {"name": "Generate text sentiment", "template_name": "text_to_sentiment", "processor_type": "aidict"},
    {"name": "Generate answers from chunks and a query", "template_name": "chunks_query_to_answer", "processor_type": "aidict"},
    {"name": "Generate chat from texts", "template_name": "text_to_chat", "processor_type": "aichat"},
    {"name": "Generate an image from text", "template_name": "text_to_image", "processor_type": "aiimage"},
    {"name": "List objects in image", "template_name": "image_to_objects", "processor_type": "aivision"},
    {"name": "Transcribe audio to text pages", "template_name": "audio_to_text", "processor_type": "aiaudio"},
]

@site.route('/logs', methods=['GET'])
@flask_login.login_required
def logs():
    # get the user and their tables
    username = current_user.name
    hostname = request.host

    logs = Log.fetch(uid=current_user.uid)

    return render_template('pages/logs.html', username=username, hostname=hostname, logs=logs)


@site.route('/', methods=['GET'])
@site.route('/pipelines', methods=['GET'])
@flask_login.login_required
def pipelines():
    # get the user and their tables
    username = current_user.name
    hostname = request.host
    pipelines = Pipeline.fetch(uid=current_user.uid)
    nodes = Node.fetch(uid=current_user.uid)
    templates = Template.fetch(uid=current_user.uid)

    # add input and output fields, plus templates
    _nodes = []
    for node in nodes:
        for template in templates:
            if template.get('template_id') == node.get('template_id'):
                node['template_name'] = template.get('name')
                node['input_fields'] = template.get('input_fields')
                node['output_fields'] = template.get('output_fields')
                break

        for key in node.get('extras').keys():
            if 'token' in key or 'password' in key:
                node['extras'][key] = '[secret]'

        _nodes.append(node)

    return render_template('pages/pipelines.html', username=username, hostname=hostname, pipelines=pipelines, nodes=_nodes)


@site.route('/pipelines/<pipe_id>', methods=['GET'])
@flask_login.login_required
def pipeline_view(pipe_id):
    # get the user and their tables
    username = current_user.name
    token = current_user.api_token
    templates = Template.fetch(uid=current_user.uid)
    nodes = Node.fetch(uid=current_user.uid)

    pipeline = Pipeline.get(uid=current_user.uid, pipe_id=pipe_id)
    
    if not pipeline:
        return redirect(url_for('site.pipelines'))

    # add input and output fields, plus template name
    _nodes = []

    # build two lists, one of the ones in the pipeline, another of all nodes
    for node in nodes:
        for template in templates:
            if template.get('template_id') == node.get('template_id'):
                node['template_name'] = template.get('name')
                node['input_fields'] = template.get('input_fields')
                node['output_fields'] = template.get('output_fields')
                break

        for key in node.get('extras').keys():
            if 'token' in key or 'password' in key:
                node['extras'][key] = '[secret]'

        if node.get('node_id') in pipeline.get('node_ids'):
            _nodes.append(node)

    # sort the list based on the current order in the pipeline
    node_order_mapping = {node_id: index for index, node_id in enumerate(pipeline.get('node_ids'))}
    def custom_sort_key(item):
        return node_order_mapping.get(item['node_id'], len(pipeline.get('node_ids')))
    _nodes = sorted(_nodes, key=custom_sort_key)

    # build the graph for inspection
    mermaid_string = build_mermaid(pipeline, _nodes)

    # build an example POST usin generative AI
    head_input_fields = _nodes[0].get('input_fields', [])
    head_field_names = [field.get('name') for field in head_input_fields]
    head_processor = _nodes[0].get('processor')

    # Create a dictionary to store the template substitution values
    substitution_values = {
        "pipe_id": pipe_id,
        "pipe_name": pipeline.get('name'),
        "hostname": request.host,
        "protocol": request.scheme,
        "token": token,
        "head_processor": head_processor,
        "head_input_fields": ", ".join(head_field_names)
    }

    # Loop over the input fields and add them to the substitution dictionary
    ai_dict = gpt_dict_completion(substitution_values, template = 'form_example')
    if not ai_dict:
        ai_dict = {"texts": ["There was a knock at the door, then silence.","Bob was there, wanting to tell Alice about an organization."]}
        substitution_values['filename'] = "animate.pdf"
        substitution_values['mime_type'] = "application/pdf"
    else:
        substitution_values.update(ai_dict)
    print(substitution_values)
    # failsafe for setting content type and filename for a few processor templates
    substitution_values.setdefault('content_type', "application/pdf")
    substitution_values.setdefault('filename', "animate.pdf")

    # load the json string
    json_string = json.dumps(ai_dict)
    json_string = json_string.replace("'", '"')
    substitution_values['json_string'] = json_string

    python_template = load_template(f'{head_processor}_python')
    curl_template = load_template(f'{head_processor}_curl')

    if not python_template or not curl_template:
        python_template = load_template('jinja2_python')
        curl_template = load_template('jinja2_curl')

    python_code = python_template.substitute(substitution_values)
    curl_code = curl_template.substitute(substitution_values)

    # render the page
    return render_template('pages/pipeline.html', username=username, pipeline=pipeline, nodes=_nodes, all_nodes=nodes,  curl_code=curl_code, python_code=python_code, mermaid_string=mermaid_string)


@site.route('/nodes', methods=['GET'])
@flask_login.login_required
def nodes():
    # get the user and their tables
    username = current_user.name
    nodes = Node.fetch(uid=current_user.uid)

    templates = Template.fetch(uid=current_user.uid)

    template_lookup = {template['template_id']: template['name'] for template in templates}

    name_random = random_name(2).split('-')[1]

    # hide the tokens and passwords
    for node in nodes:
        extras = node.get('extras', None)
        if extras:
            for key in extras.keys():
                if 'token' in key or 'password' in key:
                    extras[key] = '[secret]'

    # update the template names
    _nodes = []
    for node in nodes:
        if node.get('template_id'):
            for template in templates:
                if template.get('template_id') == node.get('template_id'):
                    node['template'] = template
                    break

        _nodes.append(node)

    return render_template(
        'pages/nodes.html', username=username, dev=app.config['DEV'], nodes=_nodes, name_random=name_random, templates=templates, processors=processors
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

    # get short name
    for x in range(20):
        name_random = random_name(2).split('-')[0]
        if len(name_random) < 9:
            break

    empty_template = '{# New Template #}\n\n{# Extras are required. #}\nextras = {"static_extra": "hello", "user_extra": None}'

    return render_template(
        'pages/template.html', username=username, dev=app.config['DEV'], api_token=api_token, dbid=dbid, template=template, has_templates=has_templates, hostname=hostname, name_random=name_random, template_examples=template_examples, empty_template=empty_template
    )


@site.route('/logs', methods=["DELETE"])
@flask_login.login_required
def delete_logs():
    Log.delete_all(current_user.uid)
    return jsonify({"result": "success"})


@site.route('/tasks')
@flask_login.login_required
def tasks():
    tasks = app.config['task_service'].fetch_tasks(user_id=current_user.uid)

    """
    for entry, task in enumerate(tasks):
        node = Node.get(uid=current_user.uid, node_id=task.get('current_node_id'))
        pipeline = Pipeline.get(uid=current_user.uid, pipe_id=task.get('pipe_id'))

        if node:
            if node.get('name'):
                tasks[entry]['node_name'] = node.get('name')
            else:
                tasks[entry]['node_name'] = task.get('current_node_id')
        else:
            tasks[entry]['node_name'] = task.get('current_node_id')

        if pipeline:
            if pipeline.get('name'):
                tasks[entry]['pipeline_name'] = pipeline.get('name')
            else:
                tasks[entry]['pipeline_name'] = task.get('pipe_id')
        else:
            tasks[entry]['pipeline_name'] = task.get('pipe_id')

    """
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


