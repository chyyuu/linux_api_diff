#!/usr/bin/env python

import re, sys, os
import rfc822, datetime
from logparser import LogPatchSplitter
from patterns import patterns

class commit:
	def __init__(self):
		self.commit_id = ''
		self.date = None
		self.author = ('', '')
		self.commit_log = ''
		# use 'filename' : 'diffcontent' to record patch
		self.patch = {}
		self.full_commit = None

	def __str__(self):
		ret  = "\tcommit id: " + self.commit_id + '\n'
		for f in self.patch:
			ret += "\t" + f + '\n\n'
			ret += ''.join(self.get_diff_content(f))
		return ret

	def filter_output(self, key):
		ret  = "\tcommit id: " + self.commit_id + '\n'
		for f in self.patch:
			content = self.get_diff_content(f)
			if len(content) == 0:
				continue
			ret += "\t" + f + '\n\n'
			for c in content:
				if c.find(key) >= 0:
					ret += c
		return ret


	def get_diff_content(self, fname):
		content = []
		block = ''
		isStart = False
		for l in self.patch[fname]:
			if l.startswith("@@"):
				if block != '':
					block += '\n'
					content.append(block)
					block = ''
				isStart = True
			if isStart == True:
				block += "\t" + l
#			if not l.startswith("+++") and l.startswith("+"):
#				if isStart == False:
#					block = ''
#					isStart = True
#				block += "\t" + l 
#				continue
#			if not l.startswith("---") and l.startswith("-"):
#				if isStart == False:
#					block = ''
#					isStart = True
#				block += "\t" + l 
#				continue
#			if isStart == True:
#				block += '\n'
#				content.append(block)
#				isStart = False
		if block != '':
			content.append(block)
		return content

	def full_commit_parser(self, fc):
		if len(fc) < 1:
			return False
	
		m = patterns['commit'].match(fc[0])
		if not m:
			return False
	
		cid = m.group(1)
		self.commit_id = cid
		self.full_commit = fc

		isPatch = False
		afterDate = False
		fname = ''
	
		for line in fc[1:]:
			m = patterns['merge'].match(line)
			if m:
				return False

			m = patterns['date'].match(line)
			if m:
				dt = rfc822.parsedate(m.group(2))
				self.date = datetime.date(dt[0], dt[1], dt[2])
				afterDate = True
				continue
			
			m = patterns['author'].match(line)
			if m:
				self.author = (m.group(1), m.group(2))
				continue

			m = patterns['diff'].match(line)
			if m:
				fname = m.group(2)[2:]
				self.patch[fname] = [line]
				isPatch = True
				continue

			if afterDate == True and isPatch == False:
				self.commit_log += line
				continue

			if isPatch == True:
				self.patch[fname].append(line)
				continue

		if fname == '' or isPatch == False or afterDate == False:
			return False
		return True

def main():
	patches = LogPatchSplitter(sys.stdin)

	commits = []
	for p in patches:
		tmpc = commit()
		if tmpc.full_commit_parser(p) == True:
			commits.append(tmpc)

#	for c in commits:
#		print "=========================================================================="
#		for l in c.patch:
#			print "------------------------------------------------------------------------"
#			for m in c.patch[l]:
#				print m,

	print len(commits)

if __name__ == '__main__':
	main()
