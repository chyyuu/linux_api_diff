#!/bin/python

import os
import sys
import sqlite3
import argparse
import datetime

start = datetime.datetime.now()
parser = argparse.ArgumentParser()
parser.add_argument('-obj', help='object file or directory', required=False)
parser.add_argument('-mode', help='1 -- analyze all apis in object directory\n2 -- analyze apis used in object directory', required=True)
parser.add_argument('-cmd_file', help='file to extract from', required=False)
args = parser.parse_args()

# specify the object directory to analyze
OBJECT = ''
if args.obj:
	OBJECT = args.obj
else:
	OBJECT = os.getcwd() 

# check the MODE
MODE = 0
if args.mode == '1' or args.mode == '2':
	MODE = int(args.mode)
	print "Choose Mode : " + args.mode
else:
	print "[Erroe] Mode argument is invalid."
	quit()

# find files that need to be analyzed
SRC_LIST = []
if os.path.isdir(OBJECT):
	temp = os.popen('find %s -name "*.o"' % OBJECT).read().strip().split('\n')
	SRC_LIST = temp[:]
	for t in temp:
		if t.find("built-in") >= 0:
			SRC_LIST.remove(t)
	print "Files to be analyzed :", len(SRC_LIST)
elif os.path.exists(OBJECT):
	SRC_LIST.append(OBJECT)
else:
	print "[ERROR] argument -obj is invalid"

# initialize sqlite3 database
print "Initializing database file"
db_file = ''
if MODE == 1:
	db_file = 'api_declare.db'
elif MODE == 2:
	db_file = 'api_depend.db'

if os.path.exists(os.getcwd() + '/' + db_file):
	os.system("rm " + db_file)
	print "delete " + db_file
conn = sqlite3.connect(os.getcwd() + "/" + db_file)
cur = conn.cursor()


if MODE == 1:
	cur.execute('CREATE TABLE IF NOT EXISTS decls (name TEXT NOT NULL, type INTEGER NOT NULL, file TEXT NOT NULL, linum INTEGER NOT NULL, decl TEXT NOT NULL, PRIMARY KEY(name, file, decl))')
	cur.execute('CREATE TABLE IF NOT EXISTS record_fields (name TEXT NOT NULL, fname TEXT NOT NULL, decl TEXT NOT NULL, PRIMARY KEY(name, fname))')
	cur.execute('CREATE TABLE IF NOT EXISTS incdeps (file TEXT NOT NULL, linum TEXT NOT NULL, included TEXT NOT NULL, PRIMARY KEY(file, linum, included))')
	cur.execute('CREATE TABLE IF NOT EXISTS explored (file TEXT NOT NULL, PRIMARY KEY(file))')
	conn.commit()
print "Database file is " + db_file

# start analyzing
print "Start analyzing... "
plugin = ''
if MODE == 1:
	plugin = './clang-plugins/build/lib/DumpDecls.so'
elif MODE == 2:	
	plugin = './clang-plugins/build/lib/DeclFilter.so'
print "clang plugin : " + plugin
# set kernel compile args
asm_args = '-include ' + os.path.realpath(sys.path[0]) + '/fake_asm.h'
#clang_include = '-I/usr/local/lib/clang/3.3/include'
clang_include = '-I/home/chyyuu/llvm-related/install/include/clang'
kernel_args = ''
compile_cmd = []
abspath = ''

# auto analyze kernel compile args
def cmp_args_gen(filename):
	global compile_cmd
	global abspath
#	print "Analyzing compile arguments..."
	cmd_file = os.path.dirname(filename) + "/." + os.path.basename(filename) + '.cmd'
	cmd_files = []
	if not os.path.exists(cmd_file):
		if os.path.isdir(OBJECT):
			cmd_files = os.popen('find %s -name "*.o.cmd"' % OBJECT).read().strip().split('\n')
		else:
			cmd_files = os.popen('find %s -name "*.o.cmd"' % os.path.dirname(OBJECT)).read().strip().split('\n')
		if len(cmd_files) == 0:
			print "Can't find .o.cmd files, analyze compile args failed."
			quit()
		if not args.cmd_file:
			for c in cmd_files:
				if c.find('built-in') < 0 and os.path.exists(c.replace('o.cmd', 'c').replace('/.', '/')):
					cmd_file = c
					print "Extract compile command from file : " + cmd_file
					break
		else:
			cmd_file = args.cmd_file
		if cmd_file == '':
			print "No file to extract compile command."
			quit()

	compile_cmd = os.popen('sed -n "1,1p" %s' % cmd_file).read().strip().split(' -')
	temp = compile_cmd[:]
	print "cmd_file:: ", cmd_file
	print "compile_cmd:: ",compile_cmd
	print "temp:: ",temp
	
	# analyze the absolute path of file
	for cc in temp:
		if cc == '':
			continue
		elif cc.startswith('I') or cc.startswith('D') or cc.startswith('i'):
			if abspath == '' and cc.startswith('I/') and cc.find('/arch/') > 0:
				abspath = cc
			continue
		else:
			compile_cmd.remove(cc)
			continue
	# change relpath to abspath
	if abspath == '':
		print "can not find abspath."
		quit()
	kernel_top_dir = abspath[1:abspath.find('/arch/')]
#	print "kernel top dir is : " + kernel_top_dir
	temp = compile_cmd[:]
	compile_cmd = []
	for cc in temp:
		if cc.startswith('I') and not cc.startswith('I/'):
			compile_cmd.append('I' + kernel_top_dir + '/' + cc[1:]) 
		elif cc.find('\\#s') >= 0:
			compile_cmd.append(cc.replace('\\#s', '#s'))
		else:
			compile_cmd.append(cc)

# backup and restore specific file
file_list = []
backup_count = 0
def backup_file(file_name):
        global file_list
        global backup_count
	if not os.path.exists(file_name):
		print "[Error] file isn't existed"
		return False	
	if os.path.exists(file_name + '.bak'):
                backup_count += 1
		return True
        file_list.append(file_name)
	if os.system("cp %s %s.bak" % (file_name, file_name)) == 0:
		return True
	else:
		return False

def restore_file(file_name):
        global file_list
        global backup_count
        if file_name == '':
                for f in file_list:
                        os.system("mv %s.bak %s" % (f, f))
                return True
        else:
                if backup_count > 0:
                        backup_count -= 1
                        return True
                elif not os.path.exists(file_name + '.bak'):
		        print "[Error] backup file isn't existed"
		        return False
	        if os.system("mv %s.bak %s" % (file_name, file_name)) == 0:
                        file_list.remove(file_name)
		        return True
        	else:
	        	return False

# function to process error which could be solved
def VLAIS_process(bug_info):
	info_list = bug_info.strip().split('\n')
	err_content = []
	for i in info_list:
		if i.find("variable length array in structure") >= 0:
			err_content.append(i)
			
	for i in err_content:
		first_colon = i.find(':')
		second_colon = i.find(':', first_colon + 1)
		file_name = i[0:first_colon]
		line = i[first_colon + 1:second_colon]
		
		if not backup_file(file_name):
			return False
		sed_cmd = "sed -n '%sp' %s" % (line, file_name)
		orig_line = os.popen(sed_cmd).read()
		mod_line = ''
		if orig_line.find('[') >= 0:
			sed_cmd = "sed -n '%s,%ss/\[.*\]/\[0\]/p' %s" % (line, line, file_name)
			mod_line = os.popen(sed_cmd).read()
		else:
			mod_line = "//" + orig_line
		sed_cmd = "sed -e '%si%s' -e '%sd' %s > ./tmp/temp.c" % (line, mod_line, line, file_name)
		#print sed_cmd
		os.system("echo %s >> ./tmp/sed_cmd" % sed_cmd)
		os.system(sed_cmd)
		os.system("cp ./tmp/temp.c %s" % file_name)

	print "process " + s + " again"
	if os.system(command) != 0:
		error_handle()
		restore_file(file_name)
	elif not restore_file(file_name):
		return False
	return True

def common_error_process(bug_info):
        info_list = bug_info.strip().split('\n')
        err_content = []
        for i in info_list:
                if i.find(": error:") >= 0:
                        err_content.append(i)
        for i in err_content:
                first_colon = i.find(':')
                second_colon = i.find(':', first_colon + 1)
                file_name = i[0:first_colon]
                line = i[first_colon + 1:second_colon]
                line_no = int(line)

                if not backup_file(file_name):
                        return False
                sed_cmd = "sed -n '%sp' %s" % (line, file_name)
                orig_line = os.popen(sed_cmd).read()
                if i.find("unsupported inline asm:") >= 0:
                        mod_line = 'int tmp = -1;'
                        line = str(line_no - 3)
                elif i.find("array size is negative") >= 0:
                        mod_line = '//' + orig_line
                else:
                        mod_line = ''
                sed_cmd = "sed -e '%si%s' -e '%sd' %s > ./tmp/temp.c" % (line, mod_line, line, file_name)
                os.system("echo %s >> ./tmp/sed_cmd" % sed_cmd)
                os.system(sed_cmd)
                os.system("cp ./tmp/temp.c %s" % file_name)

        print "process " + s + " again"
        if os.system(command) != 0:
                restore_file('')
                return False
#        if not restore_file(file_name):
#                return False
        return True

# process compiling error "BUILD_BUG_ON"
def BUILD_BUG_ON_process(bug_info):
        info_list = bug_info.strip().split('\n')
        err_content = []
        for i in info_list:
                if i.find("array size is negative") >= 0:
                        err_content.append(i)
        for i in err_content:
                first_colon = i.find(':')
                second_colon = i.find(':', first_colon + 1)
                file_name = i[0:first_colon]
                line = i[first_colon + 1:second_colon]

                if not backup_file(file_name):
                        return False
                sed_cmd = "sed -n '%sp' %s" % (line, file_name)
                orig_line = os.popen(sed_cmd).read()
                mod_line = "//" + orig_line
                sed_cmd = "sed -e '%si%s' -e '%sd' %s > ./tmp/temp.c" % (line, mod_line, line, file_name)
                os.system("echo %s >> ./tmp/sed_cmd" % sed_cmd)
                os.system(sed_cmd)
                os.system("cp ./tmp/temp.c %s" % file_name)

        print "process " + s + " again"
        if os.system(command) != 0:
                restore_file(file_name)
                return False
        if not restore_file(file_name):
                return False
        return True

# common error handler
def error_handle():
	command = ' '.join(['clang', clang_args, asm_args, clang_include, kernel_args, s, '>> ./tmp/log 2>./tmp/bug_info'])
	os.system(command)
	bug_info = os.popen("cat ./tmp/bug_info").read()
        # process VLAIS error
	if bug_info.find('variable length array in structure') >= 0:
		print "find VLAIS error, try to fix..."
		if not VLAIS_process(bug_info):
			print "fix failed, please fix it manually"
			quit()
		print "fix successed, now continue..."
        # process common error
        elif bug_info.find(": error:") >= 0:
                print "find common error, try to fix..."
                if not common_error_process(bug_info):
                        print "fix failed, please fix it manually"
                        quit()
                print "fix successed, now continue..."
	else:
		print "can't process this error, please fix it manually"
		quit()		

# start to compile object files
database = os.getcwd() + '/' + db_file
#os.chdir(kernel_top_dir)
clang_args = ''
#black_list = ['hmac.o', 'raid10.o', 'ip6_tables.o', 'arp_tables.o', 'ip_tables.o']

# MODE 1 will load dump-decls pass
if MODE == 1:
	clang_args="-cc1 -std=gnu89 -load " + plugin + ' -plugin dump-decls -plugin-arg-dump-decls ' + database
# MODE 2 will load decl-filter pass
elif MODE == 2:	
	clang_args="-cc1 -std=gnu89 -print-stats -load " + plugin + ' -plugin decl-filter -plugin-arg-decl-filter ' + database

# restore temporary log file
os.system('rm -rf ./tmp; mkdir ./tmp; echo > ./tmp/log; echo > ./tmp/error; echo > ./tmp/cmd; echo > ./tmp/sed_cmd')
for s in SRC_LIST:
	print "s in SRC_LIST:: ",s
	# ignore scripts and tools directory
	if s.find('/scripts/') >= 0 or s.find('/tools/') >= 0 or s.find(".mod.") >= 0:
		continue
#	if os.path.basename(s) in black_list:
#		continue
	if not os.path.exists(s.replace('.o', '.c')):
		print "[Warning] file not exist : " + s.replace('.o', '.c')
		continue
	cmp_args_gen(s)
	kernel_args = '-' + ' -'.join(compile_cmd)
        if kernel_args == '-':
            continue
#	print "Compile command is : "
#	print kernel_args

	s = s.replace('.o', '.c')
	print "processing file " + s
	command = ' '.join(['clang', clang_args, asm_args, clang_include, kernel_args, s, '>> ./tmp/log 2>>./tmp/error'])
	os.system('echo %s >> ./tmp/error' % s)
	os.system('echo %s >> ./tmp/log' % s)
	os.system('echo %s >> ./tmp/cmd' % s)
	os.system('echo %s >> ./tmp/cmd' % kernel_args)
	if os.system(command) != 0:
		error_handle()
# restore files which were modified
restore_file('')
print "Finished"

# compute the cost time
end = datetime.datetime.now()
print "total cost time : " + str((end - start).seconds) + 's'
