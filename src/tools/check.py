''' 通过给定检查逻辑实现对指定配置文件的检查功能

主函数为Checker(dep_path, config_path, file_path, save_file)
参数含义为: 
    * dep_path: 经过config_yacc抽取后的*_dep.json文件路径
    * config_path: 经过config_yacc抽取后的*_config.json文件路径
    * file_path: 需要检查的.config文件路径
    * save: 检查结果的路径信息

错误信息包括: 
    * 类型错误: type error, 配置项类型错误
    * 依赖不满足: depends error, 配置项未通过select启动且依赖不满足
    * 未找到配置项: lack config, 未在内核Kconfig文件中找到指定配置项
    * range未满足: range error, 
    * 取值未满足: restrict warming, 配置项取值未满足要求, 通常为default或imply关键字
    * 依赖风险: unmet dependence, 配置项通过select强制启动, 但是依赖未满足

父类配置项错误会影响当前子类配置项的判断, 可利用HAVE_CHECK进一步开发
'''
import re
import time

# import tools
import tools.check_lex as check_lex
import tools.utils as utils

HAVE_CHECK = {}
LAST_CONFIG = []  # (name, value)
ERROR_CONFIG_FLAG = []
ERROR_JSON = {}


def reset_GLOBAL():
    global HAVE_CHECK, LAST_CONFIG, ERROR_CONFIG_FLAG, ERROR_JSON
    HAVE_CHECK = {}
    LAST_CONFIG = []
    ERROR_CONFIG_FLAG = []
    ERROR_JSON = {}


def get_tokens(data):
    '''check_lex借助ply.lex实现的词法分析器
    将输入的data数据解析, 并返回list
    '''
    check_lex.lexer.input(data)
    result = []
    while True:
        tok = check_lex.lexer.token()
        if not tok:
            break
        result.append(tok)
    return result


class Error:
    ''' 整理错误信息, 最后打印到*_error.json中

    属性包括:
        * name: 配置项名称
        * path: 配置项存储路径
        * error: 存储具体的错误信息
        * value: 错误配置在配置文件(.config)中的具体取值
        * dep_value: 配置项的属性信息, 以及在配置文件的取值
    '''

    def __init__(self, parser, config_name, error, index=-1) -> None:
        self.name = config_name
        self.path = self.get_path(parser.CONFIG, config_name, index)
        self.error = [error]
        self.type = self.update_type(parser.CONFIG_DEP, config_name)
        self.value = parser.CONFIG_VALUE[config_name] \
                if parser.CONFIG_VALUE.get(config_name, None) is not None \
                else None
        self.dep_value = [self.handle_value(parser, index)]

    def update_type(self, CONFIG, config_name):
        if CONFIG.get(config_name, None) is not None:
            result = None
            for item in CONFIG[config_name]:
                result = item['type']
            return result
        else:
            return None

    def get_path(self, CONFIG, config_name, index):
        if CONFIG.get(config_name, None) is not None:
            path = CONFIG[config_name][index]['path']
            # path = []
            # for item in CONFIG[config_name]:
            #     # if item['path'] not in path:
            #         path.append(item['path'])
            return path
        else:
            return None

    def update_value(self, CONFIG_VALUE, line):
        words = get_tokens(line)
        result = ''
        for item in words:
            result += ' ' if len(result) > 0 else ''
            if item.type == 'WORD' and not re.fullmatch('-?[0-9]+', item.value) \
                    and re.fullmatch('[A-Z0-9_x]+', item.value):
                value = CONFIG_VALUE.get(item.value, 'n')
                result += item.value + ' {= ' + value + '}'
            else:
                result += item.value
        return result

    def handle_value(self, parser, index):
        if index == -1:
            return None
        config_dep = parser.CONFIG_DEP.get(self.name, None)
        result = {
            'rev_select': self.update_value(parser.CONFIG_VALUE, config_dep[index]['rev_select']),
            'depends': self.update_value(parser.CONFIG_VALUE, config_dep[index]['dep']),
            'restrict': self.update_value(parser.CONFIG_VALUE, config_dep[index]['restrict']),
        }
        return result


def add_error(parse, config_name, error_data, index = -1):
    global ERROR_JSON
    target = ERROR_JSON.get(config_name, None)
    if target and error_data not in target.error:
        target.error.append(error_data)
        target.dep_value.append(target.handle_value(index))
    else:
        node = Error(parse, config_name, error_data, index)
        ERROR_JSON[config_name] = node


def check_MODULES(parser):
    for item in parser.CONFIG_VALUE:
        if parser.CONFIG_VALUE[item] == 'm':
            if parser.CONFIG_VALUE['MODULES'] != 'y':
                add_error(parser, 'MODULES', \
                          'the configuration has tristate type, but MODULES is not enable')
            break


def check_type(config_type, value):
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


def value2num(value) -> int:
    '''按照Kconfig文档要求, 数字类按原值计算
    对于bool类型, y = 2,  m = 1,  n = 0
    其余类型全部为 0
    '''
    if isinstance(value, int):
        return value
    if re.fullmatch('-?[0-9]+', value):
        return int(value)
    elif value[0:2] == '0x':
        return int(value, 16)
    elif value == 'y':
        return 2
    elif value == 'm':
        return 1
    elif value == 'n':
        return 0
    return 0


def num2value(num) -> str:
    if num == 2:
        return 'y'
    elif num == 1:
        return 'm'
    else:
        return 'n'


def get_last_config_name():
    global LAST_CONFIG
    result = []
    for item in LAST_CONFIG:
        result.append(item[0])
    return result


def get_last_config_value():
    global LAST_CONFIG
    result = []
    for item in LAST_CONFIG:
        result.append(item[1])
    return result


def get_config_value(parser, word):
    '''在配置文件中查找配置项的取值
    若未出现则认为是n
    数字类型也返回string形式
    '''
    if isinstance(word, int):
        return str(word)
    if re.fullmatch('-?[0-9]+', word) or word[0:2] == '0x':
        return word
    if re.fullmatch('[A-Z0-9_x]+', word):
        if word in parser.CONFIG_VALUE:
            if word in get_last_config_name():
                return parser.CONFIG_VALUE[word]
            if HAVE_CHECK.get(word, None) is None:
                if parser.CONFIG_DEP.get(word, None) == None:
                    add_error(parser, word, "lack config")
                    return parser.CONFIG_VALUE[word]
                check_config(parser, word)
            return parser.CONFIG_VALUE[word]
        else:
            return 'n'
    else:
        return word


def check_bracket(parse, tokens, index):
    save = []
    temp = []
    index += 1
    while index < len(tokens):
        if tokens[index].value == '(':
            save.append(temp)
            temp = []
        elif tokens[index].value == ')':
            if len(save) == 0:
                index += 1
                break
            else:
                value = reduce(check_expr(parse, temp))
                temp = save.pop()
                temp += get_tokens(value)
        else:
            temp.append(tokens[index])
        index += 1
    return (reduce(check_expr(parse, temp)), index)


def handle_op(parse, tokens, index, value):
    if index < len(tokens):
        if tokens[index].value in ['=', '!=', '<', '<=', '>', '>=']:
            next = tokens[index + 1].value
            next = value2num(get_config_value(parse, next))
            value = value2num(get_config_value(parse, value))
            if tokens[index].value == '=':
                value = 'y' if value == next else 'n'
            elif tokens[index].value == '!=':
                value = 'y' if value != next else 'n'
            elif tokens[index].value == '<':
                value = 'y' if value < next else 'n'
            elif tokens[index].value == '<=':
                value = 'y' if value <= next else 'n'
            elif tokens[index].value == '>':
                value = 'y' if value > next else 'n'
            elif tokens[index].value == '>=':
                value = 'y' if value >= next else 'n'
            return (value, index + 2)
    return (value, index)


def get_bracket(parse, tokens, index) -> (bool, int):
    if index < len(tokens) and tokens[index].value == '[':
        index += 1
        save = []
        while index < len(tokens) and tokens[index].value != ']':
            save.append(tokens[index])
            index += 1
        index += 1
        if value2num(reduce(check_expr(parse, save))):
            return (True, index)
        else:
            return (False, index)
    return (True, index)


def handle_bracket(parse, tokens, index, value, stack):
    if index < len(tokens) and tokens[index].value == '[':
        (result, index) = get_bracket(parse, tokens, index)
        if result:
            stack.append(value)
        else:
            if len(stack) > 0:
                prev = stack.pop()
                if prev == '!' and len(stack) > 0:
                    stack.pop()
            else:
                stack.append('del_next')
    else:
        stack.append(value)
    return (stack, index)


def op2num(op):
    if op == '!': return 3
    elif op == '&&': return 2
    else: return 1


def infix2suffix(stack) -> list:
    result = []
    op = []
    for item in stack:
        if item in ['&&', '||', '!']:
            if len(op) == 0:
                op.append(item)
            else:
                while len(op) and op2num(op[-1]) >= op2num(item):
                    result.append(op.pop())
                op.append(item)
        else:
            result.append(item)
    while len(op):
        result.append(op.pop())
    return result


def reduce(stack) -> str:
    result = []
    index = 0
    while index < len(stack):
        if stack[index] == 'del_next':
            index += 1
        else:
            result.append(stack[index])
        index += 1
    stack = result
    if len(stack) == 0: return 'n'
    if len(stack) == 1: return stack[0]
    cal_stack = infix2suffix(stack)
    result = []
    for item in cal_stack:
        if item == '!':
            tmp = result.pop()
            result.append(num2value(2 - value2num(tmp)))
        elif item == '&&':
            right = result.pop()
            left = result.pop()
            result.append(num2value(min(value2num(left), value2num(right))))
        elif item == '||':
            right = result.pop()
            left = result.pop()
            result.append(num2value(max(value2num(left), value2num(right))))
        else:
            result.append(item)
    return result[0]


def check_expr(parse, tokens):
    stack = []  # 存储解析后表达式
    index = 0
    while index < len(tokens):
        if tokens[index].type in ['NOT', 'AND', 'OR']:
            stack.append(tokens[index].value)
            index += 1
        elif tokens[index].type == 'OPEN_PARENT':  # (
            (value, index) = check_bracket(parse, tokens, index)
            stack.append(value)
        elif tokens[index].type == 'WORD':
            value = get_config_value(parse, tokens[index].value)
            # 如果后跟不等式判断, 检查表达式是否成立
            (value, index) = handle_op(parse, tokens, index + 1, value)
            # 如果后跟if表达式, 检查表达式是否成立
            (stack, index) = handle_bracket(parse, tokens, index, value, stack)
        elif tokens[index].type == 'SP_WORD':
            value = 'y'
            # 如果后跟不等式判断, 检查表达式是否成立
            index += 1
            if index < len(tokens) and tokens[index].value in ['=', '!=', '<', '<=', '>', '>=']:
                index += 2
            if len(stack) > 0 and stack[len(stack) - 1] == '!':
                stack.append('n')
            else:
                stack.append('y')
    return stack


def check_select(parse, tokens):
    stack = check_expr(parse, tokens)
    if len(stack) == 1 and stack[0] == 'None' or not len(stack): return 'n'
    return reduce(stack)


def check_dep(parse, tokens):
    stack = check_expr(parse, tokens)
    if not len(stack): return 'y'
    return reduce(stack)


def check_restrict(parse, tokens, config_name, config_value, config_index):
    '''
    restrict表达式中, 格式通常为()[XXX], []内部if表达式形式多样, 需要全面考虑
    表达式内部不存在sp_word, 多出现在()或[]内部进行比较
    表达式内部若出现word[expr], 通常为imply语句
    '''
    stack = []  # 存储解析后表达式
    index = 0
    while index < len(tokens):
        if tokens[index].type in ['OR', 'NOT', 'AND']:
            stack.append(tokens[index].value)
            index += 1
        elif tokens[index].type == 'OPEN_PARENT':
            index += 1
            parent_index = 0
            temp = []
            while index < len(tokens):
                if tokens[index].value == '(':
                    parent_index += 1
                elif tokens[index].value == ')':
                    if parent_index == 0:
                        break
                    parent_index -= 1
                temp.append(tokens[index])
                index += 1
            index += 1
            if len(temp) == 1:
                if temp[0].type == 'WORD':
                    (result, index) = get_bracket(parse, tokens, index)
                    if result:
                        value = get_config_value(parse, temp[0].value)
                        config_value = get_config_value(parse, config_value)
                        if value != config_value:
                            stack.append('n')
                        else:
                            stack.append('y')
                    else:
                        stack.append('y')
                elif temp[0].type == 'SP_WORD':
                    (result, index) = get_bracket(parse, tokens, index)
                    stack.append('y')
                elif temp[0].type == 'QUOTE_WORD':
                    value = temp[0].value
                    if len(value) == 2:
                        value = 'y' if len(config_value) == 0 else 'n'
                    else:
                        value = 'y' if value == config_value else 'n'
                    (stack, index) = handle_bracket(parse, tokens, index, value, stack)
            elif len(temp) == 2:
                if temp[0].type == 'NOT' and (temp[1].type == 'WORD' or temp[1].type == 'SP_WORD'):
                    value = 'y' if config_value == reduce(check_expr(parse, temp)) else 'n'
                    (stack, index) = handle_bracket(parse, tokens, index, value, stack)
                elif temp[0].type == 'WORD' and temp[1].type == 'WORD':
                    (result, index) = get_bracket(parse, tokens, index)
                    if result:
                        left = value2num(get_config_value(parse, temp[0].value))
                        right = value2num(get_config_value(parse, temp[1].value))
                        config_value = value2num(get_config_value(parse, config_value))
                        if left <= config_value and config_value <= right:
                            pass
                        else:
                            add_error(parse, config_name, "range error", config_index)
                    stack.append('y')
            else:
                value = reduce(check_expr(parse, temp))
                (stack, index) = handle_bracket(parse, tokens, index, value, stack)
    if len(stack) == 0 or len(stack) == 1 and stack[0] == 'del_next':
        return True
    return True if value2num(reduce(stack)) else False


def check_config(parser, config_name):
    global HAVE_CHECK, LAST_CONFIG
    if parser.CONFIG_VALUE.get(config_name, None) == None \
            or parser.CONFIG_VALUE.get(config_name, None) == 'n':
        HAVE_CHECK[config_name] = True
        return
    config_value = parser.CONFIG_VALUE.get(config_name, 'n')
    LAST_CONFIG.append((config_name, config_value))
    if config_name in parser.CONFIG_VALUE:
        index = -1
        error_save = {
            'result' : None,
            'type error' : [],
            'unmet dependences' : [],
            'restrict warming' : [],
            'depends error' : []
        }
        for item in parser.CONFIG_DEP[config_name]:
            index += 1
            if not check_type(item['type'], config_value):
                HAVE_CHECK[config_name] = False
                error_save['type error'].append(index)
                continue
            select_tokens = get_tokens(item['rev_select'])
            dep_tokens = get_tokens(item['dep'])
            if len(select_tokens) and value2num(check_select(parser, select_tokens)):
                HAVE_CHECK[config_name] = True
                if len(item['dep']) and not value2num(check_dep(parser, dep_tokens)):
                    error_save['unmet dependences'].append(index)
                    continue
                elif len(error_save['unmet dependences']):
                    error_save['unmet dependences'].pop()
            elif len(dep_tokens) == 0 or value2num(check_dep(parser, dep_tokens)):
                restrict_tokens = get_tokens(item['restrict'])
                if len(error_save['depends error']):
                    error_save['depends error'].pop()
                if len(restrict_tokens) == 0 or \
                        check_restrict(parser, restrict_tokens, config_name, config_value, index):
                    HAVE_CHECK[config_name] = True
                    if len(error_save['restrict warming']):
                        error_save['restrict warming'].pop()
                else:
                    HAVE_CHECK[config_name] = False
                    error_save['restrict warming'].append(index)
            else:
                HAVE_CHECK[config_name] = False
                error_save['depends error'].append(index)
            if HAVE_CHECK[config_name]:
                break
        # 看error_save有无错误，有则填入
        if len(error_save['depends error']):
            add_error(parser, config_name, "depends error", error_save['depends error'][0])
        if len(error_save['restrict warming']):  
            add_error(parser, config_name, "restrict warming", error_save['restrict warming'][0])
        if len(error_save['unmet dependences']):
            add_error(parser, config_name, "unmet dependences", error_save['unmet dependences'][0])
    else:
        # 如果未检查且不在.config文件, 默认是正确的
        HAVE_CHECK[config_name] = True
    error_save['result'] = True if HAVE_CHECK[config_name] else False
    LAST_CONFIG.pop()
    return


def Checker(parser, save_file):
    global HAVE_CHECK
    begin = time.time()
    check_MODULES(parser)
    for name in parser.CONFIG_VALUE:
        if parser.CONFIG_VALUE[name] == 'n':
            HAVE_CHECK[name] = True
            continue
        elif parser.CONFIG_DEP.get(name, None) == None:
            add_error(parser, name, "lack config")
            continue
        check_config(parser, name)
    cost = time.time() - begin
    print("\rCheck time\t\t{}".format(str(cost)))
    global ERROR_JSON
    if len(ERROR_JSON) > 0:
        print("{:<40}".format("[Prepare write check result]") + "file => " + save_file)
        utils.write_json_file(ERROR_JSON, save_file)
    else:
        print("{:<40}".format("[Check end]") + "The configuration is right !")

