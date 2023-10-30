import random
import string

import ast
import re
import copy
import hashlib

from io import BytesIO

import requests
import json

import openai

from google.cloud import vision, storage, documentai
from google.api_core.client_options import ClientOptions

from typing import Dict

import PyPDF2

from flask import current_app as app
from flask import url_for

from jinja2 import Environment

from enum import Enum

# supress OpenAI resource warnings for unclosed sockets
import warnings
warnings.filterwarnings("ignore")

from SlothAI.web.custom_commands import random_word, random_sentence, process_and_segment_texts_with_overlap
from SlothAI.web.models import User, Node, Template, Pipeline

from SlothAI.lib.tasks import Task, process_data_dict_for_insert, transform_data, get_values_by_json_paths, box_required, validate_dict_structure, NonRetriableError, RetriableError, MissingInputFieldError, MissingOutputFieldError, UserNotFoundError, PipelineNotFoundError, NodeNotFoundError, TemplateNotFoundError
from SlothAI.lib.database import table_exists, add_column, create_table, get_columns, featurebase_query
from SlothAI.lib.util import extras_from_template, fields_from_template, remove_fields_and_extras, strip_secure_fields, filter_document, load_from_storage, random_string

env = Environment()
env.globals['random_word'] = random_word
env.globals['random_sentence'] = random_sentence
env.globals['process_and_segment_texts_with_overlap'] = process_and_segment_texts_with_overlap

class DocumentValidator(Enum):
	INPUT_FIELDS = 'input_fields'
	OUTPUT_FIELDS = 'output_fields'

retriable_status_codes = [408, 409, 425, 429, 500, 503, 504]

processers = {}
processer = lambda f: processers.setdefault(f.__name__, f)

def process(task: Task) -> Task:
	user = User.get_by_uid(task.user_id)
	if not user:
		raise UserNotFoundError(task.user_id)
	
	pipeline = Pipeline.get(uid=task.user_id, pipe_id=task.pipe_id)
	if not pipeline:
		raise PipelineNotFoundError(pipeline_id=task.pipe_id)
	
	node_id = task.next_node()
	node = Node.get(uid=task.user_id, node_id=node_id)
	if not node:
		raise NodeNotFoundError(node_id=node_id)

	missing_field = validate_document(node, task, DocumentValidator.INPUT_FIELDS)
	if missing_field:
		raise MissingInputFieldError(missing_field, node.get('name'))

	# template the extras off the node
	extras = evaluate_extras(node, task)
	if extras:
		task.document.update(extras)

	# grab the available token for the node
	if "openai_token" in node.get('extras'):
		task.document['OPENAI_TOKEN'] = extras.get('openai_token')

	# get the user
	user = User.get_by_uid(uid=task.user_id)

	# if "x-api-key" in node.get('extras'):
	task.document['X-API-KEY'] = user.get('db_token')
	# if "database_id" in node.get('extras'):
	task.document['DATABASE_ID'] = user.get('dbid')

	# processer methods are responsible for adding errors to documents
	task = processers[node.get('processor')](node, task)

	# TODO, decide what to do with errors and maybe truncate pipeline
	if task.document.get('error'):
		return task

	if "OPENAI_TOKEN" in task.document.keys():
		task.document.pop('OPENAI_TOKEN', None)
	if "X-API-KEY" in task.document.keys():
		task.document.pop('X-API-KEY', None)
	if "DATABASE_ID" in task.document.keys():
		task.document.pop('DATABASE_ID', None)

	# strip out the sensitive extras
	clean_extras(extras, task)
	missing_field = validate_document(node, task, DocumentValidator.OUTPUT_FIELDS)
	if missing_field:
		raise MissingOutputFieldError(missing_field, node.get('name'))

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
def embedding(node: Dict[str, any], task: Task) -> Task:
	# load openai key then drop it from the document
	if "text-embedding-ada-002" in task.document.get('model'):
		openai.api_key = task.document.get('openai_token')

	# output and input fields
	template = Template.get(template_id=node.get('template_id'))
	output_fields = template.get('output_fields')
	output_field = output_fields[0].get('name')
	
	input_fields = template.get('input_fields')
	input_field = input_fields[0].get('name')

	if "text-embedding-ada-002" in task.document.get('model'):
		try:
			embedding_results = openai.Embedding.create(input=task.document.get(input_field), model=task.document.get('model'))
		except Exception as ex:
			task.document['error'] = f"exception talking to OpenAI ada embedding: {ex}"
			task.document[output_field] = []
			return task

		task.document[output_field] = [_object.get('embedding') for _object in embedding_results.get('data')]
	else:
		task.document[output_field] = []
 
	return task


@processer
def aidict(node: Dict[str, any], task: Task) -> Task:
	# output and input fields
	template = Template.get(template_id=node.get('template_id'))
	output_fields = template.get('output_fields')
	output_field = output_fields[0].get('name')
	
	input_fields = template.get('input_fields')
	input_field = input_fields[0].get('name')

	if "gpt" in task.document.get('model'):
		openai.api_key = task.document.get('openai_token')

	template_text = remove_fields_and_extras(template.get('text'))

	if template_text:
		jinja_template = env.from_string(template_text)
		prompt = jinja_template.render(task.document)
	
	completion = openai.ChatCompletion.create(
		model = task.document.get('model'),
		messages = [
			{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, text markup, or any text other than the output requested, which is a python dictionary."},
			{"role": "user", "content": prompt}
		]
	)

	answer = completion.choices[0].message

	ai_dict_str = answer.get('content').replace("\n", "").replace("\t", "").lower()
	ai_dict_str = re.sub(r'\s+', ' ', ai_dict_str).strip()
	ai_dict_str = ai_dict_str.strip('python_dict = ')

	try:
		ai_dict = eval(ai_dict_str)
	except (ValueError, SyntaxError):
		task.document['error'] = f"exception talking to OpenAI dict create: {ex}"
		ai_dict = {}

	task.document.update(ai_dict)
	
	return task


@processer
def aiimage(node: Dict[str, any], task: Task) -> Task:
	# output and input fields
	template = Template.get(template_id=node.get('template_id'))
	output_fields = template.get('output_fields')
	output_field = output_fields[0].get('name')
	
	input_fields = template.get('input_fields')

	for field in input_fields:
		name = field.get('name')
		if name == 'prompt':
			prompt = field
		elif name == 'num_images':
			num_images = field

	# Check if 'prompt' and 'num_images' were found, or throw an error
	if not prompt or not num_images:
		raise ValueError("Both 'prompt' and 'num_images' fields are required.")
	
	if "dall-e" in task.document.get('model'):
		openai.api_key = task.document.get('openai_token')

		try:
			response = openai.Image.create(
				prompt = task.document.get('prompt')[:1000]
				n=int(task.document.get('num_images')),
				size="1024x1024"
			)
			urls = [[]]

			# Loop over the 'data' list and extract the 'url' from each item
			for item in response['data']:
				if 'url' in item:
					urls[0].append(item['url'])

			task.document[output_field] = urls
		
		except Exception as ex:
			print(ex)
			task.document['error'] = f"exception talking to OpenAI image create: {ex}"
			task.document[output_field] = []
			return task
	else:
		task.document[output_field] = []
 
	return task


@processer
def read_file(node: Dict[str, any], task: Task) -> Task:
	template = Template.get(template_id=node.get('template_id'))
	if not template:
		raise TemplateNotFoundError(template_id=node.get('template_id'))
	output_fields = template.get('output_fields')
	output_field = output_fields[0].get('name')

	user = User.get_by_uid(uid=task.user_id)
	uid = user.get('uid')
	filename = task.document.get('filename')
	mime_type = task.document.get('content_type')

	if mime_type == "application/pdf":
		# Get the document
		gcs = storage.Client()
		bucket = gcs.bucket(app.config['CLOUD_STORAGE_BUCKET'])
		blob = bucket.blob(f"{uid}/{filename}")
		image_content = blob.download_as_bytes()

		# Create a BytesIO object for the PDF content
		pdf_content_stream = BytesIO(image_content)
		pdf_reader = PyPDF2.PdfReader(pdf_content_stream)
		num_pages = len(pdf_reader.pages)

		# processor for document ai
		opts = ClientOptions(api_endpoint=f"us-documentai.googleapis.com")
		client = documentai.DocumentProcessorServiceClient(client_options=opts)
		parent = client.common_location_path(app.config['PROJECT_ID'], "us")
		processor_list = client.list_processors(parent=parent)
		for processor in processor_list:
			name = processor.name
			break # stupid google objects

		pdf_processor = client.get_processor(name=name)

		texts = []

		# build seperate pages and process each, adding text to texts
		for page_num in range(num_pages):
			pdf_writer = PyPDF2.PdfWriter()
			pdf_writer.add_page(pdf_reader.pages[page_num])
			page_stream = BytesIO()
			pdf_writer.write(page_stream)

			# Get the content of the current page as bytes
			page_content = page_stream.getvalue()

			# load data
			raw_document = documentai.RawDocument(content=page_content, mime_type="application/pdf")

			# make request
			request = documentai.ProcessRequest(name=pdf_processor.name, raw_document=raw_document)
			result = client.process_document(request=request)
			document = result.document

			# move to texts
			texts.append(document.text.replace("'","`").replace('"', '``').replace("\n"," ").replace("\r"," ").replace("\t"," "))

			# Close the page stream
			page_stream.close()

	else:
		task.document.update({"error": "This processor only supports PDFs. Upload with type set to `application/pdf`."})
		return task

	# update the document
	task.document[output_field] = texts
	
	return task


@processer
def callback(node: Dict[str, any], task: Task) -> Task:
	template = Template.get(template_id=node.get('template_id'))
	if not template:
		raise TemplateNotFoundError(template_id=node.get('template_id'))
	
	user = User.get_by_uid(uid=task.user_id)
	if not user:
		raise UserNotFoundError(user_id=task.user_id)

	# need to rewrite to allow mapping tokens to the url template
	# alternately we could require a jinja template processor to be used in front of this to build the url
	auth_uri = task.document.get('callback_uri')

	# strip secure stuff out of the document
	document = strip_secure_fields(task.document) # returns document

	keys_to_keep = []
	for field in template.get('output_fields', []):
		for key, value in field.items():
			if key == 'name':
				keys_to_keep.append(value)

	if len(keys_to_keep) == 0:
		data = document
	else:
		data = filter_document(document, keys_to_keep)

	# must add node_id and pipe_id
	data['node_id'] = node.get('node_id')
	data['pipe_id'] = task.pipe_id

	try:
		resp = requests.post(auth_uri, data=json.dumps(data))
		if resp.status_code != 200:
			message = f'got status code {resp.status_code} from callback'
			if resp.status_code in retriable_status_codes:
				raise RetriableError(message)
			else:
				raise NonRetriableError(message)
		
	except (
		requests.ConnectionError,
		requests.HTTPError,
		requests.Timeout,
		requests.TooManyRedirects,
		requests.ConnectTimeout,
	) as exception:
		raise RetriableError(exception)
	except Exception as exception:
		raise NonRetriableError(exception)

	return task


@processer
def read_fb(node: Dict[str, any], task: Task) -> Task:
	user = User.get_by_uid(task.user_id)
	doc = {
		"dbid": user.get('dbid'),
		"db_token": user.get('db_token'),
		"sql": task.document['sql']
		}

	resp, err = featurebase_query(document=doc)
	if err:
		if "exception" in err:
			raise RetriableError(err)
		else:
			# good response from the server but query error
			raise NonRetriableError(err)

	# response data
	fields = []
	data = {}

	for field in resp.schema['fields']:
		fields.append(field['name'])
		data[field['name']] = []

	for tuple in resp.data:
		for i, value in enumerate(tuple):
			data[fields[i]].append(value)

	template = Template.get(template_id=node.get('template_id'))
	if not template:
		raise TemplateNotFoundError(template_id=node.get('template_id'))
	
	_keys = template.get('output_fields')
	if _keys:
		keys = [n['name'] for n in _keys]
		task.document.update(transform_data(keys, data))
	else:
		task.document.update(data)

	return task


from SlothAI.lib.schemar import Schemar
@processer
def write_fb(node: Dict[str, any], task: Task) -> Task:

	auth = {"dbid": task.document['DATABASE_ID'], "db_token": task.document['X-API-KEY']}

	template = Template.get(template_id=node.get('template_id'))
	_keys = template.get('input_fields') # must be input fields but not enforced
	keys = [n['name'] for n in _keys]
	data = get_values_by_json_paths(keys, task.document)

	table = task.document['table']
	tbl_exists, err = table_exists(table, auth)
	if err:
		raise RetriableError("issue checking for table in featurebase")
	
	# if it doesn't exists, create it
	if not tbl_exists:
		create_schema = Schemar(data=data).infer_create_table_schema() # check data.. must be lists
		err = create_table(table, create_schema, auth)
		if err:
			if "exception" in err:
				raise RetriableError(err)
			else:
				# good response from the server but query error
				raise NonRetriableError(err)
			
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

			err = add_column(table, {'name': key, 'type': task.document["schema"][key]}, auth)
			if err:
				if "exception" in err:
					raise RetriableError(err)
				else:
					# good response from the server but query error
					raise NonRetriableError(err)

			column_type_map[key] = task.document["schema"][key]

	columns, records = process_data_dict_for_insert(data, column_type_map, table)

	sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES {','.join(records)};"
	_, err = featurebase_query({"sql": sql, "dbid": task.document['DATABASE_ID'], "db_token": task.document['X-API-KEY']})
	if err:
		if "exception" in err:
			raise RetriableError(err)
		else:
			# good response from the server but query error
			raise NonRetriableError(err)
	
	return task

# remove these
# ============

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


# helper functions
# ================

def validate_document(node, task: Task, validate: DocumentValidator):
	template = Template.get(template_id=node.get('template_id'))
	fields = template.get(validate)
	if fields:
		missing_key = validate_dict_structure(template.get('input_fields'), task.document)
		if missing_key:
			return missing_key
	
	return None


def evaluate_extras(node, task) -> Dict[str, any]:
	# get the node's current extras, which may be templated
	extras = node.get('extras', {})

	# combine with inputs
	combined_dict = extras.copy()
	combined_dict.update(task.document)

	# eval the extras from inputs_fields first
	extras_template = env.from_string(str(combined_dict))
	extras_from_template = extras_template.render(combined_dict)
	extras_eval = ast.literal_eval(extras_from_template)

	# remove the keys that were in the document
	extras_eval = {key: value for key, value in extras_eval.items() if key not in task.document}

	return extras_eval


def clean_extras(extras: Dict[str, any], task: Task):
	if extras:
		for k in extras.keys():
			if k in task.document.keys():
				del task.document[k]
	return task


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

