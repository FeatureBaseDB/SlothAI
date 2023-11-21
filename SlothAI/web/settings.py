import os
import json

from google.cloud import ndb

from flask import Blueprint, jsonify, request, redirect, url_for
from flask import current_app as app

import flask_login
from flask_login import current_user

from SlothAI.web.models import User
from SlothAI.lib.util import random_string

from SlothAI.lib.database import featurebase_query

settings_handler = Blueprint('settings', __name__)

# LOGIN POST
@settings_handler.route('/connect', methods=['POST'])
@flask_login.login_required
def connect_db():
    uid = current_user.uid

    try:
        data = request.get_json()
    except:
        return jsonify({"error": "Data must be posted as a dictionary containing the dbid and db_token keys with values."}), 406

    dbid = data.get('dbid')
    db_token = data.get('db_token')

    if not dbid or not db_token:
        return jsonify({"error": "You need to enter both the dbid and db_token fields."}), 406

    # check for access to FeatureBase database
    resp, err = featurebase_query(
        {
            "sql": f"SHOW TABLES;",
            "dbid": f"{dbid}",
            "db_token": f"{db_token}" 
        }
    )

    if err:
        if "Unauthorized" in err:
            return jsonify({"error": "Error authenticating. Enter or check your credentials."}), 401
        else:
            return jsonify({"error": f"Unhandled error while authenticating: {err}. Try again."}), 409
    
    if not resp.execution_time:
        return jsonify({"error": "Something horrible happened, and I have no idea what."}), 400

    # look the user up (here we know they are telling the truth)
    user = User.update_db(uid, dbid, db_token)

    if not user:
        return jsonify({"error": "You are not authenticated. Check your login or token and try again."}), 401

    return jsonify({"success": "FeatureBase account successfully connected."})


@settings_handler.route('/disconnect/<dbid>', methods=['DELETE'])
@flask_login.login_required
def disconnect_db(dbid):
    uid = current_user.uid
    if not uid:
        return jsonify({"error": "Error authenticating. Enter or check your credentials."}), 401

    user = User.update_db(uid, None, None)
    return jsonify({"success": "FeatureBase account removed."})