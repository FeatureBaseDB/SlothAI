import json
import config
import threading
from flask import Blueprint
from flask import request
from lib.util import random_string
from lib.ai import ai
from lib.database import featurebase_query, create_table, table_exists, get_columns, add_column
from lib.tasks import create_task, box_required
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
		print(f"task aborted with error: {task_payload}: {e}")
		# cannot decode the payload or some other non retryable error, do nothing
		return
	except RetryException as e:
		if 'ip_address' in document:
			del document['ip_address']
		if 'error' in document:
			del document['error']
		create_task(document)
	except Exception as e:
		print("YOU NEED TO LOOK AT THIS: unhandled exception. task won't be retried but maybe it should be?")
		return

	

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
			ai(ai_model, document)
			if 'error' in document:
				raise RetryException(f"got error in {kind}: {document['error']}")
		else:

			if not document.get('text_stack', None):
				document['text_stack'] = document.get('data').get('text').copy()

			target = document.get('text_stack').pop()
			document['text_target'] = target

			ai(ai_model, document)
			if document.get('error', None):
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
	
	ai("chatgpt_table_schema", document)
	if "error" in document.keys():
		raise RetryException(document.get('error'))
	
	if not tbl_exists:
		err = create_table(document.get('name'), document['create_schema_string'], auth)
		if err:
			raise RetryException(err)

	else:
		cols, err = get_columns(document.get('name'), auth)
		if err:
			raise RetryException(err)

		
		for k,v in document['create_schema_dict'].items():
			if k not in cols.keys():
				err = add_column(document.get('name'), {'name': k, 'type':v}, auth)
				if err:
					raise RetryException(err)


	values = []
	for i in range(len(data['text'])):
		value = "("
		for column in document['insert_schema_list']:
			if column == "_id":
				value += f"'{random_string(6)}'"
			else:
				if len(data[column]) > i:
					v = data[column][i]
					if isinstance(v, str):
						v = f"'{v}'"
				else:
					print(f"there is a column that we're trying to insert but the length of that column is not equal to the length of text. what is going on\n DATA:{data}")
				value += f"{v}"
			value += ", "
		values.append(value[:-2] + ")")

	sql = f"INSERT INTO {document.get('name')} {document['insert_schema_string']} VALUES {','.join(values)};"
	_, err = featurebase_query({"sql": sql, "dbid": user.get('dbid'), "db_token": user.get('db_token')})
	if err:
		raise RetryException(f"failed to insert data: {err}")
	else:
		return "success", 200