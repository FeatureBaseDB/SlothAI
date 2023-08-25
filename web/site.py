import os
import sys

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

import flask_login
site = Blueprint('site', __name__)

import config

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')

# main route
@site.route('/')
@flask_login.login_required
def index():
	return render_template(
		'pages/home.html'
	)

