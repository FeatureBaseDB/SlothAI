import json
from flask import Blueprint
from flask import request
from flask import current_app as app
from SlothAI.lib.ai import ai
from SlothAI.lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from SlothAI.lib.tasks import box_required, get_task_schema, retry_task, process_data_dict_for_insert, Task, box_required_for_node
from SlothAI.web.models import User, Pipeline

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks/process/<cron_key>', methods=['POST'])
def process_tasks(cron_key):
	# validate call with a key
	if cron_key != app.config['CRON_KEY']:
		print(f"ERROR: invalid cron_key. dropping task.")
		return f"Not authenticated. Flushing request.", 200

	# Parse the task payload sent in the request.
	task_payload = request.get_data(as_text=True)
	task = Task.from_json(task_payload)

	# verify user
	user = User.get_by_uid(task.user_id)
	if not user:
		print(f"ERROR: user not found. dropping task.")
		return f"Not authenticated. Flushing request.", 200

	# check we have the pipeline still (user could delete since ingestion)
	pipeline = Pipeline.get(uid=task.uid, pipe_id=task.pipe_id)
	if not pipeline:
		print(f"ERROR: table with id {task.pipe_id} not found. dropping task.")
		return f"Can't find the table specified. Flushing request.", 200

	node = task.next_node()
	model = node.get('extras').get('model')

	# models requiring boxes get deferred
	defer, selected_box = box_required_for_node(node) # COULD BE WRONG
	if defer:
		return f"Starting GPUs...", 418 # return resource starting 

	# grab the IP for locally run models and stuff it into the document
	if selected_box:
		task.document['ip_address'] = selected_box.get('ip_address')


	# rework this soon to get the model flavor not in the name
	document, requeue = ai(_model.get('ai_model', None), _model, document)
	if 'error' in document:
		return f"got error in {_model}: {document['error']}", 400
	
	document['models'].remove(_model)
















	# # at this point we should have data for every text element for every model.
	# auth = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	# tbl_exists, document['error'] = table_exists(document.get('name'), auth)
	# if document.get("error", None):
	# 	retry_task(document)
	# 	return "retrying", 200

	# if not tbl_exists:
	# 	document = get_task_schema(document)
	# 	if document.get("error", None):
	# 		print(f"ERROR: {document['error']}. dropping task.")
	# 		return document['error'], 200
		
	# 	# new tables always have id keys
	# 	schema = "(_id id, " + ", ".join([f"{fld} {typ}" for fld, typ in document.get('schema', {}).items()]) + ")"
		
	# 	document['error'] = create_table(document.get('name'), schema, auth)
	# 	if document.get("error", None):
	# 		retry_task(document)
	# 		return "retrying", 200

	# column_type_map, document['error'] = get_columns(document.get('name'), auth)
	# if document.get("error", None):
	# 	retry_task(document)
	# 	return "retrying", 200
	
	# columns = [k for k in column_type_map.keys()]

	# # add columns if data key cannot be found as an existing column
	# for key in document['data'].keys():
	# 	if key not in columns:
	# 		if not document.get("schema", None):
	# 			document = get_task_schema(document)
	# 			if document.get("error", None):
	# 				print(f"ERROR: {document['error']}. dropping task.")
	# 				return document['error'], 200
	# 		document['error'] = add_column(document.get('name'), {'name': key, 'type': document["schema"][key]}, auth)
	# 		if document['error']:
	# 			retry_task(document)
	# 			return "retrying", 200
	# 		column_type_map[key] = document["schema"][key]


	# records = []
	# columns = ['_id'] + list(document['data'].keys())

	# columns, records = process_data_dict_for_insert(document['data'], column_type_map, document.get('name'))

	# sql = f"INSERT INTO {document.get('name')} ({','.join(columns)}) VALUES {','.join(records)};"
	# print(sql[:200])
	# _, document['error'] = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})
	# if document.get("error", None):
	# 	retry_task(document)
	# 	return "retrying", 200
	# else:
	# 	return "success", 200
