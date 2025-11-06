cd /home/guosy/Kconfig/OS/linux

make clean

make defconfig

cp .config .config_tmp

scripts/config -e EDD
scripts/config -d EDD_OFF

diff .config .config_tmp

make -j $(nproc) bzImage modules
