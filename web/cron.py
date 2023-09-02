import os
import sys
import json

import requests

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

from lib.util import random_string
from lib.gcloud import box_status

from web.models import Box, Jobs

cron = Blueprint('cron', __name__)

import config

# get box status
@cron.route('/boxes/status/<box_id>/<cron_key>', methods=['GET'])
def status_handler(box_id="all", cron_key=""):
	if cron_key != config.cron_key:
		return

	if box_id == "all":
		boxes = box_status()
	
	for box in boxes:
		# check sloth- (with dash) is in name
		if "sloth-" in box.get('box_id'):
			# run create (which updates)
			Box.create(box.get('box_id'), box.get('ip_address'), box.get('zone'), box.get('status'))

	return boxes

@cron.route('/jobs/process/<cron_key>', methods=['GET'])
def jobs_process(cron_key):
	if cron_key != config.cron_key:
		return

	for x in range(5):
		job = Jobs.select_next_scheduled_job()
		if not job:
			break
		print("would do job", job)
		
		Jobs.delete(job.get('jid'))

	return "success", 200