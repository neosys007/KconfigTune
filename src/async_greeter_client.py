

import asyncio
from asyncio import subprocess
import logging
from datetime import datetime
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

class LEBench:
    def __init__(
        self,
        prefix: str = "lebench_",
        output_dir: str = "/home/sunying/kernelforge/benchmark/LEBench/data",
        kernel_version: str = "5.4.246extconfig+"
    ):
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_file = os.path.join(output_dir, f"{prefix}results_{timestamp}.out")
        self.score_file = os.path.join(output_dir, f"{prefix}total_score_{timestamp}.txt")
        
        # 定义绝对路径
        self.bin_path = "/home/sunying/kernelforge/benchmark/LEBench/OS_Eval"
        self.kernel_image = f"vmlinuz-{kernel_version}"
        
        # 构建命令
        self.cmd = [
            "sudo",
            self.bin_path,
            "0",
            self.kernel_image
        ]
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

    def run(self) -> float:
        """执行测试并保存结果"""
        try:
            # 验证可执行文件存在
            if not os.path.exists(self.bin_path):
                raise FileNotFoundError(f"可执行文件不存在: {self.bin_path}")
            kernel_path = os.path.join(os.path.dirname(self.bin_path), self.kernel_image)
            # if not os.path.exists(kernel_path):
            #     raise FileNotFoundError(f"内核镜像不存在: {kernel_path}")

            # 执行命令
            result = subprocess.run(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                cwd=os.path.dirname(self.bin_path)
            )
            
            # 保存原始日志
            with open(self.result_file, "w") as f:
                f.write(result.stdout)
            
            # 计算总分（仅累加测试项时间，排除总时长）
            total_score = self.calculate_total_score(result.stdout)
            
            # 保存总分
            with open(self.score_file, "w") as f:
                f.write(f"Total Time: {total_score:.6f} seconds\n")
                f.write(f"Scientific Notation: {total_score:.4e} seconds")
            
            return total_score  # 返回总得分
        
        except subprocess.CalledProcessError as e:
            print(f"命令执行失败: {e.stderr}")
            return 0.0  # 如果失败，返回 0
        except FileNotFoundError as e:
            print(e)
            return 0.0  # 如果文件未找到，返回 0

    def calculate_total_score(self, data: str) -> float:
        """解析日志并累加所有测试项时间（排除总时长）"""
        total = 0.0
        lines = data.split('\n')
        in_test_block = False  # 标记是否在测试块中

        for line in lines:
            line = line.strip()
            
            # 检测测试块开始
            if line.startswith("Performing test"):
                in_test_block = True
                
            # 检测测试块中的耗时行
            elif in_test_block and line.startswith("Test took:"):
                # 提取时间数值
                match = re.match(r'Test took:\s+([0-9.]+)\s+seconds', line)
                if match:
                    try:
                        total += float(match.group(1))
                    except ValueError:
                        print(f"忽略无效时间值: {line}")
                in_test_block = False  # 重置标记

        return total

    def print_summary(self):
        try:
            with open(self.score_file) as f:
                print(f"\n{' Test Summary ':=^50}")
                print(f"Result File: {self.result_file}")
                print(f"Score File: {self.score_file}")
                print(f"\n{f.read()}")
                print('=' * 50)
        except FileNotFoundError:
            print("未找到结果文件，请先运行测试")


class UnixbenchCollector():
    def __init__(self):
        prefix="/home/sunying/kernelforge/benchmark/byte-unixbench/"
        # 统一输出目录结构
        self.base_dir = prefix + "UnixBench"
        os.makedirs(self.base_dir, exist_ok=True)
        self.log_file = os.path.join(self.base_dir, "run.log")  # 主日志文件

    def run(self):
        """执行并记录完整日志"""
        try:
            # 执行并将日志输出到 log_file
            self._run_benchmark()
            # 返回基准测试分数
            return self.get_system_score()
        except Exception as e:
            logger.error(f"Unixbench执行异常: {str(e)}")
            raise

    def _run_benchmark(self):
        """执行基准测试"""
        try:
            with open(self.log_file, "w") as lf:
                # 执行Unixbench的命令并将日志写入文件
                process = subprocess.run(
                    "./Run",  # cmd现在是字符串格式
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    cwd=self.base_dir,
                    shell=True
                )
                exit_code = process.returncode

                if exit_code != 0:
                    raise RuntimeError(f"Unixbench执行失败退出码:{exit_code})")
        except Exception as e:
            logger.error(f"Unixbench执行异常: {str(e)}")
            raise

    def get_system_score(self):
        score_pattern = re.compile(r'System Benchmarks Index Score\s+(\d+\.\d+)')
        scores = []  # 存储所有找到的分数
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    match = score_pattern.search(line)
                    if match:
                        scores.append(float(match.group(1)))  # 存储所有匹配的分数
        
        # 如果找到了分数，返回最后一个
            if scores:
                return scores[-1]
            else:
                raise ValueError("未找到系统基准测试总分")
        except Exception as e:
            logger.error(f"获取系统基准分数失败: {str(e)}")
            raise



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
reboot_menu = subprocess.check_output(
    "awk -F\"'\" '/menuentry / {print $2}' /boot/grub/grub.cfg | grep $(uname -r) | head -n 1",
    shell=True,
    text=True
).strip()  # 使用 strip() 去除可能的换行符


NETPERF_BENCH_OUTPUT = '/home/sunying/netperf/'
REBOOT_MENU = reboot_menu # 重启后grub加载的内核菜单项（一次性）reboot_menu = subprocess.check_output(
    
# KconfigDep parse path
KCONFIG_PATH = os.getenv('KCONFIG_PATH')

SERVER_IP = "192.168.8.136"

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
    counter = 10
    with open(COUNTER_FILE, 'r') as cnt_file:
        line = cnt_file.readline()
        counter = int(line)
        print("counter is " + str(counter) + '\n')
        print("the grub is " + str(REBOOT_MENU)+'\n')

    async with grpc.aio.insecure_channel(SERVER_ADDR) as channel:
        stub = xtuner_pb2_grpc.XtunerStub(channel)
        config_items,tunnable = genConfigItems(CONFIG_PATH)
        config_items = json.dumps(config_items)

        logger.debug('[%s][%d]training start' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
        request = xtuner_pb2.DebugLogMsg(
                    msg = 'begin to run unixbench benchmark',
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
            logger.debug('[%s][%d]run UnixBench benchmark' % (time.strftime("%Y-%m-%d %X", time.localtime()), counter))
            unixbench = UnixbenchCollector()
            total_score = unixbench.run()
            #total_score = 1000
            values.append(str(total_score))
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
        print("configfile path is " +ConfigFile)
        arch = "x86"
        changeNode.changeNode(LINUX_SOURCE, target_with_str, KCONFIG_PATH, arch, ConfigFile)

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
        subprocess.run('grub-reboot \"' + REBOOT_MENU + '\"', shell=True)
        subprocess.run('reboot', shell=True)


if __name__ == '__main__':
    # logging.basicConfig(filename='XtuneClientLog.txt', level=logging.DEBUG)
    logger = logging.getLogger("XtuneLog")
    logging.basicConfig(level="DEBUG")
    file_handler = logging.FileHandler("XtuneClientLog.txt", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    asyncio.run(run())
