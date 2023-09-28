import json
from flask import Blueprint
from flask import request
from flask import current_app as app
from SlothAI.lib.util import random_string
from SlothAI.lib.ai import ai
from SlothAI.lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from SlothAI.lib.tasks import box_required, create_task, get_task_schema, retry_task
from SlothAI.lib.schemar import string_to_datetime, datetime_to_string
from SlothAI.web.models import User, Table, Models

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks/process/<cron_key>/<uid>', methods=['POST'])
def start_tasks(cron_key, uid):
	# validate call with a key
	if cron_key != app.config['CRON_KEY']:
		print(f"ERROR: invalid cron_key. dropping task.")
		return f"Not authenticated. Flushing request.", 200

	# verify user
	user = User.get_by_uid(uid)
	if not user:
		print(f"ERROR: user not found. dropping task.")
		return f"Not authenticated. Flushing request.", 200

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)
	document = json.loads(task_payload)

	# check we have the table still (user could delete since ingestion)
	table = Table.get_by_uid_tid(uid, document.get('tid'))
	if not table:
		print(f"ERROR: table with id {document.get('tid')} not found. dropping task.")
		return f"Can't find the table specified. Flushing request.", 200

	# models requiring boxes get deferred
	defer, selected_box = box_required(table.get('models'))
	if defer:
		return f"Starting GPUs...", 418 # return resource starting 

	# grab the IP for locally run models and stuff it into the document
	if selected_box:
		document['ip_address'] = selected_box.get('ip_address')

	#  (੭｡╹▿╹｡)੭
	# popping ai methods called by name from document.embedding -> lib/ai.py
	models = document.get('models', []).copy()
	for _model in models:
		# rework this soon to get the model flavor not in the name
		document = ai(_model.get('ai_model', None), _model, document)
		if 'error' in document:
			return f"got error in {_model}: {document['error']}", 400
		
		document['models'].remove(_model)

	# at this point we should have data for every text element for every model.
	auth = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	tbl_exists, document['error'] = table_exists(document.get('name'), auth)
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200

	if not tbl_exists:
		document = get_task_schema(document)
		if document.get("error", None):
			print(f"ERROR: {document['error']}. dropping task.")
			return document['error'], 200
		
		# new tables always have id keys
		schema = "(_id id, " + ", ".join([f"{fld} {typ}" for fld, typ in document.get('schema', {}).items()]) + ")"
		
		document['error'] = create_table(document.get('name'), schema, auth)
		if document.get("error", None):
			retry_task(document)
			return "retrying", 200

	columns_dict, document['error'] = get_columns(document.get('name'), auth)
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200
	
	columns = [k for k in columns_dict.keys()]

	# add columns if data key cannot be found as an existing column
	for key in document['data'].keys():
		if key not in columns:
			if not document.get("schema", None):
				document = get_task_schema(document)
				if document.get("error", None):
					print(f"ERROR: {document['error']}. dropping task.")
					return document['error'], 200
			document['error'] = add_column(document.get('name'), {'name': key, 'type': document["schema"][key]}, auth)
			if document['error']:
				retry_task(document)
				return "retrying", 200
			columns_dict[key] = document["schema"][key]

	values = []
	value_columns = []
	document['data']['_id'] = 'dummy_value'

	for i in range(len(document['data']['text'])):
		value = "("
		for column in document['data'].keys():
			if column == "_id":
				if columns_dict['_id'] == "string":
					value += f"'{random_string(6)}', "
				else: # id
					value += f"identifier('{document.get('name')}'), "
				if i == 0:
					value_columns.append(column)
				continue
			if len(document['data'][column]) > i:
				if i == 0:
					value_columns.append(column)
				v = document['data'][column][i]
				typ = columns_dict[column]
				if "timestamp" in typ: # format timestamp
					dt = string_to_datetime(v)
					v = datetime_to_string(dt)
				if isinstance(v, str):
					v = v.replace("'", "''")
					v = f"'{v}'" 
				value += f"{v}, "
		values.append(value[:-2] + ")")

	sql = f"INSERT INTO {document.get('name')} ({','.join(value_columns)}) VALUES {','.join(values)};"
	_, document['error'] = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})
	if document.get("error", None):
		retry_task(document)
		return "retrying", 200
	else:
		return "success", 200