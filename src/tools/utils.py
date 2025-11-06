import json
import os
import pickle
import re
import logging

import tools.check_lex as check_lex


class EmployeeEncoder(json.JSONEncoder):
    '''辅助自定义类结构写入json文件'''
    def default(self, o):
        return o.__dict__


def load_Kconfig(path):
    '''
    读取Kconfig文件, 并处理非UTF-8字符
    参数:
        path: 文件路径信息
    返回值: 文件数据
    Raises: 出现未处理的utf-8字符
    '''
    with open(path, 'r') as file:
        data = file.read()
        data = data.replace(u'\xa0', ' ')
    return data


def load_json(path):
    '''读取json文件
    参数:
        path: 文件路径
    返回值: json数据
    '''
    with open(path, 'r') as file:
        data = json.load(file)
    return data


def write_json_file(data, save_file):
    ''' 借助EmployeeEncoder类将数据写入json文件内
    参数:
        data: 自定义类数据
        save_file: 保存路径
    返回值: None
    '''
    print("{:<40}".format("[Write json]"))
    jsonDate = json.dumps(data, indent=4, cls=EmployeeEncoder)
    with open(save_file, 'w') as file:
        file.write(jsonDate)


def getWord(line):
    result = []

    check_lex.lexer.input(line)
    while True:
        tok = check_lex.lexer.token()
        if not tok:
            break
        if tok.type == 'WORD':
            if re.fullmatch('[0-9]+', tok.value) or tok.value[0:2] == '0x':
                pass
            if re.fullmatch('[A-Z0-9_x]+', tok.value):
                if tok.value not in result:
                    result.append(tok.value)
    return result


def dict_add_item(save, left, right):
    if save.get(left, None):
        if right not in save[left]:
            save[left].append(right)
    else:
        save[left] = [right]
    return save

def stack_pop(stack):
    if len(stack) > 0:
        return stack.pop()
    else:
        raise AttributeError("stack pop error!")

def saveAllNode(folder, AllNode):
    if folder[-1] != '/':
        folder += '/'
    pkl = folder + "node.pkl"
    with open(pkl, 'wb') as f:
        pickle.dump(AllNode, f)


def loadPkl(folder):
    if folder[-1] != '/':
        folder += '/'
    pkl = folder + "node.pkl"
    with open(pkl, "rb") as f:
        AllNode = pickle.load(f)
    return AllNode

def load_config(path):  # HAVE_CHECK放在for循环, 检查config时自动查看config取值
    ''' 加载.config配置文件
    对于配置文件中不存在以及is not set的config取值为n
    '''
    save = {}
    with open(path, 'r') as file:
        lines = file.readlines()
        name = ''
        for line in lines:
            if line[0:9] == '# CONFIG_':
                name = line.replace('# CONFIG_','').replace(' is not set\n', '').strip()
                ptr = save.get(name, None)
                if not ptr:
                    save[name] = 'n'
                else:
                    print("error, repeat config => " + name + " in .config")
            elif line[:7] == 'CONFIG_':
                line = line[7:].replace('\n', '')
                (name_str, value_str) = line.split('=', 1)
                name = name_str.strip()
                value = value_str.strip()
                ptr = save.get(name, None)
                if not ptr:
                    save[name] = value
                else:
                    print("error, repeat config => " + name + " in .config")
    print("{:<40}".format("[Load config end!]") + "got " + str(len(save)) + " config")
    return save

def handleCONFIG_(target) -> dict:
    if target == None:
        return None
    res = {}
    for item in target:
        if item[:7] == "CONFIG_":
            res[item[7:]] = target[item]
        else:
            res[item] = target[item]
        if isinstance(target[item], int) and not isinstance(target[item], bool):
            res[item] = str(target[item])
        elif isinstance(target[item], int) and target[item] >= 0x0 and target[item] <= 0xFFFFFFFFFFFFFFFF:
            res[item] = hex(target[item])
    return res

class Parser:
    def __init__(self, folder, ConfigFile, OSPath = None, TargetDict = None) -> None:
        if OSPath:
            logFile = OSPath + "/.changeNode" if OSPath[-1] == '/' else OSPath + "/.changeNode"
            self.OSPath = OSPath
            self.logger = Logger(logFile)
        self.TargetDict = handleCONFIG_(TargetDict)
        self.KconfigDict = loadPkl(folder)
        self.CONFIG_DEP = load_json(folder + '/dep.json')
        self.CONFIG = load_json(folder + '/config.json')
        self.CONFIG_VALUE = load_config(ConfigFile)
        self.AllChange = {}

class Logger:
    def __init__(self, logFile=None, logName = "KconfigLog"):
        self.logFile = logFile
        self.logger = logging.getLogger(logName)
        self.logger.setLevel(logging.DEBUG)

        if logFile:
            if os.path.exists(logFile):
                os.remove(logFile)
            file_handler = logging.FileHandler(logFile)
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("\n%(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    @property
    def log_file(self):
        return self.logFile.split('/')[-1]

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

    def debug(self, message):
        self.logger.debug(message)