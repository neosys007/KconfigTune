kernel_path="/home/guosy/Kconfig/OS/linux"

cd "$kernel_path"

make clean

rm .config .config.old

make defconfig
