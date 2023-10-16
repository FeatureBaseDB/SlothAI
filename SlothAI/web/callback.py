import json
from flask import Blueprint, request, jsonify
import flask_login
from SlothAI.web.models import User, Log  # Assuming you have the necessary imports

callback = Blueprint('callback', __name__)

@callback.route('/<user_name>/callback', methods=['POST'])
@flask_login.login_required
def handle_callback(user_name):
    user = User.get_by_name(name=user_name)

    if not user:
        error_message = "User not found"
        app.logger.error(f"ERROR: {error_message}")
        error_response = {'error': 'UserNotFound', 'message': error_message}
        return jsonify(error_response), 400

    try:
        # Parse the JSON payload sent in the request
        payload = json.loads(request.data)
    except json.JSONDecodeError as ex:
        error_message = "Unable to unmarshal data as JSON"
        app.logger.error(f"ERROR: {error_message}")
        error_response = {'error': 'InvalidJSON', 'message': error_message}
        return jsonify(error_response), 400

    # Create a log entry with the entire JSON document as 'line'
    log = Log.create(user_id=user.get('uid'), line=json.dumps(payload))

    if log:
        success_message = "Successfully logged message"
        app.logger.info(success_message)
        success_response = {'message': success_message}
        return jsonify(success_response), 200

    error_message = "Failed to write log"
    app.logger.error(f"ERROR: {error_message}")
    error_response = {'error': 'LogWriteError', 'message': error_message}
    return jsonify(error_response), 500
