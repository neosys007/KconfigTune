'''
预处理程序

主函数为Preprocessing(root, target, file)
其参数含义为
    * root: Linux内核路径
    * target: 目标架构, 例如x86、mips
    * file: 预处理结果保存路径

预处理过程不会检查Kconfig文件编写规范,
若出现“There is an unknown error. Note the error message above!”
需要人工检查Kconfig相关信息
'''

import os
import re
import time

import ply.lex as lex

ERROR_FLAG = False
DISPLAY = False

states = (
    ('STRING', 'exclusive'),
    ('HELP', 'exclusive'),
    ('SOURCE', 'exclusive'),
    ('SP', 'exclusive'),
    ('WRONG', 'exclusive'),
)

reserved = {
    'mainmenu': 'MAINMENU',
    'menuconfig': 'MENUCONFIG',
    'menu': 'MENU',
    'endmenu': 'ENDMENU',
    'if': 'IF',
    'endif': 'ENDIF',
    'bool': 'BOOL',
    'tristate': 'TRISTATE',
    'int': 'INT',
    'hex': 'HEX',
    'string': 'STRING',
    'choice': 'CHOICE',
    'endchoice': 'ENDCHOICE',
    'depends': 'DEPENDS',
    'on': 'ON',
    'select': 'SELECT',
    'default': 'DEFAULT',
    'imply': 'IMPLY',
    'range': 'RANGE',
    'visible': 'VISIBILE',
    'modules': 'MODULES',
    # 'source'        : 'SOURCE',
    'config': 'CONFIG',
    'comment': 'COMMENT',
    'def_bool': 'DEF_BOOL',
    'def_tristate': 'DEF_TRISTATE',
    'optional': 'OPTIONAL',
    'prompt': 'PROMPT',
}

tokens = [
    'WORD',
    'QUOTE_WORD',
    'OR',  # ||
    'AND',  # &&
    'EQUAL',  # =
    'UNEQUAL',  # !=
    'LESS',  # <
    'LESS_EQUAL',  # <=
    'GREATER',  # >
    'GREATER_EQUAL',  # >=
    'NOT',  # !
    'OPEN_PARENT',  # (
    'CLOSE_PARENT',  # )
    'COLON_EQUAL',  # :=
    'PLUS_EQUAL',  # +=
    'DOLLER',  # $
    'EOL',
    'HELP',
    'HELP_CONTEXT',
    'SOURCE',
] + list(reserved.values())

t_OR = '\|\|'
t_AND = '&&'
t_EQUAL = '='
t_UNEQUAL = '!='
t_LESS = '<'
t_LESS_EQUAL = '<='
t_GREATER = '>'
t_GREATER_EQUAL = '>='
t_NOT = '!'
t_OPEN_PARENT = '\('
t_CLOSE_PARENT = '\)'
# t_COLON_EQUAL = ':='
t_PLUS_EQUAL = '\+='

t_ignore = ' \t-'
t_ignore_commet = r'\# .*'


def t_option(t):
    r'option.*\n'


def t_COLONEQUAL(t):
    r':='
    t.lexer.begin('WRONG')

t_WRONG_ignore = ''
def t_WRONG_NL(t):
    r'.*\n'
    t.type = "COLON_EQUAL"
    t.value = 'wrong'
    t.lexer.begin('INITIAL')
    return t


def t_WRONG_error(t):
    print(PATH[len(PATH) - 1] + " => WRONG Illegal charactor '%s'" % t.value[-10:20])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


def t_BOOLEAN(t):
    r'boolean'
    t.type = 'BOOL'
    t.value = 'bool'
    return t


def t_error(t):
    print(PATH[len(PATH) - 1] + " initial Illegal charactor '%s'" % t.value[-10:20])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


def t_SOURCE(t):
    r'source'
    t.lexer.begin('SOURCE')
    t.type = 'SOURCE'
    return t

def t_ESPSOURCE(t):
    r'rsource|orsource'
    t.lexer.begin('SOURCE')
    t.type = 'SOURCE'
    t.value = 'source'
    return t


def t_HELP(t):
    r'help'
    t.lexer.begin('HELP')
    t.type = 'HELP'
    return t


def t_WORD(t):
    r'[\.A-Za-z0-9_-]+'
    if t.value.count('.') > 0:
        t.type = 'QUOTE_WORD'
    else:
        t.type = reserved.get(t.value, 'WORD')
    return t


def t_EOL(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t


def t_NEXTLINE(t):
    r'\\\n'
    t.lexer.lineno += len(t.value)
    pass


string_context = ""
STRING_FLAG = ''


def t_TO_STRING(t):
    r'\" | \''
    global STRING_FLAG
    STRING_FLAG = t.value
    t.lexer.begin('STRING')


SP_COUNT = 0
SP_CONTEXT = ''


def t_DOLLER(t):
    r'\$\('
    global SP_COUNT, SP_CONTEXT
    t.lexer.begin('SP')
    SP_COUNT = 1
    SP_CONTEXT = '${{('


##########################  SP_word ##########################
t_SP_ignore = ''


def t_SP_IF(t):
    r'[ |\t]+if[ |\t]+'
    global SP_COUNT, SP_CONTEXT
    raise


def t_SP_NL(t):
    r'\n'
    global SP_COUNT, SP_CONTEXT
    raise


def t_SP_CONTEXT(t):
    r'[^\n\(\)]'
    global SP_CONTEXT
    SP_CONTEXT += t.value


def t_SP_BEGIN(t):
    r'\('
    global SP_COUNT, SP_CONTEXT
    SP_COUNT += 1
    SP_CONTEXT += t.value


def t_SP_END(t):
    r'\)'
    global SP_COUNT, SP_CONTEXT
    if SP_COUNT == 1:
        SP_CONTEXT += t.value + '}}'
        t.value = SP_CONTEXT
        t.type = 'WORD'
        SP_COUNT = 0
        SP_CONTEXT = ''
        t.lexer.begin('INITIAL')
        return t
    else:
        SP_CONTEXT += t.value
        SP_COUNT -= 1


def t_SP_error(t):
    print(PATH[len(PATH) - 1] + " => SP Illegal charactor '%s'" % t.value[-10:20])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


##########################  string  ##########################
t_STRING_ignore = ''


def t_STRING_NOTEND(t):
    r'\\\" | \\\''
    global string_context
    string_context += '\''


def t_STRING_END(t):
    r'\" | \''
    global string_context
    if len(STRING_FLAG) == 0:
        print("lack symbol")
    elif (t.lexpos < t.lexer.lexlen and t.lexer.lexdata[t.lexpos + 1] == '$') \
        or (t.lexpos + 2 < t.lexer.lexlen and (t.lexer.lexdata[t.lexpos + 2] == '"'or t.lexer.lexdata[t.lexpos + 2] == "'")):
        pass
    elif t.value == STRING_FLAG:
        t.lexer.begin('INITIAL')
        t.value = '"' + string_context + '"'
        string_context = ""
        t.type = 'QUOTE_WORD'
        return t
    string_context += '\''


def t_STRING_CONTEXT(t):
    r'[^\n\r\"\'\\]'
    global string_context
    string_context += t.value


def t_STRING_NL(t):
    r'\n+'
    print(PATH[len(PATH) - 1] + " => string multi-line strings not supported\n")
    t.lexer.begin('INITIAL')
    global string_context
    t.value = '"' + string_context + '"'
    string_context = ""
    t.type = 'QUOTE_WORD'
    return t


def t_STRING_error(t):
    print(PATH[len(PATH) - 1] + " => string Illegal charactor '%s'" % t.value[-10:20])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


##########################   help   ##########################
t_HELP_ignore = ''
help_context = ""


def get_word(line):
    result = ""
    index = 0
    while index < len(line):
        if re.match(r'\S', line[index]):
            # if line[index] != ' ' and line[index] != '\t' and line[index] != '\n':
            break
        index += 1
    while index < len(line):
        # if line[index] != ' ' and line[index] != '\t' and line[index] != '\n':
        if re.match(r'\S', line[index]):
            result += line[index]
            index += 1
        else:
            break
    return (result, index)


def get_eol(line):
    index = 0
    while index < len(line):
        if line[index] == '\n':
            return True
        elif line[index] == ' ' or line[index] == '\t':
            index += 1
        elif re.match(r'\S', line[index]):
            return False


def check_help_end(data):
    if len(data) == 0:
        return True
    i = 0
    while i < len(data):
        if data[i] == '\t' or data[i] == ' ':
            (word, tmp1) = get_word(data[i:len(data)])
            if word == 'config':
                (word, tmp2) = get_word(data[i + tmp1:len(data)])
                if re.fullmatch(r'[A-Za-z0-9_-]+', word) and get_eol(
                        data[i + tmp1 + tmp2:len(data)]):
                    return True
                else:
                    return False
            else:
                return False
        elif data[i] == '\n':
            i += 1
            continue
        else:
            (word, tmp1) = get_word(data[i:len(data)])
            if word == 'config':
                (word, tmp2) = get_word(data[i + tmp1:len(data)])
                if re.fullmatch(r'[A-Za-z0-9_-]+', word) and get_eol(
                        data[i + tmp1 + tmp2:len(data)]):
                    return True
                else:
                    return False
            else:
                break
    return True


def t_HELP_CONTEXT(t):
    r'[\S ]+'
    global help_context
    if check_help_end(t.lexer.lexdata[t.lexer.lexpos:t.lexer.lexlen]):
        t.type = "HELP_CONTEXT"
        t.value = help_context + t.value
        index = 0
        while index < len(t.value):
            if re.fullmatch('[a-zA-Z]', t.value[index]):
                # if t.value[index] == r'[a-zA-Z]':
                break
            index += 1
        t.value = '\t\t' + t.value[index:]
        t.lexer.begin('INITIAL')
        help_context = ""
        return t
    help_context += t.value


def t_HELP_WHITESPACE(t):
    r'[ \t]+'
    pass


def t_HELP_NL(t):
    r'\n+'
    global help_context
    if len(help_context) > 0:
        help_context += '\n\t\t'
    else:
        help_context += '\t\t'


def t_HELP_error(t):
    print(PATH[len(PATH) - 1] +
          " => help Illegal charactor '%s'" % t.value[-10:20])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


# ##########################  source  ##########################
t_SOURCE_ignore = ''


def t_SOURCE_CONTEXT(t):
    # r'([a-zA-Z0-9_]+\/?)+'
    r'.*\n'
    regex = re.compile(r"[\ ]+#.*\n")
    value = regex.sub('', t.value)
    if value[-1] == '\n':
        value = value[1:-1]
    else :
        value = value[1:]
    if value[0] == '"':
        value = value[1:]
    if value[-1] == '"':
        value = value[:-1]

    t.type = 'QUOTE_WORD'
    t.value = '"' + value + '"'
    t.lexer.begin('INITIAL')
    return t


# def t_SOURCE_DOT(t):
#     r"\""
#     pass


def t_SOURCE_error(t):
    print(PATH[len(PATH) - 1] + " => source Illegal charactor '%s'" % t.value[-5:5])
    global ERROR_FLAG
    ERROR_FLAG = True
    t.lexer.skip(1)


##########################  assign  ##########################
# 在kconfig文件开始判断，不是INITIAl文件就跳入ASSIGN状态中
# def t_ASSIGN_VAL(t):
#     r'[^\s\n]+.*'
#     t.type = "ASSIGN_VAL"
#     return t
##############################################################

lexer = lex.lex()

##########################  other   ##########################
NOT_PARSE = [
    'scripts/kconfig', '/scripts/Kconfig.include'
]
PATH = []

DIS_COUNT = -1
def dis(file, root):
    global DIS_COUNT
    DIS_COUNT += 1
    if DIS_COUNT == 0 and DISPLAY:
        rows, columns = os.popen('stty size', 'r').read().split()
        print("\rread file => " + file.replace(root, '').ljust(int(columns) - 30), end='\r', flush=True)
    elif DIS_COUNT == 50:
        DIS_COUNT = -1

def not_parse(file_path, root):
    if file_path.replace(root, '') in PATH:
        return True
    for item in NOT_PARSE:
        if item in file_path:
            return True
    return False


def handle_indentation(file):
    res = ""
    pre_indentation = 0
    keywords = ["mainmenu", "menu", "endmenu", "if", "endif", "config", "menuconfig", "choice", "endchoice", "source",
                "orsource", "rsource"]
    lines = file.readlines()
    new_lines = []
    help_flag = False
    for line in lines:
        line = line.strip("\n")

        stripped_line = line.lstrip()
        space_count = len(line) - len(stripped_line)
        
        line = line.lstrip()
        if line == "" or line.startswith("#"):
            new_lines.append(line)
        else:
            if any(line.startswith(kw) for kw in keywords):
                if help_flag and space_count >= pre_indentation:
                    new_lines.append('\t' + line)
                else:
                    new_lines.append(line)
            else:
                if line.startswith("help"):
                    help_flag = True
                new_lines.append('\t' + line)
            
            if help_flag == True and space_count < pre_indentation:
                help_flag = False
            pre_indentation = space_count

    res = "\n".join(new_lines)
    return res


def read_data(root, file):
    global PATH
    if not_parse(file, root):
        return []
    dis(file, root)
    PATH.append(file.replace(root, ''))
    res = []
    res.append("PATH path")
    res.append("QUOTE_WORD \"" + file.replace(root, '') + '"')
    res.append("EOL \\n")

    try:
        with open(file, 'r', errors='ignore') as file:
            data = file.read()
            data = data.replace(u'\xa0', ' ')
            lexer.input(data)
            while True:
                tok = lexer.token()
                if not tok:
                    break
                if tok.type == 'COLON_EQUAL':
                    res.pop()
                elif tok.type == "WORD":
                    res.append('WORD ' + tok.value)
                elif tok.type == "QUOTE_WORD":
                    res.append('QUOTE_WORD ' + tok.value)
                elif tok.type == "EOL":
                    res.append('EOL \n')
                else:
                    res.append(tok.type + ' ' + tok.value)
    except Exception:
        pass
    res.append("EOL \\n")
    res.append("ENDPATH endpath")
    res.append("EOL \\n")
    return res


def write_file(file_name, result):
    target = [
        'mainmenu',
        'menuconfig',
        'menu',
        'endmenu',
        'endif',
        'choice',
        'endchoice',
        'config',
        'comment',
        'path',
        'endpath',
    ]
    with open(file_name, 'w') as file:
        index = 0
        while index < len(result):
            if get_type(result[index]) == "EOL":
                file.write('\n')
                while index + 1 < len(result):
                    if get_type(result[index + 1]) == "EOL":
                        index += 1
                    else:
                        break
            elif get_type(result[index]) == "HELP":
                file.write('\t')
                file.write(get_value(result[index]))
                file.write('\n')
            elif get_type(result[index]) == "HELP_CONTEXT":
                file.write(get_value(result[index]))
                file.write('\n')
            elif get_type(result[index]) == "IF":
                if get_type(result[index - 1]) != "EOL" and get_type(
                        result[index - 1]) != "HELP_CONTEXT":
                    file.write('\t')
                file.write(get_value(result[index]))
            elif get_value(result[index]) not in target:
                file.write('\t')
                file.write(get_value(result[index]))
            else:
                file.write(get_value(result[index]))
            index += 1


def get_type(target):
    res = target.split(' ', 1)
    return res[0]


def get_value(target):
    res = target.split(' ', 1)
    if len(res) > 1:
        return res[1]
    else:
        return None


def handle_source(root, file, target, result):
    if not_parse(file, root):
        return result
    res = read_data(root, file)
    index = 0
    while index < len(res):
        if get_type(res[index]) == "SOURCE" \
                and get_type(res[index + 1]) == "QUOTE_WORD": # arch/$(SRCARCH)/Kconfig
            path = get_value(res[index + 1])[1:len(get_value(res[index + 1])) -1]
            if path.count("$(SRCARCH)") > 0:
                path = path.replace("$(SRCARCH)", target)
            if path.count("$SRCARCH") > 0:
                path = path.replace("$SRCARCH", target)
            if path.count("$(HEADER_ARCH)") > 0:
                path = path.replace("$(HEADER_ARCH)", target)
            tmp = path.split('/')
            if tmp[0] != 'scripts' and tmp[0] != 'Documentation':
                fullpath = root + '/' + path
                if path not in PATH:
                    tmp = read_data(root, fullpath)
                    res = res[0:index + 1] + tmp + res[index + 2:len(res)]
            else:
                index += 1
        elif get_type(res[index]) == "DEPENDS" and get_type(res[index + 1]) != "ON":
            result.append(res[index])
            result.append('ON on')
        else:
            result.append(res[index])
        index += 1
    return result


def Traversal(root, path, target, result):
    if not os.path.exists(path):
        print("Wrong path!" + path)
        return result
    files = os.listdir(path)

    for file in files:
        if re.match(r'Kconfig[\.]*', file):
            if not not_parse(path + '/' + file, root):
                result = handle_source(root, path + '/' + file, target, result)

    for file in files:
        if os.path.isdir(path + '/' + file):
            if path + '/' + file == root + "/Documentation":
                continue
            if path + '/' + file == root + "/scripts":
                file += '/gcc-plugins'
            if path + '/' + file == root + "/arch":
                file += '/' + target
            result = Traversal(root, path + '/' + file, target, result)

    return result


def Preprocessing(root, target, file, display):
    global PATH, DISPLAY
    DISPLAY = display
    PATH = []
    begin = time.time()
    result = Traversal(root, root, target, [])
    cost = time.time() - begin
    write_file(file, result)
    print("\nPreprocessing time\t\t{}".format(str(cost)))
    if ERROR_FLAG:
        print("{:<40}".format("[WARMING]") + "There is an unknown error. Note the error message above!")

if __name__ == '__main__':
    # data = '''source \"$IDF_PATH/components/esp_psram/Kconfig.spiram.common\"    # insert non-chip-specific items here
    # '''
    with open("/home/guosy/Kconfig/OS/kernel-source/drivers/media/i2c/soc_camera/Kconfig", "r") as file:
        # 读取文件内容
        data = file.read()
    PATH.append("test")
    lexer.input(data)
    while True:
        tok = lexer.token()
        if not tok:
            break
        print(tok)