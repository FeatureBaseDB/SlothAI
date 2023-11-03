import json
import traceback

from flask import Blueprint, request
from flask import current_app as app
from flask_login import current_user

from SlothAI.lib.processor import process
from SlothAI.lib.tasks import Task, RetriableError, NonRetriableError, TaskState
# from SlothAI.web.models import Task as TaskModel

import flask_login
from flask_login import current_user

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks/process/<cron_key>', methods=['POST'])
def process_tasks(cron_key):

	try:
		# validate call with a key
		if cron_key != app.config['CRON_KEY']:
			raise NonRetriableError("invalid cron key")

		# Parse the task payload sent in the request.
		task = Task.from_json(request.get_data(as_text=True))

		task = process(task)

		node = task.remove_node()
		if len(task.nodes) > 0:
			app.config['task_service'].queue_task(task)			
		else:
			app.config['task_service'].update_task(task_id=task.id, state=TaskState.COMPLETED)

		app.logger.info(f"successfully processed task with id {task.id} on node with id {node} in pipeline with id {task.pipe_id}")

	except RetriableError as e:
		task.error = str(e)
		app.logger.error(f"processing task with id {task.id} on node with id {task.next_node()} in pipeline with id {task.pipe_id}: {str(e)}: retrying task.")
		app.config['task_service'].retry_task()
		# task.retry()
	except Exception as e:
		traceback.print_exc()
		task.error = str(e)
		app.logger.error(f"processing task with id {task.id} on node with id {task.next_node()} in pipeline with id {task.pipe_id}: {str(e)}: dropping task.")
		app.config['task_service'].drop_task(task)
		
	return f"successfully completed node", 200

@tasks.route('/tasks', methods=['DELETE'])
@flask_login.login_required
def delete_tasks():
	# if task is running locally, kill it but make sure to send 200 resp to app engine
	
	# delete it's entry from  
	return "OK", 200

@tasks.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):

	# task = app.store.get_task(user_id=)

	return f"{task_id}: OK", 200