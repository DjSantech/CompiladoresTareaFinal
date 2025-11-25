# -*- coding: utf-8 -*-
# Parser para SLY: construye el AST a partir de los tokens del lexer.

import logging
import sly

from lexer  import Lexer
from errors import error, errors_detected
from model  import * # CORREGIDO: Se usa solo * para importar todos los nodos (incluyendo ArrayInit)

# Helper: fija el número de línea en el nodo y lo retorna
def _L(node, lineno):
    node.lineno = lineno
    return node

class Parser(sly.Parser):
    start = "prog"

    # Configuración de SLY
    log = logging.getLogger()
    log.setLevel(logging.ERROR)
    # expected_shift_reduce = 1 # Opcional, pero bueno mantenerlo
    debugfile = 'grammar.txt'

    # Tokens del lexer
    tokens = Lexer.tokens

    # Programa: secuencia de declaraciones o sentencias
    @_("decl_list", "stmt_list")
    def prog(self, p):
        seq = p.decl_list if hasattr(p, "decl_list") else p.stmt_list
        return _L(Program(body=seq), getattr(p, "lineno", None))

    # ------------------------------------------------------------------
    # DECLARACIONES
    # ------------------------------------------------------------------
    @_("decl decl_list")
    def decl_list(self, p):
        return [p.decl] + p.decl_list

    @_("empty")
    def decl_list(self, p):
        return []

    # Declaraciones sin inicialización
    @_("ID ':' type_simple ';'")
    def decl(self, p):
        return _L(VarDecl(name=p.ID, type=SimpleType(name=p.type_simple)), p.lineno)

    @_("ID ':' type_array_sized ';'")
    def decl(self, p):
        return _L(VarDecl(name=p.ID, type=p.type_array_sized), p.lineno)

    @_("ID ':' type_func ';'")
    def decl(self, p):
        return _L(VarDecl(name=p.ID, type=p.type_func), p.lineno)
    
    # Declaraciones con inicialización
    @_("decl_init")
    def decl(self, p):
        return p.decl_init

    @_("ID ':' type_simple '=' expr ';'")
    def decl_init(self, p):
        return _L(VarDecl(name=p.ID, type=SimpleType(name=p.type_simple), init=p.expr), p.lineno)

    # REGLA CORREGIDA para inicialización de Array (usa la regla array_init)
    @_("ID ':' type_array_sized '=' array_init ';'")
    def decl_init(self, p):
        # Esta regla usa el nodo ArrayInit construido por def array_init()
        return _L(VarDecl(name=p.ID, type=p.type_array_sized, init=p.array_init), p.lineno)

    @_("ID ':' type_func '=' '{' opt_stmt_list '}'")
    def decl_init(self, p):
        body = _L(Block(stmts=p.opt_stmt_list), p.lineno)
        return _L(VarDecl(name=p.ID, type=p.type_func, init=body), p.lineno)

    # ------------------------------------------------------------------
    # SENTENCIAS / INICIALIZACIÓN DE ARRAY
    # ------------------------------------------------------------------
    @_("stmt_list")
    def opt_stmt_list(self, p):
        return p.stmt_list

    @_("empty")
    def opt_stmt_list(self, p):
        return []
    
    # REGLAS PARA ARRAY_INIT (sección de inicialización de arrays)
    # CORRECCIÓN 1: Se usa el literal '{' y '}' en lugar de LBRACE/RBRACE
    @_("'{' expr_list '}'")
    def array_init(self, p):
        # Esto parsea '{ expr_list }' y usa el nodo ArrayInit
        return _L(ArrayInit(values=p.expr_list), p.lineno)

    @_('expr')
    def expr_list(self, p):
        # Un solo elemento en la lista (se mantiene como la base unificada)
        return [p.expr]
        
    # CORRECCIÓN 2: Se usa el literal ',' en lugar de COMMA
    @_("expr_list ',' expr")
    def expr_list(self, p):
        # Múltiples elementos en la lista (recursivo)
        return p.expr_list + [p.expr]
        
    @_('empty')
    def expr_list(self, p):
        # Lista vacía (e.g., {} )
        return []

    @_("stmt stmt_list")
    def stmt_list(self, p):
        return [p.stmt] + p.stmt_list

    @_("stmt")
    def stmt_list(self, p):
        return [p.stmt]

    @_("open_stmt")
    @_("closed_stmt")
    def stmt(self, p):
        return p[0]

    @_("if_stmt_closed")
    @_("for_stmt_closed")
    @_("while_stmt")
    @_("do_while_stmt")
    @_("simple_stmt")
    def closed_stmt(self, p):
        return p[0]

    @_("if_stmt_open", "for_stmt_open")
    def open_stmt(self, p):
        return p[0]

    # if / else
    @_("IF '(' opt_expr ')'")
    def if_cond(self, p):
        return p.opt_expr

    @_("if_cond closed_stmt ELSE closed_stmt")
    def if_stmt_closed(self, p):
        return _L(IfStmt(cond=p.if_cond, then=p.closed_stmt0, otherwise=p.closed_stmt1), p.lineno)

    @_("if_cond stmt")
    def if_stmt_open(self, p):
        return _L(IfStmt(cond=p.if_cond, then=p.stmt, otherwise=None), p.lineno)

    @_("if_cond closed_stmt ELSE if_stmt_open")
    def if_stmt_open(self, p):
        return _L(IfStmt(cond=p.if_cond, then=p.closed_stmt, otherwise=p.if_stmt_open), p.lineno)

    # for (init; cond; step) stmt
    @_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
    def for_header(self, p):
        return (p.opt_expr0, p.opt_expr1, p.opt_expr2)

    @_("for_header open_stmt")
    def for_stmt_open(self, p):
        i, c, s = p.for_header
        return _L(ForStmt(init=i, cond=c, step=s, body=p.open_stmt), p.lineno)

    @_("for_header closed_stmt")
    def for_stmt_closed(self, p):
        i, c, s = p.for_header
        return _L(ForStmt(init=i, cond=c, step=s, body=p.closed_stmt), p.lineno)

    # while
    @_("WHILE '(' opt_expr ')' stmt")
    def while_stmt(self, p):
        return _L(WhileStmt(cond=p.opt_expr, body=p.stmt), p.lineno)

    # do-while
    @_("DO block_stmt WHILE '(' opt_expr ')' ';'")
    def do_while_stmt(self, p):
        return _L(DoWhileStmt(body=p.block_stmt, cond=p.opt_expr), p.lineno)

    @_("DO stmt WHILE '(' opt_expr ')' ';'")
    def do_while_stmt(self, p):
        return _L(DoWhileStmt(body=p.stmt, cond=p.opt_expr), p.lineno)

    # simples
    @_("print_stmt")
    @_("return_stmt")
    @_("block_stmt")
    @_("decl")
    @_("expr ';'")
    def simple_stmt(self, p):
        return p[0]

    @_("PRINT opt_expr_list ';'", "PRINT '(' opt_expr_list ')' ';'")
    def print_stmt(self, p):
        return _L(PrintStmt(args=p.opt_expr_list), p.lineno)

    @_("RETURN opt_expr ';'")
    def return_stmt(self, p):
        return _L(ReturnStmt(expr=p.opt_expr), p.lineno)

    @_("'{' stmt_list '}'")
    def block_stmt(self, p):
        return _L(Block(stmts=p.stmt_list), p.lineno)

    # ------------------------------------------------------------------
    # EXPRESIONES
    # ------------------------------------------------------------------
    @_("empty")
    def opt_expr_list(self, p):
        return []
    
    @_("expr_list")
    def opt_expr_list(self, p):
        return p.expr_list

    # CORRECCIÓN 3: Se eliminan las reglas duplicadas de expr_list de esta sección
    # Las reglas de expr_list de la sección SENTENCIAS son las únicas válidas.

    @_("empty")
    def opt_expr(self, p):
        return None

    @_("expr")
    def opt_expr(self, p):
        return p.expr

    @_("expr1")
    def expr(self, p):
        return p.expr1

    @_("lval '=' expr1")
    def expr1(self, p):
        return _L(Assign(target=p.lval, value=p.expr1), p.lineno)

    @_("expr2")
    def expr1(self, p):
        return p.expr2

    @_("ID")
    def lval(self, p):
        return _L(Identifier(name=p.ID), p.lineno)

    @_("ID '[' expr ']'")
    def lval(self, p):
        return _L(ArrayIndex(array=Identifier(name=p.ID), index=p.expr), p.lineno)

    @_("expr2 LOR expr3")
    def expr2(self, p):
        return _L(BinOper(oper='||', left=p.expr2, right=p.expr3), p.lineno)

    @_("expr3")
    def expr2(self, p):
        return p.expr3

    @_("expr3 LAND expr4")
    def expr3(self, p):
        return _L(BinOper(oper='&&', left=p.expr3, right=p.expr4), p.lineno)

    @_("expr4")
    def expr3(self, p):
        return p.expr4

    @_("expr4 EQ expr5")
    @_("expr4 NE expr5")
    @_("expr4 LT expr5")
    @_("expr4 LE expr5")
    @_("expr4 GT expr5")
    @_("expr4 GE expr5")
    def expr4(self, p):
        return _L(BinOper(oper=p[1], left=p.expr4, right=p.expr5), p.lineno)

    @_("expr5")
    def expr4(self, p):
        return p.expr5

    @_("expr5 '+' expr6")
    @_("expr5 '-' expr6")
    def expr5(self, p):
        return _L(BinOper(oper=p[1], left=p.expr5, right=p.expr6), p.lineno)

    @_("expr6")
    def expr5(self, p):
        return p.expr6

    @_("expr6 '*' expr7")
    @_("expr6 '/' expr7")
    @_("expr6 '%' expr7")
    def expr6(self, p):
        return _L(BinOper(oper=p[1], left=p.expr6, right=p.expr7), p.lineno)

    @_("expr7")
    def expr6(self, p):
        return p.expr7

    @_("expr7 '^' expr8")
    def expr7(self, p):
        return _L(BinOper(oper='^', left=p.expr7, right=p.expr8), p.lineno)

    @_("expr8")
    def expr7(self, p):
        return p.expr8

    @_("'-' expr8")
    @_("NOT expr8")
    def expr8(self, p):
        # El operador '!' debe usar UnaryOp
        if p[0] == '!':
            # Asumiendo que UnaryOp toma el operador '!'
            return _L(UnaryOp(op='!', expr=p.expr8), p.lineno)
        else:
            # El operador '-' (negativo unario) usa UnaryOper
            return _L(UnaryOper(oper=p[0], expr=p.expr8), p.lineno)

    @_("INC expr8")
    def expr8(self, p):
        return _L(PreInc(expr=p.expr8), p.lineno)

    @_("DEC expr8")
    def expr8(self, p):
        return _L(PreDec(expr=p.expr8), p.lineno)

    @_("expr9")
    def expr8(self, p):
        return p.expr9

    @_("expr9 INC")
    def expr9(self, p):
        return _L(PostfixOper(oper='++', expr=p.expr9), p.lineno)

    @_("expr9 DEC")
    def expr9(self, p):
        return _L(PostfixOper(oper='--', expr=p.expr9), p.lineno)

    @_("group")
    def expr9(self, p):
        return p.group

    @_("'(' expr ')'")
    def group(self, p):
        return p.expr

    @_("ID '(' opt_expr_list ')'")   # llamada a función
    def group(self, p):
        return _L(Call(func=Identifier(name=p.ID), args=p.opt_expr_list), p.lineno)

    @_("ID '[' expr ']'")
    def group(self, p):
        return _L(ArrayIndex(array=Identifier(name=p.ID), index=p.expr), p.lineno)

    @_("factor")
    def group(self, p):
        return p.factor

    @_("'[' expr ']'")
    def index(self, p):
        return p.expr

    @_("ID")
    def factor(self, p):
        return _L(Identifier(name=p.ID), p.lineno)

    @_("INTEGER_LITERAL")
    def factor(self, p):
        return _L(Integer(value=p.INTEGER_LITERAL), p.lineno)

    @_("FLOAT_LITERAL")
    def factor(self, p):
        return _L(Float(value=p.FLOAT_LITERAL), p.lineno)

    @_("CHAR_LITERAL")
    def factor(self, p):
        return _L(Char(value=p.CHAR_LITERAL), p.lineno)

    @_("STRING_LITERAL")
    def factor(self, p):
        return _L(String(value=p.STRING_LITERAL), p.lineno)

    @_("TRUE")
    def factor(self, p):
        return _L(Boolean(value=True), p.lineno)

    @_("FALSE")
    def factor(self, p):
        return _L(Boolean(value=False), p.lineno)
        
    @_("ARRAY '(' opt_expr_list ')'")   # cubre el caso en que 'array' es palabra reservada
    def group(self, p):
        return _L(Call(func=Identifier(name="array"), args=p.opt_expr_list), p.lineno)

    # ------------------------------------------------------------------
    # TIPOS
    # ------------------------------------------------------------------
    @_("INTEGER")
    @_("FLOAT")
    @_("BOOLEAN")
    @_("CHAR")
    @_("STRING")
    @_("VOID")
    def type_simple(self, p):
        return p[0]
        # ADICIONAL: cuando el lexer no marcó la keyword y vino como ID
    @_("ID")
    def type_simple(self, p):
        kw = p.ID.lower()
        if kw in ("int", "float", "bool", "boolean", "char", "string", "void"):
            return "bool" if kw == "boolean" else kw   # normaliza a minúsculas coherentes
        # cualquier otro ID como tipo pasa tal cual (tu checker decidirá si es válido)
        return kw

    @_("ARRAY '[' ']' type_simple")
    @_("ARRAY '[' ']' type_array")
    def type_array(self, p):
        base = SimpleType(name=p.type_simple) if hasattr(p, "type_simple") else p.type_array
        return ArrayType(base=base, size=None)

    @_("ARRAY index type_simple")
    @_("ARRAY index type_array_sized")
    def type_array_sized(self, p):
        base = SimpleType(name=p.type_simple) if hasattr(p, "type_simple") else p.type_array_sized
        return ArrayType(base=base, size=p[1])

    @_("FUNCTION type_simple '(' opt_param_list ')'")
    @_("FUNCTION type_array_sized '(' opt_param_list ')'")
    def type_func(self, p):
        ret = SimpleType(name=p.type_simple) if hasattr(p, "type_simple") else p.type_array_sized
        return FuncType(ret=ret, params=p.opt_param_list)

    @_("empty")
    def opt_param_list(self, p):
        return []

    @_("param_list")
    def opt_param_list(self, p):
        return p.param_list

    @_("param_list ',' param")
    def param_list(self, p):
        return p.param_list + [p.param]

    @_("param")
    def param_list(self, p):
        return [p.param]

    @_("ID ':' type_simple")
    def param(self, p):
        return _L(Param(name=p.ID, type=SimpleType(name=p.type_simple)), p.lineno)

    @_("ID ':' type_array")
    def param(self, p):
        return _L(Param(name=p.ID, type=p.type_array), p.lineno)

    @_("ID ':' type_array_sized")
    def param(self, p):
        return _L(Param(name=p.ID, type=p.type_array_sized), p.lineno)

    # Vacío
    @_("")
    def empty(self, p):
        return None

    # Errores sintácticos
    def error(self, p):
        lineno = p.lineno if p else 'EOF'
        value = repr(p.value) if p else 'EOF'
        error(f"Syntax error at {value}", lineno)


# Utilidades para usar el parser directamente
def ast_to_dict(node):
    if isinstance(node, list):
        return [ast_to_dict(item) for item in node]
    elif hasattr(node, "__dict__"):
        return {k: ast_to_dict(v) for k, v in node.__dict__.items()}
    else:
        return node

def parse(txt: str):
    l = Lexer()
    tokens = list(l.tokenize(txt))   # evitar consumir el generador
    p = Parser()
    return p.parse(iter(tokens))

if __name__ == '__main__':
    import sys
    from rich.console import Console
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python parser.py <filename>")
    txt = open(sys.argv[1], encoding='utf-8').read()
    
    # Es crucial llamar a set_source si quieres ver el error con la línea de código
    import importlib
    errors = importlib.import_module("errors")
    errors.set_source(sys.argv[1], txt) 
    
    ast = parse(txt)
    
    if not errors.errors_detected():
        Console().print(ast.pretty())
