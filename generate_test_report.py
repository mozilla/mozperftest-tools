#!/usr/bin/python3
"""
Used to check what tests are running where. Primarily for Raptor and Browsertime.
"""
import argparse
import os
import json

try:
	from urllib.parse import urlencode
	from urllib.request import urlopen, urlretrieve
except ImportError:
	from urllib import urlencode, urlretrieve
	from urllib2 import urlopen

DEFAULT_TASK = "Gz9K6jGjQd6MvI2v6_02xg"
LINK = "https://firefoxci.taskcluster-artifacts.net/{}/0/public/full-task-graph.json"


def reporter_parser():
	parser = argparse.ArgumentParser("This tool can be used to generate a report of where eveyrthing is " +
									 "currently running.")
	parser.add_argument('--decision-task-id', type=str, default='',
						help='The decision task to get the full-task-graph.json file from.')
	parser.add_argument('--full-task-graph-path', type=str, default='',
						help='A path to a full-task-graph.json artifact to use instead of '
						'obtaining it from a decision task.')
	parser.add_argument('--tests', type=str, nargs='+', default=['raptor', 'browsertime'],
						help='The tests to build a report for (pattern matched). ' +
						'Defaults to raptor and browsertime.')
	parser.add_argument('--platforms', type=str, nargs='+', default=[],
						help='Platforms to return results for. Defaults to all.')
	parser.add_argument('--output', type=str, nargs=1, default=os.getcwd(),
						help='This is where the data will be saved. Defaults to CWD.')
	parser.add_argument('--platform-breakdown', action='store_true', default=False,
						help='Get a platform breakdown instead of a test breakdown.')
	parser.add_argument('--branch-breakdown', action='store_true', default=False,
						help='Get a branch breakdown instead of a test breakdown.')
	parser.add_argument('--match-all-tests', action='store_true', default=False,
						help='Only tests which match all --tests entries will be selected.')
	parser.add_argument('--ignore-no-projects', action='store_true', default=False,
						help='Prevents displaying tests with no projects.')
	parser.add_argument('--field', type=str, default='attributes.run_on_projects',
						help='The field to search for (defaults to `attributes.run_on_projects`).')
	parser.add_argument('--show-all-fields', action="store_true", default=False,
						help='Show all available fields in the given FTG.')
	return parser

def get_json(url, params=None):
	print("Requesting full-task-graph.json from: %s" % url)
	if params is not None:
		url += '?' + urlencode(params)

	r = urlopen(url).read().decode('utf-8')

	return json.loads(r)

def pattern_match(name, patterns):
	if not patterns:
		return True
	found = False
	for pattern in patterns:
		if pattern in name:
			found = True
			break
	return found

def pattern_match_all(name, patterns):
	if not patterns:
		return True
	found = True
	for pattern in patterns:
		if pattern not in name:
			found = False
	return found


def _get_all_fields(info, parent=''):
	fields = []
	keys = list(info.keys())
	for key in keys:
		if parent != "":
			newparent = '{}.{}'.format(parent, key)
		else:
			newparent = key
		if isinstance(info[key], dict):
			fields.extend(
				_get_all_fields(info[key], parent=newparent)
			)
		else:
			fields.append(newparent)
	return fields


def print_fields(ftg):
	allfields = set()
	for test, info in ftg.items():
		allfields = set(_get_all_fields(info)) | allfields

	for field in sorted(allfields):
		print(field)


def generate_report(
		decision_task,
		tests,
		platforms,
		platform_breakdown=False,
		branch_breakdown=False,
		match_all_tests=False,
		field='attributes.run_on_projects',
		show_all_fields=False,
		ftg_path=''
	):

	# Get the graph
	if not ftg_path:
		dt = decision_task or DEFAULT_TASK
		cached_data = "%s.json" % dt
		if not os.path.exists(cached_data):
			ftg = get_json(LINK.format(dt))
			with open(cached_data, 'w') as f:
				json.dump(ftg,f)
		else:
			with open(cached_data, 'r') as f:
				ftg = json.load(f)
	else:
		with open(ftg_path, 'r') as f:
			ftg = json.load(f)

	## FILTER
	# Filter out all tests that are not wanted
	filt_test_ftg = {}
	for test in ftg:
		if match_all_tests:
			if pattern_match_all(test, tests):
				filt_test_ftg[test] = ftg[test]
		else:
			if pattern_match(test, tests):
				filt_test_ftg[test] = ftg[test]

	# Filter out all platforms that are not wanted
	filt_ftg = {}
	for test in filt_test_ftg:
		if pattern_match(test, platforms):
			filt_ftg[test] = filt_test_ftg[test]

	if len(filt_ftg) == 0:
		print("Could not find any matching test+platform combinations.")
		return {}

	if show_all_fields:
		print_fields(filt_ftg)
		return None

	def get_field_value(info, field):
		# Field is combined with `.` to 
		# denote nested entries.
		value = info
		path = field.split('.')
		for key in path:
			value = value[key]
		if not isinstance(value, list):
			value = [str(value)]
		return value

	## BREAKDOWN
	# Split test from platform name
	split_data = {}
	for test, test_info in filt_ftg.items():
		splitter = '/pgo-'
		if '/opt-' in test:
			splitter = '/opt-'
		if splitter not in test:
			continue
		platform, test = test.split(splitter)
		platform = platform + splitter.replace('-', '')

		first = test
		second = platform
		if platform_breakdown:
			first = platform
			second = test

		if first not in split_data:
			split_data[first] = {}
		if second not in split_data[first]:
			split_data[first][second] = []
		projects = get_field_value(test_info, field)
		if not projects:
			projects = ['none']
		split_data[first][second].extend(projects)

	if branch_breakdown:
		# Reorder the data
		new_split_data = {}
		for first, second_data in split_data.items():
			for second, projects in second_data.items():
				for project in projects:
					if project not in new_split_data:
						new_split_data[project] = {}
					if first not in new_split_data[project]:
						new_split_data[project][first] = []
					new_split_data[project][first].append(second)
		split_data = new_split_data

	return split_data

def view_report(report, output, ignore_no_projects=False, branch_breakdown=False):
	"""
	Expecting a report with the form (or with test and platform swapped):
	{'test-name': {'platform-name': [projects]}, ...}
	"""
	print("Report Breakdown\n")

	for first, second_info in sorted(report.items()):
		indent = '    '
		print(first)

		printed = False
		for second, projects in sorted(second_info.items()):
			def _check_empty(projects):
				if len(projects) == 0:
					return True
				if len(projects) > 1:
					return False
				if projects[0] == 'none':
					return True
			if ignore_no_projects and _check_empty(projects):
				continue
			if not branch_breakdown:
				print(indent + second + ': ' + ', '.join(projects))
				printed = True
			else:
				print("")
				print(indent + second + ':')
				for entry in projects:
					print(indent + indent + entry)
				printed = True
		if not printed:
			print(indent + "No tests satisfying criteria")
		print("")
	return

if __name__=="__main__":
	args = reporter_parser().parse_args()

	report = generate_report(
		args.decision_task_id,
		args.tests,
		args.platforms,
		platform_breakdown=args.platform_breakdown,
		branch_breakdown=args.branch_breakdown,
		match_all_tests=args.match_all_tests,
		field=args.field,
		show_all_fields=args.show_all_fields,
		ftg_path=args.full_task_graph_path
	)
	if report:
		view_report(
			report,
			args.output,
			ignore_no_projects=args.ignore_no_projects,
			branch_breakdown=args.branch_breakdown
		)
