#!/usr/bin/python3
"""
Used to check what tests are running where. Primarily for Raptor and Browsertime.
"""
import argparse
import os
import json
from enum import Enum
from typing import Iterable

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
	parser.add_argument('--fields', type=str, default=['attributes.run_on_projects'],
						help='The field to search for (defaults to `attributes.run_on_projects`).')
	parser.add_argument('--show-all-fields', action="store_true", default=False,
						help='Show all available fields in the given FTG.')
	parser.add_argument('--locate', type=str, default="",
						help='Documents which jobs is running on which repo.')
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
		fields=['attributes.run_on_projects'],
		show_all_fields=False,
		ftg_path=''
	):
	if args.locate:
		fields.append('task.extra.treeherder.tier')

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
	if type(ftg) == list:
		for test in ftg:
			if match_all_tests:
				if pattern_match_all(test, tests):
					filt_test_ftg[test] = ftg[test]
			else:
				if pattern_match(test, tests):
					filt_test_ftg[test] = ftg[test]
	elif type(ftg) == dict:
		for task_id, test in ftg.items():
			if match_all_tests:
				if pattern_match_all(test['label'], tests):
					filt_test_ftg[test] = ftg[test]
			else:
				if pattern_match(test['label'], tests):
					filt_test_ftg[test['label']] = ftg[task_id]

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

	def get_fields_value(info, fields):
		# Field is combined with `.` to
		# denote nested entries.
		values = []
		for field in fields:
			path = field.split('.')
			pivot = info
			for key in path:
				pivot = pivot[key]
			if isinstance(pivot, list):
				pivot = ''.join(pivot)
			values.append(str(pivot))
		return values

	## BREAKDOWN
	# Split test from platform name
	split_data = {}
	for test, test_info in filt_ftg.items():
		if args.locate:
			# if test_info.get('label'):
			# 	test = test_info['label']
			if args.locate == 'fenix':
				if test_info.get('kind') not in ('browsertime', 'visual-metrics',):
					continue
				if 'mozilla-mobile/fenix/blob' in test_info['task']["metadata"]["source"] and \
						test_info['task']['extra']['treeherder-platform'] not in test_info['label']:
					test = f"test-{test_info['task']['extra']['treeherder-platform']}-{test_info['label']}"
			if not test.startswith('test-'):
				continue
		splitter = '/pgo-'
		if '/opt-' in test:
			splitter = '/opt-'
		if splitter not in test:
			platform, test = "unknown-platform", test
			try:
				platform = test_info.get("dependencies", {}).get("build")
				if not platform:
					platform = "unknown-platform"
			except Exception as e:
				print("Error trying to get platform for %s" % test)
				print("%s %s" % (e.__class__.__name__, e))
		else:
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
		projects = get_fields_value(test_info, fields)
		if not args.locate and not projects[0]:
			projects[0] = 'None'
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


class Filters():
	REPOS = [
		{'name': 'mozilla-central', 'type': 'location'},
		{'name': 'mozilla-beta', 'type': 'location'},
		{'name': 'trunk', 'type': 'location'}
	]
	FENIX_REPOS = [{'name': 'fenix', 'matches': ('all',), 'type': 'location'}]
	TIER = [{'name': 'tier', 'matches': ('1', '2', '3',), 'multivariant': True, 'type': 'tier'}]
	COMPONENTS = [{'name': 'webextension', 'matches': ('raptor',)}, 'browsertime']
	DESKTOP_APPS = ['firefox', 'chrome', 'chromium']
	MOBILE_APPS = ['geckoview', 'fenix', 'refbrow', 'fennec']
	FENIX_APP = ['fenix']
	DESKTOP_OS = ['linux', 'windows', 'macosx']
	MOBILE_DEVICES = ['p2', 'g5']
	VARIANTS = [{'name': 'fission', 'matches': ('fis',)}]
	PLATFORM_FILTERS = [
		{'name': 'webrender', 'matches': ('wr', 'qr',)},
		'shippable'
	]
	TYPES = [
		{'name': 'pageload', 'matches': ('tp6',)},
		'vismet',
		{
			'name': 'benchmark',
			'matches': (
				'assorted-dom',
				'ares6',
				'jetstream2',
				'motionmark',
				'speedometer',
				'stylebench',
				'sunspider',
				'unity-webgl',
				'wasm-godot',
				'wasm-misc',
				'webaudio',
				'youtube-playback'
			),
			'multivariant': True
		}
	]
	TALOS = [
		'chrome',
		{'name': 'basic compositor video', 'matches': ('bcv',)},
		'damp',
		'dromaeojs',
		{'name': 'g', 'matches': ('g1', 'g2', 'g3', 'g4', 'g5',), 'multivariant': True},
		'profiling',
		'motionmark',
		'other',
		'perf-reftest',
		'realworld-webextensions',
		'singletons',
		{'name': 'sessionrestore', 'matches': ('sessionrestore-many-windows',)},
		'svgr',
		'tabswitch',
		'tp5o',
		'webgl',
		'xperf',
		'bcv'
	]
	DESKTOP_FILTERS = REPOS + TIER + COMPONENTS + DESKTOP_APPS + PLATFORM_FILTERS + VARIANTS + TYPES + DESKTOP_OS
	MOBILE_FILTERS = REPOS + TIER + COMPONENTS + MOBILE_APPS + PLATFORM_FILTERS + VARIANTS + TYPES + MOBILE_DEVICES
	FENIX_FILTERS = TIER + COMPONENTS + FENIX_APP + PLATFORM_FILTERS + VARIANTS + TYPES + MOBILE_DEVICES
	TALOS_FILTERS = REPOS + TIER + TALOS + PLATFORM_FILTERS + VARIANTS + DESKTOP_OS


def locate_jobs(report):
	jobs = []
	plain_filters = []
	for device, tests in report.items():
		# if device.startswith("test"):
		if 'browsertime' in args.tests or 'raptor' in args.tests:
			if args.locate == 'desktop':
				if not any(os in device for os in Filters.DESKTOP_OS):
					continue
				filters = Filters.DESKTOP_FILTERS
			elif args.locate == 'mobile' or args.locate == 'android':
				if not any(os in device for os in Filters.MOBILE_DEVICES):
					continue
				filters = Filters.MOBILE_FILTERS
			elif args.locate == 'fenix':
				if not any(os in device for os in Filters.MOBILE_DEVICES):
					continue
				filters = Filters.FENIX_FILTERS
			else:
				raise Exception("Invalid --locate param: [desktop, mobile, android, fenix]")
		else:
			if args.locate == 'talos':
				filters = Filters.TALOS_FILTERS
			else:
				raise Exception("Invalid --locate param: [talos]")

		if '/' in device:
			os, build_type = device.split('/')
		else:
			os = device
		for test, repos in tests.items():
			repo_list = repos[0]
			tier = repos[1]
			signature = f"{device}-{test}: {repo_list}/tier{tier}"
			job = {
				'device': os,
				'build_type': build_type or '',
				'test_name': test,
				'repos': ','.join(repo_list),
				'tier': tier
			}
			for filter in filters:
				if type(filter) == str:
					# append to header
					if filter not in plain_filters:
						plain_filters.append(filter)
					if filter in signature:
						job[filter] = True
				elif type(filter) == dict:
					# append to header
					if filter['name'] not in plain_filters:
						plain_filters.append(filter['name'])
					if filter.get('multivariant'):
						for match in filter['matches']:
							if filter.get('type') == 'tier':
								job[filter['name']] = tier
							elif match in signature:
								job[filter['name']] = match
					# elif filter.get('matches') in signature or filter['name'] in signature:
					elif filter.get('type') != 'location' \
						and (any(match in signature for match in filter.get('matches', ('',))) \
							or filter['name'] in signature):
						job[filter['name']] = True
					elif filter.get('type') == 'location':
						if 'all/tier' in signature:
							job[filter['name']] = True
						elif any(match in signature for match in filter.get('matches', ('None',))) \
								or filter['name'] in signature:
							job[filter['name']] = True

			jobs.append(job)
	format_to_sheet(jobs, plain_filters)


def format_to_sheet(report, filters):
	headings = 'device, test_name, '
	content = []
	for item in report:
		row = ''
		row = append_column(row, item['device'])
		row = append_column(row, item['test_name'])
		for heading in filters:
			row = append_column(row, item.get(heading, ""))
		if not content:
			content.append(headings + ', '.join(filters))
		else:
			content.append(row)
	if len(content) == 1:
		print("There are no jobs for the selected criteria.")
	else:
		for line in content:
			print(line)


def append_column(content, value='', indent=''):
	SEPARATOR = ','
	if value is True:
		value = 'Yes'
	if not content:
		res = value + SEPARATOR
	else:
		res = content + indent + value + SEPARATOR
	return res


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
		fields=args.fields,
		show_all_fields=args.show_all_fields,
		ftg_path=args.full_task_graph_path
	)
	if report:
		if args.locate:
			locate_jobs(report)
		else:
			view_report(
				report,
				args.output,
				ignore_no_projects=args.ignore_no_projects,
				branch_breakdown=args.branch_breakdown
			)

