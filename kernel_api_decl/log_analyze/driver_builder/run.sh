LINUX_DIR=/home/wh/driver-api/kernels/linux-4.1
OLD_VER=v3.5
NEW_VER=v4.1
DIFF_DB=/home/wh/driver-api/linux_api_diff/kernel_api_decl/e1000-3.5.4-4.1-diff-with-macros.db
LINUX_GIT=/home/wh/linux-kernels/linux
echo $LINUX_GIT
cd e1000
make > log.txt 2>&1
cd ..
python ../error_interpreter.py -err_report e1000/log.txt -diff_db $DIFF_DB -old_ver $OLD_VER -new_ver $NEW_VER -linux_git $LINUX_GIT > results.txt

