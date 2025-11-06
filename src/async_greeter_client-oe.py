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
'''
KconfigTune 自动化训练调优框架 —— client端

主要功能：
1. 训练流程步骤控制
2. 应用benchmark
3. 发送训练数据给server
4. 从server接收参数设置值
'''

import asyncio
from asyncio import subprocess
import logging

import grpc
import xtuner_pb2
import xtuner_pb2_grpc
import json
from json import loads as jsonLoads
import os
import subprocess
import csv
import time
from numpy import *
import re
import ast

import changeNode

BENCHMARK_COUNT = 10

# 应用benchmark
class DataCollector:
    cmd = None
    err_file = None
    out_file = None

    def run(self):
        if self.cmd != None:
            # 运行多次benchmark，降低异常值影响
            for i in range(BENCHMARK_COUNT):
                if len(self.err_file)>0:
                    cmd = "%s 2>%s >%s" % (self.cmd, self.err_file, self.out_file+str(i))
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # os.system("%s >%s" % (self.cmd, self.out_file+str(i)))
                    cmd = "%s >%s" % (self.cmd, self.out_file+str(i))
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(10)

class RedisDataCollector(DataCollector):
    def __init__(self, prefix):
        err_file = "redis_bench.err"
        out_file = "redis_bench.out"
        self.out_file = prefix + out_file
        self.err_file = prefix + err_file
        self.cmd = "redis-benchmark -t set --csv"

class MemcaDataCollector(DataCollector):
    def __init__(self, prefix):
        out_file = "mem_bench.out"
        self.err_file = ""
        self.out_file = prefix + out_file
        self.cmd = "memtier_benchmark  -P memcache_text -p 11211 -n 20000 -h localhost -t 10 -c 50 --ratio 1:0 --key-prefix=\"test\" --key-minimum=10000000 --key-maximum=20000000 -d 1024"
                
class HttpdDataCollector(DataCollector):
    def __init__(self, prefix):
        out_file = "httpd_bench.out"
        self.out_file = prefix + out_file
        self.err_file = ""
        self.cmd = "ab -c 500 -n 100000 http://localhost:80/"

class NginxDataCollector(DataCollector):
    def __init__(self, prefix):
        out_file = "nginx_bench.out"
        self.out_file = prefix + out_file
        self.err_file = ""
        self.cmd = "ab -c 500 -n 100000 http://localhost:8081/"
        
class PGSqlDataCollector(DataCollector):
    def __init__(self, prefix):
        out_file = "pgsql_bench.out"
        self.out_file = prefix + out_file
        self.err_file = ""
        self.cmd = "pgbench -r -c 100 -j 16 -T 30 -U postgres -h localhost -p 5432 -d test"

class MysqlDataCollector(DataCollector):
    def __init__(self, prefix):
        out_file = "mysql_bench.csv"
        self.err_file = ""
        self.out_file = prefix + out_file
        
        config_path = path.join(path.dirname(COUNTER_FILE), 'mysql.json')
        with open(config_path) as file:
            data = file.read()
        json_obj = json.loads(data)
        self.port = json_obj['port']
        self.username = json_obj['username']
        self.password = json_obj['password']
        self.select_db = json_obj['select_db']
        self.table_size = json_obj['table_size']
        self.table_num = json_obj['table_num']
        self.events = json_obj['events']
        self.time = json_obj['time']
        self.threads = json_obj['threads']
        self.command_type_list = json_obj['command_type_list']
        pass
    
    def run(self):
        for command_type in self.command_type_list:
            command_prefix = [
                'sysbench',
                '--db-driver=mysql',
                '--mysql-port={port}'.format(port=self.port),
                '--mysql-user={username}'.format(username=self.username),
                '--mysql-password={password}'.format(password=self.password),
                '--mysql-db={select_db}'.format(select_db=self.select_db),
                '--table_size={table_size}'.format(table_size=self.table_size),
                '--tables={table_num}'.format(table_num=self.table_num),
                '--events={events}'.format(events=self.events),
                '--time={time}'.format(time=self.time),
                '--threads={threads}'.format(threads=self.threads),
                '{command_type}'.format(command_type=command_type)
            ]
            command_suffix_prepare = ['prepare']
            command_suffix_run = ['run']
            command_suffix_cleanup = ['cleanup']

            records = []

            # prepare data
            subprocess.run(command_prefix + command_suffix_prepare)

            # run bench
            for i in range(BENCHMARK_COUNT):
                result = subprocess.run(command_prefix + command_suffix_run, stdout=subprocess.PIPE)
                format_data = result.stdout.decode('utf-8')
                d = {}
                flag = False
                key_fix = ''
                for line in format_data.split("\n"):
                    split_result = re.split(r":\s*", line)
                    if len(split_result) < 2:
                        continue
                    key = split_result[0].strip()

                    if len(split_result[1]) < 1:
                        if flag:
                            key_fix += " - " 
                            key_fix += key
                        else:
                            key_fix = key
                            flag = True
                            print(key_fix)
                        continue
                    flag = False

                    value_strs = re.split(r"\s+", split_result[1])
                    value = value_strs[0].strip()
                    key = key_fix + ' - ' + key
                    d[key] = value
                records.append(d)

            # cleanup data
            subprocess.run(command_prefix + command_suffix_cleanup)

            df = pd.DataFrame(records)
            df.to_csv(self.out_file, index = False)

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
HTTPD_BENCH_OUTPUT = os.getenv('HTTPD_BENCH_OUTPUT')
PGSQL_BENCH_OUTPUT = os.getenv('PGSQL_BENCH_OUTPUT')
MYSQL_BENCH_OUTPUT = os.getenv('MYSQL_BENCH_OUTPUT')
NGINX_BENCH_OUTPUT = os.getenv('NGINX_BENCH_OUTPUT')
MEMCA_BENCH_OUTPUT = os.getenv('MEMCA_BENCH_OUTPUT')
# hostName
HOST_NAME = os.getenv('HOST_NAME') # 主机名，这里是固定的，后续可以修改 "Xtune-client-1" 
# grub reboot menu
REBOOT_MENU = os.getenv('REBOOT_MENU') # 重启后grub加载的内核菜单项（一次性）
# KconfigDep parse path
KCONFIG_PATH = os.getenv('KCONFIG_PATH')


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

# 每个训练轮次运行
async def run() -> None:
    # 获取剩余训练次数
    counter = 1
    with open(COUNTER_FILE, 'r') as cnt_file:
        line = cnt_file.readline()
        counter = int(line)
        print("counter is " + str(counter) + '\n')

    async with grpc.aio.insecure_channel(SERVER_ADDR) as channel:
        stub = xtuner_pb2_grpc.XtunerStub(channel)
        config_items,tunnable = genConfigItems(CONFIG_PATH)
        config_items = json.dumps(config_items)

        logger.debug('[%s][%d]training start' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        request = xtuner_pb2.DebugLogMsg(
                    msg = 'begin to run postgresql benchmark',
                    counter=counter,
                    hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        
        # 当前内核版本
        kv = subprocess.check_output(['uname', '-sr']).decode().strip()
        logger.debug('[%s][%d]kernel version:%s' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, kv) )
        # 判断是否训练内核，是 —— 上一轮调整参数可以正常启动，否 —— 上一轮调整参数无法正常启动
        if 'oe2203' not in kv:
            is_train_kernel = True
        else:
            is_train_kernel = False
        
        keys = []
        values = []
        if is_train_kernel:           
            # 获取内核大小
            cmd_get_size = 'stat -c \"%s\" arch/x86/boot/bzImage'
            ks = subprocess.check_output(cmd_get_size.split(' '), cwd=LINUX_SOURCE).decode().strip()
            
            logger.debug('[%s][%d]run postgresql benchmark' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
            # 运行应用benchmark
            print('PGSQL_BENCH_OUTPUT is %s\n' % PGSQL_BENCH_OUTPUT)
            pgsql_collector = PGSqlDataCollector(PGSQL_BENCH_OUTPUT)
            pgsql_collector.run()
            # logger.debug('[%s][%d]run http benchmark' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
            # print('HTTPD_BENCH_OUTPUT is %s\n' % HTTPD_BENCH_OUTPUT)
            # httpd_collector = HttpdDataCollector(HTTPD_BENCH_OUTPUT)
            # httpd_collector.run()

            # 读取多次benchmark测量数据平均值
            pgsql_benchmark_dict = {}
            for i in range(BENCHMARK_COUNT):
                with open(pgsql_collector.out_file+str(i), 'r') as f:
                    lines = f.readlines()
                    for l in lines:
                        line = l.strip()
                        if '=' in line:
                            key = line.split('=')[0].strip()
                            if key in pgsql_benchmark_dict:
                                pgsql_benchmark_dict[key].append(float(re.findall(r"\d+\.?\d*", line.split('=')[1])[0]))
                            else:
                                pgsql_benchmark_dict[key] = [float(re.findall(r"\d+\.?\d*", line.split('=')[1])[0])]
                            if key == 'tps':
                                break;
            for k in pgsql_benchmark_dict:
                keys.append(k)
                values.append(str(mean(pgsql_benchmark_dict[k])))

            # 读取多次benchmark测量数据平均值
            # httpd_benchmark_dict = {}
            # for i in range(BENCHMARK_COUNT):
            #     with open(httpd_collector.out_file+str(i), 'r') as f:
            #         lines = f.readlines()
            #         for l in lines:
            #             line = l.strip()
            #             if line.startswith('Failed requests'):
            #                 fail_request = int(re.findall(r"\d+\.?\d*", line.split(':')[1])[0])
            #                 if fail_request > 0:
            #                     logger.debug('[%s][%d]http failed request %d' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, fail_request))
            #                     break
            #             if (line.startswith('Requests per second') or line.startswith('Time per request')) and line.endswith('(mean)'):
            #                 k = line.split(':')[0]
            #                 if k in httpd_benchmark_dict:
            #                     httpd_benchmark_dict[k].append(float(re.findall(r"\d+\.?\d*", line.split(':')[1])[0]))
            #                 else:
            #                     httpd_benchmark_dict[k] = [float(re.findall(r"\d+\.?\d*", line.split(':')[1])[0])]
            # for k in httpd_benchmark_dict:
            #     keys.append(k)
            #     values.append(str(mean(httpd_benchmark_dict[k])))

            # nginx_benchmark_dict = {}
            # for i in range(BENCHMARK_COUNT):
            #     with open(nginx_collector.out_file+str(i), 'r') as f:
            #         lines = f.readlines()
            #         for l in lines:
            #             line = l.strip()
            #             if line.startswith('Failed requests'):
            #                 fail_request = int(re.findall(r"\d+\.?\d*", line.split(':')[1])[0])
            #                 if fail_request > 0:
            #                     logger.debug('[%s][%d]http failed request %d' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, fail_request))
            #                     break
            #             if (line.startswith('Requests per second') or line.startswith('Time per request')) and line.endswith('(mean)'):
            #                 k = line.split(':')[0]
            #                 if k in nginx_benchmark_dict:
            #                     nginx_benchmark_dict[k].append(float(re.findall(r"\d+\.?\d*", line.split(':')[1])[0]))
            #                 else:
            #                     nginx_benchmark_dict[k] = [float(re.findall(r"\d+\.?\d*", line.split(':')[1])[0])]
            # for k in nginx_benchmark_dict:
            #     keys.append(k)
            #     values.append(str(mean(nginx_benchmark_dict[k])))
            
            # redis_benchmark_dict = {}
            # for i in range(BENCHMARK_COUNT):
            #     with open(redis_collector.out_file+str(i), 'r') as f:
            #         reader = csv.reader(f)
            #         for row in reader:
            #             if row[0] in redis_benchmark_dict:
            #                 redis_benchmark_dict[row[0] ].append(float(row[1]))
            #             else:
            #                 redis_benchmark_dict[row[0] ] = [float(row[1])]
            # for k in redis_benchmark_dict:
            #     keys.append(k)
            #     values.append(str(mean(redis_benchmark_dict[k])))
            
            # mysql_pd = pd.read_csv(mysql_collector.out_file)
            # keys.append('events')
            # values.append(str(mysql_pd['General statistics - total number of events'].mean()))

            # memca_benchmark_dict = {}
            # for i in range(BENCHMARK_COUNT):
            #     with open(memca_collector.out_file+str(i), 'r') as f:
            #         lines = f.readlines()
            #         for l in lines:
            #             line = l.strip()
            #             if line.startswith('Sets'):
            #                 if 'Sets' in memca_benchmark_dict:
            #                     memca_benchmark_dict['Sets'].append(float(line.split()[1]))
            #                 else:
            #                     memca_benchmark_dict['Sets'] = [float(line.split()[1])]
            #                 break
            # keys.append('Sets')
            # values.append(str(mean(memca_benchmark_dict['Sets'])))

            # 增加评价指标：内核镜像大小
            keys.append("ksize")
            values.append(ks)
            keys.append('status')
            values.append('success')
        else:
            keys.append('status')
            values.append('failed')

        request = xtuner_pb2.UploadRequest(
                values = values,
                keys = keys,
                tunnable = tunnable,
                config=config_items,
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.UploadMetrics(request)
        logger.debug('[%s][%d]set config value' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))

        # 按server返回的建议值，设置内核配置（配置项满足依赖关系）
        subprocess.run('cp ../train_config/start.config .config', cwd=LINUX_SOURCE, shell=True)        
        target_dict = ast.literal_eval(response.result)
        target_with_str = dict((k,str(v)) for k,v in target_dict.items())
        ConfigFile = LINUX_SOURCE + ".config" if LINUX_SOURCE[-1] == '/' else LINUX_SOURCE + "/.config"
        changeNode.changeNode(LINUX_SOURCE, target_with_str, KCONFIG_PATH, ConfigFile)

        # 编译内核
        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to compile kernel',
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        logger.debug('[%s][%d]make ARCH=x86 -j16' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        subprocess.run('make ARCH=x86 -j16', cwd=LINUX_SOURCE, shell=True)

        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to compile kernel modules',
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        logger.debug('[%s][%d]make ARCH=x86 modules -j16' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        subprocess.run('make ARCH=x86 modules -j16', cwd=LINUX_SOURCE, shell=True)
        
        # backup .config
        bakcmd = 'cp .config ../train_config/%d.config' % (counter)
        subprocess.run(bakcmd, cwd=LINUX_SOURCE, shell=True)

        # 安装内核模块和镜像
        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to install kernel modules',
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        logger.debug('[%s][%d]make INSTALL_MOD_STRIP=1 ARCH=x86 modules_install' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        subprocess.run('make INSTALL_MOD_STRIP=1 ARCH=x86 modules_install', cwd=LINUX_SOURCE, shell=True)
        logging.debug('module installation completed.')
        logger.debug('[%s][%d]module installation completed.' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        request = xtuner_pb2.DebugLogMsg(
                msg = 'begin to install kernel',
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        logger.debug('[%s][%d]make ARCH=x86 install' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        subprocess.run('make ARCH=x86 install', cwd=LINUX_SOURCE, shell=True)
        # logging.debug('kernel installation completed.') 
        logger.debug('[%s][%d]kernel installation completed.' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        
        # 剩余训练轮数-1
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
        
        # 重启
        logger.debug('[%s][%d]reboot begins' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        request = xtuner_pb2.DebugLogMsg(
                msg = 'going to reboot',
                counter=counter,
                hostName=HOST_NAME)
        response = await stub.PrintDebugMsg(request)
        subprocess.run('grub2-reboot \"' + REBOOT_MENU + '\"', shell=True)
        subprocess.run('reboot', shell=True)


if __name__ == '__main__':
    # logging.basicConfig(filename='XtuneClientLog.txt', level=logging.DEBUG)
    logger = logging.getLogger("XtuneLog")
    logging.basicConfig(level="DEBUG")
    file_handler = logging.FileHandler("XtuneClientLog.txt", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    asyncio.run(run())
