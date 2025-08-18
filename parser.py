import sly
from lexer import Lexer

class Parser(sly.Parser):
    # Traer tokens del lexer
    tokens = Lexer.tokens

    precedence = (
        ('left', '+', '-'),
        ('left', '*', '/'),
        ('right', '^'),
    )

    # --------- PROGRAMA PRINCIPAL ----------
    @_('decl_list')
    def program(self, p):
        return ('program', p.decl_list)

    @_('decl_list decl')
    def decl_list(self, p):
        return p.decl_list + [p.decl]

    @_('decl')
    def decl_list(self, p):
        return [p.decl]

    # --------- DECLARACIONES (variables y funciones) ----------
    @_('ID ":" type ";"')
    def decl(self, p):
        return ('vardecl', p.ID, p.type)

    @_('FUNCTION ID "(" param_list ")" ":" type "{" stmt_list "}"')
    def decl(self, p):
        return ('funcdef', p.ID, p.param_list, p.type, p.stmt_list)

    @_('stmt_list stmt')
    def stmt_list(self, p):
        return p.stmt_list + [p.stmt]

    @_('stmt')
    def stmt_list(self, p):
        return [p.stmt]

    # --------- TIPOS ----------
    @_('INTEGER')
    def type(self, p):
        return 'int'

    @_('STRING')
    def type(self, p):
        return 'string'

    # --------- SENTENCIAS ----------
    @_('expr ";"')
    def stmt(self, p):
        return ('exprstmt', p.expr)

    @_('RETURN expr ";"')
    def stmt(self, p):
        return ('return', p.expr)

    @_('PRINT expr ";"')
    def stmt(self, p):
        return ('print', p.expr)

    # --------- IF / ELSE ----------
    @_('IF "(" expr ")" "{" stmt_list "}"')
    def stmt(self, p):
        return ('if', p.expr, p.stmt_list, None)

    @_('IF "(" expr ")" "{" stmt_list "}" ELSE "{" stmt_list "}"')
    def stmt(self, p):
        return ('if', p.expr, p.stmt_list0, p.stmt_list1)

    # --------- FOR ----------
    @_('FOR "(" expr ";" expr ";" expr ")" "{" stmt_list "}"')
    def stmt(self, p):
        return ('for', p.expr0, p.expr1, p.expr2, p.stmt_list)

    # --------- EXPRESIONES ----------
    @_('ID "=" expr')
    def expr(self, p):
        return ('assign', p.ID, p.expr)

    @_('expr "+" expr')
    def expr(self, p):
        return ('add', p.expr0, p.expr1)

    @_('expr "-" expr')
    def expr(self, p):
        return ('sub', p.expr0, p.expr1)

    @_('expr "*" expr')
    def expr(self, p):
        return ('mul', p.expr0, p.expr1)

    @_('expr "/" expr')
    def expr(self, p):
        return ('div', p.expr0, p.expr1)

    @_('expr "<" expr')
    def expr(self, p):
        return ('lt', p.expr0, p.expr1)

    @_('expr ">" expr')
    def expr(self, p):
        return ('gt', p.expr0, p.expr1)

    @_('expr EQ expr')
    def expr(self, p):
        return ('eq', p.expr0, p.expr1)

    @_('INT')
    def expr(self, p):
        return ('int', p.INT)

    @_('ID')
    def expr(self, p):
        return ('id', p.ID)

    # --------- ERRORES ----------
    def error(self, p):
        if p:
            print(f"Error de sintaxis en token {p.type}, valor {p.value}, línea {p.lineno}")
        else:
            print("Error de sintaxis al final del archivo")
