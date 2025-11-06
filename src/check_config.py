import os
import re

import git
import main

home = "/home/guosy/Kconfig/check_result/"
linux_path = "/home/guosy/Kconfig/linux"
linux = git.Repo(linux_path)

if __name__ == '__main__':
    config_path = "./source/check/"

    tags = []
    for item in linux.tags:
        tags.append(item.name)
    arch = ''

    for folder in os.listdir(config_path):
        index = 0
        arch = folder
        print("folder => " + arch + "\t" +
              str(len(os.listdir(config_path + '/' + folder))))
        for config in os.listdir(config_path + '/' + folder):
            tag = config.split('_')[0]
            tag = tag.replace('.0', '', 1).replace('config-', '')
            tag = 'v' + tag
            if re.fullmatch('v\d+(\.\d+){0,2}(-rc\d+)?', tag):
                if tag in tags:
                    index += 1
                    # with open('result', 'a') as file:
                    #     file.write("find => " + arch + '\t' + tag + '\n')
                    config_file = config_path + arch + '/' + config
                    folder = home + tag + '-' + arch + '/'
                    print(folder)
                    # if not os.path.exists(folder):
                    #     linux.git.checkout(tag, '--force')
                    linux.git.checkout(tag, '--force')
                    main.umain(linux_path, tag, arch, config_file, '/check_result/')
                else:
                    # with open('result', 'a') as file:
                    #     file.write("Not find => " + arch + '\t' + tag + '\n')
                    pass

    print("The check finished!")
