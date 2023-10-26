import json

from flask import Blueprint, request
from flask import current_app as app

from SlothAI.lib.processor import process
from SlothAI.lib.tasks import Task
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
    pipeline = Pipeline.get(uid=task.user_id, pipe_id=task.pipe_id)
    if not pipeline:
        print(f"ERROR: pipeline with id {task.pipe_id} not found. dropping task.")
        return f"Can't find the pipeline specified. Flushing request.", 200

    # rework this soon to get the model flavor not in the name
    task = process(task)
    if 'error' in task.document and task.document['error']:
        return f"got error: {task.document['error']}", 400
    
    requeue = task.remove_node()
    if requeue:
        task.queue()
    
    return f"successfully completed node", 200