from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request

import flask_login
from flask_login import current_user

from lib.ai import ai
from lib.tasks import create_task, get_task_schema, box_required
from lib.database import get_columns, get_unique_column_values

from web.models import Table, Models

table = Blueprint('table', __name__)

# client connection
client = ndb.Client()

# API HANDLERS
@table.route('/tables/list', methods=['GET'])
@flask_login.login_required
def tables_list():
	return None

# API QUERY
@table.route('/tables/<tid>/query', methods=['POST'])
@flask_login.login_required
def query(tid):
	table = Table.get_by_uid_tid(current_user.uid, tid)

	if table:
		try:
			json_data = request.get_json()
		except Exception as ex:
			return jsonify({"response": f"Check your JSON! {ex}"}), 400

		if not json_data.get('query', None):
			return jsonify({"response": "'query' field is required"}), 406 # todo get error code

	# populate with the query and the table name
	document = {"query": f"{json_data.get('query')}", "table_name": table.get("name")}

	emb = {"data": {"text": json_data.get('query')}}

	# models requiring boxes get deferred
	defer, selected_box = box_required(table.get('models'))
	if defer:
		return f"Starting GPUs...", 418 # return resource starting
	
	# grab the IP for locally run models and stuff it into the document
	if selected_box:
		emb['ip_address'] = selected_box.get('ip_address')

	for model in table.get('models', None):
		kind = model.get('kind', None)
		if kind == 'embedding':
			ai_model = model.get('ai_model', None)
			ai(ai_model, model, emb) #emb['data']['']

	# use the table and get the column schema
	auth = {"dbid": current_user.dbid, "db_token": current_user.db_token}
	document['columns'] = get_columns(table.get('name'), auth)[0]

	document = ai("query_analyze", "gpt-3.5-turbo", document)
	print(document)
	document = {"sql": document.get('sql'), "explain": f"{document.get('explain')}"}

	return document, 200


# Distinct values
@table.route('/tables/<tid>/unique_values', methods=['GET'])
@flask_login.login_required
def set_values(tid):
	table = Table.get_by_uid_tid(current_user.uid, tid)
	if table:
		try:
			json_data = request.get_json()
		except Exception as ex:
			return jsonify({"response": f"request data must be valid JSON: {ex}"}), 400

		if not json_data.get('columns', None):
			return jsonify({"response": "'columns' field with list of column names is required"}), 400
		else:
			columns = json_data['columns']
			if not isinstance(columns, list):
				return jsonify({"response": "'columns' field with list of column names is required"}), 400


	# use the table and get the column schema
	auth = {"dbid": current_user.dbid, "db_token": current_user.db_token}

	vals, err = get_unique_column_values(table.get("name"), columns, auth)
	if err:
		return jsonify({"error": err}), 400

	return jsonify(vals), 200

# API INGEST
@table.route('/tables/<tid>/ingest', methods=['POST'])
@flask_login.login_required
def ingest_post(tid):
	table = Table.get_by_uid_tid(current_user.uid, tid)
	
	if table:
		try:
			json_data = request.get_json()
		except Exception as ex:
			return jsonify({"response": f"Check your JSON! {ex}"}), 400

		if not json_data.get('text', None):
			return jsonify({"response": "'text' field is required"}), 406 # todo get error code

		# move to data
		document = {"data": json_data}
		if 'text' in json_data: # TODO: make this configurable by the user
			text_value = json_data['text']
			if not isinstance(text_value, list):
				# If 'text' is not an array, convert it to a single-element list
				json_data['text'] = [text_value]
		else:
			return jsonify({"response": "need 'text' field..."})

		print("get task schema")
		print(document)
		# don't create a task if there is going to be an issue converting user
		# data to a valid schema.
		document = get_task_schema(document)
		if document.get('error', None):
			return jsonify({"error": document['error']}), 400

		# this populates the model object in the document
		# map table document to document (includes uid, etc.)
		document.update(table)
		document['retries'] = 0

		# write to the job queue
		job_id = create_task(document)
		document['job_id'] = job_id

		# pop secure info
		document.pop('openai_token')
		document.pop('uid')

		return jsonify(document), 200
	else:
		return jsonify({"response": f"table with id {tid} not found"}), 404


# API DELETE
@table.route('/tables/<tid>', methods=['DELETE'])
@flask_login.login_required
def table_delete(tid):
	# find the user's table
	table = Table.get_by_uid_tid(current_user.uid, tid)

	# Prepare JSON response data
	json_data = {"response": "success", "message": "Table deleted successfully!"}

	if table:
		# delete table
		Table.delete(table.get('tid'))
		flash(f"Deleted table `{table.get('name')}`.")
		return jsonify(json_data), 200
	else:
		json_data['response'] = "error"
		json_data['message'] = "Error deleting table."
		return jsonify(json_data), 501


# API ADD
@table.route('/tables', methods=['POST'])
@flask_login.login_required
def tables_add():
	tables = Table.get_all_by_uid(uid=current_user.uid)

	# Check if the request contains JSON data
	if request.is_json:
			json_data = request.get_json()

			_models = []
			for _model in json_data.get('mids'):
				model = Models.get_by_mid(_model)
				_models.append(model)

			_table = Table.create(
				current_user.uid, 
				json_data.get('tableName'), 
				_models,
				json_data.get('openaiToken')
			)

			if _table:
				return jsonify(_table), 200
	
	return "error", 501
