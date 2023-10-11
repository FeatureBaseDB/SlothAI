from flask import Blueprint
from flask import request
from flask import current_app as app
from SlothAI.lib.ai import process
from SlothAI.lib.tasks import Task, box_required_for_node
from SlothAI.web.models import User, Pipeline, Node

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
	pipeline = Pipeline.get(uid=task.user_id, pipe_id=task.pipe_id)
	if not pipeline:
		print(f"ERROR: table with id {task.pipe_id} not found. dropping task.")
		return f"Can't find the table specified. Flushing request.", 200

	node = task.next_node()
	node = Node.get(uid=task.user_id, name=node)
	model = node.get('extras').get('model')

	# models requiring boxes get deferred
	defer, selected_box = box_required_for_node(node)
	if defer:
		return f"Starting GPUs...", 418 # return resource starting 

	# grab the IP for locally run models and stuff it into the document
	if selected_box:
		task.document['ip_address'] = selected_box.get('ip_address')


	# rework this soon to get the model flavor not in the name
	task.document = process(model, task)
	if 'error' in task.document:
		return f"got error in {model}: {task.document['error']}", 400
	
	requeue = task.remove_node()
	if requeue:
		task.queue()
	
	return f"successfully completed node {node.get('name')}", 200
	