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
	print("in instructor")
	ip_address = document.get('ip_address')

	password = config.sloth_token
	url = f"http://sloth:{password}@{ip_address}:9898/embed"

	# Set the headers to indicate that you're sending JSON data
	headers = {
		"Content-Type": "application/json"
	}
	print("line 98")
	# Send the POST request with the JSON data
	response = requests.post(url, data=json.dumps(document.get('data')), headers=headers)
	print("line 96")
	# Check the response status code for success
	if response.status_code == 200:
		document['data']['embedding'] = response.json().get('embeddings')
	else:
		document['error'] = f"POST request failed with status code {response.status_code}: {response.text}"
	print("line 102")
	if config.dev == "True":
		with open("dump.txt", "w") as file:
			json.dump(document, file, indent=4)
	print("line 106")
	return document

@model
def ada(document):
	# this needs to be more dynamic, but for now it's hard coded
	# load user's openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	texts = []
	for _text in document.get('data').get('text'): 
		texts.append(_text.replace("\n", " "))

	model = document.get('models').get('embedding')
	embedding_results = openai.Embedding.create(input=texts, model=model)['data']

	embeddings = []
	for _object in embedding_results:
		embeddings.append(_object.get("embedding"))

	document['data']['embedding'] = embeddings

	# process and return

	if config.dev == "True":
		with open("dump.txt", "w") as file:
			json.dump(document, file, indent=4)

	return document

	
@model
def chatgpt_extract_keyterms(document):
	# load user's openai key then drop it from the document
	openai.api_key = document.get('openai_token')

	# build a place to put them
	keyterms = []

	for _text in document.get('data').get('text'):
		# substitute things
		template = load_template("complete_dict_qkg")
		prompt = template.substitute({"text": _text})

		try:
			completion = openai.ChatCompletion.create(
			  model = document.get('models').get('keyterms'),
			  messages = [
				{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, or any text other than the output requested."},
				{"role": "user", "content": prompt}
			  ]
			)
		except Exception as ex:
			print("caught you! ", ex)
			document['error'] = f"exception talking to OpenAI {ex}"
			return document

		answer = completion.choices[0].message
		
		_dict = eval(answer.get('content').replace("\n", ""))
		
		keyterms.append(_dict.get('keyterms'))

	document['data']['keyterms'] = keyterms

	return document


