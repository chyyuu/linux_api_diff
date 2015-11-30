#!/bin/bash

# packages required
packages=(
"build-essential"
"python"
"sqlite3"
"libsqlite3-dev"
"git"
"cmake"
)

# install required packages
for p in ${packages[@]}
do
	sudo apt-get install ${p}
	if [ $? == 0 ]
	then
		echo "${p} is installed."
	else
		echo "install ${p} failed."
		exit
	fi
done

# compile & install LLVM&Clang 3.3
# decompress llvm sources
if [ ! -e ${PWD}/llvm ]
then
	tar xf llvm_clang_3.3_with_header_gen_patch.tar.gz
fi
# enter llvm sources dir and create build dir
cd llvm
mkdir build-llvm
# enter build dir
cd build-llvm
# configure llvm
../configure --enable-optimized
# get number of cores
num=$(cat /proc/cpuinfo | grep "cpu cores" | wc -l)
# start build
if [ ${num} > 1 ]
then 
	make -j ${num}
else
	make 
fi
# install llvm to system path
if [ $? == 0 ]
then 
	sudo make install
	if [ $? == 0 ]
	then
		echo "install llvm&clang success."
	fi
else
	echo "build llvm&clang failed."
	exit
fi

# compile clang plugin
# return to top dir
cd ../..
# enter clang plugin dir
cd clang-plugins
# create build dir
mkdir build
cd build
# configure plugin
cmake ..
# compile plugins
make
if [ $? == 0 ]
then
	echo "compile clang plugins success."
else
	echo "compile clang plugins failed."
fi

