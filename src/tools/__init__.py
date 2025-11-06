__all__ = ['preprocess.py', 'config_yacc.py', 'check.py', 'changeNode.py']

import os

import tools.check as config_check
import tools.config_yacc as config_yacc
import tools.preprocess as preprocess
import tools.utils as utils


def preprocessing(root, target, file, display) -> None:
    preprocess.Preprocessing(root, target, file, display)


def load_Kconfig(path) -> str:
    return utils.load_Kconfig(path)


def load_json(path):
    return utils.load_json(path)


def load_config(path):  # HAVE_CHECK放在for循环, 检查config时自动查看config取值
    ''' 加载.config配置文件
    对于配置文件中不存在以及is not set的config取值为n
    '''
    return utils.load_config(path)


def check_file_data(path) -> bool:
    '''检查文件是否存在且文件内部是否有数据
    参数:
        path: 文件路径信息
    返回值: 布尔类型
    '''
    if os.path.exists(path) and os.path.isfile(path):
        with open(path, 'r') as file:
            data = file.read()
            if len(data) > 0:
                return True
            else:
                return False
    else:
        return False


def check_folder(root, tag, arch) -> str:
    ''' 检查保存文件夹是否存在, 不存在则在当前根目录下创建文件夹
    参数:
        root: 根路径
        tag: 当前Linux内核版本
        arch: 需要处理的指定架构
    返回值: 文件夹名称
    '''
    if root[-1] == '/':
        folder_name = root + tag + '-' + arch
    else:
        folder_name = root + '/' + tag + '-' + arch
    if os.path.exists(folder_name):
        return folder_name + '/'
    else:
        os.mkdir(folder_name)
        return folder_name + '/'


def write_json(data, save_file) -> None:
    utils.write_json_file(data, save_file)


def parse(Kconfig, folder, display) -> None:
    ''' ply包问题, 需要在同路径下调度parser
    参数:
        Kconfig: 预处理后的文件路径
        folder: 保存的文件夹路径
        display: 是否显示终端信息，可加快识别速度
    返回值: None
    '''
    config_yacc.ParseKconfig(Kconfig, folder, display)


def check(folder, ConfigFile, save_file) -> None:
    parser = utils.Parser(folder, ConfigFile)
    config_check.reset_GLOBAL()
    config_check.Checker(parser, save_file)


def check_config(parse, config_name, target_value) -> (bool, bool, bool):
    # 主要用与changeNode
    config_check.reset_GLOBAL()
    save = []
    if config_name in parse['CONFIG_DEP']:
        index = -1
        for item in parse['CONFIG_DEP'][config_name]:
            index += 1
            dep = check_dep(parse, item['dep'])
            rev_dep = check_select(parse, item['rev_select'])
            restrict = config_check.check_restrict(
                    parse, \
                    config_check.get_tokens(item['restrict']), \
                    config_name, target_value, index
                )
            restrict = False if restrict == 'n' else True
            save.append((dep, rev_dep, restrict))
        if len(save) == 1:
            return (dep, rev_dep, restrict, 0)
        else:
            raise
    else:
        return None

def check_select(parse, line):
    tokens = config_check.get_tokens(line)
    stack = config_check.check_expr(parse, tokens)
    if len(stack) == 1 and stack[0] == 'None' or not len(stack):
        return 'n'
    return config_check.reduce(stack)


def check_dep(parse, line):
    tokens = config_check.get_tokens(line)
    stack = config_check.check_expr(parse, tokens)
    if len(stack) == 0:
        return 'y'
    return config_check.reduce(stack)

def make_dict(dep_data, flag) -> dict:
    getFather = {}
    getKid = {}
    for name in dep_data:
        for detail in dep_data[name]:
            temp = utils.getWord(detail['rev_select']) + utils.getWord(detail['dep'])
            for item in temp:
                getFather = utils.dict_add_item(getFather, name, item)
                getKid = utils.dict_add_item(getKid, item, name)
    if flag:
        return getKid
    else:
        return getFather

def getKid(config_dep, save):
    dep_data = load_json(config_dep)
    jsondata = make_dict(dep_data, True)
    print("{:<40}".format("[Prepare write ConfigPath]") + "file => " + save)
    write_json(jsondata, save)


def getFather(config_dep, save):
    dep_data = load_json(config_dep)
    jsondata = make_dict(dep_data, False)
    print("{:<40}".format("[Prepare write ConfigPath]") + "file => " + save)
    write_json(jsondata, save)

def get_path(SourcePath, SavePath):
    data = load_json(SourcePath)
    ConfigPath = {}
    for item in data:
        ConfigPath[item] = []
        for ptr in data[item]:
            ConfigPath[item].append(ptr['path'])
    print("{:<40}".format("[Prepare write ConfigPath]") + "file => " + SavePath)
    write_json(ConfigPath, SavePath)

def get_help(SourcePath, SavePath):
    data = load_json(SourcePath)
    ConfigPath = {}
    for item in data:
        ConfigPath[item] = []
        for ptr in data[item]:
            help = ptr['help'].replace('\n\t\t', '').replace('\t\t', '')
            ConfigPath[item].append(help)

    print("{:<40}".format("[Prepare write ConfigHelp]") + "file => " + SavePath)
    write_json(ConfigPath, SavePath)
