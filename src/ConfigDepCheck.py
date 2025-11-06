#!/usr/bin/python3

'''此文件可用于实现针对指定Linux内核相关功能, 包括：
  1 预处理文件(所有Kconfig文件整理到一个文件内)
  2 Kconfig解析, 生成配置项数据的json文件, 全部以string形式存储
  3 检查配置文件, 根据指定配置文件检查是否存在问题

为了便于批量化处理, 将同一版本的结果存储到指定文件夹内
  文件名格式为tag-arch
  可以进一步封装函数完成特定的批量化需求

检测中仅输出error具体错误数量, 用于提示检测具体的依赖错误
错误信息包括: 
    * 类型错误: type error, 配置项类型错误
    * 依赖不满足: depends error, 配置项未通过select启动且依赖不满足
    * 未找到配置项: lack config, 未在内核Kconfig文件中找到指定配置项
    * range未满足: range error, 
    * 取值未满足: restrict warning, 配置项取值未满足要求, 通常为default或imply关键字
    * 依赖风险: unmet dependence, 配置项通过select强制启动, 但是依赖未满足

已经测试过的操作系统有
  * Linux原生内核代码
  * Apertis
  * ARCH
  * EndlessOS
  * openEuler
  * debian
  * ubuntu
'''

import getopt
import os
import platform
import sys

import tools

arch_relate = {'x86_64':'x86', 'aarch64':'arm64'}

def umain(linux, tag, arch, configPath, save_folder='./', display = False):
    # 检测保存文件夹是否存在
    folder = tools.check_folder(save_folder, tag, arch)

    # 预处理阶段
    Kconfig = folder + tag + '_' + arch + '.Kconfig'
    if tools.check_file_data(Kconfig):
        print("{:<40}file => {}".format("[Have preprocessing]", Kconfig))
    else:
        tools.preprocessing(linux, arch, Kconfig, display)
        print("{:<40}file => {}".format("[Preprocessing end]", Kconfig))

    # Kconfig解析器
    config = folder + 'config.json'
    config_dep = folder + 'dep.json'
    if tools.check_file_data(config) and tools.check_file_data(config_dep):
        print("{:<40}file => {}".format("[Kconfig has been parsed!]", config))
        print("{:<40}file => {}".format("", config))
    else:
        tools.parse(Kconfig, folder, display = display)

    # 检查配置文件
    save_file = folder + 'error.json'
    if len(configPath) != 0:
        tools.check(folder, configPath, save_file)


if __name__ == '__main__':
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, "hc:v:s:o:a:d:", ["check=","version=","src=","arch=", "display="])
    except getopt.GetoptError:
        print('checkKconfigDep.py -c <checkfile> -v <kernelversion> -s <sourcecode> -o <output> -a <arch> -d <display(True/False)>')
        sys.exit(2)
        
    tmpdir = os.getcwd()
    # Linux内核位置
    linux = "./"
    # linux版本号
    tag = 'no_input'
    # 指定架构
    localarch = platform.machine()
    if localarch in arch_relate.keys():
        arch = arch_relate[localarch]
    else:
        arch = localarch
    save_folder='./'
    configPath = ''
    dis = False

    for opt, arg in opts:
        if opt == '-h':
            print ('checkKconfigDep.py -c <checkfile> -v <kernelversion> -s <sourcecode> -o <output> -a <arch> -d <display(True/False)>')
            sys.exit()
        elif opt in ("-c", "--checkfile"):
            configPath = arg
        elif opt in ("-v", "--version"):
            tag = arg
        elif opt in ("-s", "--sourcecode"):
            linux = arg
        elif opt in ("-a", "--arch"):
            arch = arg
        elif opt in ("-o", "--output"):
            save_folder = '/'+arg
        elif opt in ("-d", "--display"):
            if arg == 'True':
                dis = True
            else:
                dis = False

    umain(linux, tag, arch, configPath, save_folder, dis)
    
