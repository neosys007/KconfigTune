# Copyright 2020 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The Python AsyncIO implementation of the GRPC helloworld.Greeter client."""

import asyncio
from asyncio import subprocess
import csv
import json
from json import loads as jsonLoads
import logging
import os
import subprocess

import grpc
import xtuner_pb2
import xtuner_pb2_grpc


class DataCollector:
    cmd = None
    err_file = None
    out_file = None

    def run(self):
        if self.cmd != None:
            os.system("%s 2>%s >%s" % (self.cmd, self.err_file, self.out_file))

class RedisDataCollector(DataCollector):
    def __init__(self, prefix):
        err_file = "redis_bench.err"
        out_file = "redis_bench.out"
        self.out_file = prefix + out_file
        self.err_file = prefix + err_file
        self.cmd = "redis-benchmark --csv"

# tunnable文件所在绝对路径，文件中包含要训练的配置项名称，一行一个。
TUNNABLE_PATH = os.getenv('XTUNNABLE_PATH')
# Linux源码所在的绝对路径（尾部不包含/）
LINUX_SOURCE = os.getenv('XTUNE_LINUX_SOURCE')
# 当前配置所在路径
CONFIG_PATH = LINUX_SOURCE + '/.config'
# counter文件路径，counter文件的内容是一个整数，表示剩余训练轮次
COUNTER_FILE = os.getenv('COUNTER_FILE')
# 训练服务器ip地址和端口，如192.168.7.173:50051
SERVER_ADDR = os.getenv('SERVER_ADDR')
# redis benchmark数据文件存放位置，绝对路径，尾部需要写/
# 在该路径指向的目录下，将会新建redis_benchmark.out和redis_benchmark.err
REDIS_BENCH_OUTPUT = os.getenv('REDIS_BENCH_OUTPUT')

# 读取.config配置文件，读取tunnable对应的项
def genConfigItems(path):
    tunnable = []
    with open(TUNNABLE_PATH, 'r') as tmp:
        for line in tmp.readlines():
            tunnable.append(line.rstrip('\n'))
    config_items = {}
    with open(CONFIG_PATH, 'r') as tmp:
        for line in tmp.readlines():
            if line.startswith('#'):
                continue
            splited = line.split('=')
            if len(splited) != 2:
                continue
            name = splited[0]
            config_items[name] = splited[1].rstrip('\n')
    return config_items,tunnable

async def run() -> None:
    counter = 1
    with open(COUNTER_FILE, 'r') as cnt_file:
        line = cnt_file.readline()
        counter = int(line)
        print("counter is " + str(counter) + '\n')

    async with grpc.aio.insecure_channel(SERVER_ADDR) as channel:
        stub = xtuner_pb2_grpc.XtunerStub(channel)
        config_items,tunnable = genConfigItems(CONFIG_PATH)
        config_items = json.dumps(config_items)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to run redis benchmark',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        print('REDIS_BENCH_OUTPUT is %s\n' % REDIS_BENCH_OUTPUT)
        redis_collector = RedisDataCollector(REDIS_BENCH_OUTPUT)
        redis_collector.run()

        keys = []
        values = []
        with open(redis_collector.out_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                keys.append(row[0])
                values.append(row[1])

        request = xtuner_pb2.UploadRequest(
                values = values,
                keys = keys,
                tunnable = tunnable,
                config=config_items,
                counter=counter)
        response = await stub.UploadMetrics(request)
        new_config_items = jsonLoads(response.result)
        subprocess.run('scripts/config --set-str SYSTEM_TRUSTED_KEYS ""', cwd=LINUX_SOURCE, shell=True)
        subprocess.run('scripts/config --set-str SYSTEM_REVOCATION_KEYS ""', cwd=LINUX_SOURCE, shell=True)
        subprocess.run('make ARCH=x86 oldconfig -j8', cwd=LINUX_SOURCE, shell=True)
        for key in tunnable:
            cmd = "scripts/config --set-val %s %s" % (key, new_config_items[key])
            print("set-val cmd is %s\n" % cmd)
            subprocess.run(cmd, cwd=LINUX_SOURCE, shell=True)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to compile kernel',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('make ARCH=x86 -j8', cwd=LINUX_SOURCE, shell=True)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to compile kernel modules',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('make ARCH=x86 modules -j8', cwd=LINUX_SOURCE, shell=True)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to install kernel modules',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('make INSTALL_MOD_STRIP=1 ARCH=x86 modules_install', cwd=LINUX_SOURCE, shell=True)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to install kernel',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('make ARCH=x86 install', cwd=LINUX_SOURCE, shell=True)

        counter -= 1
        print("new counter generated\n")
        if counter <= 0:
            subprocess.run('systemctl disable xtune-collector.service', shell=True)
            os.remove(COUNTER_FILE)
            print("soft link to xtune-collector.service has been deleted\n")
        else:
            with open(COUNTER_FILE, 'w') as cnt_file:
                line = str(counter)
                cnt_file.write(line)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'going to reboot',
                counter=counter)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('reboot', shell=True)


if __name__ == '__main__':
    logging.basicConfig()
    asyncio.run(run())
