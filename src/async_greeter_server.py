import asyncio
import logging

import grpc
from google.protobuf import empty_pb2
import xtuner_pb2
import xtuner_pb2_grpc
from threading import Thread, Timer
from queue import Queue

# gaussian_process
# from sklearn.gaussian_process import GaussianProcessRegressor
# from sklearn.gaussian_process.kernels import ConstantKernel, RBF

# scikit-tune
import random
import os
import subprocess
from kerneltune.history import Observation, History
from kerneltune.util import StatusCode
from kerneltune.optimize import BayesianOptimizer as SMAC
from kerneltune.util import generate_configspace
from kerneltune.alignment import alignment_configspace
from kerneltune.logging import get_logger, setup_logger

from decimal import Decimal

import numpy as np
import json
from json import loads as jsonLoads
import time
import pandas as pd
import re

queue_trainer = Queue(maxsize=0)
queue_transmit = Queue(maxsize=0)

TASK = 'pgsql'
DATA_DIR = '/home/sunying/XtuneKconfigPerf/data/'
base_httpd_bench = {"Xtune-client-11":27870.89,"Xtune-client-12":26094.09,"Xtune-client-3":19548.17,"Xtune-client-21":18661.019}
base_nginx_bench = {"Xtune-client-11":35180.815,"Xtune-client-12":28769,"Xtune-client-13":27903.90556}
base_redis_bench = {"Xtune-client-11":153609.83,"Xtune-client-12":159489.64,"Xtune-client-21":50276.52}
base_pgsql_bench = {"Xtune-client-1":8878.834,"Xtune-client-16":4911.797198}
base_mysql_bench = {"Xtune-client-12":68114}
base_memca_bench = {"Xtune-client-21":249940.8567}

FAILED_PERF = -101
BENCHMARK_COUNT = 20

PGSQL_BENCH_OUTPUT = '/home/sunying/benchmark/pgbench/'

def Tunnable2Str(l):
    l = list(l)
    return '#'.join(list(map(str, l)))

def Str2Tunnable(s):
    return list(map(int, str(s).split('#')))

# benchmark
def compute_redis_performance(keys, values):
    # Simply get train_y by adding all metrics
    # FIXME: need more proper function to do this
    # train_y = 0.0
    # for value in values:
    #     train_y += float(value)
    # return train_y
    
    # SET
    index = 0
    for k in keys:
        if k == "SET":
            break
        index += 1
    train_y = float(values[index])
    return train_y

def compute_memca_performance(keys, values):
    index = 0
    for k in keys:
        if k == 'Sets':
            return float(values[index])
        index += 1
    return float(values[0].strip('"'))

def compute_httpd_performance(keys, values):
    # Simply get train_y by adding all metrics
    # FIXME: need more proper function to do this
    index = 0
    for k in keys:
        if k == 'Requests per second':
            return float(values[index])
        index += 1
    return float(values[0])

def compute_pgsql_performance(keys, values):
    index = 0
    for k in keys:
        if k == 'tps':
            return float(values[index])
        index += 1
    return float(values[0])

def compute_mysql_performance(keys, values):
    index = 0
    for k in keys:
        if k == 'events':
            return float(values[index])
        index += 1
    return float(values[0])

def read_pgsql_performance():
    pgsql_benchmark_dict = {}
    for i in range(BENCHMARK_COUNT):
        with open(PGSQL_BENCH_OUTPUT+"pgsql_bench.out"+str(i), 'r') as f:
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
    if 'tps' in pgsql_benchmark_dict:
        return np.mean(pgsql_benchmark_dict['tps'])
    else:
        return 0

# parse config define json, get config type
def get_configtype_from_define(config_def_json, config_name):
    # cut "CONFIG_"
    clean_name = config_name[7:]
    if clean_name in config_def_json:
        type = config_def_json[clean_name][0]["type"]
        if type == 'bool':
            return {"type": "cate", "choices": ["y", "n"]}
        elif type == 'tristate':
            return {"type": "cate", "choices": ["y", "m", "n"]}
        elif type == "int":
            value_range = config_def_json[clean_name][0]["value"]["range"]
            if len(value_range) > 0:
                range_list = re.findall(r"\d+", value_range[0])
                return {"type": "int", "bound": [int(range_list[0]), int(range_list[1]) ], "step": 1}
            else:
                return {"type": "int", "bound": [0, 10000000], "step": 1}
        # elif type == "hex":
        #     value_range = config_def_json[clean_name][0]["value"]["range"]
        #     if len(value_range) > 0:
        #         # hex to int
        #         range_list = 
        #         return {"type": "int", "bound": [ ], "step": 1}
        #     else:
        #         return {"type": "int", "bound": [0, 10000000], "step": 1}
        else:
            return {"type": "others"}
    else:
        # default bool
        return {"type": "cate", "choices": ["y", "n"]}

def exception_outtime(hostname):
    # notify AI exception
    queue_trainer.put(('exception', hostname))

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

# class PGSqlDataCollector(DataCollector):
#     def __init__(self, prefix):
#         out_file = "pgsql_bench.out"
#         self.out_file = prefix + out_file
#         self.err_file = ""
#         self.cmd = "pgbench -r -c 100 -j 16 -T 30 -U postgres -h 192.168.8.124 -p 5432 test"

class Tunner(xtuner_pb2_grpc.XtunerServicer):
    def __init__(self):
        self.tmp_run = 0
        self.train_data_list = []
        self.tmp_train_starttime = {}
        self.tmp_train_endtime = {}
        self.tmp_train_value = {}
        # self.host_timer = {}

    async def PrintDebugMsg(self, request: xtuner_pb2.DebugLogMsg,
            context: grpc.aio.ServicerContext):
        global client_dict
        global hasPrint
        global logger
        logger.info('[%s][%d]%s: %s' % (time.strftime("%Y-%m-%d %X", time.localtime()), request.counter, request.hostName, request.msg))
        
        if "benchmark" in request.msg:
            trainkey = str(request.counter)+'&'+request.hostName
            self.tmp_train_starttime[trainkey] = int(time.time())
            # cancel timing
            # if request.hostName in self.host_timer:
            #     self.host_timer[request.hostName].cancel()
            
        elif "reboot" in request.msg:
            trainkey = str(request.counter + 1)+'&'+request.hostName
            self.tmp_train_endtime[trainkey] = int(time.time())
            # output
            if len(self.train_data_list) > 0:
                pd.DataFrame(self.train_data_list).to_csv(TASK+"_tune_train_data.csv", index=False)
            # start up timing
            # if request.counter > 0:
            #     t = Timer(300, exception_outtime, (request.hostName,))
            #     self.host_timer[request.hostName] = t
            #     t.start()
        
        if request.counter == 0:
            # end train
            client_dict[request.hostName] = True
            # optimal_value = self.history_optimal_value
            all_done = True
            for value in client_dict.values():
                if value == False:
                    all_done = False
                    break
            if all_done == True and hasPrint == False:
                # logger.info('[%d]%s: optimal_result: %s' % (request.counter, request.hostName, str(optimal_value)))
                queue_trainer.put(('end', None))
                hasPrint = True
                # pd.DataFrame(self.train_data_list).to_csv(r"kconfig_tune_train_data.csv", index=False)
            self.tmp_run = 0
        else:
            client_dict[request.hostName] = False
        
        logger.debug('[%s][%d]%s: return PrintDebugMsg' % (time.strftime("%Y-%m-%d %X", time.localtime()), request.counter, request.hostName))
        return empty_pb2.Empty()

    async def UploadMetrics(
            self, request: xtuner_pb2.UploadRequest,
            context: grpc.aio.ServicerContext) -> xtuner_pb2.UploadReply:
        # global client_dict
        # client_dict[request.hostName] = False
        logger.debug('[%s][%d]%s: request.keys= %s'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), request.counter, request.hostName, str(request.keys)))
        logger.debug('[%s][%d]%s: request.values= %s\n'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), request.counter, request.hostName, str(request.values)))
        
        if request.keys.pop() == "status":
            train_status = request.values.pop()
        if train_status == 'success':
            # tmp_perf = compute_redis_performance(request.keys,request.values)
            # tmp_perf = compute_httpd_performance(request.keys,request.values)
            # tmp_perf = compute_pgsql_performance(request.keys,request.values)
            # tmp_perf = compute_mysql_performance(request.keys,request.values)
            tmp_perf = compute_memca_performance(request.keys,request.values)
            
            # remote benchmark
            # pgsql_collector = PGSqlDataCollector(PGSQL_BENCH_OUTPUT)
            # pgsql_collector.run()
            
            # tmp_perf = read_pgsql_performance()
            tmp_perf_improve = (tmp_perf-base_pgsql_bench[request.hostName])/base_pgsql_bench[request.hostName]
        else:
            # failed kernel 
            tmp_perf = 0
            tmp_perf_improve = FAILED_PERF
        last_train_time =0
        trainkey = str(request.counter+1)+'&'+request.hostName
        if trainkey in self.tmp_train_endtime:           
            last_train_time = self.tmp_train_endtime[trainkey] - self.tmp_train_starttime[trainkey]
            dict_train_data1 = {"counter":(request.counter+1), "hostname":request.hostName, "traintime":last_train_time, \
                "value":self.tmp_train_value[trainkey], "perf":tmp_perf, "improve":tmp_perf_improve}
            dict_train_data2 = {}
            dict_train_data2.update(dict_train_data1)
            dict_train_data2.update(dict(zip(request.keys,request.values)))
            self.train_data_list.append(dict_train_data2)
            self.tmp_train_starttime.pop(trainkey)
            self.tmp_train_endtime.pop(trainkey)
            self.tmp_train_value.pop(trainkey)

        # parse config items from request
        config_items = jsonLoads(request.config)

        # first train
        if self.tmp_run == 0:
            # initial optimizer
            # 定义待调优的参数配置
            # TODO: a) Adjust the value range based on the configuration option definition;
            #       b) Add default values for configuration options that do not appear in.config
            #       based on the complete set of configuration items
            config_option = {}
            with open(DATA_DIR+'config.json', 'r') as f:
                config_def_json = json.load(f)
            for item in request.tunnable:
                if item in config_items:
                    literal = config_items[item]
                    val = literal
                else:
                    val = "n"
                config_value_dict = get_configtype_from_define(config_def_json, item)                
                if config_value_dict["type"] == 'int':
                    if val == "n":
                        config_value_dict["default"] = 0
                    else:
                        config_value_dict["default"] = int(val)
                else:
                    config_value_dict["default"] = val
                config_option[item] = config_value_dict
            
            tmp_train_data = {'counter':request.counter, 'hostName':request.hostName, 'tunnable':list(request.tunnable),'config_option':config_option}
            queue_trainer.put(('train', tmp_train_data))
            
            name, reply_msg = None, None
            while name != 'train' or reply_msg == None:
                (name, reply_msg) = queue_transmit.get()
        else:
            tmp_update_data = {'counter':request.counter, 'hostName':request.hostName, 'perf':tmp_perf_improve, 'tunnable':list(request.tunnable),'traintime':last_train_time}
            queue_trainer.put(('update', tmp_update_data))
            
            name, reply_msg = None, None
            while name != 'update' or reply_msg == None:
                (name, reply_msg) = queue_transmit.get()

        self.tmp_run = request.counter
        self.tmp_train_value[str(request.counter)+'&'+request.hostName] = reply_msg
        return xtuner_pb2.UploadReply(result=reply_msg)


async def serve() -> None:
    global logger
    server = grpc.aio.server()
    xtuner_pb2_grpc.add_XtunerServicer_to_server(Tunner(), server)
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    logger.info("[%s]Starting server on %s", time.strftime("%Y-%m-%d %X", time.localtime()), listen_addr)
    await server.start()
    await server.wait_for_termination()


def read_default_value():
    global logger
    shared_default_parameters = {}
    config_name_list = []
    with open(DATA_DIR+"tunnable_all", 'r') as file_obj:
        for l in file_obj.readlines():
            config_name_list.append(l.strip())
    with open(DATA_DIR+"start.config") as file_obj:
            lines = file_obj.readlines()
    for line in lines:
        line = line.strip()
        if len(line) == 0:
            continue
        if line.startswith("#"):
            tokens = line.split(" ")
            if len(tokens) == 5 and line.endswith("is not set"):
                # config not set
                config_name = tokens[1]
                if config_name in config_name_list:
                    shared_default_parameters[config_name] = 'n'
        else:
            config_name = line.split('=')[0]
            if config_name in config_name_list:
                value = line.split('=')[1]
                if value.isdigit():
                    # int
                    shared_default_parameters[config_name] = int(value)
                elif value.startswith('0x'):
                    # hex
                    shared_default_parameters[config_name] = hex(int(value, 16))
                else:
                    shared_default_parameters[config_name] = value
    for c in config_name_list:
        if c not in shared_default_parameters:
            shared_default_parameters[c] = 'n'
    
    logger.info("[%s]shared default[%d]= %s", time.strftime("%Y-%m-%d %X", time.localtime()), len(shared_default_parameters), shared_default_parameters)
    return shared_default_parameters

class Trainer(Thread):
    def __init__(self, name=None):
        self.history_optimal_value = None
        self.advisor = None
        self.config_advice_value = {}
        self.shared_default = read_default_value()
        self.counter = 0
        Thread.__init__(self,name=name)
    
    def run(self):
        while True:
            (name, data) = queue_trainer.get()
            logger.info('PIPE Received: %s\n' % name)
            if name == 'train':
                self.train(data)
            elif name == 'update':
                self.update(data)
            elif name == 'end':
                self.end()
            elif name == 'exception':
                self.process_exception(data)
    
    def train(self, data):
        global logger
        counter = data['counter']
        hostName = data['hostName']
        tunnable = data['tunnable']
        config_option = data['config_option']
        logger.debug('[%s]: config_option = %s\n' % (TASK, str(config_option)))
        space = generate_configspace(config_option)

        # self.advisor = KernelTune(configspace=space, n_initial_points=60)
        # self.advisor = BayesianOptimizer(configspace=space, n_initial_points=30)
        history = TASK + '_history.json'
        if history is not None and os.path.exists(history):
            alignment_configspace(history, space, self.shared_default)
            history = History.load(history.replace('.json', '_alignment.json'))

        self.advisor = SMAC(configspace=space, n_initial_points=60, history=history)
        
        # 获取建议的配置
        # tmp_config_advice_value = self.advisor.get_configuration()
        tmp_config_advice_value = self.advisor.suggest()
        logger.info('[%s][%d]%s: config_advise_values= %s'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, hostName, str(tmp_config_advice_value)))
        self.config_advice_value[hostName] = tmp_config_advice_value
        reply_dict = {}
        for item in tunnable:
            if item in tmp_config_advice_value:
                reply_dict[item] = tmp_config_advice_value[item]
        reply_msg = json.dumps(reply_dict)
        logger.debug('[%s][%d]%s: UploadReply= %s\n'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, hostName, str(reply_msg)))
        queue_transmit.put(('train', reply_msg))
    
    def update(self, data):
        global logger
        counter = data['counter']
        hostName = data['hostName']
        perf = data['perf']
        tunnable = data['tunnable']
        traintime = data['traintime']

        # 更新观测历史
        if hostName in self.config_advice_value.keys():
            # observation = Observation(configuration=self.config_advice_value[hostName], performance=(-train_y,))
            last_config = self.config_advice_value[hostName]
            if perf == FAILED_PERF:
                observation = Observation(configuration=last_config,
                                      state=StatusCode.Failed)
            else:
                try:
                    observation = Observation(configuration=last_config,
                                        performance=-perf,
                                        runtime=traintime, # sec
                                        state=StatusCode.Success)
                except Exception as e:
                    observation = Observation(configuration=last_config, state=StatusCode.Failed)
            # logger.debug(observation)
            self.advisor.update(observation)
            # tune_logger.debug(f"Observation {counter}: {observation}")

        # 获取建议的配置
        # tmp_config_advice_value = self.advisor.get_configuration()
        tmp_config_advice_value = self.advisor.suggest()
        repeat_time = 0
        while tmp_config_advice_value in self.advisor.history.configurations:
            repeat_time += 1
            logger.warn('[%s][%d]%s: repeat config_advise_values= %s'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, hostName, str(tmp_config_advice_value)))
            # tmp_config_advice_value = self.advisor.get_configuration()
            tmp_config_advice_value = self.advisor.suggest()
            if repeat_time > 10:
                break            
        
        logger.info('[%s][%d]%s: config_advise_values= %s'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, hostName, str(tmp_config_advice_value)))
        self.config_advice_value[hostName] = tmp_config_advice_value
        # logger.debug(self.history_optimal_value)
        reply_dict = {}
        for item in tunnable:
            if item in tmp_config_advice_value:
                reply_dict[item] = tmp_config_advice_value[item]
        reply_msg = json.dumps(reply_dict)
        logger.debug('[%s][%d]%s: UploadReply= %s\n'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), counter, hostName, str(reply_msg)))
        queue_transmit.put(('update', reply_msg)) # , self.history_optimal_value
        
        # 记录训练历史数据
        self.counter += 1
        if self.counter % 50 == 0:
            self.advisor.history.save(TASK +'_history.json', self.shared_default)
        
    def end(self):
        global logger
        # self.history = self.advisor.get_history()
        self.history_optimal_value = self.advisor.optimized_result()
        logger.info('[%s]--------------------------\r config_optimal_values= %s\r-----------------------------'
                     % (time.strftime("%Y-%m-%d %X", time.localtime()), str(self.history_optimal_value)))
        # tune_logger.debug(f"OptimizedResult: {self.history_optimal_value}")
        self.advisor.history.save(TASK +'_history.json', self.shared_default)
        # importances = self.advisor.importances()
        # logger.info('[%s]--------------------------\r importances= %s\r-----------------------------'
        #              % (time.strftime("%Y-%m-%d %X", time.localtime()), str(importances)))
        
    def process_exception(self, hostname):
        # report to AI
        e_config = self.config_advice_value[hostname]
        observation = Observation(configuration=e_config,
                                      state=StatusCode.Failed)
        self.advisor.update(observation)


if __name__ == '__main__':
    client_dict = {}
    hasPrint = False
    logger = logging.Logger("XtuneLog", level="DEBUG")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler("./XtuneTrain.log", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    tune_logger = get_logger(__name__)
    setup_logger("tuneAI.log")
    
    trainer_thread = Trainer(name='TranerThread')
    trainer_thread.start()
    asyncio.run(serve())
