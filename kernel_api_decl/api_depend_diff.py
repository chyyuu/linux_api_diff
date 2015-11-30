import os
import sqlite3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-db_old', help='api database in old kernel', required=True)
parser.add_argument('-db_new', help='api database in new kernel', required=True)
parser.add_argument('-db_obj', help='database of apis that need to be compared', required=False)
parser.add_argument('-output', help='database name of output', required=False)
args = parser.parse_args()

# check args
if not os.path.exists(args.db_old):
	print "[Error] database of elder kernel " + args.db_old + " isn't existed."
	quit()
else: 
	print "database of elder kernel is : " + args.db_old
if not os.path.exists(args.db_new):
	print "[Error] database of newer kernel " + args.db_new + " isn't existed."
	quit()
else: 
	print "database of newer kernel is : " + args.db_new
#if not os.path.exists(args.db_obj):
#	print "[Error] database of object " + args.db_obj + " isn't existed."
#	quit()
#else: 
#	print "database of object is : " + args.db_obj

# connect to database
conn_old = sqlite3.connect(args.db_old)
conn_new = sqlite3.connect(args.db_new)
if  args.db_obj:
	conn_obj = sqlite3.connect(args.db_obj)
cur_old = conn_old.cursor()
cur_new = conn_new.cursor()
if args.db_obj:
	cur_obj = conn_obj.cursor()

# get decls table of object database
decls_obj = []
if args.db_obj:
	cur_obj.execute('select * from decls')
	decls_obj = cur_obj.fetchall()
	if len(decls_obj) == 0:
		print "[Error] read nothing from table decls of database " + args.db_obj
		quit()
else:
	cur_old.execute('select * from decls')
	decls_obj = cur_old.fetchall()

# get macros table of object database
# note: macros table only exist in database which generateed by kernel_api.py in mode 2,
#		so if db_obj is not set, macros_obj will be empty and useless
macros_obj = []
if args.db_obj:
	cur_obj.execute('select * from macros')
	macros_obj = cur_obj.fetchall()
	if len(macros_obj) == 0:
		print "[Error] read nothing from table macros of database " + args.db_obj
		quit()

# create output database
OUTPUT_DB = ''
if args.output:
	OUTPUT_DB = args.output
else:
	OUTPUT_DB = 'output.db'
conn_out = sqlite3.connect(OUTPUT_DB)
cur_out = conn_out.cursor()
cur_out.execute('DROP TABLE IF EXISTS decls_chg')
cur_out.execute('CREATE TABLE IF NOT EXISTS decls_chg (name TEXT NOT NULL, file TEXT NOT NULL,\
 start_line INTEGER NOT NULL, kind INTEGER NOT NULL, old_decl TEXT NOT NULL,\
 old_file TEXT NOT NULL, new_decl TEXT NOT NULL, new_file TEXT NOT NULL,\
 type TEXT NOT NULL, PRIMARY KEY(name, file, start_line, kind, old_decl, new_decl, old_file, new_file))')
cur_out.execute('DROP TABLE IF EXISTS macros_chg')
cur_out.execute('CREATE TABLE IF NOT EXISTS macros_chg (name TEXT NOT NULL, file TEXT NOT NULL,\
 start_line INTEGER NOT NULL, old_decl TEXT NOT NULL,\
 old_file TEXT NOT NULL, new_decl TEXT NOT NULL, new_file TEXT NOT NULL,\
 type TEXT NOT NULL, PRIMARY KEY(name, file, start_line, old_decl, new_decl, old_file, new_file))')
conn_out.commit()
print "output database is : " + OUTPUT_DB

# analyze the changes between elder kernel and newer kernel
print "Start analyzing..."

def table_insert(table_name, value_list):
#	print value_list
	if value_list[4].find("\'") >= 0:
		return True
		value_list[4] = value_list[4].replace("\'", "\\\'")
		print value_list

	# fix the \\ in defination
	if table_name == 'macros_chg':
		if value_list[5].find("'") >= 0:
			value_list[5] = value_list[5].replace("'", "''")
		if value_list[3].find("'") >= 0:
			value_list[3] = value_list[3].replace("'", "''")

	if value_list[6].find("\'") >= 0:
		return True
		value_list[6] = value_list[6].replace("\'", "\\\'")
		print value_list
	if table_name == 'decls_chg':
		if len(value_list) != 9:
			print "[Error] value_list don't contain enough values to insert table decls_chg"
			return False
		if not cur_out.execute("INSERT INTO decls_chg VALUES('%s', '%s', %d, %d, '%s',\
 '%s', '%s', '%s', '%s')" % (value_list[0], value_list[1], value_list[2], value_list[3],\
 value_list[4], value_list[5], value_list[6], value_list[7], value_list[8])):
			print value_list
		return True
	# insert item into table macros_chg
	if table_name == 'macros_chg':
		if len(value_list) != 8:
			print "[Error] value_list don't contain enough values to insert table macros_chg"
			return False
#		print value_list
		if not cur_out.execute("INSERT INTO macros_chg VALUES('%s', '%s', %d, '%s',\
 '%s', '%s', '%s', '%s')" % (value_list[0], value_list[1], value_list[2], value_list[3],\
 value_list[4], value_list[5], value_list[6], value_list[7])):
			print value_list
		return True

# filter reduplicated contents
def filter_decls(decls):
	if decls[0][0] == "task_struct":
	   print decls[0][0]
	temp = decls[:]
	if decls[0][1] == 3:
		for d in decls:
			if (len(d[4]) - len(d[0])) <= 11:
				temp.remove(d)
	return temp

#def get_rel_path(abs_path):
#	if not abs_path.startswith('/'):
#		return abs_path
#	arch_pos = 0
#	include_pos = 0
#	kernel_pos = 0
#	if abs_path.find("")

NOT_FOUND = 'NOT FOUND'
decls_records = []
if args.db_obj:
	NAME = 1
	FILE = 0
	START_LINE = 2
	KIND = 6
else:
	NAME = 0
	FILE = 2
	START_LINE = 3
	KIND = 1
# find the top kernel source path
cur_old.execute('select file from decls where file like "%kconfig.h"')
cur_new.execute('select file from decls where file like "%kconfig.h"')
kernel_dir_old = cur_old.fetchone()[0].replace("/./", "/")
kernel_dir_new = cur_new.fetchone()[0].replace("/./", "/")
kdir_len_old = len(kernel_dir_old[:-23])
kdir_len_new = len(kernel_dir_new[:-23])

# process differences in decls
for d in decls_obj:
	if d[NAME] in decls_records:
		continue
	decls_records.append(d[NAME])
	sql_cmd = "select * from decls where name='%s' and type!=1 order by type" % d[NAME]
	value_list = []
	cur_old.execute(sql_cmd)
	cur_new.execute(sql_cmd)
	decls_old = list(cur_old.fetchall())
	decls_new = list(cur_new.fetchall())

#	if d[NAME] == "task_struct":
#		print d[NAME]
	if len(decls_old) > 1:
		decls_old = filter_decls(decls_old)[:]
	if len(decls_new) > 1:
		decls_new = filter_decls(decls_new)[:]
#	if d[NAME] == "task_struct":
#		print len(decls_old)

	if len(decls_old) == 0 and len(decls_new) == 0:
		print "[Warning] declaration \'" + d[NAME] + "\' isn't found in both old and new database."
		continue
	elif len(decls_old) == 0:
		value_list = [d[NAME], d[FILE], d[START_LINE], d[KIND], NOT_FOUND, NOT_FOUND, decls_new[0][4], decls_new[0][2], 'ADD']
		if not table_insert('decls_chg', value_list):
			print "table_insert failed."
			quit()
	elif len(decls_new) == 0:
		value_list = [d[NAME], d[FILE], d[START_LINE], d[KIND], decls_old[0][4], decls_old[0][2], NOT_FOUND, NOT_FOUND, 'DELETE']
		if not table_insert('decls_chg', value_list):
			print "table_insert failed."
			quit()
	elif len(decls_old) == len(decls_new):
		for i in range(len(decls_old)):
			# replace "/./" from file column
			decls_old[i] = list(decls_old[i])
			decls_new[i] = list(decls_new[i])
			decls_old[i][2] = decls_old[i][2].replace("/./", "/")
			decls_new[i][2] = decls_new[i][2].replace("/./", "/")
	
			if decls_old[i][2][kdir_len_old:] == decls_new[i][2][kdir_len_new:] and decls_old[i][4] == decls_new[i][4]:
				continue
			else:
				change_type = ''

				if (not decls_old[i][2][kdir_len_old:] == decls_new[i][2][kdir_len_new:]) and decls_old[i][4] == decls_new[i][4]:
					change_type = "FILE CHANGED"
				elif decls_old[i][2][kdir_len_old:] == decls_new[i][2][kdir_len_new:] and (not decls_old[i][4] == decls_new[i][4]):
					change_type = "DECL CHANGED"
				else:
					change_type = "ALL CHANGED"
				value_list = [d[NAME], d[FILE], d[START_LINE], d[KIND], decls_old[i][4], decls_old[i][2], decls_new[i][4], decls_new[i][2], change_type]
				if not table_insert('decls_chg', value_list):
						print "table_insert failed."
						quit()
	# found different number of results from old and new decls
	else:
		if len(decls_old) > len(decls_new):
			less = decls_new
			more = decls_old
			kdir_len_less = kdir_len_new
			kdir_len_more = kdir_len_old
		else:
			less = decls_old
			more = decls_new
			kdir_len_less = kdir_len_old
			kdir_len_more = kdir_len_new
		for l in less:
			l = list(l)
			l[2] = l[2].replace("/./", "/")
			for m in more:
				m = list(m)
				m[2] = m[2].replace("/./", "/")
				# type and file are same
				if l[1] == m[1] and l[2][kdir_len_less:] == m[2][kdir_len_more:]:
					# definations are different
					if not l[4] == m[4]:
						if len(decls_old) > len(decls_new):
							value_list = [d[NAME], d[FILE], d[START_LINE], d[KIND], m[4], m[2], l[4], l[2], "DECL CHANGED"]
						else:
							value_list = [d[NAME], d[FILE], d[START_LINE], d[KIND], l[4], l[2], m[4], m[2], "DECL CHANGED"]
						if not table_insert('decls_chg', value_list):
							print "table_insert failed."
							quit()
						break

#process differences in macros
macros_records = []
for m in macros_obj:
	if m[NAME] in macros_records:
		continue
	macros_records.append(m[NAME])
	sql_cmd = "select * from decls where name='%s' and type = 1 order by file" % m[NAME]
	value_list = []
	cur_old.execute(sql_cmd)
	cur_new.execute(sql_cmd)
	macros_old = list(cur_old.fetchall())
	macros_new = list(cur_new.fetchall())

	if len(macros_old) == 0 and len(macros_new) == 0:
		print "[Warning] macro \'" + m[NAME] + "\' isn't found in both old and new database."
		continue
	elif len(macros_old) == 0:
		value_list = [m[NAME], m[FILE], m[START_LINE], NOT_FOUND, NOT_FOUND, macros_new[0][4], macros_new[0][2], 'ADD']
		if not table_insert('macros_chg', value_list):
			print "table_insert failed."
			quit()
	elif len(macros_new) == 0:
		value_list = [m[NAME], m[FILE], m[START_LINE], macros_old[0][4], macros_old[0][2], NOT_FOUND, NOT_FOUND, 'DELETE']
		if not table_insert('macros_chg', value_list):
			print "table_insert failed."
			quit()
	elif len(macros_old) == len(macros_new):
		for i in range(len(macros_old)):
			# replace "/./" from file column
			macros_old[i] = list(macros_old[i])
			macros_new[i] = list(macros_new[i])
			macros_old[i][2] = macros_old[i][2].replace("/./", "/")
			macros_new[i][2] = macros_new[i][2].replace("/./", "/")
			
			if macros_old[i][2][kdir_len_old:] == macros_new[i][2][kdir_len_new:] and macros_old[i][4] == macros_new[i][4]:
				continue
			else:
				change_type = ''
				if (not macros_old[i][2][kdir_len_old:] == macros_new[i][2][kdir_len_new:]) and macros_old[i][4] == macros_new[i][4]:
					change_type = "FILE CHANGED"
				elif macros_old[i][2][kdir_len_old:] == macros_new[i][2][kdir_len_new:] and (not macros_old[i][4] == macros_new[i][4]):
					change_type = "DECL CHANGED"
				else:
					change_type = "ALL CHANGED"
				value_list = [m[NAME], m[FILE], m[START_LINE], macros_old[i][4], macros_old[i][2], macros_new[i][4], macros_new[i][2], change_type]
				if not table_insert('macros_chg', value_list):
					print "table_insert failed."
					quit()
	# found different number of results from old and new macros
	else:
		# for debug
#		print m[NAME]
		if len(macros_old) > len(macros_new):
			less = macros_new
			more = macros_old
			kdir_len_less = kdir_len_new
			kdir_len_more = kdir_len_old
		else:
			less = macros_old
			more = macros_new
			kdir_len_less = kdir_len_old
			kdir_len_more = kdir_len_new
		for le in less:
			le = list(le)
			le[2] = le[2].replace("/./", "/")
			for mo in more:
				mo = list(mo)
				mo[2] = mo[2].replace("/./", "/")
				# file is same
				if le[2][kdir_len_less:] == mo[2][kdir_len_more:]:
					# if found the same one, jump out the loop
					if le[4] == mo[4]:
						break
					else:
						if len(macros_old) > len(macros_new):
							value_list = [m[NAME], m[FILE], m[START_LINE], mo[4], mo[2], le[4], le[2], "DECL CHANGED"]
						else:
							value_list = [m[NAME], m[FILE], m[START_LINE], le[4], le[2], mo[4], mo[2], "DECL CHANGED"]
						if not table_insert('macros_chg', value_list):
							print "table_insert failed."
							quit()
						break
		
conn_out.commit()
print "Finished"

