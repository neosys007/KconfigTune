#!python3

# help信息与arch对应

import json
from multiprocessing import Process
import os

import tools


def check_folder(root, target) -> str:
    if root[-1] == '/':
        folder_name = root + target
    else:
        folder_name = root + '/' + target
    if os.path.exists(folder_name):
        return folder_name + '/'
    else:
        os.mkdir(folder_name)
        return folder_name + '/'

def preprocess(linux, tag, arch, save_folder, display):
    # 检测保存文件夹是否存在
    folder = check_folder(save_folder, arch)

    # 预处理阶段
    Kconfig = folder + tag + '_' + arch + '.Kconfig'
    if tools.check_file_data(Kconfig):
        print("{:<40}file => {}".format("[Have preprocessing]", Kconfig))
    else:
        tools.preprocessing(linux, arch, Kconfig, display)
        print("{:<40}file => {}".format("[Preprocessing end]", Kconfig))

def sub_process(tag, arch, folder, display):
    # 预处理阶段结果
    Kconfig = folder + tag + '_' + arch + '.Kconfig'

    # Kconfig解析器
    config = folder + tag + '_' + arch + '_config.json'
    config_dep = folder + tag + '_' + arch + '_dep.json'
    if tools.check_file_data(config) and tools.check_file_data(config_dep):
        print("{:<40}file => {}".format("[Kconfig has been parsed!]", config))
        print("{:<40}file => {}".format("", config))
    else:
        tools.parse(Kconfig, config, config_dep, display = display)


def get_dir(path) -> list:
    result = []
    for item in os.listdir(path):
        if os.path.isdir(path + '/' + item):
            result.append(item)
    return result


class Config:
    def __init__(self, arch, target) -> None:
        self.path = target['path']
        self.name = target['name']
        self.type = target['type']
        self.arch = [arch]

        self.group = target['group']

        self.value = {
            "prompt": target['value']['prompt'],
            "default": target['value']['default'],
            "imply": target['value']['imply'],
            "select": target['value']['select'],
            "depends": target['value']['depends'],
            "range": target['value']['range'],
            "modules": target['value']['modules']
        }
        # self.help = target['help']
        self.help = {}
    
    def add_help(self, help):
        for item in self.help:
            if self.help[item] == help:
                return
        self.help[self.arch[-1]] = help

class ConfigDep:
    def __init__(self, arch, target) -> None:
        self.type = target['type']
        self.arch = [arch]
        self.rev_select = target['rev_select']
        self.dep = target['dep']
        self.restrict = target['restrict']

AllConfig = {}
AllConfigDep = {}

def compare_config(save, target) -> bool:
    if save.path != target['path']: return False
    if save.type != target['type']: return False
    if save.group != target['group']: return False
    # if save.help != target['help']: return False
    save = save.value
    target = target['value']
    if save['prompt'] != target['prompt']: return False
    if save['default'] != target['default']: return False
    if save['imply'] != target['imply']: return False
    if save['select'] != target['select']: return False
    if save['depends'] != target['depends']: return False
    if save['range'] != target['range']: return False
    if save['modules'] != target['modules']: return False
    return True

def compare_dep(save, target) -> bool:
    if save.type != target['type']: return False
    if save.rev_select != target['rev_select']: return False
    if save.dep != target['dep']: return False
    if save.restrict != target['restrict']: return False
    return True

def handle_config(arch, save, target, Class, func) -> list:
    for name in target:
        # bug
        if save.get(name):
            for target_item in target[name]:
                # flag = False
                flag = True
                for save_item in save[name]:
                    if func(save_item, target_item):
                        if arch not in save_item.arch:
                            save_item.arch.append(arch)
                            try:
                                save_item.add_help(target_item['help'])
                            except:
                                pass
                            flag = False
                        # else:
                        #     flag = True
                if flag:
                    save[name].append(Class(arch, target_item))
        else:
            for item in target[name]:
                if save.get(name):
                    save[name].append(Class(arch, item))
                else:
                    save[name] = [Class(arch, item)]
    return save


def handle_arch(tag, arch):
    path = './' + tag + '/' + arch + '/'
    config = tools.load_json(path + tag + '_' + arch + '_config.json')
    dep = tools.load_json(path + tag + '_' + arch + '_dep.json')
    global AllConfig, AllConfigDep
    AllConfig = handle_config(arch, AllConfig, config, Config, compare_config)
    AllConfigDep = handle_config(arch, AllConfigDep, dep, ConfigDep, compare_dep)

def check_alive(path) -> bool:
    try:
        tools.load_json(path + '_config.json')
    except:
        return False
    try:
        tools.load_json(path + '_dep.json')
    except:
        return False
    return True

if __name__ == '__main__':
    # Linux内核位置
    linux = "/home/guosy/Kconfig/OS/linux"
    # linux版本号
    tag = 'test'

    root = check_folder('./', tag)
    arch_lis = get_dir(linux + '/arch')

    process_list = {}

    for arch in arch_lis:
        preprocess(linux, tag, arch, root, False)
        subp = Process(target= sub_process, args=(tag, arch, root + arch + '/', False))
        process_list[arch] = subp
        subp.start()

    while len(process_list):
        arch = ''
        for item in process_list:
            if not process_list[item].is_alive() and check_alive(root + item + '/' + tag + '_' + item):
                process_list.pop(item)
                arch = item
                break
        if len(arch) != 0:
            handle_arch(tag, arch)
            arch = ''
    
    tools.write_json(AllConfig, root + tag + '_' + 'config.json')
    tools.write_json(AllConfigDep,  root + tag + '_' + 'dep.json')

