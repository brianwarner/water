#!/usr/bin/python3

# Copyright 2018 Brian Warner
# https://github.com/brianwarner/water
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier:  Apache-2.0

import sys
import getopt
import os.path
import sqlite3
import time
import subprocess
from collections import namedtuple
import csv
import datetime

source = ''
repo = ''
verbose = 0
obnoxious = 0
sensitivity = 5
output_csv = 'water.csv'
write_csv_header = 1

#### Helper functions ####

def print_usage():
		print ("\nUsage:\n"
		"  python water.py -r <path to cloned git repo> -s <path to snapshot of project>\n\n"
		"Required arguments:\n"
		"    -r <path>    The path to the git repo to be compared against\n"
		"    -s <path>    The path to the directory containing the snapshot of code to be analyzed\n\n"
		"Optional analysis arguments:\n"
		"    -S <number>  Adjusts sensitivity. Lines shorter than <number> are not considered for matching.\n"
		"                  Whitespace lines are always ignored.\n\n"
		"Optional output arguments:\n"
		"    -o <file>    Specify an alternate filename for the summary CSV\n"
		"    -v           Increase verbosity\n"
		"    -V           Obnoxious verbosity\n"
		"    -h           Print this help message\n\n"
		"Preparing your inputs:\n"
		"  The snapshot directory and the cloned git repo must have the same directory\n"
		"  structure.  For example, if the repo is structured like this:\n\n"
		"    .git\n"
		"    file1\n"
		"    file2\n"
		"    directory1/file3\n"
		"    directory2/file4\n\n"
		"  then the directory with the snapshot must also be structured the same:\n\n"
		"    file1\n"
		"    file2\n"
		"    directory1/file3\n"
		"    directory2/file4\n\n"
		"Output:\n"
		"    water.csv    A CSV file in your working directory with the analysis results.\n\n")

#### The real program starts here ####

print ("\nWater (WWTR) is licensed under the Apache License, Version 2.0\n\n"
	"Copyright 2018 Brian Warner <brian@bdwarner.com>\n"
	"Get the most recent version from https://github.com/brianwarner/water\n")

opts,args = getopt.getopt(sys.argv[1:],'r:s:o:S:vVh')

for opt,arg in opts:
	if opt == '-r':
		if not os.path.isabs(arg):
			repo = os.path.abspath(arg)
		else:
			repo = arg

	elif opt == '-s':
		if os.path.isabs(arg):
			source = arg
		else:
			source = os.path.abspath(arg)+'/'

	elif opt == '-o':
		output_csv = arg
		print('Option set: results will be written to %s' % arg)

	elif opt == '-v':
		verbose = 1
		print('Option set: verbosity increased')

	elif opt == '-V':
		verbose = 1
		obnoxious = 1
		print('Option set: verbosity increased obnoxiously')

	elif opt == '-h':
		print_usage()
		sys.exit(0)

# Make sure we have all the required inputs

if not source or not repo:
	print_usage()
	sys.exit(0)

db_conn = sqlite3.connect(':memory:')
cursor = db_conn.cursor()

cursor.execute('''CREATE TABLE data (filename TEXT,
	author_name TEXT, author_email TEXT, author_date TEXT,
	committer_name TEXT, committer_email TEXT, committer_date TEXT,
	commit_hash TEXT, number_lines INTEGER,
	unique(filename, author_name, author_email, author_date,
	committer_name, committer_email, committer_date, commit_hash)
	ON CONFLICT IGNORE)''')

print('\nBeginning analysis.')

start_time=time.time()

# Get the total number of files we'll need to consider

if verbose:
	total_files = sum([len(files) for root, directories, files in os.walk(source)])
	file_count = 1

# Walk through all the files in the snapshot directory

for root, directories, filenames in os.walk(source):
	for filename in filenames:

		# Check if we're in the .git directory, which should be ignored

		if os.path.join(source,'.git') in root:

			if verbose:
				print('\n Ignoring file (%s of %s): .git directory' % (file_count,total_files))
				file_count += 1
			continue

		if filename[-4:] == '.swp':

			if verbose:
				print('\n Ignoring file (%s of %s): .swp file' % (file_count,total_files))
				file_count += 1
			continue

		current_file = os.path.join(root,filename)

		matched = 0
		unmatched = 0

		if obnoxious:
			print('\n   Walking through the file:')

		# We have to open in rb because we may encounter binaries

		snapshot_file = open(current_file,'rb')

		for file_line_raw in snapshot_file:

			# Set some safe defaults in case the line isn't matched to the git log

			author_name = author_email = author_date = '(Unknown)'
			committer_name = committer_email = committer_date = '(Unknown)'
			commit_hash = ''

			# Escape delimiters and escape characters for a safe Popen

			file_line = file_line_raw.decode("utf-8",errors="ignore").replace("\\","\\\\").replace('"','\\"')

			# Filter out lines which are too short, to reduce false positives

			if len(file_line.strip()) < sensitivity:
				continue

			if obnoxious:
				print('    File line: %s' % file_line)

			# Look for the first patch change which matches the line in the file

			git_log_command = ('git -C %s log -S"%s" --pretty=format:"'
				'hash: %%H%%n'
				'author_name: %%an%%nauthor_email: %%ae%%nauthor_date:%%ai%%n'
				'committer_name: %%cn%%ncommitter_email: %%ce%%ncommitter_date: %%ci%%n'
				'EndPatch" -- %s' % ((repo, file_line, current_file[len(source):])))

			git_log_raw = subprocess.Popen([(git_log_command)],
				stdout=subprocess.PIPE, shell=True)

			# If we found a match, store metadata from the patch

			for line in git_log_raw.stdout.read().decode("utf-8",errors="ignore").split(os.linesep):

				if len(line) == 0:
					continue

				if line.find('hash: ') == 0:
					commit_hash = line[6:]
					match_found = 1
					matched += 1
					if obnoxious:
						print('    commit_hash: %s' % commit_hash)

				if line.find('author_name: ') == 0:
					author_name = line[13:].replace("'","\\'")
					if obnoxious:
						print('    author_name: %s' % author_name)
					continue

				if line.find('author_email: ') == 0:
					author_email = line[14:].replace("'","\\'")
					if obnoxious:
						print('    author_email: %s' % author_email)
					continue

				if line.find('author_date: ') == 0:
					author_date = line[12:22]
					if obnoxious:
						print('    author_date: %s' % author_date)
					continue

				if line.find('committer_name: ') == 0:
					committer_name = line[16:].replace("'","\\'")
					if obnoxious:
						print('    committer_name: %s' % committer_name)
					continue

				if line.find('committer_email: ') == 0:
					committer_email = line[17:].replace("'","\\'")
					if obnoxious:
						print('    committer_email: %s' % committer_email)
					continue

				if line.find('committer_date: ') == 0:
					committer_date = line[16:26]
					if obnoxious:
						print('    committer_date: %s' % committer_date)
					continue

			# If a match was found store the info, otherwise move on

			if commit_hash:

				if obnoxious:
					print('    * Matched: %s\n' % file_line.strip())

				# Brute forcification since sqlite has no 'ON DUPLICATE UPDATE'

				cursor.execute('''INSERT OR IGNORE INTO data (filename,
					author_name, author_email, author_date,
					committer_name, committer_email, committer_date,
					commit_hash, number_lines)
					VALUES (?,?,?,?,?,?,?,?,0)''',
					(current_file,
					author_name, author_email, author_date,
					committer_name, committer_email, committer_date,
					commit_hash))

				cursor.execute('''UPDATE data SET number_lines =
					number_lines+1 WHERE filename = ? AND
					author_name = ? AND author_email = ? AND author_date = ? AND
					committer_name = ? AND committer_email = ? AND committer_date = ? AND
					commit_hash = ?''',
					(current_file,
					author_name, author_email, author_date,
					committer_name, committer_email, committer_date,
					commit_hash))

				continue

			else:
				unmatched += 1

		# After finishing the file, store number of unmatched lines (if any)

		if unmatched:
			cursor.execute(''' INSERT INTO data (filename,
				author_name, author_email, author_date,
				committer_name, committer_email, committer_date,
				commit_hash, number_lines)
				VALUES (?,
				'Unmatched','Unmatched','Unmatched',
				'Unmatched','Unmatched','Unmatched',
				'N/A',?)''', (current_file,unmatched))

		if verbose:
			print('\n  Matched lines: %s' % matched)
			print('  Unmatched lines: %s\n' % unmatched)

		if obnoxious:
			print('  Writing results to %s\n' % output_csv)

		# Check if we need to write a CSV header, incl. UTF-8 BOM

		if write_csv_header:

			with open(output_csv,'w') as outfile:
				csv_writer = csv.writer(outfile)

				outfile.write('\ufeff')

				csv_writer.writerow(['File','Author name','Author email','Author date',
					'Committer name','Committer email','Committer date',
					'Commit','Number of lines'])

			write_csv_header = 0

		# Write the current file's info to CSV

		with open(output_csv,'a', newline='', encoding='utf-8') as outfile:
			csv_writer = csv.writer(outfile)

			data = cursor.execute('''SELECT * from data''')
			csv_writer.writerows(data)

		# Clear out the database for the next file

		cursor.execute("DELETE FROM data")

db_conn.close()

elapsed_time = time.time() - start_time

print('Analysis completed in %s. Results written to %s\n' %
(datetime.timedelta(seconds=int(elapsed_time)),output_csv))

