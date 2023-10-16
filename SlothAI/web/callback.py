import json
from flask import Blueprint
from flask import request
from flask import current_app as app
from SlothAI.web.models import User, Pipeline, Node, Log

callback = Blueprint('callback', __name__)

@callback.route('/default_callback/<cron_key>', methods=['POST'])
def handle_callback(cron_key):
    # validate call with a key
    if cron_key != app.config['CRON_KEY']:
        print(f"ERROR: invalid cron_key. dropping task.")
        return f"Not authenticated. Flushing request.", 200

	# Parse the task payload sent in the request.
    payload = request.get_data(as_text=True)
    try:
        payload = json.loads(payload)
    except Exception as ex:
        return "unable to unmarshal data as json\n", 400

    user_id = payload.get('user_id', None)
    pipe_id = payload.get('pipe_id', None)
    node_id = payload.get('node_id', None)
    message = payload.get('message', None)

    if not user_id or not pipe_id or not node_id or not message:
        return "data payload must be json which includes user_id, pipe_id, node_id, and message\n", 400

    # could trust the client for these, check for now.
    user = User.get_by_uid(uid=user_id)
    if not user:
        print(f"ERROR: user not found: dropping task")
        return f"Not authenticated. Flushing request.\n", 400
    
    pipeline = Pipeline.get(uid=user_id, pipe_id=pipe_id)
    if not pipeline:
        print(f"ERROR: pipeline not found: dropping task")
        return f"Not authenticated. Flushing request.\n", 400

    node = Node.get(user_id=user_id, node_id=node_id)
    if not node:
        print(f"ERROR: node not found: dropping task")
        return f"Not authenticated. Flushing request.\n", 400

    # could do some checking here that node is a callback node

    log = Log.create(user_id=user_id, pipe_id=pipe_id, node_id=node_id, message=message)
    if log:
        return f"successfully logged message\n", 200

    return "did not successfully write log\n", 500