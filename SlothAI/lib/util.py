import re
import random
import string
import secrets
import socket

from coolname import generate_slug

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