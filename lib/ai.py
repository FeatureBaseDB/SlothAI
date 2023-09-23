import os
import sys
import datetime
import random
import string
import requests
import json
import time
import ast
import re

import openai

import traceback
from string import Template

from lib.database import featurebase_query

import config

# supress OpenAI resource warnings for unclosed sockets
import warnings
warnings.filterwarnings("ignore")

# AI model call by method name
models = {}
model = lambda f: models.setdefault(f.__name__, f)

# unhardcode this # TODO
# does not include schemer model as that uses our token, not the user's
openai_token_required_models = ["chatgpt_extract_keyterms", "ada"]

def ai(model_method, model, document={}):
	# get the user's API token, if available
	openai_token = document.get('openai_token')
	
	if not openai_token and document.get('model') in openai_token_required_models:
		# rewrite to match document flow
		document['error'] = "model %s errors with no token" % (model_method)
		document['explain'] = "I encountered an error talking with OpenAI."

	# call the model
	try:
		document = models[model_method](model, document)

	except Exception as ex:
		if config.dev:
			print(traceback.format_exc())
		print(traceback.format_exc())
		document['error'] = "model *%s* errors with %s." % (model_method, ex)
		document['explain'] = "I encountered an error talking with my AI handler."

	return document

# helper functions
# ================

# load template
def load_template(name="default"):
	# file path
	file_path = "./templates/prompts/%s.txt" % (name)

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
	try:
		completion = openai.ChatCompletion.create(
			model = model,
			messages = [
			{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, or any text other than the output requested."},
			{"role": "user", "content": prompt}
			]
		)
	except Exception as ex:
		print(ex)
		document['error'] = f"exception talking to OpenAI chat completion: {ex}"
		return document

	answer = completion.choices[0].message

	ai_dict_str = answer.get('content').replace("\n", "").replace("\t", "").lower()
	ai_dict_str = re.sub(r'\s+', ' ', ai_dict_str).strip()

	try:
	    ai_dict = ast.literal_eval(ai_dict_str)
	except (ValueError, SyntaxError):
	    print("Error: Invalid JSON format in ai_dict_str.")
	    ai_dict = {}

	return ai_dict


# model functions
# ===============
@model 
def instructor(ai_model, document):
	ip_address = document.get('ip_address') # TODO: move this into the model

	password = config.sloth_token
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

@model 
def sloth_keyterms(ai_model, document):
	ip_address = document.get('ip_address')

	password = config.sloth_token
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


@model
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

	
@model
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


# handle old name
@model
def chatgpt_extract_keyterms(ai_model, document):
	return  gpt_keyterms(ai_model, document)


# get a question	
@model
def gpt_question(ai_model, document):
	# load openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	for _text in document.get('data').get('text'):

		# substitute things
		try:
			template = load_template("form_question")
			prompt = template.substitute({"text": _text})
		except Exception as ex:
			print(ex)
			document['error'] = "template wouldn't load"
			return document

		# get the template's dict
		ai_dict = gpt_dict_completion(prompt, ai_model.get('name'))

		# extract the question and stuff into the document
		if document.get('data', None):
			if document.get('data').get('questions', None):
				document['data']['questions'].append(ai_dict.get('question'))
			else:
				document['data']['questions'] = [ai_dict.get('question')]

	return document