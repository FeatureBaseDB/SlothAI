import json
from flask import Blueprint
from flask import request
from flask import current_app as app
from SlothAI.web.models import User, Pipeline, Node, Log

callback = Blueprint('callback', __name__)

@callback.route('/<user_name>/callback', methods=['POST'])
def handle_callback(user_name):

    user_api_token = request.args.get('token')
    if not user_api_token:
        return "must supply token query string / parameter", 400

	# Parse the task payload sent in the request.
    payload = request.get_data(as_text=True)
    try:
        payload = json.loads(payload)
    except Exception as ex:
        return "unable to unmarshal data as json\n", 400

    pipe_id = payload.get('pipe_id', None)
    node_id = payload.get('node_id', None)
    message = payload.get('message', None)

    if not pipe_id or not node_id or not message:
        return "data payload must be json which includes user_id, pipe_id, node_id, and message\n", 400

    # could trust the client for these, check for now.
    user = User.get_by_name(name=user_name)
    if not user:
        print(f"ERROR: user not found\n")
        return f"ERROR: user not found\n", 400
    
    if user_api_token != user.get('api_token'):
        print(f"ERROR: Invalid user api token\n")
        return f"ERROR: Invalid user api token\n", 400
    
    pipeline = Pipeline.get(uid=user.get('uid'), pipe_id=pipe_id)
    if not pipeline:
        print(f"ERROR: pipeline not found\n")
        return f"ERROR: pipeline not found\n", 400

    node = Node.get(user_id=user.get('uid'), node_id=node_id)
    if not node:
        print(f"ERROR: node not found\n")
        return f"ERROR: node not found\n", 400

    # could do some checking here that node is a callback node

    log = Log.create(user_id=user.get('uid'), pipe_id=pipe_id, node_id=node_id, message=message)
    if log:
        return f"successfully logged message\n", 200

    return "did not successfully write log\n", 500