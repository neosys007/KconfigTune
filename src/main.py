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

# from memory_profiler import profile
import tools
import argparse
import sys
import os


# @profile(precision=4,stream=open('memory_profiler.log','w+'))
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
    if sys.argv[1:]:
        parser = argparse.ArgumentParser(description="help")
        parser.add_argument('--os', '-s', help="Linux path")
        parser.add_argument('--tag', '-t', help="Linux tag")
        parser.add_argument('--arch', '-a', help="Linux arch")
        parser.add_argument('--config', '-c', help="check file")
        parser.add_argument('--output', '-o', default="./", help="output path")
        parser.add_argument('--display', '-d', default=True, help="display control")

        args = parser.parse_args()

        linux = args.os
        tag = args.tag
        arch = args.arch
        config = args.config
        output = args.output
        display = args.display

        umain(linux, tag, arch, config, output, display)
    else:
        # # Linux内核位置
        linux = "/home/guosy/Kconfig/OS/v6.6"
        # linux版本号
        tag = '6.6'
        # 指定架构
        arch = 'x86'
        # 需要检查的.config文件路径
        configPath = linux + "/.config"

        umain(linux, tag, arch, configPath, './', True)

    