import ply.lex as lex

##############################################
# 针对dep的词法的简化版lex程序
# 跳过$开始的单词
##############################################
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

