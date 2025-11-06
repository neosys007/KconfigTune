#!/bin/bash

kernel_path="/home/guosy/Kconfig/OS/linux"

make -j $(nproc) bzImage modules