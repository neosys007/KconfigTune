from multiprocessing import Process
import os
import time

import git
import tools

linux = ''
check_path = ''
save_path = ''
linux_repo = None

def umain(linux, tag, arch, configPath, save_folder='./', display = False):
    # 检测保存文件夹是否存在
    folder = save_path + tag + '-' + arch + '/'

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

def multi_check(arch, tag, config = '') -> None:
    save_folder = save_path + tag + '-' + arch
    if not os.path.exists(save_folder):
        os.mkdir(save_folder)
    
    root = os.getcwd()
    os.chdir("./OS/linux")
    if os.system("make defconfig") == 0:
        os.chdir(root)
    if os.system("mv /home/guosy/Kconfig/OS/linux/.config " + save_folder):
        print(tag + "mv .config error")
    
    Kconfig = save_folder + tag + '_' + arch + '.Kconfig'
    if not tools.check_file_data(Kconfig):
        # checkout(tag)
        tools.preprocess.Preprocessing(linux, arch, save_folder + '/' + tag + '_' + arch + '.Kconfig', False)
    if config != '':
        config = check_path + '/' + arch + '/' + config
    
    subp = Process(target = umain, args = (linux, tag, arch, config, save_path + '/' + arch, False))
    subp.start()

def checkout(tag) -> None:
    try:
        linux_repo.git.checkout('v' + tag, '--force')
    except Exception:
        print("checkout error => v" + tag)

def reverse(path = ''):
    if not os.path.exists(save_path + path):
        os.mkdir(save_path + path)
    result = []
    for tmp in os.listdir(check_path + path):
        if tmp != '.DS_Store':
            result.append(tmp)
    return result

##############################################################
# linux

def handle_linux_tag(file_name) -> str:
    tag = file_name.split('.config')[0].replace('.config', '')
    return tag[1:]

def check_linux() -> None:
    global check_path, save_path, linux_repo, linux
    linux = "./OS/linux"
    check_path = './target/community/'
    save_path = './result/linux/'
    linux_repo = git.Repo(linux)
    for arch in reverse():
        for config in reverse(arch):
            tag = handle_linux_tag(config)
            multi_check(arch, tag, config)

##############################################################
# openSuse

def handle_suse_tag(file_name) -> str:
    if file_name[:7] == 'config-':
        file_name = file_name.split('-')
        file_name = file_name[1]
    else:
        file_name = file_name.split('_')
        file_name = file_name[0]
    tag_list = file_name.split('.')
    tag = tag_list[0] + '.' + tag_list[1]
    if tag_list[2] != '0':
        tag += '.' + tag_list[2]
    return tag

def check_suse() -> None:
    global check_path, save_path, linux_repo, linux
    linux = "./OS/SUSE"
    check_path = './target/check_config/openSuse/'
    save_path = './result/SUSE/'
    linux_repo = git.Repo(linux)
    for arch in reverse():
        for config in reverse(arch):
            tag = handle_suse_tag(config)
            multi_check(arch, tag, config)

##############################################################
# archlinux

def handle_archlinux_tag(file_name) -> str:
    name_list = file_name.split('.')
    tag = name_list[0] + '.' + name_list[1]
    arch = name_list[2].split('-')
    if arch[0] != '0':
        tag += '.' + arch[0]
    if len(arch) == 2:
        if arch[1] == '1' or arch[1] == 'arch1':
            arch = '-arch1'
        else:
            arch = '-arch2'

    else:
        arch = '-arch1'
    tag += arch
    return tag

def check_archlinux() -> None:
    global check_path, save_path, linux_repo, linux
    linux = "./OS/archlinux"
    check_path = './target/check_config/ArchLinux/'
    save_path = './result/ArchLinux/'
    linux_repo = git.Repo(linux)
    for arch in reverse():
        print(arch)
        for config in reverse(arch):
            tag = handle_archlinux_tag(config)
            multi_check(arch, tag, config)

##############################################################
# ubuntu

def handle_ubuntu_tag(file_name) -> str:
    name_list = file_name.split('-')
    name_list = name_list[1].split('.')
    tag = name_list[0] + '.' + name_list[1]
    if name_list[2] != '0':
        tag += '.' + name_list[2]
    return tag

def check_ubuntu() -> None:
    global check_path, save_path, linux_repo, linux
    linux = "./OS/ubuntu"
    check_path = './target/check_config/Ubuntu/'
    save_path = './result/ubuntu/'
    linux_repo = git.Repo(linux)
    for arch in reverse():
        print(arch)
        for config in reverse(arch):
            tag = handle_ubuntu_tag(config)
            multi_check(arch, tag, config)

def get_456():
    arch = 'x86'
    global check_path, save_path, linux_repo, linux
    linux = "./OS/linux"
    # check_path = './target/check_config/'
    save_path = './result/chenguo/'
    linux_repo = git.Repo(linux)
    for tag in linux_repo.tags:
        if tag.name[1] == '4' or tag.name[1] == '5' or tag.name[1] == '6':
            try:
                linux_repo.git.checkout(tag.name, '--force')
            except:
                print("error tag => " + tag.name)
                continue
            
            multi_check(arch, tag.name)


if __name__ == '__main__':
    # check_suse()
    # check_archlinux()
    # check_ubuntu()
    check_linux()

    # get_456()
