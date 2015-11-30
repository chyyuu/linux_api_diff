##Linux内核接口分析系统使用文档      

####1 内核接口信息收集        

1. 准备好一个完整的Linux内核源码，这里假设路径为/home/xxx/linux/  

2. 正常编译该Linux内核源码，并确认编译成功   
    
3. 运行kernel_api.py脚本：
 
		$python kernel_api.py -obj /home/xxx/linux/ -abs /home/xxx/linux/ -mode 1   
其中-obj是指要分析的源码目录，-abs是linux内核源码的路径，-mode 1是选择模式1，即分析目标源码中所有的接口信息

4. 运行结束后当前目录下应该会生成api_declare.db，其中保存了目标版本内核的接口信息
5. 为了保证以后再次运行时不会覆盖该文件，应该及时将该文件重命名，最好以Linux的内核版本命名

注：如果不在当前目录下使用该工具时，需要将脚本中的clang_plugin变量的相对路径修改为绝对路径，否则工具无法找到clang插件  
                    
####2 接口差异性分析  

1. 准备好两个版本的Linux内核接口信息数据库（由“内核接口信息收集分析”得到），这里假设为linux-3.8.db和linux-3.14.db

2. 分析目标代码所使用的内核接口，这里假设目标代码为内核中的drivers/net/ehternet/intel/e1000（注：如果想要对两个版本的内核中所有的接口进行差异性分析，这里的步骤2可以跳过）:

		$python kernel_api.py -obj /home/xxx/linux/drivers/net/ehternet/intel/e1000/ -abs /home/xxx/linux/ -mode 2

3. 运行结束后能够生成数据库文件api_depend.db，其中储存着目标代码所使用的内核接口信息

4. 开始进行差异性分析：

		$python api_depend_diff.py -db_old linux-3.8.db -db_new linux-3.14.db -db_obj api_depend.db -output linux-3.8-3.14-diff.db
如果想要对整个内核中的接口信息进行差异分析，那么上面的命令中的参数-db_obj可以不予设置，如下：

		$python api_depend_diff.py -db_old linux-3.8.db -db_new linux-3.14.db -output linux-3.8-3.14-diff.db
这时，系统会以-db_old参数指定的数据库为标准在两个版本的数据库之间进行接口差异分析，因此可以获得哪些接口被删除，和哪些接口发生了变化，如果想要获得哪些接口是新添加的，那么需要将-db_old和-db_new两个参数指定的数据库进行调换，然后所得的数据库中显示被删除的接口便是从旧版本到新版本内核后新添加的接口，命令如下：
		
		$python api_depend_diff.py -db_old linux-3.15.db -db_new linux-3.8.db -db_obj api_depend.db -output linux-3.14-3.8-diff.db

5. 第4步结束后会生成数据库文件linux-3.8-3.15-diff.db，如果不指定参数-output的话，默认会生成output.db，e1000所使用的接口信息的差异分析结果就储存在该数据库文件中
                   
####3 将结果转化为html        

差异性分析的结果是保存在数据库文件中的，如果想要查看的话可以使用工具sqliteman等来查看，sqliteman的安装方法：

		$sudo apt-get install sqliteman

如果需要以更直接的方式查看差异性分析的结果，可以使用db_to_html.py将结果转换成html格式:

		$python db_to_html.py
     
该工具自动读取当前目录下的output.db文件（如果你的结果没有使用工具的默认命名，那么需要修改结果文件的名称为output.db），并将其中的内容转换成html格式到results.html，然后使用浏览器打开该文件即可

注：目前该脚本只能对差异分析所生成的数据库文件使用，无法对其他分析过程所生成的数据库文件使用

####4 将结果保存到MySQL 

为了提供更多的数据库管理方式和结果查看方式，系统提供了将sqlite3生成的数据库文件导入到MySQL中的工具，即sqlite_to_mysql.py

		$python sqlite_to_mysql.py -sqlite api_denpend.db -mysql test -user root -pwd xxx

这里假设MySQL使用的数据库为test，用户名为root，密码为xxx，需要转换的数据库文件为api_depend.db

成功后应该会在MySQL中的test数据库中出现api_depend.db中拥有的表和相应的内容。

注：该工具理论上应该可以对所有的数据库文件使用，但有可能会出现一些sql的语法错
