#!/usr/bin/env python

import argparse
import os, sys, re
import sqlite3
from commit_parser import commit
from patterns import err_patterns
from logparser import LogPatchSplitter

# arguments need in analyze
parser = argparse.ArgumentParser()
parser.add_argument('-err_report', help='error report of compiling', required=True)
parser.add_argument('-diff_db', help='difference database of kernel_api_decl', required=True)
parser.add_argument('-old_ver', help='old linux version, like v3.4', required=True)
parser.add_argument('-new_ver', help='new linux version, like v3.4', required=True)
parser.add_argument('-linux_git', help='the path to linux git tree directory', required=True)
args = parser.parse_args()

# check if arguments are valid
print 'Checking arguments...'
if not os.path.exists(args.err_report):
	print "[Error] \'" + args.err_report + "\' is not existed."
	quit()
if not os.path.exists(args.diff_db):
	print "[Error] \'" + args.diff_db + "\' is not existed."
	quit()
if not os.path.exists(args.linux_git):
	print "[Error] \'" + args.linux_git + "\' is not existed."
	quit()

# some useful variables
CUR_DIR = os.path.abspath(os.curdir)
ERR_REPORT = os.path.abspath(args.err_report)
DIFF_DB = os.path.abspath(args.diff_db)
LINUX_GIT = os.path.abspath(args.linux_git)
OLD_VER = args.old_ver
NEW_VER = args.new_ver

# connect to diff database
conn_diff = sqlite3.connect(args.diff_db)
CURSOR_DIFF = conn_diff.cursor()

# check if the linux version numbers is valid
os.chdir(LINUX_GIT)
tags = os.popen('git tag').read().strip().split('\n')
if len(tags) <= 1:
	print "[Error] linux git tree is invalid."
	quit()
if not args.old_ver in tags:
	print "[Error] linux version " + args.old_ver + " is not in linux git tree."
	quit()
if not args.new_ver in tags:
	print "[Error] linux version " + args.new_ver + " is not in linux git tree."
	quit()
print 'Done'

# class of diff result
class Diff:
	def __init__(self, name, fname, start_line, old_decl, old_file, new_decl, new_file, type_chg):
		self.name = name
		self.fname = fname
		self.start_line = start_line
		self.old_decl = old_decl
		self.old_file = old_file
		self.new_file = new_file
		self.new_decl = new_decl
		self.type_chg = type_chg

	def __str__(self):
		ret = ''
		ret += "DECL NAME:\t" + self.name + '\n'
		ret += "FILE NAME:\t" + self.fname + '\n'
		ret += "CHANGE TYPE:\t" + self.type_chg + '\n'
		if self.type_chg == "ADD":
			ret += "DECLARATION:\t" + self.new_decl + '\n'
		if self.type_chg == "DELETE":
			ret += "DECLARATION:\t" + self.old_decl + '\n'
		if self.type_chg == "FILE CHANGED" or self.type_chg == "ALL CHANGED":
			ret += "ORIGIN FILE:\t" + self.old_file + '\n'
			ret += "CURRENT FILE:\t" + self.new_file + '\n'
		if self.type_chg == "DECL CHANGED" or self.type_chg == "ALL CHANGED":
			ret += "ORIGIN DECL:\t" + self.old_decl + '\n'
			ret += "CURRENT DECL:\t" + self.new_decl + '\n'
		return ret

# the class of error
class Error:
	"""
		Error is class of error which is extracted from error report,
		and it stores the detailed information of each error, the reason
		will be contained too
	"""

	def __init__(self, info, code, kind, api):
		self.info = info
		self.code = code
		self.kind = kind
		self.api = api
		self.sub_api = ""
		self.diff_result = []
		self.commit = []
		# suggestion is some patch of linux with similar change
		self.suggestion = []

	def __str__(self):
		ret = ''
		ret += 'INFO : ' + self.info + '\n'
		ret += 'CODE : ' + self.code + '\n'
		ret += 'KIND : ' + self.kind + '\n'
		ret += 'API : ' + self.api + '\n'
		ret += 'SBU API : ' + self.sub_api + '\n'
		return ret

	def set_sub_api(self, sub_api):
		if sub_api == "":
			print "[ERROR]: sub_api is an empty string."
			quit()
		self.sub_api = sub_api
	
	def get_err_info(self):
		ret = self.info + self.code
		return ret

	def interpret(self):
		if self.api == '' or len(self.diff_result) == 0:
			print "[ERROR]: information is incomplete, can not interpret."
			return
		# for general changes
		if self.sub_api == "":
			self.commit = commit_locate(self.api, self.diff_result[0].fname, self.diff_result[0].type_chg)
		else:
		# for some changes between member and fields
			self.commit = commit_locate(self.sub_api, self.diff_result[0].fname, self.diff_result[0].type_chg)
		print "[INTERPRET] this error may be caused by the commit following\n"
		for c in self.commit:
			print c.filter_output(self.api)
		if self.sub_api == "":
			self.suggestion = suggestion_search(self.commit, self.api, self.diff_result[0].type_chg)
		else:
			self.suggestion = suggestion_search(self.commit, self.sub_api, self.diff_result[0].type_chg)
		print "[INTERPRET] and maybe you could fix this error as the following commit does\n"
		for s in self.suggestion:
			print s.filter_output(self.api)

# extract api which has problem from expected error information into problems
def expected_handle(info, next_line, api_name):
	global problems
	code = next_line.strip().split(' ')
	count = len(code) - 1
	while count >= 0:
		if code[count].find(api_name) >= 0:
			break
		count -= 1
	api = code[count - 1]
	error = Error(info, next_line, 'expected', api)
	problems['expected'].append(error)

# no member error has two key string, api_name and member_name,
# we need search diff result through api_name and the related commit
# need to be searched by member_name
def no_member_handle(info, next_line, api_name, member_name):
	global problems
	# the api_name may be like "struct sk_buff", so we should pick out 
	# the "struct"
	names = api_name.split(' ')
	error = Error(info, next_line, 'no member', names[len(names) - 1])
	error.set_sub_api(member_name)
	problems['no member'].append(error)
	
# unknown field error only has field name, the api name need to be found 
# by diff result
def unknown_field_handle(info, next_line, field_name):
	global problems
	api_name = ""
	if field_name == "":
		print "[ERROR]: field_name is empty string."
		quit()
	sql_cmd = 'select * from decls_chg where old_decl like "%' + field_name + '%"'	
	CURSOR_DIFF.execute(sql_cmd)
	result = CURSOR_DIFF.fetchall()
	if len(result) == 0:
		print "[WARNING]: can't find api_name which has field name '" + field_name + "' from diff database, we will try to interpret this error without api_name. "
	elif len(result) > 1:
		first = ""
		for r in result:
			if first == "":
				first = r[0]
				continue
			if first != r[0]:
				print "[WARNING]: found multiple api which has field " + field_name + ", we use the first one as default: " + first
				break
		api_name = first
	else:
		api_name = result[0][0]
	error = Error(info, next_line, 'unknown field', str(api_name))
	error.set_sub_api(field_name)
	problems['unknown field'].append(error)

# HIBIT error handle
def HIBIT_handle(info, next_line, api_name):
	# the api_name is not the really api name, but the variable name
	words = next_line.split(' ')
	api_pos = 0
	while api_pos < len(words):
		if words[api_pos] == api_name:
			api_pos -= 1
			break
		api_pos += 1
	if api_pos < len(words):
		general_handle(info, next_line, words[api_pos], 'HIBIT')
		return
	print "[Warning]: cannot find the api name of this error."
	return

# general error handle
def general_handle(info, next_line, api_name, type_name):
	global problems
	# starts with skb_ may be generated by macro
	if api_name.startswith("skb_"):
		api_name = api_name[4:]
	error = Error(info, next_line, type_name, api_name)
	problems[type_name].append(error)

# get the relative path of LINUX_GIT from abspath
def get_relative_path(abspath):
	os.chdir(LINUX_GIT)
	fname = os.path.basename(abspath)
	cmd = 'find -name "' + fname + '"'
	flist = os.popen(cmd).read().strip().split('\n')
	if flist[0] == '':
		os.popen('git checkout ' + OLD_VER)
		flist = os.popen(cmd).read().strip().split('\n')
	os.chdir(CUR_DIR)
	if flist[0] == '':
		print "[WARNING]: " + fname + " is not existed."
		return fname
	for f in flist:
		if abspath.find(f[1:]) >= 0:
			return f
	print "[WARNING]: can not find relative path of '" + fname + "'."
	return fname

# locate commits which change the api
def commit_locate(api, fname, diff_type):
	rpath = get_relative_path(fname)
	os.chdir(LINUX_GIT)
	git_cmd = ''
	if diff_type.find("CHANGED") > 0 :
		git_cmd = "git log --no-merges -p -G'"
	else:
		git_cmd = "git log --no-merges -p -S'"
	git_cmd += api + "' " + OLD_VER + ".." + NEW_VER + " -- " + rpath[2:]
	# split all commits found
	found = os.popen(git_cmd)
	patches = LogPatchSplitter(found)
	commits = []
	# construct commit object for each commit with patch
	for p in patches:
		tmpc = commit()
		if tmpc.full_commit_parser(p) == True:
			commits.append(tmpc)
	os.chdir(CUR_DIR)
	return commits

def suggestion_search(reason_commits, api, chg_type):
	os.chdir(LINUX_GIT)
	git_cmd = ''
	commits = []

	# find suggestions from reason commits
	if len(reason_commits) > 0:
		git_cmd = "git log -p -1 " + reason_commits[0].commit_id
		reason_patch = LogPatchSplitter(os.popen(git_cmd))
		for rp in reason_patch:
			rc = commit()
			if rc.full_commit_parser(rp) == True:
				commits.append(rc)

	if chg_type == 'DECL CHANGED':
		git_cmd = "git log --no-merges -p -2 -G'"
	else:
		git_cmd = "git log --no-merges -p -2 -S'"
	git_cmd += api + "' " + OLD_VER + ".." + NEW_VER + " -- drivers/"
	patches = LogPatchSplitter(os.popen(git_cmd))
	
	for p in patches:
		tmpc = commit()
		if tmpc.full_commit_parser(p) == True:
			commits.append(tmpc)
	os.chdir(CUR_DIR)
	return commits

# search diff results from database
def search_diff_results(problems):
	for ty in problems:
		errs = problems[ty]
		for err in errs:
			sql_cmd = "select * from decls_chg where name=\'" + err.api + "\'"
			CURSOR_DIFF.execute(sql_cmd)
			result = CURSOR_DIFF.fetchall()
			if len(result) > 0:
				for r in result:
					diff = Diff(r[0],r[1],r[2],r[4],r[5],r[6],r[7],r[8])
					err.diff_result.append(diff)
			sql_cmd = "select * from macros_chg where name=\'" + err.api + "\'"
			CURSOR_DIFF.execute(sql_cmd)
			result = CURSOR_DIFF.fetchall()
			if len(result) > 0:
				for r in result:
					diff = Diff(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7])
					err.diff_result.append(diff)

# analyze error report, extract error type and reason
print 'Reading and analyzing error report...',
err_file = open(ERR_REPORT, 'r')
# store error type and the corresponding apis, the key is error type
problems = {}
problems['expected'] = []
problems['implicit'] = []
problems['undeclared'] = []
problems['arguments'] = []
problems['no member'] = []
problems['unknown field'] = []
problems['HIBIT'] = []

for line in err_file:
	m = err_patterns['expected'].match(line)
	if m:
		expected_handle(line, err_file.next(), m.group(3))
		continue
	m = err_patterns['implicit'].match(line)
	if m:
		general_handle(line, err_file.next(), m.group(3), 'implicit')
		continue
	m = err_patterns['undeclared'].match(line)
	if m:
		general_handle(line, err_file.next(), m.group(3), 'undeclared')
	m = err_patterns['arguments'].match(line)
	if m:
		general_handle(line, err_file.next(), m.group(3), 'arguments')
		continue
	# no member error has two key string, the api name and the member name
	m = err_patterns['no member'].match(line)
	if m:
		no_member_handle(line, err_file.next(), m.group(3), m.group(4))
		continue
	# unknown field error only output the field name, api name should be 
	# found in diff database
	m = err_patterns['unknown field'].match(line)
	if m:
		unknown_field_handle(line, err_file.next(), m.group(3))
		continue
	# HIBIT is "has initializer but incomplete type"
	m = err_patterns['HIBIT'].match(line)
	if m:
		HIBIT_handle(line, err_file.next(), m.group(3))
		continue

p_count = 0
for p in problems:
	for e in problems[p]:
		p_count += 1

print 'Finished'
print "Found " + str(p_count) + " problems in error report."

print "Querying differences results in database...",
search_diff_results(problems)
print 'Finished'
#problems['arguments'][0].interpret()

print 'Start to analyze each problem...\n'
for p in problems:
	for e in problems[p]:
		# if cannot find diff result, we will ignore it
		if len(e.diff_result) == 0:
			continue
	#	print e
		print "----Error information as follows:"
		print "\t" + e.get_err_info()
		print "----Related difference analysis results as follows:"
		print e.diff_result[0]
		print 'Try to interpret...'
		e.interpret()
		print 'Interpret finished.'
print 'All problems done.'
#problems['undeclared'][6].interpret()



