import os
import sys
import datetime
import random
import string
import requests

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

def ai(model_name="none", document={}):
	# get the user's API token	
	openai_token = config.openai_token

	if not openai_token:
		# rewrite to match document flow
		document['error'] = "model %s errors with no token." % (model_name)
		document['explain'] = "I encountered an error talking with OpenAI."
		return document
	else:
		# set token for model to use
		document['openai_token'] = openai_token

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
def chatgpt_complete_dict(document):
	# load openai key then drop it from the document
	openai.api_key = document.get('openai_token')
	document.pop('openai_token', None)

	try:
		# substitute things
		template = load_template("complete_dict_qkg")
		prompt = template.substitute(document)

		completion = openai.ChatCompletion.create(
		  model = config.completion_model,
		  messages = [
			{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, or any text other than the output requested."},
			{"role": "user", "content": prompt}
		  ]
		)
		answer = completion.choices[0].message
		print("==========")
		print(answer)
		print("==========")

	except Exception as ex:
		print("EXECPTION")
		print(ex)
		answer = "Call to OpenAI chat failed: %s" % ex

	ai_dict = eval(answer.get('content').replace("\n", ""))
	
	return ai_dict


