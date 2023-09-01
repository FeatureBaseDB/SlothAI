import os
import sys
import random
import string
import time
import json

import requests
from string import Template

import config

# random strings
def random_string(size=6, chars=string.ascii_letters + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))


###############
# FeatureBase #
###############

def drop_database(name):
	# create FeatureBase database
	fb_query = featurebase_query(
		{
			"sql": f"DROP TABLE {name};",
			"dbid": f"{auth.get('dbid')}",
			"token": f"{auth.get('token')}" 
		}
	)


def create_database(name, schema, auth):
	# create FeatureBase database
	fb_query = featurebase_query(
		{
			"sql": f"CREATE TABLE {name} {schema};",
			"dbid": f"{auth.get('dbid')}",
			"token": f"{auth.get('token')}" 
		}
	)

	# check status
	if fb_query.get('error'):
		if "exists" in fb_query.get('error'):
			print(f"FeatureBase database `{name}` already exists.")
		else:
			print(fb_query.get("explain"))
			print("FeatureBase returned an error. Check your credentials or create statement!")
	else:
		print(f"Created `{name}` database on FeatureBase Cloud.")


def apply_schema(list_of_lists, schema):
	result = []
	for row in list_of_lists:
		dict_row = {}
		for i, val in enumerate(row):
			dict_row[schema[i]] = val
		result.append(dict_row)
	return result


# "sql" key in document should have a valid query
def featurebase_query(document, debug=False):
	# try to run the query
	try:
		sql = document.get("sql")
		dbid = document.get('dbid')
		token = document.get('token')
		
		result = requests.post(
			url=f"{config.featurebase_endpoint}{dbid}/query/sql",
			data=sql.encode('utf-8'),
			headers={
				'Content-Type': 'text/plain',
				'X-API-Key': f"{token}",
			}
		)
		print(result.text)

		if debug:
			print(document.get('sql'))
			print(json.dumps(result.text))
		
		if json.loads(result.text).get('message'):
			if json.loads(result.text).get('message') == "unauthorized":
				document['message'] = "unauthorized"
				return document
		
		result = result.json()

	except Exception as ex:
		# bad query?
		print("error: ", ex)
		exc_type, exc_obj, exc_tb = sys.exc_info()
		document['error'] = "%s: %s" % (exc_tb.tb_lineno, ex)
		return document

	if result.get('error', ""):
		# featurebase reports and error
		document['explain'] = "Error returned by FeatureBase: %s" % result.get('error')
		document['error'] = result.get('error')
		document['data'] = result.get('data')

	elif 'data' in result:
		# got some data back from featurebase
		document['data'] = result.get('data')
		document['schema'] = result.get('schema')
		document['execution-time'] = result.get('execution-time')

		field_names = []

		for field in result.get('schema').get('fields'):
			field_names.append(field.get('name'))

		document['results'] = apply_schema(result.get('data'), field_names)
	else:
		document['explain'] = "Query was successful, but returned no data."

	return document
