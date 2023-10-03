from google.cloud import ndb

from flask import Blueprint, flash, jsonify, request

import flask_login
from flask_login import current_user

from SlothAI.lib.ai import ai
from SlothAI.lib.tasks import create_task, get_task_schema, box_required
from SlothAI.lib.database import get_columns, get_unique_column_values, featurebase_query
from SlothAI.web.models import Pipeline, Models

pipeline = Blueprint('pipeline', __name__)

# client connection
client = ndb.Client()

# API HANDLERS
@pipeline.route('/pipelines/list', methods=['GET'])
@flask_login.login_required
def tables_list():
	return None