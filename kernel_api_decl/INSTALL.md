##Linux内核接口分析系统安装说明

####需要的软件

1. python
2. sqlite3
3. libsqlite3-dev(under ubuntu)
4. LLVM/clang 3.3 (从源码编译)

####编译安装LLVM&Clang

找到位于kernel_api_decl文件夹中的源码压缩包llvm_clang_3.3_with_header_gen_patch.tar.gz，并解压

	$tar xvf llvm_clang_3.3_with_header_gen_patch.tar.gz

解压后会出现llvm文件夹，执行下面的命令

	$cd llvm
	$mkdir build-llvm
	$cd build-llvm
	$../configure --enable-optimized
	$make
	$sudo make install

编译安装成功后clang应该可以直接调用，使用下面的命令测试

	$clang --version

如果能够正确地显示clang的版本号，那么表示LLVM&Clang安装成功

####编译clang插件

进入kernel_api_decl/clang-plugins文件夹中，然后执行如下命令	

	$mkdir build
	$cd build
	$cmake ..
	$make

编译完成后在当前目录下会生成lib文件夹，如果其中存在DeclFilter.so和DumpDecls.so这两个文件，表示clang插件编译成功
