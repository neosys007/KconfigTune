import json
import os

count = None

def reset_count() -> None:
    global count
    count = {
        'lack config' : 0,
        'depends error' : 0,
        'restrict warning': 0,
        'unmet dependences': 0,
        'type error' : 0,
        'range error': 0
    }

def dict_print(target) -> None:
    print(json.dumps(target, indent=4))

def load_json(path) -> list:
    with open(path) as file:
        return json.load(file)

def analysis_json(path) -> None:
    data = load_json(path)
    for item in data:
        for tmp in data[item]['error']:
            global count
            if tmp in count:
                count[tmp] += 1

def linux_tmp():
    root = '/home/guosy/Kconfig/result/check_config'
    reset_count()
    for linux_name in os.listdir(root):
        reset_count()
        print(linux_name)
        for arch in os.listdir(root + '/' + linux_name):
            for folder in os.listdir(root + '/' + linux_name + '/' + arch):
                for file in os.listdir(root + '/' + linux_name + '/' + arch + '/' + folder):
                    if len(file.split('_')) > 2 and file.split('_')[2] == 'error.json':
                        analysis_json(root + '/' + linux_name + '/' + arch + '/' + folder + '/' + file)
        dict_print(count)

def LinuxDistri(root):
    for arch in os.listdir(root):
        print(arch)
        reset_count()
        for folder in os.listdir(root + '/' + arch):
            for file in os.listdir(root + '/' + arch + '/' + folder):
                if len(file.split('_')) > 2 and file.split('_')[2] == 'error.json':
                    analysis_json(root + '/' + arch + '/' + folder + '/' + file)
        dict_print(count)

def linux():
    root = '/home/guosy/Kconfig/result/check_config'
    reset_count()
    for arch in os.listdir(root):
        for folder in os.listdir(root + '/' + arch):
            for file in os.listdir(root + '/' + arch + '/' + folder):
                if len(file.split('_')) > 2 and file.split('_')[2] == 'error.json':
                    analysis_json(root + '/' + arch + '/' + folder + '/' + file)
    dict_print(count)

def handle_count(path):
    result = {
        'depend_error'  : 0,
        'unmet_depend'  : 0,
        'type_error'    : 0,
        'value_warming' : 0,
        'range_error'   : 0,
        'choice'        : 0
    }
    count = 0
    for folder in os.listdir(path):
        count += 1
        data = load_json(path + '/' + folder + '/' + 'check.json')
        result.update(data)
        print(result)
    print(count)


def count_depends(path):
    data = load_json(path)
    name = None
    max = 0
    for item in data:
        # if len(data[item][0]['dep']) > max:
        if data[item][0]['dep'].count('(') > max:
            max = data[item][0]['dep'].count('(')
            name = item
    print(name)

if __name__ == '__main__':
    '''
    ArchLinux   '/home/guosy/Kconfig/result/ArchLinux'
    Debian
    Fedora
    openSuse    '/home/guosy/Kconfig/result/SUSE'
    Ubuntu      '/home/guosy/Kconfig/result/ubuntu'
    '''
    # print("Archlinux")
    # LinuxDistri('/home/guosy/Kconfig/result/ArchLinux')
    # print("openSuse")
    # LinuxDistri('/home/guosy/Kconfig/result/SUSE')
    # print("Ubuntu")
    # LinuxDistri('/home/guosy/Kconfig/result/ubuntu')
    # linux()
    # handle_count("/home/guosy/Kconfig/count")
    count_depends('/home/guosy/Kconfig/v2.6.39-rc7-x86/v2.6.39-rc7_x86_dep.json')


