#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bminor2ir.py — Traductor de B-Minor a un IR de tres direcciones.

Uso básico:
    python bminor2ir.py archivo.bminor > out.ir

Suposiciones:
- Ya existen los módulos:
    - parser  con una función  parse(text) -> Program
    - checker con una función check(program)  (opcional, si ya está tipado)
    - model   con las clases del AST (Program, Function, VarDecl, BinOp, etc.)

- Los nombres de las clases y atributos pueden cambiar según tu proyecto,
  por eso el código está escrito de forma "por nombre de clase" y con muchos
  comentarios para que el estudiante pueda adaptar los `isinstance` y los
  campos (.expr, .left, .right, .op, etc.) a su propio `model.py`.

- IR de salida:
    * Encabezado de función:
        func <nombre>(a0, a1, ...):
    * Instrucciones de tres direcciones:
        t0 = const 5
        t1 = add t0, t0
        iflt t1, t0, L1
        goto L2
        label L1
        ...
        ret t3
    * Llamadas:
        param t0
        param t1
        call walk, 2 -> t2
"""

from __future__ import annotations
import sys
import importlib


# ============================================================
#  Utilidades de nombres temporales y etiquetas
# ============================================================

class NameFactory:
    """Esta clase se encarga de producir nombres únicos de temporales y etiquetas."""
    def __init__(self) -> None:
        self.temp_counter = 0
        self.label_counter = 0

    def new_temp(self) -> str:
        """Genera un nuevo nombre de temporal, por ejemplo t0, t1, t2, ..."""
        name = f"t{self.temp_counter}"
        self.temp_counter += 1
        return name

    def new_label(self, prefix: str = "L") -> str:
        """Genera una nueva etiqueta con un prefijo (por defecto L)."""
        name = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return name


# ============================================================
#  Generador de IR
# ============================================================

class IRGenerator:
    """
    Esta clase se encarga de recorrer el AST de B-Minor y generar
    una lista de instrucciones de IR de tres direcciones.

    El estudiante puede adaptar los métodos `_gen_stmt_*` y `_gen_expr_*`
    a los nombres reales de las clases del AST.
    """

    def __init__(self, name_factory: NameFactory) -> None:
        self.nf = name_factory
        self.lines: list[str] = []
        self.var_env: dict[str, str] = {}
        self.current_function: str | None = None

    # --------------------------------------------------------
    #  API pública principal
    # --------------------------------------------------------

    def gen_program(self, program) -> str:
        """
        Recorre el nodo raíz Program y genera el IR de todas las funciones
        y variables globales.
        """
        # Se asume que `program.decls` es una lista de declaraciones
        for d in getattr(program, "decls", []):
            clsname = type(d).__name__
            if clsname in ("Function", "FuncDecl", "FunctionDecl"):
                self._gen_function(d)
            elif clsname in ("VarDecl", "GlobalVarDecl"):
                self._gen_global(d)
            else:
                # El estudiante puede añadir más casos si su AST los tiene.
                pass

        return "\n".join(self.lines)

    # --------------------------------------------------------
    #  Declaraciones
    # --------------------------------------------------------

    def _gen_global(self, decl) -> None:
        """
        Genera la declaración IR de una variable global.

        Se asume algo como:
            name: str
            type: ...
            init: expresión opcional
        """
        name = getattr(decl, "name", None)
        init = getattr(decl, "init", None)

        if init is None:
            # Global sin inicializador
            self.lines.append(f"global {name}")
        else:
            # Global con inicializador (se compila como constante)
            t = self._gen_expr(init)
            self.lines.append(f"global {name} = {t}")

    def _gen_function(self, func) -> None:
        """
        Genera el IR de una función completa, incluyendo su cuerpo.

        Se asume una estructura aproximada:
            func.name: str
            func.params: lista de VarDecl
            func.body: Block o similar
        """
        self.current_function = getattr(func, "name", "<anon>")
        self.var_env = {}  # nueva tabla de variables para la función

        # Parámetros
        params = []
        for i, p in enumerate(getattr(func, "params", [])):
            pname = getattr(p, "name", f"arg{i}")
            # En el IR se nombran como a0, a1, ...
            ir_name = f"a{i}"
            self.var_env[pname] = ir_name
            params.append(ir_name)

        self.lines.append(f"func {self.current_function}({', '.join(params)}):")

        # Cuerpo
        body = getattr(func, "body", None)
        if body is not None:
            self._gen_stmt(body)

        # Por si alguna ruta de código no termina con return
        self.lines.append("    ret")

        self.lines.append("")  # línea en blanco para separar funciones
        self.current_function = None
        self.var_env = {}

    # --------------------------------------------------------
    #  Sentencias
    # --------------------------------------------------------

    def _gen_stmt(self, stmt) -> None:
        """Despacha la sentencia al método apropiado según el tipo de nodo."""
        clsname = type(stmt).__name__

        if clsname in ("Block", "StmtBlock"):
            # Se asume stmt.stmts como lista de sentencias
            for s in getattr(stmt, "stmts", []):
                self._gen_stmt(s)

        elif clsname in ("VarDecl", "LocalVarDecl"):
            self._gen_stmt_vardecl(stmt)

        elif clsname in ("Assign", "Assignment"):
            self._gen_stmt_assign(stmt)

        elif clsname in ("IfStmt", "IfElse", "If"):
            self._gen_stmt_if(stmt)

        elif clsname in ("WhileStmt", "While"):
            self._gen_stmt_while(stmt)

        elif clsname in ("ForStmt", "For"):
            self._gen_stmt_for(stmt)

        elif clsname in ("ReturnStmt", "Return"):
            self._gen_stmt_return(stmt)

        elif clsname in ("ExprStmt", "ExpressionStmt"):
            expr = getattr(stmt, "expr", None)
            if expr is not None:
                self._gen_expr(expr)  # se descarta el resultado

        else:
            # Si el AST tiene más tipos de sentencias, aquí se añaden.
            # También se puede imprimir un aviso para depuración.
            # print("Advertencia: sentencia no soportada:", clsname)
            pass

    def _gen_stmt_vardecl(self, decl) -> None:
        """
        Genera IR para declaraciones de variables locales.

        Se asume algo como:
            decl.name: str
            decl.init: expresión opcional
        """
        vname = getattr(decl, "name", None)
        if vname is None:
            return

        # El IR representa variables como nombres simbólicos locales.
        if vname not in self.var_env:
            self.var_env[vname] = vname

        init = getattr(decl, "init", None)
        if init is not None:
            t = self._gen_expr(init)
            self.lines.append(f"    {vname} = mov {t}")

    def _lhs_to_string(self, lhs) -> str:
        """
        Convierte el lado izquierdo de una asignación en un "destino" IR.
        Soporta variables simples y, opcionalmente, indexación de arreglos.
        """
        clsname = type(lhs).__name__
        if clsname in ("Identifier", "Var", "VarRef"):
            name = getattr(lhs, "name", None)
            # Busca en el entorno local; si no está, lo toma literal.
            return self.var_env.get(name, name)

        if clsname in ("IndexExpr", "ArrayIndex", "Subscript"):
            # Se asume algo como lhs.array y lhs.index (o lhs.indexes[0])
            arr = getattr(lhs, "array", None)
            idx = getattr(lhs, "index", None) or getattr(lhs, "index_expr", None)
            arr_name = self._lhs_to_string(arr)
            tidx = self._gen_expr(idx)
            tmp = self.nf.new_temp()
            # Se codifica como un "slot" arr[idx] en un temporal.
            self.lines.append(f"    {tmp} = addr {arr_name}, {tidx}")
            return f"*{tmp}"  # notación *tmp para "contenido en arr[idx]"

        # Si no se reconoce, se devuelve una representación genérica.
        return str(lhs)

    def _gen_stmt_assign(self, stmt) -> None:
        """
        Genera IR para una asignación.

        Se asume algo como:
            stmt.left, stmt.right    o   stmt.target, stmt.value
        """
        lhs = getattr(stmt, "left", None) or getattr(stmt, "target", None)
        rhs = getattr(stmt, "right", None) or getattr(stmt, "value", None)

        dest = self._lhs_to_string(lhs)
        rv = self._gen_expr(rhs)
        self.lines.append(f"    {dest} = mov {rv}")

    def _gen_stmt_if(self, stmt) -> None:
        """
        Genera IR para una sentencia if-else.

        Se asume algo como:
            stmt.cond, stmt.then_branch, stmt.else_branch
        """
        cond = getattr(stmt, "cond", None) or getattr(stmt, "condition", None)
        then_branch = getattr(stmt, "then_branch", None) or getattr(stmt, "then_stmt", None)
        else_branch = getattr(stmt, "else_branch", None) or getattr(stmt, "else_stmt", None)

        tcond = self._gen_expr(cond)
        l_true = self.nf.new_label("then")
        l_false = self.nf.new_label("else")
        l_end = self.nf.new_label("endif")

        # cond != 0
        self.lines.append(f"    ifne {tcond}, 0, {l_true}")
        self.lines.append(f"    goto {l_false}")
        self.lines.append(f"  label {l_true}")
        if then_branch is not None:
            self._gen_stmt(then_branch)
        self.lines.append(f"    goto {l_end}")

        self.lines.append(f"  label {l_false}")
        if else_branch is not None:
            self._gen_stmt(else_branch)
        self.lines.append(f"  label {l_end}")

    def _gen_stmt_while(self, stmt) -> None:
        """
        Genera IR para un while.

        Se asume:
            stmt.cond, stmt.body
        """
        cond = getattr(stmt, "cond", None) or getattr(stmt, "condition", None)
        body = getattr(stmt, "body", None)

        l_cond = self.nf.new_label("while_cond")
        l_body = self.nf.new_label("while_body")
        l_end = self.nf.new_label("while_end")

        self.lines.append(f"  label {l_cond}")
        tcond = self._gen_expr(cond)
        self.lines.append(f"    ifne {tcond}, 0, {l_body}")
        self.lines.append(f"    goto {l_end}")

        self.lines.append(f"  label {l_body}")
        if body is not None:
            self._gen_stmt(body)
        self.lines.append(f"    goto {l_cond}")
        self.lines.append(f"  label {l_end}")

    def _gen_stmt_for(self, stmt) -> None:
        """
        Genera IR para un for convirtiéndolo en un while.

        Se asume:
            stmt.init, stmt.cond, stmt.step, stmt.body
        """
        init = getattr(stmt, "init", None)
        cond = getattr(stmt, "cond", None) or getattr(stmt, "condition", None)
        step = getattr(stmt, "step", None) or getattr(stmt, "increment", None)
        body = getattr(stmt, "body", None)

        if init is not None:
            self._gen_stmt(init)

        l_cond = self.nf.new_label("for_cond")
        l_body = self.nf.new_label("for_body")
        l_end = self.nf.new_label("for_end")

        self.lines.append(f"  label {l_cond}")
        tcond = self._gen_expr(cond)
        self.lines.append(f"    ifne {tcond}, 0, {l_body}")
        self.lines.append(f"    goto {l_end}")

        self.lines.append(f"  label {l_body}")
        if body is not None:
            self._gen_stmt(body)
        if step is not None:
            self._gen_stmt(step)
        self.lines.append(f"    goto {l_cond}")
        self.lines.append(f"  label {l_end}")

    def _gen_stmt_return(self, stmt) -> None:
        """
        Genera IR para una sentencia return.

        Se asume un atributo .expr o .value para el retorno opcional.
        """
        expr = getattr(stmt, "expr", None) or getattr(stmt, "value", None)
        if expr is None:
            self.lines.append("    ret")
        else:
            t = self._gen_expr(expr)
            self.lines.append(f"    ret {t}")

    # --------------------------------------------------------
    #  Expresiones
    # --------------------------------------------------------

    def _gen_expr(self, expr) -> str:
        """Despacha la expresión al método adecuado y devuelve un temporal con el resultado."""
        clsname = type(expr).__name__

        if clsname in ("Integer", "IntLiteral", "Number"):
            value = getattr(expr, "value", None)
            t = self.nf.new_temp()
            self.lines.append(f"    {t} = const {value}")
            return t

        if clsname in ("Boolean", "BoolLiteral"):
            value = getattr(expr, "value", None)
            v = 1 if value else 0
            t = self.nf.new_temp()
            self.lines.append(f"    {t} = const {v}")
            return t

        if clsname in ("Identifier", "Var", "VarRef"):
            name = getattr(expr, "name", None)
            # Local o global: se devuelve el nombre IR que esté en el entorno
            return self.var_env.get(name, name)

        if clsname in ("StringLiteral", "String"):
            # Para simplificar, se guarda como constante "interna".
            value = getattr(expr, "value", "")
            t = self.nf.new_temp()
            self.lines.append(f'    {t} = const "{value}"')
            return t

        if clsname in ("UnaryOp", "UnaryExpr"):
            return self._gen_expr_unary(expr)

        if clsname in ("BinOp", "BinaryOp", "BinaryExpr"):
            return self._gen_expr_binary(expr)

        if clsname in ("CallExpr", "Call", "FuncCall"):
            return self._gen_expr_call(expr)

        if clsname in ("IndexExpr", "ArrayIndex", "Subscript"):
            return self._gen_expr_index(expr)

        # Si hay más tipos de expresiones, se pueden añadir.
        # print("Advertencia: expresión no soportada:", clsname)
        t = self.nf.new_temp()
        self.lines.append(f"    {t} = <unhandled_expr {clsname}>")
        return t

    def _gen_expr_unary(self, expr) -> str:
        """
        Genera IR para una expresión unaria.

        Se asume atributos:
            expr.op: str   (p.ej. '-', '!')
            expr.expr o expr.operand
        """
        op = getattr(expr, "op", None)
        sub = getattr(expr, "expr", None) or getattr(expr, "operand", None)
        v = self._gen_expr(sub)
        t = self.nf.new_temp()

        if op == "-":
            self.lines.append(f"    {t} = neg {v}")
        elif op == "!":
            # NOT lógico: t = (v == 0)
            self.lines.append(f"    {t} = eq {v}, 0")
        else:
            self.lines.append(f"    {t} = uop_{op} {v}")

        return t

    def _binop_mnemonic(self, op: str) -> str:
        """Traduce el operador de B-Minor al mnemónico de IR."""
        m = {
            "+": "add",
            "-": "sub",
            "*": "mul",
            "/": "div",
            "%": "mod",
            "<": "lt",
            "<=": "le",
            ">": "gt",
            ">=": "ge",
            "==": "eq",
            "!=": "ne",
            "&&": "and",
            "||": "or",
        }
        return m.get(op, f"op_{op}")

    def _gen_expr_binary(self, expr) -> str:
        """
        Genera IR para una expresión binaria.

        Se asume:
            expr.op: str
            expr.left, expr.right
        """
        left = getattr(expr, "left", None)
        right = getattr(expr, "right", None)
        op = getattr(expr, "op", None)

        t_left = self._gen_expr(left)
        t_right = self._gen_expr(right)
        t_res = self.nf.new_temp()
        mnem = self._binop_mnemonic(op)
        self.lines.append(f"    {t_res} = {mnem} {t_left}, {t_right}")
        return t_res

    def _gen_expr_call(self, expr) -> str:
        """
        Genera IR para una llamada a función.

        Se asume:
            expr.func: Identifier o similar (nombre)
            expr.args: lista de expresiones
        """
        func_node = getattr(expr, "func", None) or getattr(expr, "callee", None)
        fname = getattr(func_node, "name", str(func_node))
        args = getattr(expr, "args", []) or getattr(expr, "arguments", [])

        # Primero se generan los parámetros
        for a in args:
            ta = self._gen_expr(a)
            self.lines.append(f"    param {ta}")

        # Luego se hace la llamada
        t_res = self.nf.new_temp()
        self.lines.append(f"    call {fname}, {len(args)} -> {t_res}")
        return t_res

    def _gen_expr_index(self, expr) -> str:
        """
        Genera IR para una indexación de arreglo: arr[idx].

        Se asume:
            expr.array, expr.index (o index_expr)
        """
        arr = getattr(expr, "array", None)
        idx = getattr(expr, "index", None) or getattr(expr, "index_expr", None)

        arr_name = self._gen_expr(arr)
        t_idx = self._gen_expr(idx)
        t_addr = self.nf.new_temp()
        t_val = self.nf.new_temp()

        self.lines.append(f"    {t_addr} = addr {arr_name}, {t_idx}")
        self.lines.append(f"    {t_val} = load {t_addr}")
        return t_val


# ============================================================
#  Funciones auxiliares de carga de parser/checker
# ============================================================

def load_module(name: str):
    """
    Esta función se encarga de cargar un módulo por nombre.
    El estudiante puede ajustar y eliminar si va a importar fijo.
    """
    return importlib.import_module(name)


def compile_program(source: str, parser_mod_name: str = "parser", checker_mod_name: str | None = "checker") -> str:
    """
    Esta función se encarga de orquestar:
    1) parsear el código fuente,
    2) chequearlo semánticamente (si hay checker),
    3) generar el IR de tres direcciones.
    """
    parser_mod = load_module(parser_mod_name)
    parse = getattr(parser_mod, "parse")

    program = parse(source)

    if checker_mod_name is not None:
        try:
            checker_mod = load_module(checker_mod_name)
            check_fn = getattr(checker_mod, "check", None)
            if check_fn is not None:
                check_fn(program)
        except ModuleNotFoundError:
            # Si no hay checker, se ignora.
            pass

    nf = NameFactory()
    gen = IRGenerator(nf)
    return gen.gen_program(program)


# ============================================================
#  main()
# ============================================================

def main(argv: list[str]) -> None:
    """
    Esta función principal se encarga de:
    - leer el archivo .bminor,
    - llamar a compile_program,
    - escribir el IR por stdout.

    El estudiante puede extenderla para aceptar argumentos como:
        --parser NOMBRE_MODULO
        --checker NOMBRE_MODULO
    """
    if len(argv) < 2:
        print("Uso: python bminor2ir.py archivo.bminor [parser_mod] [checker_mod]", file=sys.stderr)
        sys.exit(1)

    filename = argv[1]
    parser_mod = argv[2] if len(argv) > 2 else "parser"
    checker_mod = argv[3] if len(argv) > 3 else "checker"

    with open(filename, "r", encoding="utf-8") as f:
        src = f.read()

    ir_txt = compile_program(src, parser_mod, checker_mod)
    sys.stdout.write(ir_txt)


if __name__ == "__main__":
    main(sys.argv)
