import os
import sys
import json
import random

import requests

from flask import Blueprint, render_template, flash
from flask import make_response, Response
from flask import redirect, url_for, abort
from flask import request, send_file

from lib.gcloud import box_status

from web.models import Box

cron = Blueprint('cron', __name__)

import config

# get box status
@cron.route('/cron/boxes/<box_id>/<cron_key>', methods=['GET'])
def status_handler(box_id="all", cron_key=""):
	if cron_key != config.cron_key:
		return

	if box_id == "all":
		boxes = box_status()
	
	box_list = []
	for box in boxes:
		box_list.append(box.get('box_id'))

		# check sloth- (with dash) is in name
		if "sloth-" in box.get('box_id'):
			# run create (which updates Box object in datastore - the cache of current boxes)
			Box.create(box.get('box_id'), box.get('ip_address'), box.get('zone'), box.get('status'))

	_boxes = Box.get_boxes()

	# purge old boxes
	for _box in _boxes:
		if _box.get('box_id') not in box_list:
			Box.delete(_box.box_id)

	return boxes
