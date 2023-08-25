import os
import sys

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

site = Blueprint('site', __name__)

import config

@site.route('/sitemap.txt')
def sitemap():
	return render_template('pages/sitemap.txt')

# main route
@site.route('/')
def index():
    return 'Hello world. <a href="/login">login</a>'

