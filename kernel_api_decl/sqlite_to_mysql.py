#!/bin/python

import os, sys
import argparse
import sqlite3
import MySQLdb

parser = argparse.ArgumentParser()
parser.add_argument('-sqlite', help='sqlite database file to convert', required=True)
parser.add_argument('-mysql', help='mysql database name, default is the name of sqlite database file', required=False)
parser.add_argument('-user', help='username of mysql', required=True)
parser.add_argument('-pwd', help='password of mysql', required=True)
args = parser.parse_args()

# some global variables
table_list = []
table_create_cmd = {}

# check arguments 
if not os.path.exists(args.sqlite):
    print args.sqlite + " is not existed"
    quit()
# connect to sqlite database
conn_sqlite = sqlite3.connect(args.sqlite)
cur_sqlite = conn_sqlite.cursor()
# check tables of database
cur_sqlite.execute("select name from sqlite_master where type='table'")
table_list = cur_sqlite.fetchall()
print "tables of database " + args.sqlite + " are:"
for t in table_list:
    print "\t" + t[0]
# collect create commands of tables below
sqlite_master = cur_sqlite.fetchall()
for t in table_list:
    cur_sqlite.execute("select sql from sqlite_master where type='table' and name='%s'" % t[0])
    cmd = cur_sqlite.fetchall()
    if not cmd:
        print "can't find create command of table " + t[0]
        quit()
    print "create command of table " + t[0] + " is:"
    print cmd[0][0]
    table_create_cmd[t[0]] = cmd[0][0]

# check mysql database argument
mysql_db = ''
if not args.mysql:
    mysql_db = '_'.join(args.sqlite.split('.'))
else:
    mysql_db = args.mysql
print "the name of mysql database is " + mysql_db

# connect to mysql database
host = "localhost"
port = 3306
user = args.user
passwd = args.pwd
try:
    conn_mysql = MySQLdb.connect(host=host,user=user,passwd=passwd,port=port)
    cur_mysql = conn_mysql.cursor()
    cur_mysql.execute("show databases like '%s'" % mysql_db)
    temp = cur_mysql.fetchall()
    # if the database was existed
    if temp:
        print "find database with the same name, do you want delete it? [y/n]"
        choose = raw_input('>>')
        while not choose in ['y', 'n', 'Y', 'N']:
            print "invalid input, please try again"
            choose = raw_input('>>')
        if choose in ['n', 'N']:
            print "please use another database name and try again."
            quit()
        print "delete database " + mysql_db
        cur_mysql.execute("drop database %s" % mysql_db)
    print "create database " + mysql_db
    cur_mysql.execute("create database %s" % mysql_db)
    cur_mysql.execute("use %s" % mysql_db)
    # create tables which extract from sqlite3 database
    for t in table_list:
        print "creating table " + t[0]
        cur_mysql.execute("%s" % table_create_cmd[t[0]].replace("TEXT", "VARCHAR(255) character set gbk"))

    # extract content from sqlite database and store them into mysql database
    for t in table_list:
        cur_sqlite.execute("select * from %s" % t[0])
        content = cur_sqlite.fetchall()
        cmd = table_create_cmd[t[0]]
        cmd = cmd[cmd.find('(') + 1:cmd.find('PRIMARY') - 2]
        for c in content:
            sql = "INSERT INTO " + t[0] + " VALUES("
            print c
            for item in c:
                if type(item) == int:
                    sql += "%d, " % item
                if type(item) == unicode:
                    sql += "'%s', " % item
            sql = sql[:-2] + ')'
            print sql
            cur_mysql.execute(sql)
    conn_mysql.commit()
except MySQLdb.Error,e:
    print "Mysql Error %d: %s" % (e.args[0], e.args[1])

