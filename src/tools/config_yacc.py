'''
语法分析代码, 借助ply.yacc包实现
语法识别完成后会生成两个文件, 其文件名格式均为, tag_arch
    * tag_arch_config.json: 
        文件会按照原语句格式进行存储, 存储数据结构为config_class.py的Config类
    * tag_arch_dep.json:
        文件按照自定义模型抽取配置信息, 存储数据结构为config_class.py的Config_dep类

主函数为ParseKconfig(file, config_file, dep_file, folder)
其参数含义是：
    * file: 预处理后的Kconfig文件路径
    * config_file: 解析识别后的tag_arch_config.json文件
    * dep_file: 解析识别后的tag_arch_dep.json
    * folder: 可指定结果保存路, 默认为当前路径下的result文件夹
'''

'''
TODO:
* 优化不可见表示
'''

import os
import re
import time

import ply.yacc as yacc
import tools.config_class as config_class
from tools.config_lex import *
import tools.utils as utils

DISPLAY = False
CONFIGDEP_FLAG = False


##########################       count       ##########################

check = {
    'depend_error'  : 0,
    'unmet_depend'  : 0,
    'type_error'    : 0,
    'value_warming' : 0,
    'range_error'   : 0,
    'choice'        : 0
}

def add_check_count(error_type) -> None:
    global check
    check[error_type] += 1

##########################      function      ##########################
def SetLastNode(node, type) -> config_class.Node:
    global LastNode
    LastNode = node

LastNodeName = ""

def NewNode(type, name) -> config_class.Node:
    global PATH_STACK, GROUP
    node = config_class.Node(name, type, get_stack_end(PATH_STACK))
    if type == 'config' or type == 'menuconfig' or type == 'choice':
        node = set_groupDep_configDep(node)
    if type != 'comment':
        Father = get_stack_end(GROUP)
        Father.node.kids.append(node)

    # bug config和menuconfig如何写入type？
    SetLastNode(node, type)
    return node

def SetLastNodeDep():
    # 处理上一个config的dep信息
    global LastNode, LastNodeName
    if LastNodeName == LastNode.name:
        return
    LastNodeName = LastNode.name
    GroupEnd = get_stack_end(GROUP) if len(GROUP) > 0 else None
    if LastNode.type == 'mainmenu':
        return
    # 组关系关键字在Group里填写
    elif LastNode.type == 'menu':
        # 保存visible
        
        pass
    elif LastNode.type == 'choice':
        dis = ""
        for item in GROUP[1:]:
            if item.node.detail is not None:
                if len(item.display) > 0:
                    dis = config_class.checkLineAnd(dis) + '( ' + item.display + ' )'
        if len(dis) > 0:
            default = GroupEnd.node.dep_temp.get_default() if GroupEnd else None
            for item in default:
                if len(item) > 1:
                    GroupEnd.node.config_dep.set_restrict(
                        item[0], '!(' + dis + ') && (' + item[1] + ')')
                else:
                    GroupEnd.node.config_dep.set_restrict(
                        item[0], '!(' + dis + ')')
    elif LastNode.type == 'config':
        if GroupEnd and GroupEnd.node.type == 'choice' and GroupEnd.node.detail.type == '':
            GroupEnd.node.set_detail_type(LastNode.detail.type)
        dis = ""
        for item in GROUP[1:]:
            if item.node.detail is not None:
                if len(item.display) > 0:
                    dis = config_class.checkLineAnd(dis) + '( ' + item.display + ' )'

        if len(LastNode.dep_temp.get_display()) > 0:
            dis = config_class.checkLineAnd(dis) + LastNode.dep_temp.get_display()
        else:
            prompt = 'y' if len(LastNode.detail.value['prompt']) else 'n'
            dis = config_class.checkLineAnd(dis) + prompt

        default = LastNode.dep_temp.get_default()
        if len(dis) > 0:
            for item in default:
                if len(item) > 1:
                    LastNode.config_dep.set_restrict(item[0], '!(' + dis + ') && (' + item[1] + ')')
                else:
                    LastNode.config_dep.set_restrict(item[0], '!(' + dis + ')')
    depends = LastNode.dep_temp.get_depends()
    if len(depends):
        result = ""
        for item in depends:
            result = config_class.checkLineAnd(result)
            result += item
        result = '{( ' + result + ' )}'
        LastNode.config_dep.set_depends(result)
        

def get_stack_end(target) -> str:
    try:
        result = target[-1]
    except Exception:
        # result = ''
        raise
    return result

def check_spword(char) -> str:
    if len(char) > 2 and char[0] == '"' and char[1] == '$':
        return "SP_WORD"
    elif len(char) > 1 and char[0] == '$':
        return "SP_WORD"


def set_groupDep_configDep(node) -> config_class.Node:
    '''
    在dep_json中保存上游组依赖信息
    '''
    result = []
    for item in GROUP:
        if item.node.detail is not None:
            result.append(item.node.detail)
    if node.type == 'config' or node.type == 'menuconfig':
        node.set_config_group(result)

    dep = ""
    for item in GROUP[1:]:
        if item.node.detail is not None:
            if len(item.node.dep_temp.get_depends()) > 0:
                # if item.node.detail.get_depends()[1] == '"' and get_stack_end(item.node.detail.get_depends()) == '"':
                #     dep = config_class.checkLineAnd(dep) + item.node.detail.get_depends()
                # else:
                    dep = config_class.checkLineAnd(dep) + item.node.detail.get_depends()

    node.config_dep.set_depends(dep)
    return node


##########################      yacc        ##########################
SELECT = {}  # {(father, kid) : [if_expr]}
IMPLY = {}  # {(father, kid) : [if_expr]}

def updateSelectImply(target, kid, if_expr):
    key = (LastNode.name, kid)
    if target.get(key, None):
        target[key].append(if_expr)
    else:
        target[key] = [if_expr]


DISPLAY_COUNT = -1
def testPrint(func, p):
    global DISPLAY_COUNT
    DISPLAY_COUNT += 1
    if DISPLAY_COUNT == 0 and DISPLAY:
        line = ""
        for item in p:
            if isinstance(item, str):
                if item != '\n':
                    line += item.replace('\n\t\t', ' ').replace('\t\t', '').replace('\n', '') + ' '
            elif isinstance(item, dict):
                line += item['string'] + ' '
        if len(line) > 0:
            if len(func + ' : ' + line) > 50:
                result = func + ' : ' + line
                result = result[:50] + '...'
            else:
                result = func + ' : ' + line
            rows, columns = os.popen('stty size', 'r').read().split()
            print(("\rparse => " + result).ljust(int(columns) - 30), end='\r', flush=True)
    else:
        DISPLAY_COUNT = -1 if DISPLAY_COUNT == 250 else DISPLAY_COUNT
        # DISPLAY_COUNT = -1

def handle_quote(target):
    if target == None:
        return target
    if len(target) >= 2 and (target[0] == '"' or target[0] == "'") and \
            (get_stack_end(target) == '"' or get_stack_end(target) == "'"):
        target = target[1:-1]
    return target


##########################      grammar     ##########################
PATH_STACK = []

root = config_class.Node("root", "root", 'root')
LastNode = root
AllNode = {}

GROUP = []


def reset_data():
    global root, LastNode, AllNode, ChoiceIndex, ChoiceIndexList, SELECT, IMPLY, PATH_STACK, GROUP, check, LastNodeName
    root = config_class.Node("root", "root", 'root')
    GROUP = [config_class.Group(root)]
    LastNode = root
    AllNode = {}
    ChoiceIndex = 0
    ChoiceIndexList = []
    SELECT = {}
    IMPLY = {}
    PATH_STACK = []
    check = {
        'depend_error'  : 0,
        'unmet_depend'  : 0,
        'type_error'    : 0,
        'value_warming' : 0,
        'range_error'   : 0,
        'choice'        : 0
    }
    LastNodeName = ""


precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'NOT'),
    ('left', 'OPEN_PARENT', 'CLOSE_PARENT'),
    ('left', 'GREATER_EQUAL'),
    ('left', 'LESS_EQUAL'),
    ('left', 'GREATER'),
    ('left', 'LESS'),
    ('left', 'UNEQUAL'),
    ('left', 'EQUAL'),
)


def p_input(p):
    '''
    input : input mainmenu_stmt
        | input config_stmt
        | input menu_stmt
        | input if_stmt
        | input choice_stmt
        | input groupend_stmt
        | input comment_stmt
        | input source_stmt
        | input type_stmt
        | input depends_stmt
        | input select_imply_stmt
        | input prompt_stmt
        | input default_stmt
        | input help_stmt
        | input range_stmt
        | input visible_stmt
        | input modules_stmt
        | input optional_stmt

        | input path_stmt
        | input endpath_stmt

        | empty
    '''
    # | input assignment_stmt
    testPrint("input", p)


def p_path_stmt(p):
    '''
    path_stmt : PATH QUOTE_WORD EOL
    '''
    p[2] = handle_quote(p[2])
    PATH_STACK.append(p[2])

    testPrint("path_stmt", p)


def p_endpath_stmt(p):
    '''
    endpath_stmt : ENDPATH EOL
    '''
    utils.stack_pop(PATH_STACK)

    testPrint("endpath_stmt", p)


def p_mainmenu_stmt(p):
    '''
    mainmenu_stmt : MAINMENU QUOTE_WORD EOL
    '''
    p[2] = handle_quote(p[2])
    global root
    root.set_type(p[1])
    root.set_name(p[2])
    root.set_path(get_stack_end(PATH_STACK))

    testPrint("mainmenu_stmt", p)


##########################      config       ##########################


def p_config_stmt(p):
    '''
    config_stmt : CONFIG WORD EOL
                | MENUCONFIG WORD EOL
    '''
    SetLastNodeDep()
    add_check_count('type_error')

    node = NewNode(p[1], p[2])

    # 记录需要打印数据，可能有重名config情况
    global AllNode
    item = AllNode.get(p[2], None)
    if not item:
        AllNode[p[2]] = [node]
    else:
        AllNode[p[2]].append(node)

    testPrint("config_stmt " + p[1], p)


def p_comment(p):
    '''
    comment_stmt : COMMENT QUOTE_WORD EOL
    '''
    SetLastNodeDep()

    comment = handle_quote(p[2])

    node = NewNode(p[1], comment)

    testPrint("comment_stmt", p)


##########################      group       ##########################
def p_menu(p):  # depends visible
    '''
    menu_stmt : MENU QUOTE_WORD EOL
    '''
    SetLastNodeDep()

    menuName = handle_quote(p[2])

    node = NewNode(p[1], menuName)

    GROUP.append(config_class.Group(node))

    testPrint("menu_stmt", p)


def p_if(p):
    '''
    if_stmt : IF expr EOL
    '''
    SetLastNodeDep()
    add_check_count('depend_error')
    
    node = NewNode(p[1], p[2]['string'])

    node.dep_temp.set_depends(p[2]['dep'])
    GROUP.append(config_class.Group(node))

    testPrint("if_stmt", p)


ChoiceIndex = 0
ChoiceIndexList = []


def p_choice(p):  # type prompt depends
    '''
    choice_stmt : CHOICE WORD EOL
                | CHOICE EOL
    '''
    SetLastNodeDep()

    global ChoiceIndex, ChoiceIndexList

    node = NewNode(p[1], 'choice' + str(ChoiceIndex))

    ChoiceIndexList.append(ChoiceIndex)
    ChoiceIndex += 1
    if p[2] != '\n':
        node.set_detail_value('prompt', p[2])

    SetLastNode(node, p[1])

    GROUP.append(config_class.Group(node))

    testPrint("choice_stmt", p)


def p_groupend_stmt(p):
    '''
    groupend_stmt : ENDMENU EOL
                | ENDIF EOL
                | ENDCHOICE EOL
    '''
    # 如果加上SetLastNodeDep()？
    target = utils.stack_pop(GROUP)
    if target.node.type == 'menu' and p[1] == 'endmenu':        
        pass
    elif target.node.type == 'if' and p[1] == 'endif':
        pass
    elif target.node.type == 'choice' and p[1] == 'endchoice':
        ####################################################
        #
        # 实现choice组内互斥放在depends依赖里判断
        #
        ####################################################
        choice = target.node.detail
        child = target.node.kids

        if choice.type == 'bool':
            add_check_count('choice')

            for item in child:
                choice_config = '{{( ' + item.name
                for tmp in child:
                    if tmp != item:
                        choice_config = config_class.checkLineAnd(choice_config)
                        choice_config += ' !' + tmp.name
                choice_config += ' )}}'
                item.config_dep.set_depends(choice_config)

        elif choice.type == 'tristate':
            pass
        else:
            print("warming, the choice group in {} has no type define! ".format(get_stack_end(GROUP).node.path))
    else:
        raise

    testPrint("groupend_stmt " + p[1], p)


##########################     optional     ##########################


def p_type_option(p):
    '''
    prompt_stmt_opt : QUOTE_WORD if_expr
                    | empty
    '''
    if p[1] is None:
        p[0] = None
    else:
        p[1] = handle_quote(p[1])

        string = None
        dep = None
        if p[2] is None:
            string = p[1]
            dep = "n" # 标记为不可见
        else:
            string = p[1] + p[2]['string']
            dep = p[2]['dep']
        p[0] = {
            'string': string,
            'dep': dep,
        }

    testPrint("prompt_stmt_opt", p)


def p_type_stmt(p):  # config choice
    '''
    type_stmt : INT prompt_stmt_opt EOL
            | HEX prompt_stmt_opt EOL
            | STRING prompt_stmt_opt EOL
            | BOOL prompt_stmt_opt EOL
            | TRISTATE prompt_stmt_opt EOL
    '''
    LastNode.set_detail_type(p[1])
    tmp = get_stack_end(GROUP)
    if tmp.node.type == 'choice' and tmp.node.detail.type == "":
        tmp.node.set_detail_type(p[1])
    if p[2] is not None:
        LastNode.set_detail_value("prompt", p[2]['string'])

        if LastNode.type == "choice":
            if tmp.node.type != 'choice':
                raise
            tmp.set_group_display(p[2]['dep'])
        elif LastNode.type == 'config':
            LastNode.dep_temp.set_display(p[2]['dep'])

    testPrint("type_stmt", p)


def p_prompt_stmt(p):  # choice comment config
    '''
    prompt_stmt : PROMPT QUOTE_WORD if_expr EOL
    '''
    p[2] = handle_quote(p[2])

    if p[3] is None:
        LastNode.set_detail_value("prompt", p[2])
    else:
        LastNode.set_detail_value("prompt", p[2] + p[3]['string'])

        if LastNode.type == "choice":
            target = get_stack_end(GROUP)
            if target.node.type != 'choice':
                raise
            target.set_group_display(p[3]['dep'])
        elif LastNode.type == 'comment':
            pass
        elif LastNode.type == 'config':
            LastNode.dep_temp.set_display(p[3]['dep'])

    testPrint("prompt_stmt", p)


def p_help_stmt(p):  # config choice
    '''
    help_stmt : HELP HELP_CONTEXT EOL
            | HELP HELP_CONTEXT
    '''
    help_context = p[2].replace('\n\t\t', ' ').replace('\t\t', '').replace('\n', '')
    LastNode.set_help(help_context)

    testPrint("help_stmt", p)

def p_depends_stmt(p):  # config choice comment menu
    '''
    depends_stmt : DEPENDS ON expr EOL
    '''
    add_check_count('depend_error')

    LastNode.set_detail_value('depends', p[3]['string'])

    if LastNode.type == "menu" or LastNode.type == "choice":
        target = get_stack_end(GROUP)
        if target.node.type != LastNode.type:
            raise
        # target.set_group_dep('(' + p[3]['dep'] + ')')
        LastNode.dep_temp.set_depends('(' + p[3]['dep'] + ')')
        # if LastNode.type == "choice":
        #     LastNode.dep_temp.set_depends(p[3]['dep'])
    elif LastNode.type == 'comment':
        pass
    elif LastNode.type == 'config' or LastNode.type == 'menuconfig':
        LastNode.dep_temp.set_depends('(' + p[3]['dep'] + ')')

    testPrint("depends_stmt", p)


def p_select_imply_stmt(p):  # config
    '''
    select_imply_stmt : SELECT QUOTE_WORD if_expr EOL
                    | SELECT WORD if_expr EOL
                    |  IMPLY WORD if_expr EOL
    '''
    global SELECT, IMPLY
    add_check_count("unmet_depend" if p[1] == 'select' else "value_warming")

    p[2] = handle_quote(p[2])

    # LastNode.set_detail_value(p[1], p[2])

    if LastNode.type == 'config' or LastNode.type == 'menuconfig':
        if p[1] == 'select':
            updateSelectImply(SELECT, p[2], '' if p[3] is None else p[3]['dep'])
            tmp = p[2] + '' if p[3] is None else p[2] + p[3]['string']
            LastNode.set_detail_value(p[1], tmp)
        else:
            updateSelectImply(IMPLY, p[2], '' if p[3] is None else p[3]['dep'])

    testPrint("select_imply_stmt " + p[1], p)


def p_range_stmt(p):  # config
    '''
    range_stmt : RANGE symbol symbol if_expr EOL
    '''
    add_check_count('range_error')

    if p[4] is None:
        LastNode.set_detail_value(p[1], '(' + p[2]['string'] + ' ' + p[3]['string'] + ')')
        LastNode.config_dep.set_restrict(p[2]['dep'] + ' ' + p[3]['dep'], '')

    else:
        LastNode.set_detail_value(p[1], '(' + p[2]['string'] + ' ' + p[3]['string'] + ')' + p[4]['string'])
        LastNode.config_dep.set_restrict(p[2]['dep'] + ' ' + p[3]['dep'], p[4]['dep'])

    testPrint("range_stmt", p)


def p_optional(p):  # choice
    '''
    optional_stmt : OPTIONAL EOL
    '''
    LastNode.set_detail_value('optional', True)

    testPrint("optional_stmt", p)


def p_default_stmt(p):  # config choice
    '''
    default_stmt : DEFAULT expr if_expr EOL
                | DEF_BOOL expr if_expr EOL
                | DEF_TRISTATE expr if_expr EOL
    '''
    add_check_count("value_warming")

    group = get_stack_end(GROUP)
    if p[1] == 'def_bool':
        LastNode.set_detail_type('bool')
        if group.node.type == 'choice' and group.node.detail.type == "":
            group.node.set_detail_type('bool')
    elif p[1] == 'def_tristate':
        LastNode.set_detail_type('tristate')
        if group.node.type == 'choice' and group.node.detail.type == "":
            group.node.set_detail_type('tristate')

    if LastNode.detail.type == "" and re.fullmatch('[0-9]+', p[2]['string']):
        LastNode.set_detail_type('int')
    elif LastNode.detail.type == "" and p[2]['string'][:2] == '0x':
        LastNode.set_detail_type('hex')

    if p[3] is None or p[3] == '\n':
        LastNode.set_detail_value("default", p[2]['string'])
        if LastNode.type == 'choice' or LastNode.type == 'config':
            LastNode.dep_temp.set_restrict([p[2]['dep']])
    else:
        LastNode.set_detail_value("default", p[2]['string'] + ' ' + p[3]['string'])
        if LastNode.type == 'choice' or LastNode.type == 'config':
            LastNode.dep_temp.set_restrict([p[2]['dep'], p[3]['dep']])

    testPrint("default_stmt", p)


def p_visible_stmt(p): # 继承性，组内配置项可见性需要考虑
    '''
    visible_stmt : VISIBILE if_expr EOL
    '''

    LastNode.set_detail_value('prompt', p[2]['string'])

    if LastNode.type == "menu" and p[2] is not None:
        target = get_stack_end(GROUP)
        if target.node.type != 'menu':
            raise # parse error
        target.set_group_display(p[2]['dep'])

    testPrint("visible_stmt", p)


def p_modules_stmt(p):
    '''
    modules_stmt : MODULES EOL
    '''
    LastNode.set_detail_value("modules", True)

    testPrint("modules_stmt", p)


def p_source(p):
    '''
    source_stmt : SOURCE QUOTE_WORD EOL
    '''
    testPrint("source_stmt", p)


##########################     other      ##########################


def p_symbol(p):
    '''
    symbol : WORD 
        | QUOTE_WORD
        | SP_WORD
    '''

    # 处理 '\$\(.*\)' 字符，降低dep的难度
    string = p[1]
    dep = p[1]
    if len(p[1]) > 0 and p[1][0] == '$':
        dep = 'SP_WORD'
    elif len(p[1]) > 1 and p[1][0] == '"' and p[1][1] == '$':
        dep = 'SP_WORD'
    elif len(p[1]) > 2 and p[1][0] == '"' and p[1][-1] == '"':
        if re.fullmatch(r'-?[0-9]+', p[1][1:-1]) or \
           (len(p[1]) == 3 and (p[1][1] == 'y' or p[1][1] == 'm' or p[1][1] == 'n')):
            dep = handle_quote(p[1])
    p[0] = {
        'string': string,
        'dep': dep,
    }

    testPrint("symbol", p)


def p_if_expr(p):
    '''
    if_expr : IF expr
            | empty
    '''
    string = None
    dep = None
    if len(p) > 1 and p[1] != None:
        dep = p[2]['dep']
        string = " if " + p[2]['string']

    if string is None and dep is None:
        p[0] = None
    else:
        p[0] = {
            'string': string,
            'dep': dep,
        }
    testPrint("if_expr", p)


def p_expr(p):
    '''
    expr : symbol
	    | symbol LESS symbol
	    | symbol LESS_EQUAL symbol
	    | symbol GREATER symbol
	    | symbol GREATER_EQUAL symbol
	    | symbol EQUAL symbol
	    | symbol UNEQUAL symbol

        | NOT expr
	    | OPEN_PARENT expr CLOSE_PARENT
        | expr OR expr
	    | expr AND expr
    '''
    string = None
    dep = None
    if len(p) == 2:
        string = p[1]['string']
        dep = p[1]['dep']
    elif len(p) == 3 and p[1] == '!':
        string = '! ' + p[2]['string']
        dep = '! ' + p[2]['dep']
    else:
        if p[2] == '<' or p[2] == '<=' or p[2] == '>' or p[2] == '>=' or \
           p[2] == '=' or p[2] == '!=' or p[2] == '||' or p[2] == '&&':
            string = p[1]['string'] + ' ' + p[2] + ' ' + p[3]['string']
            dep = p[1]['dep'] + ' ' + p[2] + ' ' + p[3]['dep']
        elif p[1] == '(' and p[3] == ')':
            string = '( ' + p[2]['string'] + ' )'
            dep = '( ' + p[2]['dep'] + ' )'

    p[0] = {
        'string': string,
        'dep': dep,
    }

    testPrint("expr", p)


##########################    assignment     ##########################

# def p_assigment_stmt(p):
#     '''
#     assignment_stmt : WORD assign_op assign_val EOL
#     '''

# def p_assign_op(p):
#     '''
#     assign_op : EQUAL
#             | COLON_EQUAL
#             | PLUS_EQUAL
#     '''

# def p_assign_val(p):
#     '''
#     assign_val : empty
#     '''


##########################    yacc default   ##########################
def p_empty(p):
    'empty :'


def p_error(p):
    if p is not None:
        if p.type != 'EOL':
            print("Syntax error!", end=" ")
            print(p)
            # print(p.lexer.lexdata[p.lexer.lexpos - 30:p.lexer.lexpos + 30])

# parser = yacc.yacc(tabmodule="kconfig",outputdir="./")
# parser = yacc.yacc(write_tables=False)
parser = yacc.yacc()


######################### handle dep function #########################
def handleSelectImply(flag, LACK_CONFIG):
    global SELECT, IMPLY
    target = SELECT if flag == 'select' else IMPLY
    for item in target:
        father = item[0]
        kid = item[1]
        kid_ptr = AllNode.get(kid, None)
        if kid_ptr is None:
            if kid not in LACK_CONFIG:
                LACK_CONFIG.append(kid)
        else:
            for index in target[item]:
                if len(index) == 0:
                    for ptr in kid_ptr:
                        if flag == 'select':
                            ptr.config_dep.set_select(father, "")
                            # ptr.detail.set_value("rev_select", father)
                        else:
                            ptr.config_dep.set_imply('(' + father + ')', "")
                            ptr.detail.set_value("rev_imply", father)
                else:
                    for ptr in kid_ptr:
                        if flag == 'select':
                            ptr.config_dep.set_select(father, index)
                            # ptr.detail.set_value("rev_select", father + " if " + index)
                        else:
                            ptr.config_dep.set_imply('(' + father + ')', index)
                            ptr.detail.set_value("rev_imply", father + " if " + index)
    return LACK_CONFIG

def ParseKconfig(file, folder, display):
    global DISPLAY
    DISPLAY = display

    config_file = folder + 'config.json'
    dep_file = folder + 'dep.json'

    reset_data()
    begin = time.time()
    parser.parse(utils.load_Kconfig(file), lexer=lexer)
    SetLastNodeDep()
    
    cost = time.time() - begin
    print("\nParse time\t\t{}".format(str(cost)))
    print("{:<40}".format("[Got All Config!]"))

    utils.saveAllNode(folder, AllNode)

    AllConfig = {}
    AllConfigDep = {}
    for item in AllNode:
        node_type = AllNode[item][0].type
        if node_type == 'config' or node_type == 'menuconfig':
            AllConfig[item] = []
            AllConfigDep[item] = []
            for tmp in AllNode[item]:
                AllConfig[item].append(tmp.detail)
                AllConfigDep[item].append(tmp.config_dep)
        if node_type == 'choice':
            AllConfigDep[item] = []
            for tmp in AllNode[item]:
                AllConfigDep[item].append(tmp.config_dep)
    lack_config = handleSelectImply("select", [])
    lack_config = handleSelectImply("imply", lack_config)

    print("{:<40}".format("[Prepare write AllConfig]") + "file => " + config_file)
    utils.write_json_file(AllConfig, config_file)

    print("{:<40}".format("[Prepare write AllConfigDep]") + "file => " + dep_file)
    utils.write_json_file(AllConfigDep, dep_file)

    check_file = folder + 'check.json'
    utils.write_json_file(check, check_file)
