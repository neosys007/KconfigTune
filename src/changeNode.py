'''
TODO
* restart_config中 如果出现询问int值 可能会死循环？

* open_config_min
* open_expr
* get_bool_value
* get_num_value
* get_string_value
* get_value
'''

import re
import subprocess
import sys
import os
import pexpect


import main
import tools
import tools.check_lex as check_lex
import tools.utils as utils

def check_type(config_type, value) -> bool:
    if value == '' or value == 'n':
        return True
    if config_type == 'bool' and (value == 'y' or value == 'n'):
        return True
    elif config_type == 'tristate' and (value == 'y' or value == 'm' or value == 'n'):
        return True
    elif config_type == 'int' and re.fullmatch('-?[0-9]+', value):
        return True
    elif config_type == 'hex' and (re.fullmatch('0', value) or value[:2] == '0x'):
        return True
    elif config_type == 'string':
        return True
    return False

def get_config_value(CONFIG_VALUE, word) -> str:
    '''
    在配置文件中查找配置项的取值
    若未出现则认为是n
    数字类型也返回string形式
    不对配置项进行检查
    仅获取在.config中的结果
    '''
    if isinstance(word, int):
        return str(word)
    if re.fullmatch('-?[0-9]+', word) or word[0:2] == '0x':
        return word
    if re.fullmatch('[A-Z0-9_x]+', word):
        return CONFIG_VALUE[word] if word in CONFIG_VALUE else 'n'
    else:
        return word

def get_tokens(data) -> list:
    """
    将字符串传唤为list
    内部类型为Token(ply包)
    in: str
    out: list
    """
    check_lex.lexer.input(data)
    result = []
    while True:
        tok = check_lex.lexer.token()
        if not tok:
            break
        result.append(tok)
    return result

def get_op(CONFIG_VALUE, tokens, index) -> (str, str, int):
    """
    检查tokens[index]是否为比较符号
    如果是, 将右侧类型生成Node
    返回op类型和Node类
    """
    if index < len(tokens) and tokens[index].value in ['=', '!=', '<', '<=', '>', '>=']:
        op = tokens[index].value
        next = tokens[index + 1].value
        index += 2
        nextValue = get_config_value(CONFIG_VALUE, next)
        if nextValue != next:
            node = Node('CONFIG', next, nextValue)
            return (op, node, index)
        else:
            return (op, next, index)
    return (None, None, index)

def get_choice_data(line) -> (str, str):
    """
    拆分完整依赖链条, 将choice组信息拆分
    返回dep信息和choice信息
    """
    pattern = re.compile(r"\{\{.*\}\}")
    result = pattern.search(line)
    if result:
        value = result.group()
        target_right = value + ' && '
        target_left = ' && ' + value
        if line.count(target_right):
            line = line.replace(target_right, '')
        elif line.count(target_left):
            line = line.replace(target_left, '')
        else:
            line = line.replace(value, '')
        value = value.replace('{{', '').replace('}}', '')
        print("value is " + value)
        return(line, value)
    else:
        return (line, "")  

def restart_config(AllChange, OSPath, arch) -> None:
    """
    调用restart config过程, 检查修改结果符合内核检查要求

    目前发现存在永远无法修改的情况，比如
    config AAA
        bool
    没有其他配置项影响的情况下, 默认配置项只能为n
    """
    match_list = [
        pexpect.EOF,
        pexpect.TIMEOUT,
        "# configuration written to .config",
        "choice\[.*\]",
        "(NEW)"
    ]
    target = {}
    for item, value in AllChange.items():
        target[item] = value[0]
        for inner, inner_value in value[1].items():
            target[inner] = inner_value
    AllChange = target
    tmp = [item + ".*(NEW) " for item in list(AllChange.keys())]
    tmp.sort(reverse=True)
    match_list.extend(tmp)

    with pexpect.spawn("make ARCH=" + arch +" oldconfig", cwd=OSPath, encoding='utf-8', logfile=sys.stdout) as oldconfig:
        while True:
            index = oldconfig.expect(match_list, timeout=10)
            # print("match " + str(index))
            if index == 0 or index == 2:
                break
            elif index == 1 or index == 3 or index == 4:
                oldconfig.sendline()
            else:
                oldconfig.sendline(AllChange[match_list[index][0:-8]][0])

def update_value(parser, name, value) -> dict:
    """
    将name配置项的值更新在CONFIG_VALUE中
    """
    parser.CONFIG_VALUE[name] = value
    if parser.OSPath[-1] == '/':
        ConfigScript = parser.OSPath + "scripts/config" 
    else:
        ConfigScript = parser.OSPath + "/scripts/config"
    cmd = ConfigScript + ' '
    if value == 'y':
        cmd += '--enable ' + name
    elif value == 'n':
        cmd += '--disable ' + name
    elif value == 'm':
        cmd += '--module ' + name
    elif value.startswith("0x") or re.fullmatch("[+-]?\\d+", value) is not None:
        cmd += '--set-val ' + name + ' ' + value
    else:
        cmd += '--set-str ' + name + ' ' + value
    p = subprocess.Popen(cmd, cwd = parser.OSPath, shell=True, stdin=subprocess.PIPE)
    p.wait()
    return parser

def infix2postfix(CONFIG_VALUE, tokens) -> list:
    """
    将tokens的中缀转为后缀
    list中为Tokens
    """
    prec = {"OPEN_PARENT": 0, "OR": 1, "AND": 1, "NOT": 2}
    stack = []
    postfix = []
    index = 0
    while index < len(tokens):
        if tokens[index].type == 'WORD':
            nodeName = tokens[index].value
            nodeValue = get_config_value(CONFIG_VALUE, nodeName)
            index += 1
            (op, next, index) = get_op(CONFIG_VALUE, tokens, index)
            node = Node("CONFIG", nodeName, nodeValue, op, next)
            postfix.append(node)
        elif tokens[index].type == 'SP_WORD':
            # 如果后跟不等式判断, 检查表达式是否成立
            index += 1
            if index < len(tokens) and tokens[index].value in ['=', '!=', '<', '<=', '>', '>=']:
                index += 2
            postfix.append(Node("CONFIG", "SP_WORD", 'y'))
        elif tokens[index].type == "OPEN_PARENT":
            stack.append(tokens[index])
            index += 1
        elif tokens[index].type == "CLOSE_PARENT":
            while stack and stack[-1].type != "OPEN_PARENT":
                postfix.append(stack.pop())
            stack.pop()
            index += 1
        else:
            while stack and prec[stack[-1].type] >= prec[tokens[index].type]:
                postfix.append(stack.pop())
            stack.append(Node(tokens[index].type))
            index += 1
    while stack:
        postfix.append(stack.pop())
    return postfix

def checkChangeResult(parser, conflict) -> None:
    """
    经内核检查程序后
    对比是否有与需求不一致的配置项
    结果保存在文件内
    """
    if len(conflict) > 0:
        writeLog(parser.OSPath, "\n\n冲突配置项: 以下配置项或其依赖项与当前架构无关")
        for item in parser.TargetDict:
            if item in conflict:
                writeLog(parser.OSPath, item)
            elif item not in parser.CONFIG_VALUE or parser.TargetDict[item] != parser.CONFIG_VALUE[item]:
                print("配置项 " + item + " 修改失败")
                # printConfigDebug(parser, item)
        writeLog(parser.OSPath, "\n\n")

def writeLog(OSPath, string) -> None:
    """
    将string信息保存在 OSPath + "/.changeNode" 文件内
    """
    logFile = OSPath + "/.changeNode" if OSPath[-1] == '/' else OSPath + "/.changeNode"
    with open(logFile, 'a+') as file:
        file.write(string + '\n')

class Node:
    def __init__(self, type, name=None, value=None, left=None, right=None) -> None:
        # 如果type是not 右值存left
        if left != None:
            if left == '=':
                self.value = 'y' if value == right else 'n'
            elif left == '!=':
                self.value = 'y' if value != right else 'n'
            elif left == '<':
                self.value = 'y' if value < right else 'n'
            elif left == '<=':
                self.value = 'y' if value <= right else 'n'
            elif left == '>':
                self.value = 'y' if value > right else 'n'
            elif left == '>=':
                self.value = 'y' if value >= right else 'n'
        elif value != 'n':
            self.value = 'y'
        else:
            self.value = 'n'
        self.type = type
        self.name = name
        self.left = left    # 也可以是op
        self.right = right  # 也可以是op的右值

    def addEdge(self, left, right = None) -> None:
        self.left = left
        self.right = right

def printConfigDep(parser) -> None:
    for itemName, (itemValue, itemDict) in parser.AllChange.items():
        dep_line = itemName + ": " + itemValue + "\n"
        dep_line += "\tdep config =>\n"
        for subItemName, subItemValue in itemDict.items():
            dep_line += "\t\t" + subItemName + " : " + subItemValue + "\n"
        dep_line += "\n"

        parser.logger.debug(dep_line)

def get_expr_if_right(parser, resList) -> list:
    """
    获取表达式中的if
    检查if成立中对应的expr
    如果没有if成立, 返回第一个expr和if表达式

    能否优化策略？
    """
    if len(resList) == 0: 
        return None
    for line in resList:
        result = []
        res = line.split(" if ")
        if len(res) > 1:
            res = tools.check_dep(parser, res[1]) # bug?
            if res == 'y' and res[0] != "SP_WORD":
                result.append(res[0])
            else:
                continue
        else:
            if res[0] != 'n':
                result.append(res[0])
        return result

def check_op(left, op, right) -> bool:
    # TODO: bug ymn -> 210
    if op == '=':
        return left == right
    elif op == '!=':
        return left != right
    elif op == '>':
        return left > right
    elif op == '>=':
        return left >= right
    elif op == '<':
        return left < right
    elif op == '<=':
        return left <= right
    return False

def split_if(line) -> (str, str):
    """
    拆分str
    expr if expr => (expr, expr)
                 => (expr, "")
                 => ("", "")
    """
    if " if " in line:
        (default, if_expr) = line.split( " if ")
    else:
        default = line
        if_expr = ""
    return (default, if_expr)

def open_expr(postfix, parser) -> (bool, dict, dict):
    nowChange = {}
    stack = []
    openError = [] # 保存无法打开的配置项
    for node in postfix:
        if node.type == 'CONFIG':
            stack.append(node)
        elif node.type == 'NOT':
            prev = stack.pop()
            (prev.left, prev.right) = (node, None)
            prev.value = 'y' if prev.value == 'n' else 'n'
            stack.append(prev)
        else:
            left = stack.pop()
            leftValue = True if left.value == 'y' else False
            right = stack.pop()
            rightValue = True if right.value == 'y' else False
            if node.type == 'AND':
                if leftValue and rightValue:
                    stack.append(left)
                else: # 可能有左右都不是当前arch应该出现的情况
                    nodes = [left, right]
                    for tmp in nodes:
                        if tmp.value == 'n':
                            (tmp.value, tmpList) = get_value(parser, tmp)
                            if tmp.value:
                                nowChange.update({tmp.name : tmp.value})
                                nowChange.update(tmpList)
                            else:
                                if tmp.name not in openError:
                                    openError.append(tmp.name)
                    if left.value is None or right.value is None:
                        tmp = left if left.value is None else right
                        tmp.value = 'n'
                        stack.append(tmp)
                    else:
                        stack.append(right)
            elif node.type == 'OR':
                if leftValue or rightValue:
                    tmp = left if leftValue else right
                    stack.append(tmp)
                else:  # 比较左值和右值 选择改动最小的
                    nodes = [left, right]
                    tmpLists = []
                    for tmp in nodes:
                        (tmp.value, tmpList) = get_value(parser, tmp)
                        tmpLists.append(tmpList)
                    minLen = float("inf")
                    minNode = None
                    for tmp, tmpList in zip(nodes, tmpLists):
                        if tmp.value is not None and tmp.value != 'n':
                            if len(tmpList) < minLen:
                                minLen = len(tmpList)
                                minNode = tmp
                                minNodeList = tmpList
                        # else:
                        #     if tmp.name not in openError:
                        #         openError.append(tmp.name)
                    if minNode:
                        stack.append(minNode)
                        nowChange.update({minNode.name : minNode.value})
                        nowChange.update(minNodeList)
                    elif left.value is None and right.value is None:
                        stack.append(right)
                    else: raise # 不应该出现这种情况 debug
            else: raise # 解析错误

    if len(stack) == 1:
        if (stack[0].value == 'n'):
            return (False, nowChange, openError)
    elif len(stack) > 1: raise # 解析错误
    return (True, nowChange, openError) # openError是否还会有值？

def get_dict_mid(dictionary) -> (str, dict):
    """
    获取dict中数量最小的
    """
    min_str = None
    mid_dict = {}
    min_len = float('inf')
    for item in dictionary:
        for key, value in item.items():
            if len(value) < min_len:
                min_str = key
                min_len = len(value)
                mid_dict = value
    return min_str, mid_dict

def get_bool_value(parser, symbol, op, right, defaultList) -> (str, list):
    op_map = {
        '=': 'y' if right == 'y' else 'n',
        '!=': 'n' if right == 'y' else 'y',
        '>' : 'y',
        '>=': 'y',
        '<' : 'n',
        '<=': 'n'
    }

    if len(defaultList) == 0 and op is None and right is None:
        return ('y', [])
    elif len(defaultList) == 0 and op == 'NOT' and right is None:
        pass
    elif len(defaultList) == 0 and op is not None and right is not None:
        if op in op_map:
            res = op_map[op]
        else: raise
        return (res, [])
    
    changeList = []
    for line in defaultList:
        change_list = {}
        (default, if_expr) = split_if(line)
        # 能否修改if_expr 与 修改结果
        postfix = infix2postfix(parser.CONFIG_VALUE, get_tokens(if_expr))
        (res_if_expr, if_open_change, openError) = open_expr(postfix, parser)
        default_value = tools.check_dep(parser, default)
            
        if op in op_map:
            # 检查default是否符合op和right的要求，如果符合检查if_expr是否成立，不成立修改
            if check_op(default_value, op, right):
                if res_if_expr:
                    change_list.update(if_open_change)
                else: # 无法修改if_expr
                    raise
            else:
                # 修改default使其符合op和right的要求
                raise
        elif op is None and right is None:
            if default_value == 'n':
                (minChange, res) = open_config_min(parser, default, 'y')
                if res:
                    change_list.update(minChange)
                    change_list.update({default : 'y'})
                    default_value = 'y'
                else: # 修改失败
                    continue
            if default_value != 'n':
                if res_if_expr:
                    change_list.update(if_open_change)
                else: # 无法修改if_expr
                    continue
            else:
                # 修改default使其符合op和right的要求
                # handle_config
                raise
        elif op == 'NOT' and right is None:
            # TODO 如何处理？
            raise
        else: raise # op 和 right 有问题
        changeList.append({default_value : change_list})
    if len(changeList):
        (min_str, min_dict) = get_dict_mid(changeList)
        return (min_str, min_dict)
    else:
        return ('y', [])

def get_num_value(parser, symbol, op, right, defaultList) -> (str, list):
    # range主要是限制
    # 如果range成立，检查range，不成立则返回default或者0
    # 遍历defaultList，如果成立，检查是否合适，不成立则修改依赖使其成立，检查是否合适
    Range = get_expr_if_right(parser, symbol.detail.value['range'])
    if Range is not None:
        RangeMin = Range.split(' ')[0]
        RangeMax = Range.split(' ')[1]
    
    changeList = []
    for line in defaultList:
        change_list = {}
        (default, if_expr) = split_if(line)
        # TODO
        # 检查default是否符合op和right的要求以及range要求
        # 如果符合检查if_expr是否成立，不成立修改
        raise
    
    if len(changeList):
        (min_str, min_dict) = get_dict_mid(changeList)
        return (min_str, min_dict)

    # 如果default都不行，且op和right存在, 遍历range，选择合适的
    if Range is not None and op is not None and right is not None:
        for num in range(RangeMin, RangeMax):
            if check_op(num, op, right):
                res = str(num) if symbol.detail.type == 'int' else str(hex(num))
                return (res, [])

    # 如果default不行且没有op和right
    if Range is not None:
        res = str(int(RangeMin)) if symbol.detail.type == 'int' else str(hex(RangeMin))
    else:
        res = '0x0' if symbol.detail.type == 'hex' else '0'
    return (res, [])

def get_string_value(parser, op, right, defaultList) -> (str, list):
    # 一般是 = 或 != 
    # 遍历defaultList，如果成立，检查是否合适，不成立则修改依赖使其成立，检查是否合适
    if len(defaultList) == 0 and op is None and right is None:
        return ""
    changeList = [] # res : {} 要修改的值
    for line in defaultList:
        change_list = {}
        (default, if_expr) = split_if(line)
        if op is not None and right is not None:
            if op not in ["=", "!="]: raise
            res = tools.check_dep(parser, if_expr)
            if check_op(tools.check_dep(parser, default), op, right):
                if res == 'y':
                    return (default, {})
                elif res == 'n':
                    # 尝试修改if_expr
                    postfix = infix2postfix(parser.CONFIG_VALUE, get_tokens(if_expr))
                    (res_if_expr, nowChange, openError) = open_expr(postfix, parser)
                    if res_if_expr == 'y':
                        changeList.append('y', nowChange)
            else:
                # 能否修改default使其符合要求？
                raise
    if len(changeList):
        (min_str, min_dict) = (min_str, min_dict) = get_dict_mid(changeList)
        return (min_str, min_dict)
    else:
        return ("", [])

def get_value(parser, node) -> (str, dict):
    '''
    目前都是用于openConfig
    获取最优解时 传回最优解需要修改的dict

    Kconfig取值计算要求
        反向依赖强制赋值
        直接依赖成立的时候查看default

    如果op和right都是None
        bool、tristate => 查看default 并检查是否合理 不合理则修改
        int、hex => 查看default 和range 并检查是否合理 不合理则修改
        string => 查看default 并检查是否合理 不合理则修改
    
    返回 (str, list)
    str为node要修改的值, None表示与架构无关
    list为为了适配node需要修改的其他值
    '''
    if node.name not in parser.CONFIG_DEP:
        return (None, [])
    
    if node.left is None:
        op = None
    elif isinstance(node.left, str):
        op = node.left
    else:
        op = node.left.type
    right = node.right

    changeList = []
    # 遍历，检查依赖是否成立，如果不成立，尝试修复依赖，并记录最小修改值
    for index in range(0, len(parser.KconfigDict[node.name])):
        symbol = parser.KconfigDict[node.name][index]
        select = tools.check_select(parser, symbol.config_dep.rev_select)
        defaultList = symbol.detail.value['default']
        if select != 'n':
            return (select, [])
        change_list = {}
        if tools.check_dep(parser, parser.CONFIG_DEP[node.name][index]['dep']) == 'n':
            # 获取打开配置项需要修改的配置项
            # 结果写入change_list
            postfix = infix2postfix(parser.CONFIG_VALUE, get_tokens(parser.CONFIG_DEP[node.name][index]['dep']))
            (res_dep, dep_open_change, openError) = open_expr(postfix, parser)
            if res_dep:
                change_list.update(dep_open_change)
            else:
                continue
        if symbol.detail.type == 'bool' or symbol.detail.type == 'tristate':
            (res, tmp_list) = get_bool_value(parser, symbol, op, right, defaultList)
        elif symbol.detail.type == 'int' or symbol.detail.type == 'hex':
            (res, tmp_list) = get_num_value(parser, symbol, op, right, defaultList) # default bug
        elif symbol.detail.type == 'string':
            (res, tmp_list) = get_string_value(parser, op, right, defaultList) # default bug
        change_list.update(tmp_list)
        changeList.append({res : change_list})
    # changeList中选择修改最小的
    if len(changeList):
        (min_str, min_dict) = (min_str, min_dict) = get_dict_mid(changeList)
        return (min_str, min_dict)
    else:
        # 没有合适配置 （直接依赖不成立或无法打开）
        return ('n', {})

# Allchange = {name : (value , {})}
def check_conflict(parser, nodeName, nodeValue) -> bool:
    if nodeValue is None: # 等待赋值，无须检查
        return True
    for itemName, (itemValue, itemDict) in parser.AllChange.items():
        if nodeName == itemName:
            if nodeValue == itemValue:
                return False
            else:
                writeLog(parser.OSPath, "配置项{%s}修改需求存在冲突" % nodeName)
                return True
        elif nodeName in itemDict.keys():
            if itemDict[nodeName] == nodeValue:
                return False
            else:
                writeLog(parser.OSPath, "配置项上游存在冲突 => ")
                writeLog(parser.OSPath, "{0} 配置项出现在 {1} 的依赖中".format(nodeName, itemName))
                return True
    return False

# def change_choice_config(parser, choiceLine, targetName, flag) -> dict:
#     # TODO: 修改choice，使目标配置项(true -> 成立 false -> 不成立)
#     tokens = get_tokens(choiceLine)
#     print("in change choiceLine" + choiceLine)
#     minChange = {}
#     for index in range(0, len(tokens)):
#         if tokens[index].type == 'WORD':
#             action_map = {
#                 (True, True): lambda: open_config_min(parser, tokens[index].value, 'y'),
#                 (True, False): lambda: close_config_min(parser, tokens[index].value),
#                 (False, True): lambda: close_config_min(parser, tokens[index].value),
#                 (False, False): lambda: open_config_min(parser, tokens[index].value, 'y')
#             }
#             key = (flag, tokens[index].value == targetName)
#             if key not in action_map:
#                 print(f"Error: {key} not found in action_map!")
#                 continue  # 避免程序崩溃
#             # (minChange, _) = action_map[(flag, tokens[index].value == targetName)]()
#             result = action_map[key]()  # 执行对应的修改操作
#             if isinstance(result, dict):  # 确保返回值是字典
#                 minChange.update(result)  # 累积修改
#             else:
#                 print(f"Warning: Unexpected return type {type(result)} from {action_map[key]}")
#     return minChange

def change_choice_config(parser, choiceLine, targetName, flag, visited=None) -> dict:
    if visited is None:
        visited = set()  # 记录已修改的变量，防止死循环
    
    tokens = get_tokens(choiceLine)
    print("in change choiceLine: " + choiceLine)

    postfix = infix2postfix(parser.CONFIG_VALUE, tokens)
    if not postfix:
        print("Error: Failed to parse choiceLine into postfix")
        return {}  # 解析失败直接返回，防止 stack 为空

    minChange = {}
    stack = []

    for node in postfix:
        if node.type == 'CONFIG':
            if node.value in visited:
                continue  # 跳过已修改的变量，防止死循环

            key = (flag, node.value == targetName)
            action_map = {
                (True, True): lambda: open_config_min(parser, node.value, 'y'),
                (True, False): lambda: close_config_min(parser, node.value),
                (False, True): lambda: close_config_min(parser, node.value),
                (False, False): lambda: open_config_min(parser, node.value, 'y')
            }

            if key in action_map:
                result = action_map[key]()
                if isinstance(result, dict):
                    minChange.update(result)
                    visited.add(node.value)  # 记录已修改变量

        elif node.type == 'NOT':
            if not stack:
                print("Error: Stack is empty before NOT operation")
                continue  # 防止 stack.pop() 抛出异常

            prev = stack.pop()
            prev.value = 'n' if prev.value == 'y' else 'y'
            stack.append(prev)

        elif node.type in ('AND', 'OR'):
            if len(stack) < 2:
                print(f"Error: Stack has insufficient elements ({len(stack)}) before {node.type}")
                continue  # 防止 stack.pop() 抛出异常

            right = stack.pop()
            left = stack.pop()

            if node.type == 'AND':
                if left.value == 'y' and right.value == 'y':
                    minChange[left.name] = 'n'
                    minChange[right.name] = 'n'
            elif node.type == 'OR':
                if left.value == 'n' and right.value == 'n':
                    minChange[left.name] = 'y'
                    minChange[right.name] = 'y'

    return minChange


def open_config_min(parser, nodeName, nodeValue) -> (dict, bool):
    # return bool (True, 修改成功； False, 修改失败； None, 与架构冲突)
    # nodeValue -> None, 需要赋值
    if nodeValue is None: 
        raise # 生成Node() 并 get_value()
    if nodeName not in parser.KconfigDict:
        return ({}, None)
    elif check_type(parser.KconfigDict[nodeName][0].type, nodeValue):
        writeLog("type error => config " + nodeName + '\n')
        return ({}, False)
    elif check_conflict(parser, nodeName, nodeValue):
        return ({}, None)
    
    saveChange = [] # 多个配置项保存修改数量
    openError = [] # 保存无法打开的配置项
    for item in parser.KconfigDict[nodeName]:
        (configDep, choiceLine) = get_choice_data(item.config_dep.dep)
        print("in open choiceLine is" +choiceLine)
        nowChange = change_choice_config(parser, choiceLine, nodeName, True)
        if len(configDep) != 0:
            tokens = get_tokens(configDep)
            postfix = infix2postfix(parser.CONFIG_VALUE, tokens)
            (res, nowChange, openError) = open_expr(postfix, parser)
            if not res and len(openError):
                errorLog = ""
                for item in openError:
                    errorLog += item + " "
                writeLog(parser.OSPath,
                        "在打开 " + nodeName + "时，以下配置项可能存在问题（与架构无关）\n\t" + errorLog)
                return ({}, False)
        nowChange.update({nodeName : nodeValue})
        saveChange.append(nowChange)
    if len(saveChange) == 0:
        return ({nodeName : nodeValue}, True)
    return (min(saveChange, key=len), True)

# def close_config_min(parser, nodeName) -> (dict, bool):
#     # 检查反向依赖 是否有无法关闭的情况
#     # TODO: 检查choice数据，是否符合
#     # return bool (True, 修改成功； False, 修改失败； None, 与架构冲突)
#     if check_conflict(parser, nodeName, 'n'):
#         return ({}, None)
#     saveChange = []
#     history = ""
#     change_history = "xxxx"
#     # for item in parser.KconfigDict[nodeName]:
#     #     print("choiceLine is" + item.config_dep.dep)
#     for item in parser.KconfigDict[nodeName]:
#         if item.config_dep.dep == "":
#             print("choiceLine is null")
#             continue
#         (_, choiceLine) = get_choice_data(item.config_dep.dep)
#         # if choiceLine == "":
#         #     print("choiceLine is null")
#         #     continue
#         print("in close choiceLine is " + choiceLine)
#         if choiceLine == change_history:
#             break
#         change_history = choiceLine
#         changeDict = change_choice_config(parser, choiceLine, nodeName, False)
#         revSelect = item.config_dep.rev_select
#         tokens = get_tokens(revSelect)
#         postfix = infix2postfix(parser.CONFIG_VALUE, tokens)
#         result = []
#         for node in postfix:
#             if node.type == 'CONFIG':
#                 result.append(node)
#             elif node.type == 'NOT':
#                 prev = result.pop()
#                 prev.left = node
#                 prev.value = True if prev.value is False else False
#                 result.append(prev)
#             else:
#                 left = result.pop()
#                 right = result.pop()
#                 if node.type == 'AND' or node.type == 'OR':
#                     if left.value:
#                         changeDict.update({left.name: 'n'})
#                     if right.value:
#                         changeDict.update({right.name: 'n'})
#         changeDict[nodeName] = 'n'
#         saveChange.append(changeDict)
#     return (min(saveChange, key=len), True)

def close_config_min(parser, nodeName) -> (dict, bool):
    """尝试关闭 `nodeName` 并最小化配置修改"""

    # 1. 检查是否与架构冲突
    if check_conflict(parser, nodeName, 'n'):
        return ({}, None)
    if nodeName not in parser.KconfigDict:
        print(f"Error: nodeName '{nodeName}' not found in parser.KconfigDict!")
        print(f"Available keys: {list(parser.KconfigDict.keys())}")
        return ({}, None)
        
    saveChange = []
    processed_choices = set()  # 记录已处理的 choiceLine
    max_iterations = 100  # 防止死循环
    iteration = 0
    print("nodeName is" + nodeName)
    for item in parser.KconfigDict[nodeName]:
        if not item.config_dep.dep:  # 为空跳过
            print("choiceLine is null")
            continue

        _, choiceLine = get_choice_data(item.config_dep.dep)
        print(f"Iteration {iteration}: Processing choiceLine: {choiceLine}")

        if choiceLine in processed_choices:
            print("Detected repeated choiceLine, exiting loop.")
            break  # 防止死循环
        processed_choices.add(choiceLine)

        # 2. 修改配置
        changeDict = change_choice_config(parser, choiceLine, nodeName, False)

        # 检查 change_choice_config 是否真正修改了 parser.KconfigDict[nodeName]
        if changeDict is None:
            print("Warning: No change detected in parser.KconfigDict[nodeName]!")
            break

        # 3. 解析 revSelect 依赖关系
        revSelect = item.config_dep.rev_select
        tokens = get_tokens(revSelect)
        postfix = infix2postfix(parser.CONFIG_VALUE, tokens)

        result = []
        for node in postfix:
            if node.type == 'CONFIG':
                result.append(node)
            elif node.type == 'NOT':
                prev = result.pop()
                prev.left = node
                prev.value = not prev.value  # 取反
                result.append(prev)
            else:
                right = result.pop()
                left = result.pop()
                if node.type in {'AND', 'OR'}:
                    if left.value:
                        changeDict[left.name] = 'n'
                    if right.value:
                        changeDict[right.name] = 'n'

        changeDict[nodeName] = 'n'
        saveChange.append(changeDict)

        iteration += 1
        if iteration >= max_iterations:
            print("Reached max iterations, exiting to prevent infinite loop.")
            break  # 强制跳出防止死循环

    # 4. 返回最小变更
    return (min(saveChange, key=len) if saveChange else {}, True)


def handle_config(flag, parser, nodeName, nodeValue) -> (dict, dict, bool):
    # flag (True => openConfig, False => closeConfig)
    # return bool (True, 修改成功； False, 修改失败； None, 与架构冲突)
    for item in parser.KconfigDict[nodeName]:
        print("choiceLine is " + item.config_dep.dep)
    (minChange, res) = open_config_min(parser, nodeName, nodeValue) if flag else close_config_min(parser, nodeName)

    for (itemName, itemValue) in minChange.items():
        if check_conflict(parser, itemName, itemValue):
            return (None, parser, False)
    
    for item in minChange:
        parser = update_value(parser, item, minChange[item])
    parser.AllChange[nodeName] = (nodeValue, minChange)
    return ({nodeName : (nodeValue, minChange)}, parser, res)

def changeNode(OSPath, TargetDict, folder, arch, ConfigFile) -> None:
    '''
    TargetDict => 字典 保存需要修改的配置项与对应取值
    folder => pkl保存文件夹
    ConfigFile => .config文件路径
    '''
    parser = utils.Parser(folder, ConfigFile, OSPath, TargetDict)
    conflict = []
    for item in parser.KconfigDict:
        res = True
        if item in parser.TargetDict:
            if parser.TargetDict[item] == 'n':
                # 关闭配置项 关闭子配置项 关闭select
                (min_change, parser, res) = handle_config(False, parser, item, 'n')
            else:
                if item in parser.CONFIG_VALUE and parser.TargetDict[item] == parser.CONFIG_VALUE[item]:
                    pass
                else:
                    # 打开父类配置项
                    (min_change, parser, res) = handle_config(True, parser, item, parser.TargetDict[item])
        else:
            # 检查直接依赖是否成立 即是否需要关闭
            for _, (_, itemDict) in parser.AllChange.items():
                if item in itemDict and itemDict[item] == 'n':
                    (min_change, parser, res) = handle_config(False, parser, item, 'n')
        # res (None, 冲突; True, 成功; False, 失败)
        if res is None:
            conflict.append(item)

    printConfigDep(parser)
    if os.path.exists(parser.logger.log_file):
        print("More detail info => " + parser.logger.log_file)
    
    # restart_config(parser.AllChange, parser.OSPath, arch)
    
    # checkChangeResult(parser, conflict)

def cpConfig(origin, destination) -> None:
    cmd = "cp " + origin + " " + destination
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    p.wait()

if __name__ == '__main__':
    '''
    需要执行main将目标内核的kconfig解析
    folder指定解析后生成的文件夹路径
    target指定需要修改的配置项与希望的取值
    ConfigFile指定希望修改的.config文件
    '''

    OSPath="/home/guosy/Kconfig/OS/kernel-source/"
    tag="riscv"
    arch="riscv"
    ConfigFile=OSPath + ".config"
    output="./"
    display=True

    # p = subprocess.Popen("rm -rf linux-riscv", shell=True, stdin=subprocess.PIPE)
    # p.wait()

    # 还原.config文件
    cpConfig(OSPath + "origin.config", ConfigFile)

    main.umain(OSPath, tag, arch, ConfigFile, output, display)

    Folder = "./"+tag+"-" +arch
    target = {
        "NAMESPACES" : "y",
        "NET_NS" : "y",
        "PID_NS" : "y",
        "IPC_NS" : "y",
        "UTS_NS" : "y",
        "CGROUPS" : "y",
        "CGROUP_CPUACCT" : "y",
        "CGROUP_DEVICE" : "y",
        "CGROUP_FREEZER" : "y",
        "CGROUP_SCHED" : "y",
        "CPUSETS" : "y",
        "MEMCG" : "y",
        "KEYS" : "y",
        "VETH" : "y",
        "BRIDGE" : "y",
        "BRIDGE_NETFILTER" : "y",
        "NF_NAT_IPV4" : "y",
        "IP_NF_FILTER" : "y",
        "IP_NF_TARGET_MASQUERADE" : "y",
        "NETFILTER_XT_MATCH_ADDRTYPE" : "y",
        "NETFILTER_XT_MATCH_CONNTRACK" : "y",
        "NETFILTER_XT_MATCH_IPVS" : "y",
        "NETFILTER_XT_MARK" : "y",
        "IP_NF_NAT" : "y",
        "NF_NAT" : "y",
        "NF_NAT_NEEDED" : "y",
        "POSIX_MQUEUE" : "y",
        "CGROUP_BPF" : "y",
        "USER_NS" : "y",
        "SECCOMP" : "y",
        "SECCOMP_FILTER" : "y",
        "CGROUP_PIDS" : "y",
        "MEMCG_SWAP" : "y",
        "MEMCG_SWAP_ENABLED" : "y",
        "BLK_CGROUP" : "y",
        "BLK_DEV_THROTTLING" : "y",
        "IOSCHED_CFQ" : "y",
        "CFQ_GROUP_IOSCHED" : "y",
        "CGROUP_PERF" : "y",
        "CGROUP_HUGETLB" : "y",
        "NET_CLS_CGROUP" : "y",
        "CGROUP_NET_PRIO" : "y",
        "CFS_BANDWIDTH" : "y",
        "FAIR_GROUP_SCHED" : "y",
        "RT_GROUP_SCHED" : "y",
        "IP_NF_TARGET_REDIRECT" : "y",
        "IP_VS" : "y",
        "IP_VS_NFCT" : "y",
        "IP_VS_PROTO_TCP" : "y",
        "IP_VS_PROTO_UDP" : "y",
        "IP_VS_RR" : "y",
        "SECURITY_SELINUX" : "y",
        "SECURITY_APPARMOR" : "y",
        "EXT4_FS" : "y",
        "EXT4_FS_POSIX_ACL" : "y",
        "EXT4_FS_SECURITY" : "y",
        "INET_XFRM_MODE_TRANSPORT" : "y",
        "VXLAN" : "y",
        "BRIDGE_VLAN_FILTERING" : "y",
        "CRYPTO" : "y",
        "CRYPTO_AEAD" : "y",
        "CRYPTO_GCM" : "y",
        "CRYPTO_SEQIV" : "y",
        "CRYPTO_GHASH" : "y",
        "XFRM" : "y",
        "XFRM_USER" : "y",
        "XFRM_ALGO" : "y",
        "INET_ESP" : "y",
        "IPVLAN" : "y",
        "MACVLAN" : "y",
        "DUMMY" : "y",
        "NF_NAT_FTP" : "y",
        "NF_CONNTRACK_FTP" : "y",
        "NF_NAT_TFTP" : "y",
        "NF_CONNTRACK_TFTP" : "y",
        "AUFS_FS" : "y",
        "BTRFS_FS" : "y",
        "BTRFS_FS_POSIX_ACL" : "y",
        "BLK_DEV_DM" : "y",
        "DM_THIN_PROVISIONING" : "y",
        "OVERLAY_FS" : "y"
    }


    changeNode(OSPath, target, Folder, arch, ConfigFile)

    # checkChangeResult(utils.Parser(Folder, ConfigFile, OSPath, target), [])
    # p = subprocess.Popen("bash ./test.sh", shell=True, stdin=subprocess.PIPE)
