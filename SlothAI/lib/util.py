import re
import random
import string
import secrets
import socket

import openai

from coolname import generate_slug

from flask import current_app as app

def random_number(size=6, chars=string.digits):
	return ''.join(random.choice(chars) for _ in range(size))


def random_string(size=6, chars=string.ascii_letters + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))


def random_name(size=3):
	return generate_slug(size)

def generate_token(size=30):
	# generate a secrets token, less the dashes for better copy pasta
	return secrets.token_urlsafe(size).replace('-','')

def handle_quotes(object):
	if isinstance(object, str):
		pattern = r"(?<!')'(?!')"
		object = re.sub(pattern, "''", object)
	if isinstance(object, list):
		for i, _ in enumerate(object):
			object[i] = handle_quotes(object[i])
	return object

def check_webserver_connection(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        s.close()
        return True
    except Exception as e:
        return False


# load template
def load_template(name="default"):
	from string import Template

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


# called only by our stuff
def gpt_dict_completion(document=None, template="just_a_dict", model="gpt-3.5-turbo", alt_token=""):
	
	if not document:
		document = {
			"instructions": "generate a short list of keyterms with the key 'keyterms':",
			"text": "[generate_random_keyterms]"
		}
	
	# load openai key then drop it from the document
	try:
		openai.api_key = app.config['OPENAI_TOKEN']
	except:
		openai.api_key = alt_token

	# substitute things
	try:
		template = load_template(template)
		prompt = template.substitute(document)
		print(prompt)
	except Exception as ex:
		print(ex)
		return document
	completion = openai.ChatCompletion.create(
		model = model,
		messages = [
		{"role": "system", "content": "You write python dictionaries for the user. You don't write code, use preambles, text markup, or any text other than the output requested, which is a python dictionary."},
		{"role": "user", "content": prompt}
		]
	)

	answer = completion.choices[0].message

	ai_dict_str = answer.get('content').replace("\n", "").replace("\t", "").lower()
	ai_dict_str = re.sub(r'\s+', ' ', ai_dict_str).strip()
	ai_dict_str = ai_dict_str.strip('python_dict = ')

	print(ai_dict_str)
	try:
		ai_dict = eval(ai_dict_str)
	except (ValueError, SyntaxError):
		print("Error: Invalid format in ai_dict_str.")
		ai_dict = {}

	return ai_dict
