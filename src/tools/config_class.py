'''
定义相关数据结构
辅助解析器进行识别以及保存等相关功能
'''

import json


class EmployeeEncoder(json.JSONEncoder):
    '''辅助自定义类结构写入json文件'''
    def default(self, o):
        return o.__dict__


def checkLineAnd(line):
    if len(line) > 0:
        line += ' && '
    return line


def checkLineOR(line):
    if len(line) > 0:
        line += ' || '
    return line


########################################################################
#   group_if类, 保存当前if组关键字的原始信息
#   * path => if所在的路径信息
#   * value => Kconfig的原始信息
########################################################################


class If:
    '''
    表示if组关系的数据结构, 辅助node类展示具体信息
    if后跟表达式为depends依赖关系
    '''
    def __init__(self, path, depends) -> None:
        self.type = 'if'
        self.path = path
        self.depends = depends

    def set_value(self, value):
        self.depends = value

    def get_depends(self):
        return '{(' + self.depends + ')}'

    def get_dis(self):
        return ''


class Menu:
    '''
    menu类的数据结构, 辅助node类展示具体信息

    属性包括: 
        * type: 固定为'menu'信息
        * path: 当前menu菜单所在的文件路径
        * name: menu提示信息, 通常仅跟在menu关键字后
        * visibile: menu属性
        * depends: menu属性
    '''
    def __init__(self, path, name) -> None:
        self.type = 'menu'
        self.path = path
        self.name = name
        self.visible = []
        self.depends = []

    def set_value(self, target, value):
        if target == 'visible':
            self.visible.append(value)
        elif target == 'prompt':
            self.prompt = value
        elif target == 'depends':
            self.depends.append(value)

    def get_depends(self):
        result = ""
        for item in self.depends:
            if len(item) > 0:
                result = checkLineAnd(result) + "( " + item + " )"
        return '{' + result + '}'

    def get_dis(self):
        result = ""
        for item in self.visible:
            if len(item) > 0:
                result = checkLineAnd(result) + '(' + item + ')'
            result += item
        return result


class Choice:
    '''
    choice组信息, 辅助node类展示具体信息

    属性包括:
    * type: choice类型, 例如bool或tristate
    * path: 当前choice组所在路径
    * name: 文法允许choice定义名称, 但是通常开发者不会进行定义, 此处以数字代替
    * prompt: choice的提示字符, 包括prompt关键字和type后跟关键字
    * default: 默认值, 允许通过if条件出现多个建议默认值
    * depends: 依赖条件
    * optional: 允许当前choice组不选择任何子配置
    * help: 辅助信息
    '''
    def __init__(self, path, name) -> None:
        self.type = 'choice'
        self.path = path
        self.name = name
        self.type = ""
        self.prompt = ""
        self.default = []
        self.depends = []
        self.optional = None
        self.help = ""

    def set_value(self, target, value):
        if target == 'type':
            self.type = value
        elif target == 'prompt':
            if len(self.prompt) > 0:
                raise
            self.prompt = ""
        elif target == 'default':
            self.default.append(value)
        elif target == 'depends':
            self.depends.append(value)
        elif target == 'optional':
            self.optional = True

    def get_depends(self):
        result = ""
        for item in self.depends:
            if len(item) > 0:
                result = checkLineAnd(result) + "( " + item + " )"
        return '{' + result + '}'

    def get_dis(self):
        return self.prompt

    def get_default(self):  # default
        result = []
        for item in self.value['default']:
            result.append(item.split(' if '))
        return result


class Config:
    '''
    保存config和menuconfig属性, 并最终输出到config.json中

    属性包括:
    * path: 配置项所在文件的路径信息
    * name: 配置项名称
    * type: 配置项类型, 例如: int, hex, bool, tristate, string
    * group: 组关系信息
    * value:
    * help:
    '''
    def __init__(self, name, path) -> None:
        self.path = path
        self.name = name
        self.type = ""

        self.group = []

        self.value = {
            "prompt": "",
            "default": [],
            "rev_imply": [],
            "select": [],
            "depends": [],
            "range": [],
            "modules": None
        }
        self.help = ""

    def set_type(self, value):
        self.type = value

    def set_value(self, target, value):
        if target == "modules":
            self.value[target] = True
        elif target == "prompt":
            if len(self.value['prompt']) > 0:
                raise
            self.value['prompt'] = value
        else:
            self.value[target].append(value)

    def set_group(self, value):
        self.group = value

    def get_dis(self):  # prompt
        if len(self.value['prompt']) == 0:
            return ""
        prompt = self.value['prompt'].split(" if ")
        if len(prompt) > 1:
            return prompt[1]
        else:
            return ""

    def get_default(self):  # default
        result = []
        for item in self.value['default']:
            result.append(item.split(' if '))
        return result


########################################################################
#   group类, 保存config的一层组关系
#   * display => if所在的路径信息
#   * depends => Kconfig的原始信息
########################################################################


class Group:
    '''
    辅助config数据结构转换组信息
    组信息中, 比较重要的两个属性, 一个是显示控制条件, 其次是依赖属性

    属性包括：
    * display: 显示控制条件, 指menu的visible或choice的两种显示控制情况
    * depends: 依赖条件, 包括menu和choice的depends以及if组关系
    '''
    def __init__(self, node) -> None:
        self.node = node
        self.display = ""
        self.depends = ""

    def set_group_display(self, value):
        self.display = checkLineAnd(self.display)
        self.display += value

    def set_group_dep(self, value):
        self.depends = checkLineAnd(self.depends)
        self.depends += value


class ConfigDep:
    '''
    保存当前config的父关系config名称, 用于检查Config是否可以被配置以及取值是否正确
    
    属性包括：
    * rev_select: 在子类中保存select语句
    * dep: 在配置项中保存从根节点到当前配置项的组依赖条件以及配置项依赖条件
    * restrict: 

    若使得config配置项成立, 有两种方式
        1, 通过select语句将子config成立
        2, 通过满足depends语句使得配置项成立
    restrict属性则用于对配置项的取值进行检查, 包括range信息以及显示控制检查
    '''
    def __init__(self) -> None:
        self.type = ""
        self.rev_select = ""
        self.dep = ""
        self.restrict = ""

    def set_select(self, value, if_expr):
        self.rev_select = checkLineOR(self.rev_select)
        if len(if_expr) > 0:
            self.rev_select += value + '[' + if_expr + ']'
        else:
            self.rev_select += value

    def set_depends(self, value):
        if len(value) > 0:
            self.dep = checkLineAnd(self.dep)
            self.dep += value

    def set_restrict(self, value, if_expr):
        self.restrict = checkLineOR(self.restrict)
        if len(if_expr) > 0:
            self.restrict += '( ' + value + ' )[' + if_expr + ']'
        else:
            self.restrict += '( ' + value + ' )'

    def set_imply(self, father, if_expr):
        save = self.restrict
        self.restrict = ""
        if len(if_expr) > 0:
            self.restrict = father + '[ ' + if_expr + ' ]'
        if len(save) > 0:
            self.restrict = checkLineOR(self.restrict) + save


class ConfigDepTemp:
    '''用于辅助Config_dep数据存储相关信息'''
    def __init__(self) -> None:
        self.display = ""
        self.restrict = []
        self.imply = []
        self.depend = []

    def set_display(self, value):
        if len(value):
            self.display = checkLineAnd(self.display) + value

    def set_restrict(self, value):
        self.restrict.append(value)

    def set_imply(self, value):
        self.imply.append(value)

    def get_default(self):  # default
        return self.restrict

    def get_display(self):
        return self.display

    def set_depends(self, value):
        self.depend.append(value)
    
    def get_depends(self):
        return self.depend


class Node:
    '''
    用于组织树结构
    
    属性包括: 
        * name: 配置名称, 通常用于config和menu属性
        * type: 用于标记节点类型, 例如config、menu、if、choice
        * path: 当前节点所在文件的路径信息
        * kids: 若节点为组关键字, 则内部存储子配置项信息
        * detail: 用特定的数据结构存储信息, 数据结构均在上述分析
        * config_dep: 通过给定的数据结构存储配置项的信息, 主要用于config配置项
        * dep_temp: 用于辅助config_dep存储相关信息
    '''
    def __init__(self, name, type, path) -> None:
        self.name = name
        self.type = type
        self.path = path

        self.kids = []

        self.detail = self.Gendetail()
        self.config_dep = self.Gendep()
        self.dep_temp = ConfigDepTemp()

    ######### function
    def set_name(self, name):
        self.name = name

    def set_type(self, type):
        self.type = type

    def set_detail_type(self, type):
        if len(self.detail.type) == 0:
            self.detail.type = type
            self.config_dep.type = type

    def set_path(self, path):
        self.path = path

    def Gendetail(self):
        if self.type == 'comment':
            return None
        elif self.type == 'config' or self.type == 'menuconfig':
            self.config_dep = ConfigDep()
            return Config(self.name, self.path)
        elif self.type == 'if':
            return If(self.path, self.name)
        elif self.type == 'menu':
            return Menu(self.path, self.name)
        elif self.type == 'choice':
            self.config_dep = ConfigDep()
            return Choice(self.path, self.name)

    def Gendep(self):
        if self.type == 'config' or self.type == 'menuconfig' \
                or self.type == 'choice' or self.type == 'menu'\
                or self.type == 'if':
            return ConfigDep()

    def set_help(self, value):
        self.detail.help = value

    def set_detail_value(self, target, value):
        if self.type != 'comment':
            self.detail.set_value(target, value)

    def set_config_group(self, value):
        self.detail.set_group(value)
