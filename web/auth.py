import datetime

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
@auth.route('/login')
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
		print(ex)
		return redirect(url_for('site.index'))


# LOGIN POST
@auth.route('/email', methods=['POST'])
def email_post():
	# bots
	password = request.form.get('password')
	if password:
		# there are no passwords, but there are hacker fucks
		return "( ︶︿︶)_╭∩╮ PASSWORD REQUIRED!\nALSO, GET OFF MY LAWN.", 500