import re
import random
import string
import secrets
import socket
import ast

import openai

from coolname import generate_slug

from flask import current_app as app
from flask import request
from flask_login import current_user

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


def fields_text_from_template(template):

    # Regular expressions to find input and output fields in the template
    input_pattern = re.compile(r'input_fields\s*=\s*(\[.*?\])', re.DOTALL)
    output_pattern = re.compile(r'output_fields\s*=\s*(\[.*?\])', re.DOTALL)

    input_match = input_pattern.search(template)
    output_match = output_pattern.search(template)

    input_content = input_match.group(1) if input_match else None
    output_content = output_match.group(1) if output_match else None

    return input_content, output_content


def fields_from_template(template):
    input_fields = []
    output_fields = []

    input_content, output_content = fields_text_from_template(template)

    try:
        input_fields = ast.literal_eval(input_content) if input_content else None
        output_fields = ast.literal_eval(output_content) if output_content else None
    except:
        return None, None, {"error": f"{ex}", "message": "Evaluation of inputs/outputs failed."}

    return input_fields, output_fields, False


def extras_from_template(template):
    extras_pattern = re.compile(r'extras\s*=\s*{([\s\S]*?)}\s*', re.DOTALL)
    extras_match = extras_pattern.search(template)

    if extras_match:
        try:
            extras_content = ast.literal_eval("{" + extras_match.group(1) + "}")
            return extras_content, False
        except Exception as ex:
            return None, {"error": f"{ex}", "message": "Evaluation of extras failed."}
    else:
        return None, {"message": f"No extras found."}


# handles merging the extras in from template, user and system definitions
def merge_extras(template_extras, node_extras):
    # Make a copy of template_extras to avoid modifying it directly
    merged_extras = template_extras.copy()

    hostname = request.host
    if "localhost" in hostname:
        protocol = "http"
    else:
        protocol = "https"

    # build the new predefined values from the system
    predefined_values = {
        "username": current_user.name,
        "callback_token": current_user.api_token,
        "callback_uri": protocol + "://" + request.host+"/"+current_user.name+"/callback?token={{extras.api_token}}"
    }

    for key, value in merged_extras.items():
        if value:
            if "[" in value and "]" in value:
                try:
                    merged_extras[key] = predefined_values[key]
                except:
                    pass

    if node_extras:
        for key, value in node_extras.items():
            if key in merged_extras:
                merged_extras[key] = node_extras[key]
            else:
                merged_extras[key] = value

    return merged_extras


def jinja_from_template(template):
    if not isinstance(template, str):
        return ""

    jinja = template[:]
    
    input_content, output_content = fields_text_from_template(template)
    extras_content = extras_from_template(template)

    # remove jinja comments
    jinja = re.sub(r'{#.*?#}', '', jinja)
    jinja = re.sub(r'{#.*?#}', '', jinja)
    jinja = re.sub(r'{#.*?#}', '', jinja)
    inp = re.compile(r'\s*input_fields\s*=\s*')
    out = re.compile(r'\s*output_fields\s*=\s*')
    jin = re.compile(r'\s*extras\s*=\s*')
    jinja = re.sub(inp, '', jinja)
    jinja = re.sub(out, '', jinja)
    jinja = re.sub(jin, '', jinja)
    if input_content:
        jinja = jinja.replace(input_content, '')
    if output_content:
        jinja = jinja.replace(output_content, '')
    if extras_content:
        jinja = jinja.replace(extras_content, '')

    return jinja
