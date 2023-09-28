import random
import string
import secrets

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