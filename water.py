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
from multiprocessing import Pool

#### Helper functions ####

def print_usage():

	print ("\nUsage:\n"
		"  python water.py -r <path to cloned git repo> -s <path to snapshot of project>\n\n"
		"Required arguments:\n"
		"    -r <path>    The path to the git repo to be compared against\n"
		"    -s <path>    The path to the directory containing the snapshot of code to be analyzed\n\n"
		"File filtering:\n"
		"  Water attempts to ignore files which will likely bias the output, such as binaries and\n"
		"  eps files.  You can disable this, but it's probably a really bad idea.\n\n"
		"  Ignored files and extensions: %s\n\n"
		"Optional analysis arguments:\n"
		"    -m           Disable multithreading (implied by -v and -V)\n"
		"    -i           Disable the ignored files list, even though they'll probably not be matched properly\n"
		"                  THIS OPTION CAN GIVE YOU GARBAGE DATA IF YOU AREN'T CAREFUL\n"
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
		"    water.csv    A CSV file in your working directory with the analysis results.\n\n"
		% str(ignore_files_list)[1:-1])

def analyze_file(root,filenames):

# This is the core of the analysis, which allows us to use multiprocessing

	if verbose:
		global file_count

	for filename in filenames:

		# If we're in a .git directory, move on to the next directory

		if root.startswith(os.path.join(source,'.git')):

			if verbose:
				print(' Ignoring %s file(s) from %s: .git directory' % (len(filenames),root))
				file_count += 1

			break

		# If the file has an ignored extension, move on to the next file

		if ignore_files and filename.endswith(ignore_files_list):

			if verbose:
				print(' Ignoring file %s (%s of %s): On the ignored files list' %
					(filename,file_count,total_files))
				file_count += 1

			continue

		# Set up the in-memory database

		db_conn = sqlite3.connect(':memory:')
		cursor = db_conn.cursor()

		cursor.execute('''CREATE TABLE data (filename TEXT,
		author_name TEXT, author_email TEXT, author_date TEXT,
		committer_name TEXT, committer_email TEXT, committer_date TEXT,
		commit_hash TEXT, number_lines INTEGER,
		unique(filename, author_name, author_email, author_date,
		committer_name, committer_email, committer_date, commit_hash)
		ON CONFLICT IGNORE)''')

		# Get all the commits related to the current file

		current_file = os.path.join(root,filename)

		if verbose:
			print('\n Analyzing file (%s of %s): %s' % (file_count,total_files,current_file))
			file_count += 1

		git_log_command = ("git -C %s log --follow -p -M "
			"--pretty=format:'"
			"hash: %%H%%n"
			"author_name: %%an%%nauthor_email: %%ae%%nauthor_date:%%ai%%n"
			"committer_name: %%cn%%ncommitter_email: %%ce%%ncommitter_date: %%ci%%n"
			"EndPatch' -- %s"
			% (repo,current_file[len(source):]))

		git_log_raw = subprocess.Popen([git_log_command], stdout=subprocess.PIPE, shell=True)

		git_log = list()

		patchline = namedtuple('patchline','commit_hash author_name author_email author_date '
			'committer_name committer_email committer_date '
			'linetext')

		# Set some defaults, just in case

		author_name = author_email = author_date = '(Unknown)'
		committer_name = committer_email = committer_date = '(Unknown)'

		linetext = ''

		# Walk through the file's log and store history data

		if obnoxious:
			print('\n   Walking through the git log:')

		for line in git_log_raw.stdout.read().decode("utf-8", errors='ignore').split(os.linesep):

			if len(line) > 0:

				# Bypass lines we don't need.

				if (line.find('diff --git ') == 0 or
					line.find('index ') == 0 or
					line.find('+++ ') == 0 or
					line.find('--- ') == 0 or
					line.find('@@ -') == 0 or
					line.find('rename to ') == 0 or
					line.find('parents: ') == 0 or
					line.find('    ') == 0):
					continue

				# Match header lines

				if line.find('hash: ') == 0:
					commit_hash = line[6:]
					if obnoxious:
						print('    commit_hash: %s' % commit_hash)

				if line.find('author_name:') == 0:
					author_name = line[13:].replace("'","\\'")
					if obnoxious:
						print('    author_name: %s' % author_name)
					continue

				if line.find('author_email:') == 0:
					author_email = line[14:].replace("'","\\'")
					if obnoxious:
						print('    author_email: %s' % author_email)
					continue

				if line.find('author_date:') == 0:
					author_date = line[12:22]
					if obnoxious:
						print('    author_date: %s' % author_date)
					continue

				if line.find('committer_name:') == 0:
					committer_name = line[16:].replace("'","\\'")
					if obnoxious:
						print('    committer_name: %s' % committer_name)
					continue

				if line.find('committer_email:') == 0:
					committer_email = line[17:].replace("'","\\'")
					if obnoxious:
						print('    committer_email: %s' % committer_email)
					continue

				if line.find('committer_date:') == 0:
					committer_date = line[16:26]
					if obnoxious:
						print('    committer_date: %s' % committer_date)
					continue

				# Store additions for comparison. Ignore removals because we
				# are only finding the last person to modify the line (for now)

				if line.find('+') == 0 and len(line[1:].strip()) > 0:
					if obnoxious:
						print('    patch line: %s' % line[1:].strip())

					git_log.append(patchline(commit_hash,author_name,author_email,author_date,
						committer_name,committer_email,committer_date,
						line[1:].strip()))
					continue

		# Now reverse the git log so we search in reverse chronological order to
		# find the first occurance of the intact line. This handles situations
		# where files were deleted and created, and is necessary because
		# git log --follow --reverse <file> doesn't seem to follow renames.

		git_log.reverse()

		# Now walk through the file and look for matches in the git log

		if obnoxious:
			print('\n   Walking through the file:')

		# We have to open in rb because we may encounter binaries

		snapshot_file = open(current_file,'rb')

		matched = 0 # can probably lose this, it'll be in the database
		unmatched = 0

		for fileline in snapshot_file:

			match_found = 0

			if len(fileline.strip()) < sensitivity:
				continue

			if obnoxious:
				print('    File line: %s' % fileline.strip())

			for git_log_line in git_log:

				if git_log_line.linetext.encode() == fileline.strip():

					if obnoxious:
						print('    * Matched: %s\n' % git_log_line.linetext)
					matched += 1
					match_found = 1

					# Brute forcification since sqlite has no 'ON DUPLICATE UPDATE'

					cursor.execute('''INSERT OR IGNORE INTO data (filename,
						author_name, author_email, author_date,
						committer_name, committer_email, committer_date,
						commit_hash, number_lines)
						VALUES (?,?,?,?,?,?,?,?,0)''',
						(current_file,
						git_log_line.author_name, git_log_line.author_email, git_log_line.author_date,
						git_log_line.committer_name, git_log_line.committer_email, git_log_line.committer_date,
						git_log_line.commit_hash))

					cursor.execute('''UPDATE data SET number_lines =
						number_lines+1 WHERE filename = ? AND
						author_name = ? AND author_email = ? AND author_date = ? AND
						committer_name = ? AND committer_email = ? AND committer_date = ? AND
						commit_hash = ?''',
						(current_file,
						git_log_line.author_name, git_log_line.author_email, git_log_line.author_date,
						git_log_line.committer_name, git_log_line.committer_email, git_log_line.committer_date,
						git_log_line.commit_hash))

					break

			if not match_found:
				unmatched += 1

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

		with open(output_csv,'a', newline='', encoding='utf-8') as outfile:
			csv_writer = csv.writer(outfile)

			data = cursor.execute('''SELECT * from data''')
			csv_writer.writerows(data)

		db_conn.close()

#### The real program starts here ####

if __name__ == '__main__':

	source = ''
	repo = ''
	multithreaded = True
	verbose = False
	obnoxious = False
	sensitivity = 5
	output_csv = 'water.csv'
	write_csv_header = True
	ignore_files = True
	ignore_files_list = ('.swp','.bin','.png','.jpg','.gif','.pdf','.eps','.ps','LICENSE')

	print ("\nWater (WWTR) is licensed under the Apache License, Version 2.0\n\n"
		"Copyright Brian Warner <brian@bdwarner.com>\n"
		"Get the most recent version from https://github.com/brianwarner/water\n")

	opts,args = getopt.getopt(sys.argv[1:],'r:s:o:md:iS:vVh')

	for opt,arg in opts:

		if opt == '-h':
			print_usage()
			sys.exit(0)

		elif opt == '-r':
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

		elif opt == '-m':
			multithreaded = False
			print('Option set: Multithreading disabled')

		elif opt == '-i':
			ignore_files = False
			print('Option set: Disabling ignored files list (YOU HAVE BEEN WARNED)')

		elif opt == '-v':
			verbose = True
			multithreaded = False
			print('Option set: verbosity increased (disables multithreading)')

		elif opt == '-V':
			verbose = True
			obnoxious = True
			multithreaded = False
			print('Option set: verbosity increased obnoxiously (disables multithreading)')

		elif opt == '-S':
			sensitivity = arg
			print('Option set: changed sensitivity to %s' % arg)

		elif opt == '-i':
			include_image_files = 1
			print('Option set: not ignoring common image file formats')

	# Make sure we have all the required inputs

	if not source or not repo:
		print_usage()
		sys.exit(0)

	print('\nBeginning analysis.')

	start_time = time.time()

	# Get the total number of files we'll need to consider

	if verbose:
		total_files = sum([len(files) for root, directories, files in os.walk(source)])

		file_count = 1

	# Write the header for the output file

	with open(output_csv,'w') as outfile:
		csv_writer = csv.writer(outfile)

		outfile.write('\ufeff')

		csv_writer.writerow(['File','Author name','Author email','Author date',
			'Committer name','Committer email','Committer date',
			'Commit','Number of lines'])

	# Walk through all the files in the source tarball

	if multithreaded:
		pool = Pool()

	for root, directories, filenames in os.walk(source):

		if multithreaded:
			pool.apply_async(analyze_file,(root,filenames))
		else:
			analyze_file(root,filenames)

	if multithreaded:
		pool.close()
		pool.join()

	elapsed_time = time.time() - start_time

	print('Analysis completed in %s. Results written to %s\n' %
	(datetime.timedelta(seconds=int(elapsed_time)),output_csv))

