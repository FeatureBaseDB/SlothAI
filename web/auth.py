import datetime
import json

from google.cloud import ndb

from flask import Blueprint, render_template, make_response, redirect, url_for, request, session, flash
from flask_login import login_user, login_manager, logout_user, login_required, current_user
import flask_login

from web.models import User, Transaction

from lib.util import random_string

import config

# client connection
client = ndb.Client()

# logins
login_manager = flask_login.LoginManager()
login_manager.session_protection = "strong"

# blueprints for auth, money and code endpoints
auth = Blueprint('auth', __name__)

# logout
@auth.route('/logout')
def logout():
	logout_user()
	flash("You are logged out.")
	return redirect(url_for('site.index'))

# LOGIN GET
@auth.route('/login', methods=['GET'])
def login():
	try:
		if current_user.email:
			session = True
		else:
			session = False
	except Exception as ex:
		session = False

	next_url = request.args.get("next")

	if not next_url:
		next_url = request.form.get('next')

	# if we have no connection to the DB, this will handle it
	try:
		# secure transaction to POST
		transaction_id = random_string(13)
		transaction = Transaction.create(uid="anonymous", tid=transaction_id)

		return render_template(
			'pages/login.html',
			config=config,
			session=session,
			app_id = random_string(9),
			transaction_id = transaction_id,
			next=next_url
		)
	except Exception as ex:
		return redirect(url_for('site.tables'))


# LOGIN POST
@auth.route('/login', methods=['POST'])
def login_post():
	# bots
	password = request.form.get('password')

	if password:
		# there are no passwords, but there are hacker fucks
		return "( ︶︿︶)_╭∩╮ PASSWORD REQUIRED!\nALSO, GET OFF MY LAWN.", 500

	dbid = request.form.get('dbid')
	db_token = request.form.get('db_token')

	# handle bots filling out forms
	transaction_id = request.form.get('transaction_id')

	# only allow posts with transaction IDs
	if transaction_id:
		with client.context():
			transaction = Transaction.query().filter(Transaction.tid==transaction_id).get()

			# if we find it, delete it and proceed
			if transaction:
				transaction.key.delete()
			else:
				return redirect(url_for('auth.login'))
	else:
		return redirect(url_for('auth.login'))

	from lib.database import featurebase_query

	# check for access to FeatureBase database
	fb_query = featurebase_query(
		{
			"sql": f"SHOW TABLES;",
			"dbid": f"{dbid}",
			"db_token": f"{db_token}" 
		}
	)

	if fb_query.get('message'):
		if fb_query.get('message') == "unauthorized":
			flash("Error authenticating. Enter your credentials again.")
			return redirect(url_for('auth.login'))		
	
	if not fb_query.get('execution-time'):
		return redirect(url_for('auth.login'))

	# look the user up (here we know they are telling the truth)
	user = User.get_by_dbid(dbid)

	if not user:
		# no user, create user and set both dbid and token
		user = User.create(dbid=dbid, db_token=db_token)

	# just log them in
	_user = User.authenticate(user.get('uid'))
	login_user(_user)

	flash("You've been logged in.")

	return redirect(url_for('site.tables'))