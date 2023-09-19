import json
import config
import threading
from flask import Blueprint
from flask import request
from lib.util import random_string
from lib.ai import ai
from lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from lib.tasks import create_task, box_required, create_dead_letter
from web.models import User, Table, Models

tasks = Blueprint('tasks', __name__)

def print_debug(text):
	if hasattr(config, 'debug') and config.debug:
		print(text)

class RetryException(Exception):
	pass

class NonRetryException(Exception):
	pass

@tasks.route('/tasks/process/<cron_key>/<uid>', methods=['POST'])
def start_tasks(cron_key, uid):
	if cron_key != config.cron_key:
		return "ERROR: auth", 401

	task_payload = request.get_data(as_text=True)
	thread = threading.Thread(target=process_task, args=(task_payload, uid))
	thread.start()
	return "success", 200

def process_task(task_payload, uid):
	try:
		document = json.loads(task_payload)
		if "data" not in document.keys():
			raise NonRetryException('tasks payload must contain a "data" key')
		data = document['data']
		if "text" not in data.keys():
			raise NonRetryException('tasks payload must contain a "text" key in the "data" element')

		user = User.get_by_uid(uid)
		if not user:
			raise RetryException('Not authenticated. Flushing request.')

		table = Table.get_by_uid_tid(uid, document.get('tid'))
		if not table:
			raise RetryException('Can\'t find the table specified. Flushing request.')

		defer, selected_box = box_required(table.get('models'))

		if defer:
			raise RetryException('Models requiring boxes get deferred')

		if selected_box:
			document['ip_address'] = selected_box.get('ip_address')

		run_model(document)

		insert_data(document, user)

	except (json.JSONDecodeError, NonRetryException) as e:
		print(f"task failed with error: {task_payload}: {e}... sending to dead letter queue.")
		create_dead_letter({'payload': str(task_payload), 'error': str(e)})
	except RetryException as e:
		if 'attempt_num' not in document:
			document['attempt_num'] = 1
	
		if document['attempt_num'] > 4:
			create_dead_letter(document)
			return
		else:
			document['attempt_num'] += 1
	
		if 'ip_address' in document:
			del document['ip_address']
		if 'error' in document:
			del document['error']
		create_task(document)
	except Exception as e:
		import traceback
		traceback.print_exc()
		print(e)
		print("ERROR: unhandled exception. task won't be retried")

def run_model(document):
	if not document.get('models', None):
		# no models, do nothing
		return

	#  (੭｡╹▿╹｡)੭
	# popping ai methods called by name from document.embedding -> lib/ai.py
	for kind in ['embedding', 'keyterms']:		
		model = Models.get_by_name(document['models'].get(kind, None))
		ai_model = model.get('ai_model', None) if model else None
		if not ai_model:
			# no ai_model found, nothing to do
			continue

		if 'gpt' not in model.get('name'):
			# our models
			document = ai(ai_model, document)

			if 'error' in document:
				raise RetryException(f"got error in {kind}: {document['error']}")
		else:
			print("calling AI")
			# stack the calls to OpenAI
			if not document.get('text_stack', None):
				document['text_stack'] = document.get('data').get('text').copy()

			target = document.get('text_stack').pop()
			document['text_target'] = target

			document = ai(ai_model, document)

			if document.get('error', None):
				document['text_stack'].append(target)
				raise RetryException(f"got error in {kind}: {document['error']}")

			if len(document.get('text_stack')) > 0:
				raise RetryException("text_stack is not empty, requeue")

			document.get('models').pop(kind) # pop the run model off the document

def insert_data(document, user):
	data = document['data']
	auth = {"dbid": user.get('dbid'), "db_token": user.get('db_token')}
	tbl_exists, err = table_exists(document.get('name'), auth)
	if err:
		raise RetryException(err)
	
	if "_id" not in data.keys():
		data['_id'] = "string"
	
	if not tbl_exists:
		ai("chatgpt_table_schema", document)
		if "error" in document.keys():
			raise RetryException(document.get('error'))
		err = create_table(document.get('name'), document['create_schema_string'], auth)
		if err:
			raise RetryException(err)

	columns, err = get_columns(document.get('name'), auth)
	if err:
		raise RetryException(err)
	columns = [k for k in columns.keys()]

	for key in data.keys():
		if key not in columns:
			if not document.get("create_schema_dict", None):
				ai("chatgpt_table_schema", document)
				if "error" in document.keys():
					raise RetryException(document.get('error'))
			err = add_column(document.get('name'), {'name': key, 'type': document["create_schema_dict"][key]}, auth)
			if err:
				raise RetryException(err)

	values = []
	value_columns = []
	for i in range(len(data['text'])):
		value = "("
		for column in columns:
			if column == "_id":
				value += f"'{random_string(6)}', "
				if i == 0:
					value_columns.append(column)
				continue
			if data.get(column, None) and len(data[column]) > i:
				if i == 0:
					value_columns.append(column)
				v = data[column][i]
				if isinstance(v, str):
					v = f"'{v}'"
				value += f"{v}, "
		values.append(value[:-2] + ")")

	sql = f"INSERT INTO {document.get('name')} ({','.join(value_columns)}) VALUES {','.join(values)};"
	_, err = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})
	if err:
		print(f"failed to insert data: {err}")
		raise RetryException(f"failed to insert data: {err}")
	else:
		return "success", 200
	
@tasks.route('/tasks/dead-letter/<cron_key>/<uid>', methods=['POST'])
def dead_letter(cron_key, uid):
	return "going to dead letter queue", 400