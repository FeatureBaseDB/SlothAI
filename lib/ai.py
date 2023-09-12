import os
import sys
import datetime
import random
import string
import requests
import json
import time

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

def ai(model_name="none", document={}):
	# get the user's API token, if available
	openai_token = document.get('openai_token')
	
	if not openai_token and document.get('model') in openai_token_required_models:
		# rewrite to match document flow
		document['error'] = "model %s errors with no token" % (model_name)
		document['explain'] = "I encountered an error talking with OpenAI."
		return document

	# call the model
	try:
		document = models[model_name](document)
		return document

	except Exception as ex:
		if config.dev == "True":
			print(traceback.format_exc())

		document['error'] = "model *%s* errors with %s." % (model_name, ex)
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


# model functions
# ===============
@model 
def instructor(document):
	ip_address = document.get('ip_address')
	password = config.sloth_token
	url = f"http://sloth:{password}@{ip_address}:9898/embed"

	# Set the headers to indicate that you're sending JSON data
	headers = {
		"Content-Type": "application/json"
	}


	# Send the POST request with the JSON data
	response = requests.post(url, data=json.dumps(document), headers=headers)

	# Check the response status code for success
	if response.status_code == 200:
		document['embeddings'] = response.json().get('embeddings')
	else:
		print(f"POST request failed with status code {response.status_code}: {response.text}")


	return document

@model
def ada(document):
	# this needs to be more dynamic, but for now it's hard coded
	# load user's openai key then drop it from the document
	openai.api_key = document.get('openai_token')
	document.pop('openai_token', None)

	# overide document.get('model') (until we can have those verified)
	model = document.get('model')

	# more hard coding security(TODO)
	if model not in ["gpt-4", "gpt-3.5-turbo"]:
		raise Exception(f"model {model} not found")

	texts = []
	for _text in document.get('text'): 
		texts.append(_text.replace("\n", " "))

	ai_document = openai.Embedding.create(input=texts, model=model)['data']

	# process and return
	return ai_document

	
@model
def chatgpt_extract_keyterms(document):
	# load user's openai key then drop it from the document
	openai.api_key = document.get('openai_token')
	document.pop('openai_token', None)

	# build a place to put them
	keyterms = []

	for _text in document.get('text'):
		# substitute things
		template = load_template("complete_dict_qkg")
		prompt = template.substitute({"text": _text})

		try:
			completion = openai.ChatCompletion.create(
			  model = config.completion_model,
			  messages = [
				{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, or any text other than the output requested."},
				{"role": "user", "content": prompt}
			  ]
			)
		except Exception as ex:
			print("caught you! ", ex)

		answer = completion.choices[0].message
		
		_dict = eval(answer.get('content').replace("\n", ""))
		
		keyterms.append(_dict.get('keyterms'))

	document['keyterms'] = keyterms

	return document


