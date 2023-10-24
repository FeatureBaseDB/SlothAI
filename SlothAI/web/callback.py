from flask import Blueprint, request, jsonify
import flask_login
from SlothAI.web.models import Log
import flask_login
from flask import Blueprint, request, current_app

callback = Blueprint('callback', __name__)

@callback.route('/<user_name>/callback', methods=['POST'])
@flask_login.login_required
def handle_callback(user_name):
    log = Log.create(user_id=flask_login.current_user.uid, line=str(request.get_data()))

    if log:
        message = "Successfully logged message"
        current_app.logger.info(message)
        return jsonify({'message': message}), 200

    error_message = "Failed to write log"
    current_app.logger.error(f"ERROR: {error_message}")
    error_response = {'error': 'LogWriteError', 'message': error_message}
    return jsonify(error_response), 500