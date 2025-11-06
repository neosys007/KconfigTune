#!/usr/bin/env python3
# **********************************************************************
# Copyright (c) 2022 Institute of Software, Chinese Academy of Sciences.
# kconfigDepDetector is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#         http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, 
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY
# OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# **********************************************************************/
"""此文件可用于实现针对指定Linux内核相关功能, 包括：
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
    * 依赖风险: unmet dependences, 配置项通过select强制启动, 但是依赖未满足

已经测试过的操作系统有
  * Linux原生内核代码
  * Apertis
  * ARCH
  * EndlessOS
  * openEuler
  * openSuse
  * debian
  * ubuntu
"""

import getopt
import json
import os
import platform
import sys

# import kconfigDepDetector.tools
import tools


def print_result(save_file):
    """ 终端打印检查结果

    Args:
        save_file (str): 输出检查结果文件路径
    """
    if os.path.exists(save_file):
        print_dict = {}
        with open(save_file) as fr:
            output = json.load(fr)
        for key in output:
            errmsg = output[key]['error']
            if isinstance(errmsg, list) and len(errmsg) > 0:
                errtype = errmsg[0]
            else:
                errtype = errmsg
                
            output_dict = {}
            output_dict['name'] = key
            kconfigpath = output[key]['path']
            if isinstance(kconfigpath, list) and len(kconfigpath) > 0:
                output_dict['path'] = kconfigpath[0]
            else:
                output_dict['path'] = kconfigpath
            output_dict['value'] = output[key]['value']
            output_dict['type'] = output[key]['type']
            output_dict['dependence'] = output[key]['dep_value'][0]

            if errtype in print_dict.keys():
                print_dict[errtype].append(output_dict)
            else:
                print_dict[errtype] = [output_dict]
        print('\r')
        
        for pk in print_dict:
            # if errortype not in pk:
            #     continue
            num = len(print_dict[pk])
            print("--------"+pk+": "+str(num)+"--------")
            for i in range(0,num):               
                print('[' + print_dict[pk][i]['name'] + ']')
                print('\tvalue = ' + print_dict[pk][i]['value'])
                if print_dict[pk][i]['path'] is not None:
                    print('\tpath = ' + print_dict[pk][i]['path'])

                dep_dict = print_dict[pk][i]['dependence']
                if dep_dict is not None:
                    sel_str = dep_dict['rev_select']
                    dep_str = dep_dict['depends']
                    restrict_str = dep_dict['restrict']
                               
                if pk == 'type error':
                    print('\ttype = ' + print_dict[pk][i]['type'])
                if pk == 'unmet dependences' and len(sel_str) > 0:
                    print('\trev_select = ' + sel_str)
                if (pk == 'depends error' or pk == 'unmet dependences') and len(dep_str) > 0:
                    print('\tdep = ' + dep_str)
                if (pk == 'range error' or pk == 'restrict warning') and len(restrict_str) > 0:
                    print('\trestrict = ' + restrict_str)

            print('\r')
    else:
        # 未检测到错误
        print("No error detected!")
    

def umain(linux, tag, arch, configPath, save_folder='./', display = False):
    """检查内核配置文件主函数

    Args:
        linux (str): 内核源码路径
        tag (str): 内核版本号
        arch (str): 体系架构
        configPath (str): 待检查内核配置文件路径
        save_folder (str, optional): 输出结果路径. Defaults to ''默认当前路径
    """
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
    config = folder + tag + '_' + arch + '_config.json'
    config_dep = folder + tag + '_' + arch + '_dep.json'
    if tools.check_file_data(config) and tools.check_file_data(config_dep):
        print("{:<40}file => {}".format("[Kconfig has been parsed!]", config))
        print("{:<40}file => {}".format("", config))
    else:
        tools.parse(Kconfig, config, config_dep, display = display)

    # 检查配置文件
    save_file = folder + tag + '_' + arch + '_error.json'
    if len(configPath) != 0:
        tools.check(config_dep, config, configPath, save_file)


    # 终端打印输出结果
    print_result(save_file)


def main():
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, "hc:v:s:o:a:", ["check=","version=","src=","output=","arch="])
    except getopt.GetoptError:
        print('check_kconfig_dep.py -c <checkfile> -v <kernelversion> -s <sourcecode> -o <output> -a <arch>')
        sys.exit(2)
        
    tmpdir = os.getcwd()
    # Linux内核位置
    linux = "./"
    # linux版本号
    tag = 'v5.19.16'
    # 指定架构
    localarch = platform.machine()
    arch_relate = {'x86_64':'x86', 'aarch64':'arm64'}
    if localarch in arch_relate:
        arch = arch_relate[localarch]
    else:
        arch = localarch
    # 输出路径
    save_folder='./'

    for opt, arg in opts:
        if opt == '-h':
            print ('checkKconfigDep.py -c <checkfile> -v <kernelversion> -s <sourcecode> -o <output> -a <arch>')
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
            if len(arg):
                save_folder = arg+'/'
    
    umain(linux, tag, arch, configPath, save_folder, True)


if __name__ == '__main__':
    main()
    
