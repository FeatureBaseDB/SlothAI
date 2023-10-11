import random
import string
import requests
import json
import ast
import re
import openai
import traceback

from typing import Dict

from string import Template
from flask import current_app as app

# supress OpenAI resource warnings for unclosed sockets
import warnings
warnings.filterwarnings("ignore")

from SlothAI.web.models import User, Pipeline
from SlothAI.lib.tasks import Task, get_task_schema, retry_task, process_data_dict_for_insert
from SlothAI.lib.database import table_exists, add_column, create_table, get_columns, featurebase_query

processers = {}
processer = lambda f: processers.setdefault(f.__name__, f)

def process(node: Dict[str, any], task: Task) -> Task:
	# TODO: nodes should own access tokens but we need to be able to store them
	# securely. For now, use app config openai_token when the extras value
	# openai_token is present in a node.
	if "openai_token" in node.get('extras'):
		task.document['OPENAI_TOKEN'] = app.config['OPENAI_TOKEN']
	
	user = User.get_by_uid(uid=task.user_id)
	if "x-api-key" in node.extras:
		task.document['X-API-KEY'] = user.get('db_token')
	if "database_id" in node.extras:
		task.document['DATABASE_ID'] = user.get('dbid')

	# TODO: could be useful to check keys in document at this point. node should
	# tell use which keys were supposed to be there before processing.

	# processer methods are responsible for adding errors to documents
	task.document = processers[node.method](node, task)

	if "openai_token" in node.extras:
		task.document.pop('OPENAI_TOKEN', None)
	if "x-api-key" in node.extras:
		task.document.pop('X-API-KEY', None)
	if "database_id" in node.extras:
		task.document.pop('DATABASE_ID', None)

	# TODO: could be useful to check keys in document at this point. node should
	# tell use which keys were supposed to be added.

	return task.document

@processer
def embedding(node: Dict[str, any], task: Task) -> Task:
	try:
		#TODO: this should not be hard coded
		if node.get('model') == 'instructor-large' or node.get('model') == 'instructor-xl':
			task.document = instructor(task.document)
		elif node.get('model') == 'text-embedding-ada-002':
			task.document = ada('text-embedding-ada-002', task.document)
	except Exception as e:
		task.document['error'] = f"ERROR: in embedding: {e}"

	return task

@processer
def keyterms(node: Dict[str, any], task: Task) -> Task:
	try:
		#TODO: this should not be hard coded
		if node.get('model') == 'sloth-extract':
			task.document = sloth_keyterms(task.document)
		elif node.get('model') == 'gpt-4' or node.get('model') == 'gpt-3.5-turbo':
			task.document = gpt_keyterms(node.get('model'), task.document)
	except Exception as e:
		task.document['error'] = f"ERROR: in keyterms: {e}"

	return task

@processer
def write(node: Dict[str, any], task: Task) -> Task:
	# just one write processer for now.
	return featurebase_write(node, task)

@processer
def read(node: Dict[str, any], task: Task) -> Task:
	# just one read processer for now.
	return featurebase_read(node, task)

def featurebase_write(node: Dict[str, any], task: Task) -> Task:

	auth = {"dbid": task.document['DATABASE_ID'], "db_token": task.document['X-API-KEY']}
	pipeline = Pipeline.get(uid=task.user_id, pipe_id=task.pipe_id)
	table_name = pipeline.get('name') # error check?
	document = task.document

	tbl_exists, document['error'] = table_exists(table_name, auth)
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200

	if not tbl_exists:
		document = get_task_schema(document)
		if document.get("error", None):
			print(f"ERROR: {document['error']}. dropping task.")
			return document['error'], 200
		
		# new tables always have id keys
		schema = "(_id id, " + ", ".join([f"{fld} {typ}" for fld, typ in document.get('schema', {}).items()]) + ")"
		
		document['error'] = create_table(table_name, schema, auth)
		if document.get("error", None):
			retry_task(document)
			return "retrying", 200

	column_type_map, document['error'] = get_columns(table_name, auth)
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200

	columns = [k for k in column_type_map.keys()]

	# add columns if data key cannot be found as an existing column
	for key in document['data'].keys():
		if key not in columns:
			if not document.get("schema", None):
				document = get_task_schema(document)
				if document.get("error", None):
					print(f"ERROR: {document['error']}. dropping task.")
					return document['error'], 200
			document['error'] = add_column(table_name, {'name': key, 'type': document["schema"][key]}, auth)
			if document['error']:
				retry_task(document)
				return "retrying", 200
			column_type_map[key] = document["schema"][key]


	records = []
	columns = ['_id'] + list(document['data'].keys())

	columns, records = process_data_dict_for_insert(document['data'], column_type_map, table_name)

	sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES {','.join(records)};"
	print(sql[:200])
	_, document['error'] = featurebase_query({"sql": sql, "dbid": auth["dbid"], "db_token": auth['db_token']})
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200
	else:
		return "success", 200

def featurebase_read(node: Dict[str, any], task: Task) -> Task:
	pass

def instructor(document):
	ip_address = document.get('ip_address') # TODO: move this into the model

	password = app.config['SLOTH_TOKEN']
	url = f"http://sloth:{password}@{ip_address}:9898/embed"

	# Set the headers to indicate that you're sending JSON data
	headers = {
		"Content-Type": "application/json"
	}
	try:
		# Send the POST request with the JSON data
		response = requests.post(url, data=json.dumps(document.get('data')), headers=headers, timeout=30)
	except Exception as ex:
		document['error'] = "server not avaliable"
		return document

	# Check the response status code for success
	if response.status_code == 200:
		document['data']['embedding'] = response.json().get('embeddings')
	else:
		document['error'] = f"POST request failed with status code {response.status_code}: {response.text}"

	return document

def sloth_keyterms(document):
	ip_address = document.get('ip_address')

	password = app.config['SLOTH_TOKEN']
	url = f"http://sloth:{password}@{ip_address}:9898/keyterms"

	# Set the headers to indicate that you're sending JSON data
	headers = {
		"Content-Type": "application/json"
	}

	if not document['data'].get('keyterms'):
		document['data']['keyterms'] = []

	try:
		# Send the POST request with the JSON data
		response = requests.post(url, data=json.dumps(document), headers=headers)
	except Exception as ex:
		document['error'] = "server not avaliable"
		return document

	# Check the response status code for success
	if response.status_code == 200:
		for _keyterms in response.json().get('keyterms'):
			document['data']['keyterms'].append(_keyterms)
	else:
		document['error'] = f"POST request failed with status code {response.status_code}: {response.text}"

	return document

def ada(model, document):
	# load openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	texts = []
	for _text in document.get('data').get('text'): 
		texts.append(_text.replace("\n", " "))

	try:
		embedding_results = openai.Embedding.create(input=texts, model=model)['data']
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

def chatgpt_extract_keyterms(ai_model, document):
	return  gpt_keyterms(ai_model, document)

# @processer
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




# # analyze the query object
# @processer
# def query_analyze(ai_model, document):

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
# @processer
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


# random strings
def random_string(size=6, chars=string.ascii_letters + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))


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
