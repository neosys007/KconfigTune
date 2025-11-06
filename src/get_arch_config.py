import tools
import ply.lex as lex

reserved = {'SP_WORD': 'SP_WORD'}
tokens = [
    'WORD',
    'QUOTE_WORD',
    'NOT',  # !
    'OR',  # ||
    'AND',  # &&
    'EQUAL',  # =
    'UNEQUAL',  # !=
    'LESS',  # <
    'LESS_EQUAL',  # <=
    'GREATER',  # >
    'GREATER_EQUAL',  # >=
    'OPEN_PARENT',  # (
    'CLOSE_PARENT',  # )
    'OPEN_BRACKET',  # [
    'CLOSE_BRACKET',  # ]
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
t_OPEN_BRACKET = '\['
t_CLOSE_BRACKET = '\]'

# t_OPEN_CURLY = '{'
# t_CLOSE_CURLY = '}'

t_ignore = ' \t{}'


def t_error(t):
    # print(t.value[:50])
    print("Illegal charactor '%s'" % t.value[0])
    raise


def t_SPWORD(t):
    r'\$\{\{.*\}\}'
    t.value = 'SP_WORD'
    t.type = 'SP_WORD'
    return t


def t_QUOTE_WORD(t):
    r'".*?"'
    if len(t.value) == 3 and (t.value[1] == 'y' or t.value[1] == 'm' or
                              t.value[1] == 'n'):
        t.value = t.value[1]
        t.type = 'WORD'
        return t
    elif t.value[1] == '$':
        t.value = 'SP_WORD'
        t.type = 'SP_WORD'
        return t
    else:
        t.type = 'QUOTE_WORD'
        return t


def t_WORD(t):
    r'[A-Za-z0-9_-]+'
    t.type = reserved.get(t.value, 'WORD')
    return t


lexer = lex.lex()

def get_tokens(data):
    if data is None:
        return []
    lexer.input(data)
    result = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        result.append(tok)
    return result

def gen_dict(dep_json) -> dict: # {key : [str]}
    data = tools.load_json(dep_json)
    res = {}
    for key, value_list in data.items():
        for item in value_list:
            if item['dep'] is not None:
                if key not in res.keys():
                    res[key] = [item["dep"]]
                else:
                    res[key].append(item["dep"])
    return res


def handle_arch_config(data, arch_data) -> list:
    res = arch_data
    res_len = len(res)
    while True:
        for key, value in data.items():
            if key not in arch_data:
                for dep in value:
                    word_list = get_tokens(dep)
                    for word in word_list:
                        if word.value in arch_data:
                            res.append(str(key))
        if res_len == len(res):
            break
        else:
            res_len = len(res)
    return res

if __name__ == '__main__':
    folder = "/home/guosy/Kconfig/6.6-x86"
    arch = "x86"

    dep_json = folder + '/dep.json'
    arch_config = ["X86", "X86_64", "X86_32"]
    res = handle_arch_config(gen_dict(dep_json), arch_config)
    with open(arch + "_config", "w") as file:
        for item in res:
            file.write(item + '\n')