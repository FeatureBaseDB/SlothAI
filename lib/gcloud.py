import os
import sys
import random
import string
import time
import json

import requests
from string import Template

import config

# random strings
def random_string(size=6, chars=string.ascii_letters + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

# get box status
def box_status(box_id="", zone=""):
	if box_id == "":
		# get all status
		
		# reach out to the controller box
		url = f"http://{config.sloth_controller_username}:{config.sloth_token}@{config.sloth_controller_ip}:8787/api/instance/list?token={config.sloth_token}"

		headers = {"Content-Type": "application/json"}
		response = requests.get(url, headers=headers)

		try:
			boxes = []

			for box in response.json():
				boxes.append({
					"box_id": box.get('name'),
					"ip_address": box.get('networkInterfaces')[0].get('accessConfigs')[0].get('natIP', None),
					"status": box.get('status'),
					"zone": box.get('zone').replace("https://www.googleapis.com/compute/v1/projects/sloth-compute/zones/", "") # just get the zone string
				})

			return boxes
		except Exception as ex:
			return {"error": ex}
	else:
		if zone == "":
			return {"error": "no zone specified"}

		# reach out to the controller box
		# /api/instance/<zone>/<instance_id>/status
		url = f"http://{config.sloth_controller_username}:{config.sloth_token}@{config.sloth_controller_ip}:8787/api/instance/{zone}/{box_id}/status?token={config.sloth_token}"

		headers = {"Content-Type": "application/json"}
		response = requests.get(url, headers=headers)

		box = response.json()

		boxes = [{
					"box_id": box.get('name'),
					"ip_address": box.get('networkInterfaces')[0].get('accessConfigs')[0].get('natIP', None),
					"status": box.get('status'),
					"zone": box.get('zone').replace("https://www.googleapis.com/compute/v1/projects/sloth-compute/zones/", "") # just get the zone string
				}]
				
		return boxes

def box_start(box_id="", zone="us-central1-a"):
		# reach out to the controller box
		# /api/instance/<zone>/<instance_id>/start
		url = f"http://{config.sloth_controller_username}:{config.sloth_token}@{config.sloth_controller_ip}:8787/api/instance/{zone}/{box_id}/start?token={config.sloth_token}"

		headers = {"Content-Type": "application/json"}
		response = requests.get(url, headers=headers)


def box_stop(box_id="", zone="us-central1-a"):
		# reach out to the controller box
		# /api/instance/<zone>/<instance_id>/start
		url = f"http://{config.sloth_controller_username}:{config.sloth_token}@{config.sloth_controller_ip}:8787/api/instance/{zone}/{box_id}/stop?token={config.sloth_token}"

		headers = {"Content-Type": "application/json"}
		response = requests.get(url, headers=headers)