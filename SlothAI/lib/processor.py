import random
import string

import ast
import re
import copy

import requests
import json

import openai

from typing import Dict

from flask import current_app as app
from flask import url_for

from jinja2 import Environment

from enum import Enum

# supress OpenAI resource warnings for unclosed sockets
import warnings
warnings.filterwarnings("ignore")

from SlothAI.web.custom_commands import random_word, random_sentence
from SlothAI.web.models import User, Node, Template

from SlothAI.lib.tasks import Task, process_data_dict_for_insert, transform_data, get_values_by_json_paths, box_required, validate_dict_structure
from SlothAI.lib.database import table_exists, add_column, create_table, get_columns, featurebase_query
from SlothAI.lib.util import extras_from_template, fields_from_template, remove_fields_and_extras, strip_secure_fields, filter_document

env = Environment()
env.globals['random_word'] = random_word
env.globals['random_sentence'] = random_sentence

class DocumentValidator(Enum):
	INPUT_FIELDS = 'input_fields'
	OUTPUT_FIELDS = 'output_fields'

processers = {}
processer = lambda f: processers.setdefault(f.__name__, f)

def process(task: Task) -> Task:
	node_id = task.next_node()
	node = Node.get(uid=task.user_id, node_id=node_id)

	valid = validate_document(node, task, DocumentValidator.INPUT_FIELDS)
	if not valid:
		task.document['error'] = "document did not have the correct input fields"
		raise Exception("document did not have the correct input fields")

	# template the extras off the node
	extras = evaluate_extras(node, task)
	if extras:
		task.document.update(extras)

	# TODO: nodes should own access tokens but we need to be able to store them
	# securely. For now, use app config openai_token when the extras value
	# openai_token is present in a node.
	# if "openai_token" in node.get('extras'):
	task.document['OPENAI_TOKEN'] = app.config['OPENAI_TOKEN']

	user = User.get_by_uid(uid=task.user_id)
	# if "x-api-key" in node.get('extras'):
	task.document['X-API-KEY'] = user.get('db_token')
	# if "database_id" in node.get('extras'):
	task.document['DATABASE_ID'] = user.get('dbid')

	# processer methods are responsible for adding errors to documents
	task = processers[node.get('processor')](node, task)

	if "OPENAI_TOKEN" in task.document.keys():
		task.document.pop('OPENAI_TOKEN', None)
	if "X-API-KEY" in task.document.keys():
		task.document.pop('X-API-KEY', None)
	if "DATABASE_ID" in task.document.keys():
		task.document.pop('DATABASE_ID', None)

	clean_extras(extras, task)
	valid = validate_document(node, task, DocumentValidator.OUTPUT_FIELDS)
	if not valid:
		task.document['error'] = "document did not have the correct output fields"
		raise Exception("document did not have the correct output fields")

	return task

@processer
def jinja2(node: Dict[str, any], task: Task) -> Task:
	template = Template.get(template_id=node.get('template_id'))
	template_text = remove_fields_and_extras(template.get('text'))

	if template_text:
		jinja_template = env.from_string(template_text)
		jinja = jinja_template.render(task.document)
		jinja_json = json.loads(jinja)
		for k,v in jinja_json.items():
			task.document[k] = v

	return task

@processer
def callback(node: Dict[str, any], task: Task) -> Task:
	template = Template.get(template_id=node.get('template_id'))
	output_fields = template.get('output_fields')

	user = User.get_by_uid(uid=task.user_id)

	uri = url_for('callback.handle_callback', user_name=user.get('name'), _external=True)
	auth_uri = f"{uri}?token={node.get('extras').get('callback_token')}"

	# strip secure stuff out of the document
	document = strip_secure_fields(task.document) # returns document

	keys_to_keep = []
	for field in output_fields:
		for key, value in field.items():
			if key == 'name':
				keys_to_keep.append(value)

	if keys_to_keep:
		data = filter_document(document, keys_to_keep)
		if not data:
			data = document
	else:
		data = document

	# must add node_id and pipe_id
	data['node_id'] = node.get('node_id')
	data['pipe_id'] = task.pipe_id

	resp = requests.post(auth_uri, data=json.dumps(data))
	if resp.status_code != 200:
		raise Exception("callback request failed")

	return task

@processer
def read_featurebase(node: Dict[str, any], task: Task) -> Task:
	user = User.get_by_uid(task.user_id)
	doc = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	doc['sql'] = task.document['sql']
	resp, _ = featurebase_query(document=doc)

	fields = []
	data = {}
	for field in resp.schema['fields']:
		fields.append(field['name'])
		data[field['name']] = []

	for tuple in resp.data:
		for i, value in enumerate(tuple):
			data[fields[i]].append(value)

	template = Template.get(template_id=node.get('template_id'))
	_keys = template.get('output_fields') # must be input fields but not enforced
	if _keys:
		keys = [n['name'] for n in _keys]
		task.document.update(transform_data(keys, data))
	else:
		task.document.update(data)

	return task

from SlothAI.lib.schemar import Schemar
@processer
def write_featurebase(node: Dict[str, any], task: Task) -> Task:

	auth = {"dbid": task.document['DATABASE_ID'], "db_token": task.document['X-API-KEY']}

	template = Template.get(template_id=node.get('template_id'))
	_keys = template.get('input_fields') # must be input fields but not enforced
	keys = [n['name'] for n in _keys]
	data = get_values_by_json_paths(keys, task.document)

	table = task.document['table']
	tbl_exists, task.document['error'] = table_exists(table, auth)
	if task.document.get("error", None):
		raise Exception("unable to check for table in FeatureBase cloud")
	
	# if it doesn't exists, create it
	if not tbl_exists:
		create_schema = Schemar(data=data).infer_create_table_schema() # check data.. must be lists
		task.document['error'] = create_table(table, create_schema, auth)
		if task.document.get('error'):
			raise Exception("unable to create table in FeatureBase cloud")

	# get columns from the table
	column_type_map, task.document['error'] = get_columns(table, auth)
	if task.document.get("error", None):
		raise Exception("unable to get columns from table in FeatureBase cloud")

	columns = [k for k in column_type_map.keys()]

	# add columns if data key cannot be found as an existing column
	for key in data.keys():
		if key not in columns:
			if not task.document.get("schema", None):
				task.document['schema'] = Schemar(data=data).infer_schema()
				if task.document.get("error", None):
					raise Exception("unable to infer schema from data.")

			task.document['error'] = add_column(table, {'name': key, 'type': task.document["schema"][key]}, auth)
			if task.document['error']:
				raise Exception("unable to add column to table in FeatureBase cloud.")

			column_type_map[key] = task.document["schema"][key]


	columns, records = process_data_dict_for_insert(data, column_type_map, table)

	sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES {','.join(records)};"
	print(sql[:200])
	_, task.document['error'] = featurebase_query({"sql": sql, "dbid": task.document['DATABASE_ID'], "db_token": task.document['X-API-KEY']})
	if task.document.get("error", None):
		raise Exception("unable to insert data into featurebase")
	
	return task

@processer
def sloth_embedding(node: Dict[str, any], task: Task) -> Task:
	return sloth_processing(node, task, "embedding")

@processer
def sloth_keyterms(node: Dict[str, any], task: Task) -> Task:
	return sloth_processing(node, task, "keyterms")


def sloth_processing(node: Dict[str, any], task: Task, type) -> Task:
	if type == "embedding":
		path = "embed"
		response_key = "embeddings"
	elif type == "keyterms":
		path = "keyterms"
		response_key = "keyterms"
	else:
		raise Exception("sloth can only process embedding or keyterms.")

	template = Template.get(template_id=node.get('template_id'))
	input_fields, output_fields = fields_from_template(template.get('text'))

	if len(input_fields) != 1:
		task.document['error'] = "sloth only supports a single input field to get embedded at this time."

	if len(output_fields) != 1:
		task.document['error'] = "sloth only supports a single output field to hold the embedding at this time."

	data = {
		"text": task.document[input_fields[0]['name']]
		# data = get_values_by_json_paths(keys, task.document)
		# TODO: could be a nested key
	}

	defer, selected_box = box_required()
	if defer:
		task.document['error'] = "sloth virtual machine is being started"
		return task
	
	url = f"http://sloth:{app.config['SLOTH_TOKEN']}@{selected_box.get('ip_address')}:9898/{path}"

	try:
		# Send the POST request with the JSON data
		response = requests.post(url, data=json.dumps(data), headers={"Content-Type": "application/json"}, timeout=30)
	except Exception as ex:
		task.document['error'] = f"Exception raised connecting to sloth virtual machine: {ex}"
		return task

	# Check the response status code for success
	if response.status_code == 200:
		task.document[output_fields[0]['name']] = response.json().get(response_key)
	else:
		task.document['error'] = f"request to sloth_embedding virtual machine failed with status code {response.status_code}: {response.text}"

	return task


def validate_document(node, task: Task, validate: DocumentValidator):
	template = Template.get(template_id=node.get('template_id'))
	fields = template.get(validate)
	if fields:
		missing_key = validate_dict_structure(template.get('input_fields'), task.document)
		if missing_key:
			return False
	
	return True


def evaluate_extras(node, task) -> Dict[str, any]:
	# get the node's current extras, which may be templated
	extras = node.get('extras', {})

	extras_template = env.from_string(str(extras))
	extras_from_template = extras_template.render(extras)
	extras_eval = ast.literal_eval(extras_from_template)
	return extras_eval


def clean_extras(extras: Dict[str, any], task: Task):
	if extras:
		for k in extras.keys():
			if k in task.document.keys():
				del task.document[k]
	return task


def ada(ai_model, document):
	# load openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	texts = []
	for _text in document.get('data').get('text'): 
		texts.append(_text.replace("\n", " "))

	try:
		embedding_results = openai.Embedding.create(input=texts, model=ai_model.get('name'))['data']
	except Exception as ex:
		print(ex)
		document['error'] = f"exception talking to OpenAI ada embedding: {ex}"
		embedding_results = []

	document['data']['embedding'] = [_object.get("embedding") for _object in embedding_results]

	return document

def gpt_keyterms(ai_model, document):
	# load openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	for _text in document.get('data').get('text'):

		# substitute things
		try:
			template = load_template("form_keyterms")
			prompt = template.substitute({"text": _text})
		except Exception as ex:
			print(ex)
			document['error'] = "template wouldn't load"
			return document

		# get the template's dict
		ai_dict = gpt_dict_completion(prompt, ai_model.get('name'))

		# extract the keyterms and stuff into the document
		if document.get('data', None):
			if document.get('data').get('keyterms', None):
				document['data']['keyterms'].append(ai_dict.get('keyterms'))
			else:
				document['data']['keyterms'] = [ai_dict.get('keyterms')]

	return document


# # handle old name
# @model
# def chatgpt_extract_keyterms(ai_model, document):
# 	return  gpt_keyterms(ai_model, document)


# # get a question	
# @model
# def gpt_question(ai_model, document):
# 	# load openai key then drop it from the document
# 	openai.api_key = document.get('openai_token')

# 	for _text in document.get('data').get('text'):

# 		# substitute things
# 		try:
# 			template = load_template("form_question")
# 			prompt = template.substitute({"text": _text})
# 		except Exception as ex:
# 			print(ex)
# 			document['error'] = "template wouldn't load"
# 			return document

# 		# get the template's dict
# 		ai_dict = gpt_dict_completion(prompt, ai_model.get('name'))

# 		# extract the question and stuff into the document
# 		if document.get('data', None):
# 			if document.get('data').get('questions', None):
# 				document['data']['questions'].append(ai_dict.get('question'))
# 			else:
# 				document['data']['questions'] = [ai_dict.get('question')]

# 	return document


# @processer
# def query_analyze(ai_model, document):
# 	# load openai key then drop it from the document
# 	openai.api_key = app.config['OPENAI_TOKEN']

# 	# substitute things
# 	try:
# 		template = load_template("query_analyze")
# 		prompt = template.substitute(document)
# 	except Exception as ex:
# 		print(ex)
# 		document['error'] = "template wouldn't load"
# 		return document

# 	# get the template's dict
# 	ai_dict = gpt_dict_completion(prompt, ai_model)

# 	# extract the keyterms and stuff into the document
# 	document['sql'] = ai_dict.get('sql')
# 	document['explain'] = ai_dict.get('explain')
# 	document['rewrite'] = ai_dict.get('rewrite')
# 	return document

# # rewrite the query object
# @model
# def query_rewrite(ai_model, document):
# 	# load openai key then drop it from the document
# 	openai.api_key = app.config['OPENAI_TOKEN']

# 	# substitute things
# 	try:
# 		template = load_template("query_rewrite")
# 		prompt = template.substitute(document)
# 	except Exception as ex:
# 		print(ex)
# 		document['error'] = "template wouldn't load"
# 		return document

# 	# get the template's dict
# 	ai_dict = gpt_dict_completion(prompt, ai_model)

# 	# extract the keyterms and stuff into the document
# 	document['sql'] = ai_dict.get('sql')
# 	document['explain'] = ai_dict.get('explain')
# 	return document




# helper functions
# ================

# load template
def load_template(name="default"):
	# file path
	file_path = "./SlothAI/templates/prompts/%s.txt" % (name)

	try:
		with open(file_path, 'r', encoding='utf-8') as f:
			template = Template(f.read())
	except Exception as ex:
		print(ex)
		print("exception in loading template")
		template = None

	return template


# complete a dict from template
def gpt_dict_completion(prompt, model):

	completion = openai.ChatCompletion.create(
		model = model,
		messages = [
		{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, or any text other than the output requested."},
		{"role": "user", "content": prompt}
		]
	)

	answer = completion.choices[0].message

	ai_dict_str = answer.get('content').replace("\n", "").replace("\t", "").lower()
	ai_dict_str = re.sub(r'\s+', ' ', ai_dict_str).strip()

	try:
		ai_dict = ast.literal_eval(ai_dict_str)
	except (ValueError, SyntaxError):
		print("Error: Invalid JSON format in ai_dict_str.")
		ai_dict = {}

	return ai_dict