import json
import config
import threading
from flask import Blueprint
from flask import request
from lib.util import random_string
from lib.ai import ai
from lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from lib.tasks import box_required, create_task, get_task_schema
from web.models import User, Table, Models

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks/process/<cron_key>/<uid>', methods=['POST'])
def start_tasks(cron_key, uid):
	# validate call with a key
	if cron_key != config.cron_key:
		return "error auth", 401

	# verify user
	user = User.get_by_uid(uid)
	if not user:
		return f"Not authenticated. Flushing request.", 200

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)
	document = json.loads(task_payload)

	# check we have the table still (user could delete since ingestion)
	table = Table.get_by_uid_tid(uid, document.get('tid'))
	if not table:
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
		# TODO: refactor for clarity as this uses the AI model decorator		
		ai_model = Models.get_by_name(_model.get("name")).get('ai_model', None)
		
		if ai_model:
			if 'gpt' not in ai_model:
				document = ai(ai_model, document)
				if 'error' in document:
					return f"got error in {_model}: {document['error']}", 400
			else:
				# stack the calls to OpenAI
				print("calling AI")
				if not document.get('text_stack', None):
					# TODO: referencing text but we want to make that variable
					document['text_stack'] = document.get('data').get('text').copy()

				target = document.get('text_stack').pop()
				document['text_target'] = target

				document = ai(ai_model, document)

				# for now the queue max retries is 13, see queue.yaml
				if document.get('error', None):
					return f"got error in {_model['name']}: {document['error']}", 429 # too many requests

				if len(document.get('text_stack')) > 0:
					create_task(document)
					return f"delete the current document", 200
		
		document['models'].remove(_model)

	# at this point we should have data for every text element for every model.
	auth = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	tbl_exists, err = table_exists(document.get('name'), auth)
	if err:
		# TODO: we need to store retries in the document
		# HUGE CALLOUT: dropping document
		print(err)
		return err, 200

	# TODO: use id keys with create table
	if not tbl_exists:
		document = get_task_schema(document)
		if document.get("error", None):
			# TODO: we need to store retries in the document
			# HUGE CALLOUT: dropping document
			print(document['error'])
			return err, 200
		
		schema = "(_id id, " + ", ".join([f"{fld} {typ}" for fld, typ in document.get('schema', {}).items()]) + ")"
		
		err = create_table(document.get('name'), schema, auth)
		if err:
			# TODO: we need to store retries in the document
			# HUGE CALLOUT: dropping document
			print(document['error'])
			return err, 200

	columns, err = get_columns(document.get('name'), auth)
	if err:
		# TODO: we need to store retries in the document
		# HUGE CALLOUT: dropping document
		print(document['error'])
		return err, 200
	
	columns = [k for k in columns.keys()]

	for key in document['data'].keys():
		if key not in columns:
			if not document.get("schema", None):
				document = get_task_schema(document)
				if document.get("error", None):
					# TODO: we need to store retries in the document
					# HUGE CALLOUT: dropping document
					print(document['error'])
					return err, 200
			err = add_column(document.get('name'), {'name': key, 'type': document["schema"][key]}, auth)
			if err:
				# TODO: we need to store retries in the document
				# HUGE CALLOUT: dropping document
				print(document['error'])
				return err, 200

	values = []
	value_columns = []
	document['data']['_id'] = 'dummy_value'
	for i in range(len(document['data']['text'])):
		value = "("
		for column in document['data'].keys():
			if column == "_id":
				value += f"identifier('{document.get('name')}'), "
				if i == 0:
					value_columns.append(column)
				continue
			if len(document['data'][column]) > i:
				if i == 0:
					value_columns.append(column)
				v = document['data'][column][i]
				if isinstance(v, str):
					v = v.replace("'", "''")
					v = f"'{v}'" 
				value += f"{v}, "
		values.append(value[:-2] + ")")

	sql = f"INSERT INTO {document.get('name')} ({','.join(value_columns)}) VALUES {','.join(values)};"
	_, err = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})
	if err:
		# TODO: we need to store retries in the document
		# HUGE CALLOUT: dropping document
		print(f"failed to insert data: {err}")
		return err, 200
	else:
		return "success", 200
