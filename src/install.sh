#!/bin/bash

# 安装pip，然后安装grpc库
echo 'install pip and grpc library'
apt install -y python3-pip
pip3 install protobuf grpcio

# 安装redis以及编译内核需要的软件包，并将redis设置为开机启动
echo 'install redis and kernel compilation dependencies'
apt install -y redis flex bison libssl-dev libelf-dev dwarves
systemctl enable redis-server.service

# 复制我们的systemd服务到系统目录，并设置为开机启动
# 进行本步骤之前请确保已经设置好new_systemd/xtune-collector.service中的环境变量已设置好
echo 'copy systemd script and enable it'
cp ./new_systemd/xtune-collector.service /lib/systemd/system
systemctl enable xtune-collector.service
