import os
import re

import git
import main

linux_path = "/home/guosy/Kconfig/OS/linux"
linux = git.Repo(linux_path)

tags = [
    'v2.6.39',
    'v3.19',
    'v4.20',
    'v5.19',
    'v6.1'
]

if __name__ == '__main__':
    arch = 'x86'
    for tag in linux.tags:
        # if tag.name[1] == '4' or tag.name[1] == '6':
        if tag.name in tags:
            try:
                linux.git.checkout(tag.name, '--force')
            except:
                print("error tag => " + tag.name)
                continue
            
            if arch in os.listdir(linux_path + '/arch'):
                main.umain(linux_path, tag.name, arch, '')
            else:
                print("no arch => " + tag.name)