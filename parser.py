
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# PARSER (SLY) — Versión comentada
# -----------------------------------------------------------------------------
# Este parser usa SLY (similar a PLY) para convertir una secuencia de tokens
# del lexer en un AST (árbol de sintaxis abstracta). La gramática escrita aquí
# describe cómo se deben escribir las construcciones del lenguaje (if, for,
# funciones, tipos, arrays, expresiones, etc.). Cada regla crea nodos del AST
# definidos en model_filled.py.
# -----------------------------------------------------------------------------

import logging
import sly
from rich import print

# Importamos el lexer del profe y la utilidad de errores del proyecto.
from lexer  import Lexer
from errors import error, errors_detected

# Importamos los nodos del AST que definimos.
from model import *

# Utilidad: setea el número de línea en el nodo y lo devuelve.
def _L(node, lineno):
    node.lineno = lineno
    return node

class Parser(sly.Parser):
    # ------------------------------------------------------------
    # Configuración básica de SLY
    # ------------------------------------------------------------
    log = logging.getLogger()
    log.setLevel(logging.ERROR)       # Silencia logs de SLY por defecto
    expected_shift_reduce = 1         # (Opcional) advertencia típica por "dangling else"
    debugfile='grammar.txt'           # Archivo con trazas si se activa debug

    # Tomamos todos los tokens del lexer
    tokens = Lexer.tokens

    # ------------------------------------------------------------
    # PROGRAMA
    #   prog -> decl_list
    # ------------------------------------------------------------
    @_("decl_list")
    def prog(self, p):
        # Raíz del árbol: una lista de declaraciones/sentencias
        return _L(Program(p.decl_list), getattr(p, "lineno", None))

    # ============================================================
    # DECLARACIONES
    # ============================================================
    # Lista de declaraciones
    @_("decl decl_list")
    def decl_list(self, p):
        return [ p.decl ] + p.decl_list

    @_("empty")
    def decl_list(self, p):
        return []

    # ----- Declaraciones de variables/tipos/funciones (solo tipo) -----
    @_("ID ':' type_simple ';'")
    def decl(self, p):
        # x : integer;
        return _L(VarDecl(name=p.ID, type=SimpleType(p.type_simple)), p.lineno)

    @_("ID ':' type_array_sized ';'")
    def decl(self, p):
        # a : array[10] integer;
        return _L(VarDecl(name=p.ID, type=p.type_array_sized), p.lineno)

    @_("ID ':' type_func ';'")
    def decl(self, p):
        # f : function integer(int a, float b);
        return _L(VarDecl(name=p.ID, type=p.type_func), p.lineno)

    # ----- Declaraciones con inicialización -----
    @_("decl_init")
    def decl(self, p):
        return p.decl_init

    @_("ID ':' type_simple '=' expr ';'")
    def decl_init(self, p):
        # x : integer = 5;
        return _L(VarDecl(name=p.ID, type=SimpleType(p.type_simple), init=p.expr), p.lineno)

    @_("ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'")
    def decl_init(self, p):
        # a : array[3] integer = {1, 2, 3};
        # Lo modelamos como una "llamada" pseudo-funcional para inicialización de arrays.
        init_expr = _L(Call(func=Identifier("array_init"), args=p.opt_expr_list), p.lineno)
        return _L(VarDecl(name=p.ID, type=p.type_array_sized, init=init_expr), p.lineno)

    @_("ID ':' type_func '=' '{' opt_stmt_list '}'")
    def decl_init(self, p):
        # g : function integer(int a) = { ...cuerpo... }
        # Guardamos el cuerpo como Block en el campo init; el tipo es FuncType.
        body = _L(Block(p.opt_stmt_list), p.lineno)
        t = p.type_func
        return _L(VarDecl(name=p.ID, type=t, init=body), p.lineno)

    # ============================================================
    # SENTENCIAS (STATEMENTS)
    # ============================================================
    # Lista de sentencias opcional (para cuerpos de bloques/funciones)
    @_("stmt_list")
    def opt_stmt_list(self, p):
        return p.stmt_list

    @_("empty")
    def opt_stmt_list(self, p):
        return []

    @_("stmt stmt_list")
    def stmt_list(self, p):
        return [p.stmt] + p.stmt_list

    @_("stmt")
    def stmt_list(self, p):
        return [p.stmt]

    # stmt puede ser open o closed (para resolver dangling-else)
    @_("open_stmt")
    @_("closed_stmt")
    def stmt(self, p):
        return p[0]

    # Sentencias "cerradas": no quedan colgando (if con else, for completo, etc.)
    @_("if_stmt_closed")
    @_("for_stmt_closed")
    @_("while_stmt")        
    @_("do_while_stmt")   
    @_("simple_stmt")
    def closed_stmt(self, p):
        return p[0]

    # Sentencias "abiertas": podrían aceptar un else adicional más adelante
    @_("if_stmt_open",
       "for_stmt_open")
    def open_stmt(self, p):
        return p[0]

    # ------------------------------
    # IF (manejo open/closed)
    # ------------------------------
    @_("IF '(' opt_expr ')'")
    def if_cond(self, p):
        # Sólo parsea la cabecera del if y retorna la condición
        return p.opt_expr

    @_("if_cond closed_stmt ELSE closed_stmt")
    def if_stmt_closed(self, p):
        # if (cond) stmt1 else stmt2;
        return _L(IfStmt(cond=p.if_cond, then=p.closed_stmt0, otherwise=p.closed_stmt1), p.lineno)

    @_("if_cond stmt")
    def if_stmt_open(self, p):
        # if (cond) stmt   (sin else todavía)
        return _L(IfStmt(cond=p.if_cond, then=p.stmt, otherwise=None), p.lineno)

    @_("if_cond closed_stmt ELSE if_stmt_open")
    def if_stmt_open(self, p):
        # if (cond) closed else (if abierto)   -> sigue "colgando"
        return _L(IfStmt(cond=p.if_cond, then=p.closed_stmt, otherwise=p.if_stmt_open), p.lineno)

    # ------------------------------
    # FOR (clásico: for (init; cond; step) stmt)
    # ------------------------------
    @_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
    def for_header(self, p):
        # Devuelve una tupla con (init, cond, step)
        return (p.opt_expr0, p.opt_expr1, p.opt_expr2)

    @_("for_header open_stmt")
    def for_stmt_open(self, p):
        i,c,s = p.for_header
        return _L(ForStmt(init=i, cond=c, step=s, body=p.open_stmt), p.lineno)

    @_("for_header closed_stmt")
    def for_stmt_closed(self, p):
        i,c,s = p.for_header
        return _L(ForStmt(init=i, cond=c, step=s, body=p.closed_stmt), p.lineno)
    
    # ------------------------------
    # WHILE
    # ------------------------------
    @_("WHILE '(' opt_expr ')' stmt")
    def while_stmt(self, p):
        return _L(WhileStmt(cond=p.opt_expr, body=p.stmt), p.lineno)

    # ------------------------------
    # DO-WHILE
    # do { stmt_list } while (cond) ;
    # ------------------------------
    @_("DO block_stmt WHILE '(' opt_expr ')' ';'")
    def do_while_stmt(self, p):
        return _L(DoWhileStmt(body=p.block_stmt, cond=p.opt_expr), p.lineno)



    # ------------------------------
    # Sentencia simple
    # ------------------------------
    @_("print_stmt")
    @_("return_stmt")
    @_("block_stmt")
    @_("decl")
    @_("expr ';'")
    def simple_stmt(self, p):
        # Si viene de "expr ';'", ya es una expresión (asignación, llamada, etc.)
        return p[0]

    # print(expr1, expr2, ...);
    @_("PRINT opt_expr_list ';'")
    def print_stmt(self, p):
        return _L(PrintStmt(args=p.opt_expr_list), p.lineno)

    # return [expr] ;
    @_("RETURN opt_expr ';'")
    def return_stmt(self, p):
        return _L(ReturnStmt(expr=p.opt_expr), p.lineno)

    # { stmt_list }
    @_("'{' stmt_list '}'")
    def block_stmt(self, p):
        return _L(Block(p.stmt_list), p.lineno)

    # ============================================================
    # EXPRESIONES
    # ============================================================
    # Listas de expresiones (para print, llamadas, inicializadores de arrays)
    @_("empty")
    def opt_expr_list(self, p):
        return []

    @_("expr_list")
    def opt_expr_list(self, p):
        return p.expr_list

    @_("expr ',' expr_list")
    def expr_list(self, p):
        return [p.expr] + p.expr_list

    @_("expr")
    def expr_list(self, p):
        return [p.expr]

    # Expresión opcional (para if, for init/cond/step, return)
    @_("empty")
    def opt_expr(self, p):
        return None

    @_("expr")
    def opt_expr(self, p):
        return p.expr

    # Gramática de expresiones por niveles de precedencia
    @_("expr1")
    def expr(self, p):
        return p.expr1

    # Asignación: lval = expr1
    @_("lval '=' expr1")
    def expr1(self, p):
        return _L(Assign(target=p.lval, value=p.expr1), p.lineno)

    @_("expr2")
    def expr1(self, p):
        return p.expr2

    # L-values posibles: ID o ID[index]
    @_("ID")
    def lval(self, p):
        return _L(Identifier(p.ID), p.lineno)

    @_("ID index")
    def lval(self, p):
        return _L(ArrayIndex(array=Identifier(p.ID), index=p.index), p.lineno)

    # expr2: OR lógico
    @_("expr2 LOR expr3")
    def expr2(self, p):
        return _L(BinOper('||', p.expr2, p.expr3), p.lineno)

    @_("expr3")
    def expr2(self, p):
        return p.expr3

    # expr3: AND lógico
    @_("expr3 LAND expr4")
    def expr3(self, p):
        return _L(BinOper('&&', p.expr3, p.expr4), p.lineno)

    @_("expr4")
    def expr3(self, p):
        return p.expr4

    # expr4: comparaciones
    @_("expr4 EQ expr5")
    @_("expr4 NE expr5")
    @_("expr4 LT expr5")
    @_("expr4 LE expr5")
    @_("expr4 GT expr5")
    @_("expr4 GE expr5")
    def expr4(self, p):
        return _L(BinOper(p[1], p.expr4, p.expr5), p.lineno)

    @_("expr5")
    def expr4(self, p):
        return p.expr5

    # expr5: suma/resta
    @_("expr5 '+' expr6")
    @_("expr5 '-' expr6")
    def expr5(self, p):
        return _L(BinOper(p[1], p.expr5, p.expr6), p.lineno)

    @_("expr6")
    def expr5(self, p):
        return p.expr6

    # expr6: multiplicación/división/módulo
    @_("expr6 '*' expr7")
    @_("expr6 '/' expr7")
    @_("expr6 '%' expr7")
    def expr6(self, p):
        return _L(BinOper(p[1], p.expr6, p.expr7), p.lineno)

    @_("expr7")
    def expr6(self, p):
        return p.expr7

    # expr7: potencia (asociatividad derecha no se maneja aquí; es binaria simple)
    @_("expr7 '^' expr8")
    def expr7(self, p):
        return _L(BinOper('^', p.expr7, p.expr8), p.lineno)

    @_("expr8")
    def expr7(self, p):
        return p.expr8

    # expr8: unarios '-' y '!' (negación lógica)
    @_("'-' expr8")
    @_("'!' expr8")
    def expr8(self, p):
        return _L(UnaryOper(p[0], p.expr8), p.lineno)
    
    @_("INC expr8")
    def expr8(self, p):
        return _L(PreInc(p.expr8), p.lineno)

    @_("DEC expr8")
    def expr8(self, p):
        return _L(PreDec(p.expr8), p.lineno)


    @_("expr9")
    def expr8(self, p):
        return p.expr9

    # expr9: postfijos x++ / x--
    @_("expr9 INC")
    def expr9(self, p):
        return _L(PostfixOper('++', p.expr9), p.lineno)

    @_("expr9 DEC")
    def expr9(self, p):
        return _L(PostfixOper('--', p.expr9), p.lineno)

    # group: (expr) | llamada | indexación | factor
    @_("group")
    def expr9(self, p):
        return p.group

    @_("'(' expr ')'")
    def group(self, p):
        return p.expr

    @_("ID '(' opt_expr_list ')'")
    def group(self, p):
        # f(a,b,c)
        return _L(Call(func=Identifier(p.ID), args=p.opt_expr_list), p.lineno)

    @_("ID index")
    def group(self, p):
        # a[i]
        return _L(ArrayIndex(array=Identifier(p.ID), index=p.index), p.lineno)

    @_("factor")
    def group(self, p):
        return p.factor

    # Indexación: [expr]
    @_("'[' expr ']'")
    def index(self, p):
        return p.expr

    # Factores: identificadores y literales
    @_("ID")
    def factor(self, p):
        return _L(Identifier(p.ID), p.lineno)

    @_("INTEGER_LITERAL")
    def factor(self, p):
        return _L(Integer(p.INTEGER_LITERAL), p.lineno)

    @_("FLOAT_LITERAL")
    def factor(self, p):
        return _L(Float(p.FLOAT_LITERAL), p.lineno)

    @_("CHAR_LITERAL")
    def factor(self, p):
        return _L(Char(p.CHAR_LITERAL), p.lineno)

    @_("STRING_LITERAL")
    def factor(self, p):
        return _L(String(p.STRING_LITERAL), p.lineno)

    @_("TRUE")
    @_("FALSE")
    def factor(self, p):
        # Los tokens TRUE/FALSE traen su lexema ('true'/'false')
        return _L(Boolean(p[0] == 'true'), p.lineno)

    # ============================================================
    # TIPOS
    # ============================================================
    # Tipos simples: integer | float | boolean | char | string | void
    @_("INTEGER")
    @_("FLOAT")
    @_("BOOLEAN")
    @_("CHAR")
    @_("STRING")
    @_("VOID")
    def type_simple(self, p):
        # El lexer ya normaliza el lexema (p.ej. 'integer')
        return p[0]

    # Array sin tamaño (para parámetros) o anidado: array [] T
    @_("ARRAY '[' ']' type_simple")
    @_("ARRAY '[' ']' type_array")
    def type_array(self, p):
        base = SimpleType(p.type_simple) if hasattr(p, "type_simple") else p.type_array
        return ArrayType(base=base, size=None)

    # Array con tamaño: array [N] T
    @_("ARRAY index type_simple")
    @_("ARRAY index type_array_sized")
    def type_array_sized(self, p):
        base = SimpleType(p.type_simple) if hasattr(p, "type_simple") else p.type_array_sized
        return ArrayType(base=base, size=p.index)

    # Tipo función: function T (parametros)
    @_("FUNCTION type_simple '(' opt_param_list ')'")
    @_("FUNCTION type_array_sized '(' opt_param_list ')'")
    def type_func(self, p):
        ret = SimpleType(p.type_simple) if hasattr(p, "type_simple") else p.type_array_sized
        return FuncType(ret=ret, params=p.opt_param_list)

    # Parámetros (opcionales)
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

    # Definiciones de parámetro: id : tipo
    @_("ID ':' type_simple")
    def param(self, p):
        return _L(Param(name=p.ID, type=SimpleType(p.type_simple)), p.lineno)

    @_("ID ':' type_array")
    def param(self, p):
        return _L(Param(name=p.ID, type=p.type_array), p.lineno)

    @_("ID ':' type_array_sized")
    def param(self, p):
        return _L(Param(name=p.ID, type=p.type_array_sized), p.lineno)

    # Producción vacía
    @_("")
    def empty(self, p):
        return None

    # ------------------------------------------------------------
    # Manejo de errores sintácticos
    # ------------------------------------------------------------
    def error(self, p):
        # p puede ser None si llegamos a EOF inesperadamente
        lineno = p.lineno if p else 'EOF'
        value = repr(p.value) if p else 'EOF'
        error(f'Syntax error at {value}', lineno)

# ---------------------------------------------
# Utilidades para usar el parser directamente
# ---------------------------------------------
def ast_to_dict(node):
    """Convierte el AST en un dict/list para poder volcarlo a JSON
    (útil para debug o pruebas)."""
    if isinstance(node, list):
        return [ast_to_dict(item) for item in node]
    elif hasattr(node, "__dict__"):
        return {key: ast_to_dict(value) for key, value in node.__dict__.items()}
    else:
        return node

def parse(txt: str):
    """Tokeniza y parsea una cadena completa y devuelve el AST."""
    l = Lexer()
    p = Parser()
    return p.parse(l.tokenize(txt))

if __name__ == '__main__':
    import sys, json
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python parser_filled.py <filename>")
    txt = open(sys.argv[1], encoding='utf-8').read()
    ast = parse(txt)
    print(json.dumps(ast_to_dict(ast), ensure_ascii=False, indent=2))
