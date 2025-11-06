'''此文件用于生成配置项的父类或子类配置项
函数依赖于main.py生成的dep.json文件

这里的子类配置从作用角度出发
一切会对当前配置产生影响的配置项均认为是其父类配置项
反之则为子类
'''

import tools

if __name__ == '__main__':
    config_dep = "./v6.2-x86/v6.2_x86_dep.json"
    save = "./v6.2-x86/v6.2_x86_dep"

    tools.getKid(config_dep, save + "_Kid.json")
    tools.getFather(config_dep, save + "_Father.json")
