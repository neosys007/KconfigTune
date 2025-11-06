#!/bin/bash

if [ "$#" -ne 1 ]; then
  echo "请输入一个int, 标记编译Linux的次数"
  exit 1
fi

loop_count=$1

kernel_path="/home/guosy/Kconfig/OS/linux"

cd "$kernel_path"

make oldconfig

cp .config .config_next


for ((i=1; i<=loop_count; i++)); do
    make clean
    cp .config_prev .config
    make -j $(nproc) bzImage modules
    cp .config_next .config

    start=$(date +%s.%3N)
    make -j $(nproc) bzImage modules
    end=$(date +%s.%3N)
    duration=$(echo "scale=3; ($end - $start) * 1000" | bc)
    echo "第 $i 次Linux内核的编译时间为 $duration 毫秒"
done
