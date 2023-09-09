import os
import sys
import json

import requests

from google.cloud import ndb

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login
from flask_login import current_user

from lib.util import random_string
from lib.ai import ai
from lib.tasks import list_tasks

from web.models import Table

site = Blueprint('site', __name__)

import config

# client connection
client = ndb.Client()

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')

# main route
@site.route('/', methods=['GET'])
@flask_login.login_required
def index():
	return render_template(
		'pages/home.html'
	)

@site.route('/tasks')
@site.route('/jobs')
@flask_login.login_required
def get_all_tasks():
	_tasks = list_tasks(current_user.uid)
	username = current_user.name
	return render_template(
		'pages/tasks.html', tasks=_tasks, username=username
	)

# main route
@site.route('/settings', methods=['GET'])
@flask_login.login_required
def settings():
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid

	return render_template(
		'pages/settings.html', username=username, api_token=api_token, dbid=dbid
	)

# main route
@site.route('/models', methods=['GET'])
@flask_login.login_required
def models():
	# get the user and their tables
	username = current_user.name
	api_token = current_user.api_token
	dbid = current_user.dbid

	return render_template(
		'pages/models.html', username=username, api_token=api_token, dbid=dbid
	)


# PAGE HANDLERS
@site.route('/tables', methods=['GET'])
@flask_login.login_required
def tables():
	# get the user and their tables
	username = current_user.name

	tables = Table.get_all_by_uid(uid=current_user.uid)

	_tables = []
	with client.context():
		if tables:
			for table in tables:
				_tables.append(table)

	return render_template('pages/tables.html', username=username, tables=_tables)


@site.route('/tables/<tid>', methods=['GET'])
@flask_login.login_required
def table_view(tid):
	# get the user and their tables
	username = current_user.name
	token = current_user.api_token

	_table = Table.get_by_uid_tid(uid=current_user.uid, tid=tid)

	if not _table:
		return redirect(url_for('site.tables'))
	
	print(_table)
	return render_template('pages/table.html', username=username, token=token, table=_table)


