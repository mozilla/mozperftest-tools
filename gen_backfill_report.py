"""
This script can be used to generate a report of the amount of
machine time used during all backfills between a start and end
date.
"""

import argparse
import os
import json
import re
import threading
import time
import urllib

try:
	from urllib.parse import urlencode
	from urllib.request import urlopen, urlretrieve
except ImportError:
	from urllib import urlencode, urlretrieve
	from urllib2 import urlopen

DEBUG = False
TOTAL_REQUESTS = 0
MAX_REQUESTS = 50
OVERRIDE = False

"""
`where` clause will be created in the script.

It will be similar to this:
	"where": {"and": [
		{"eq":{"job.type.symbol":"Bk"}},
		{"gte": {"date": STARTTIME},
		{"lt": {"date": ENDTIME},
	]}

All TIME values must follow the standards laid out in:
https://github.com/mozilla/ActiveData/blob/dev/docs/jx_time.md

"""
AD_BACKFILL_QUERY = {
	"from": "treeherder",
	"where": None,
	"select":[
		"build.revision",
		"job.details.url",
		"repo.branch.name"
	],
	"limit": 10000
}


"""
`where` clause will be created in the script

It will be similar to this:
	"where": {"and": [
		# Make sure action.duration is positive
		{"gt":{"action.duration":0}},
		{"in": {"run.taskcluster.id": [TASKIDS]}}
	]}
"""
AD_TIME_QUERY = {
	"from": "treeherder",
	"where": None,
	"select":{
		"name":"action.duration",
		"value":"action.duration",
		"aggregate":"sum"
	},
	"limit": 10000
}


def backfill_parser():
	"""
	Parser for the backfill generation script.
	"""
	parser = argparse.ArgumentParser("This tool can be used to generate a report of how much machine time " +
									 "is being consumed by backfills.")
	parser.add_argument('--start-date', type=str, default='',
						help='The start date for where to start looking for backfilled jobs. '
						'Defaults to 1 year back.')
	parser.add_argument('--end-date', type=str, default='',
						help='The end date for where to start looking for backfilled jobs.')
	parser.add_argument('--branches', type=str, nargs='+', default=['autoland'],
						help='The branch to find backfilled jobs in.')
	return parser


def debug(msg):
	"""Helper function for debug prints"""
	if DEBUG: print(msg)


def get_json(url, params=None):
	"""
	Gets a JSON artifact from a given URL.
	"""
	if params is not None:
		url += '?' + urlencode(params)

	r = urlopen(url).read().decode('utf-8')

	return json.loads(r)


def query_activedata(query_json):
	"""
	Used to run queries on active data.
	"""
	active_data_url = 'http://activedata.allizom.org/query'

	req = urllib.request.Request(active_data_url)
	req.add_header('Content-Type', 'application/json')
	jsondata = json.dumps(query_json)

	jsondataasbytes = jsondata.encode('utf-8')
	req.add_header('Content-Length', len(jsondataasbytes))

	print("Querying Active-data...")
	response = urllib.request.urlopen(req, jsondataasbytes)
	print("Status:" + str(response.getcode()))

	data = json.loads(response.read().decode('utf8').replace("'", '"'))['data']
	return data


def generate_backfill_report(start_date='', end_date='', branches=['autoland']):
	"""
	This generation works as follows:
		(i):   Find all backfill tasks between the given dates.
		If no dates are given, then we look over the past year.
		If only a start date is given, then we look from then to now.
		If only an end date is given, then we look from 1 year ago up
		to the end date.

		(ii):  Using the backfill tasks that were found, download all
		the to-run-<PUSH_ID>.json files and label-to-taskid-<PUSH_ID>.json
		files.

		(iii): For each to-run file, find the tests that are
		being retriggered and their taskid. Then, obtain the sum
		of the runtime for all these taskids.
	"""
	conditions = [
		{"eq": {"job.type.symbol": "Bk"}},
		{"in": {"repo.branch.name": branches}},
	]

	where_clause = {"and": conditions}

	if end_date:
		conditions.append({
			"lt": {"action.start_time": {"date": str(end_date)}}
		})
	if start_date:
		conditions.append({
			"gte": {"action.start_time": {"date": str(start_date)}}
		})
	else:
		# Restrict to 1 year back
		print("Setting start-date as 1 year ago. This query will take some time...")
		conditions.append({
			"gte": {"action.start_time": {"date": "today-year"}}
		})

	if start_date or end_date:
		print(
			"Date specifications detected. "
			"Ensure that they follow these guidelines: "
			"https://github.com/mozilla/ActiveData/blob/dev/docs/jx_time.md" 
		)

	AD_BACKFILL_QUERY["where"] = where_clause
	debug(json.dumps(AD_BACKFILL_QUERY, indent=4))
	data = query_activedata(AD_BACKFILL_QUERY)

	print("Analyzing backfills performed on the revisions: %s" % data["build.revision"])

	# Go through all the URL groupings and match up data from each PUSHID
	alltaskids = []
	total_groups = len(data['job.details.url'])
	matcher = re.compile(r"-([\d]+).json")
	for c, url_grouping in enumerate(data['job.details.url']):
		if not url_grouping: continue

		print(
			"\nProcessing %s from %s (%s/%s)" %
			(
				data['build.revision'][c],
				data['repo.branch.name'][c],
				c,
				total_groups
			)
		)
		push_data = {}

		# Gather groupings
		for url in url_grouping:
			if not url: continue

			matches = matcher.findall(url)
			if not matches: continue

			# Only one match should be found
			if len(matches) > 1:
				print("Bad URL found: %s" % url)
				continue

			pushid = matches[0]
			if pushid not in push_data:
				push_data[pushid] = {}

			fname = url.split('/')[-1]
			if 'label-to-taskid' in fname:
				fname = 'label-to-taskid'
			elif 'to-run-' in fname:
				fname = 'to-run'
			else:
				# We don't care about these files
				continue

			push_data[pushid][fname] = {'url': url, 'data': None}

		def download(url, storage):
			"""Downloads a JSON through a thread"""
			global TOTAL_REQUESTS
			global MAX_REQUESTS
			global OVERRIDE

			while TOTAL_REQUESTS >= MAX_REQUESTS and not OVERRIDE:
				time.sleep(0.5)

			TOTAL_REQUESTS += 1
			print("Downloading %s" % url)
			storage['data'] = get_json(url)
			TOTAL_REQUESTS -= 1

		# [WIP] Fails quite often with timeouts when running on 1 year of data.
		#
		# Download all the artifacts - batch them in case
		# we are looking very far back.
		# threads = []
		# for _, push_files in push_data.items():
		# 	for file, file_info in push_files.items():
		# 		t = threading.Thread(
		# 			target=download,
		# 			args=(file_info['url'], file_info)
		# 		)
		# 		t.daemon = True
		#
		# 		t.start()
		# 		threads.append(t)
		# for t in threads:
		# 	t.join()

		# Get all of the TASKIDs of the backfilled jobs
		taskids = []
		for pid, push_files in push_data.items():
			# [WIP] Fails quite often with timeouts.
			#
			# tasks_running = push_files['to-run']['data']
			# labeled_tasks = push_files['label-to-taskid']['data']
			# if not tasks_running or not labeled_tasks: continue

			try:
				print("Getting %s" % push_files['to-run']['url'])
				tasks_running = get_json(push_files['to-run']['url'])
				print("Getting %s" % push_files['label-to-taskid']['url'])
				labeled_tasks = get_json(push_files['label-to-taskid']['url'])
			except Exception:
				print("Failed on push %s" % pid)
				continue

			# Artifacts don't exist - skip them
			if 'code' in tasks_running or \
			   'code' in labeled_tasks:
				print("Artifacts don't exist in push %s" % pid)
				continue

			taskids.extend([
				labeled_tasks[taskname]
				for taskname in tasks_running
			])

		alltaskids.extend(taskids)

	AD_TIME_QUERY['where'] = {
		"and":[
			{"gt":{"action.duration":0}},
			{"in": {"run.taskcluster.id": alltaskids}}
		]
	}

	debug(json.dumps(AD_TIME_QUERY, indent=4))
	data = query_activedata(AD_TIME_QUERY)

	print(
		"Total runtime of backfilled tasks: %s hours" %
		(int(data['action.duration'])/3600)
	)


def main():
	args = backfill_parser().parse_args()
	report = generate_backfill_report(
		start_date=args.start_date,
		end_date=args.end_date,
		branches=args.branches
	)


if __name__=="__main__":
	main()
