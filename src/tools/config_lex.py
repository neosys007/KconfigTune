import ply.lex as lex

states = (
    ('STRING', 'exclusive'),
    ('HELP', 'exclusive'),
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
    'source': 'SOURCE',
    'config': 'CONFIG',
    'comment': 'COMMENT',
    'def_bool': 'DEF_BOOL',
    'def_tristate': 'DEF_TRISTATE',
    'optional': 'OPTIONAL',
    'prompt': 'PROMPT',
    'path': 'PATH',
    'endpath': 'ENDPATH',
}

tokens = [
    'WORD',
    'QUOTE_WORD',
    "SP_WORD",
    # 'ASSIGN_VAL',
    # operator
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
    # 'COLON_EQUAL',      # :=
    # 'PLUS_EQUAL',       # +=
    'EOL',
    'HELP',
    'HELP_CONTEXT',
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
# t_PLUS_EQUAL = '\+='

t_ignore = ' \t'
t_ignore_commet = r'\# .*'


def t_SP_WORD(t):
    r'\$(\{\{(.*?)\}\})?'
    t.type = "SP_WORD"
    return t


def t_ANY_error(t):
    print(t.value[:50])
    print("Illegal charactor '%s'" % t.value[0])
    # raise


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
    t.type = 'EOL'
    return t


def t_NEXTLINE(t):
    r'\\\n'
    t.lexer.lineno += len(t.value)
    pass


def t_TO_STRING(t):
    r'\"'
    t.lexer.begin('STRING')


##########################  string  ##########################
t_STRING_ignore = ''


def t_STRING_CONTEXT(t):
    r'.*?"'
    t.value = '"' + t.value[:len(t.value) - 1] + '"'
    t.type = 'QUOTE_WORD'
    t.lexer.begin('INITIAL')
    return t


##########################   help   ##########################
t_HELP_ignore = ''
help_context = ""


def t_HELP_CONTEXT(t):
    r'[\t]+.*'
    global help_context
    help_context += t.value


def t_HELP_NL(t):
    r'\n+'
    global help_context
    if len(help_context) > 0:
        help_context += '\n'
    # 检查换行后是否有缩进
    for ch in t.lexer.lexdata[t.lexer.lexpos:]:
        if ch != '\t':
            t.type = "HELP_CONTEXT"
            t.value = help_context
            t.lexer.begin('INITIAL')
            help_context = ""
            return t
        else:
            break


lexer = lex.lex()
