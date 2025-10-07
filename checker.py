# checker.py — Análisis semántico para tu model.py
from typing import Optional, List
from errors  import error, errors_detected
from model   import *           # Program, VarDecl, Assign, Identifier, BinOper, etc.
from symtab  import Symtab
from typesys import typenames, check_binop, check_unaryop

# -------------------------------------------------------
# Helpers de tipos
# -------------------------------------------------------
def resolve_type(t: Optional[Type]) -> Optional[str]:
    if t is None:
        return None
    if isinstance(t, SimpleType):
        return t.name
    if isinstance(t, ArrayType):
        base = resolve_type(t.base)
        size = None
        if isinstance(t.size, Integer):
            size = t.size.value
        elif isinstance(t.size, Literal) and isinstance(t.size.value, int):
            size = t.size.value
        size_repr = f"{size}" if size is not None else ""
        return f"array[{size_repr}] {base}".strip()
    if isinstance(t, FuncType):
        r = resolve_type(t.ret) if t.ret else 'void'
        ps = [resolve_type(p.type) for p in t.params]
        return f"function {r}({', '.join(ps)})"
    return None

def is_type(tname: Optional[str], original: Optional[Type] = None) -> bool:
    if tname is None:
        return False
    if isinstance(original, ArrayType):
        base = resolve_type(original.base)
        return base in typenames
    return tname in typenames

def array_base_from_name(tname: Optional[str]) -> Optional[str]:
    if not tname:
        return None
    if tname.startswith("array"):
        parts = tname.split()
        return parts[-1] if len(parts) >= 2 else None
    return None

def types_equal(a: Optional[str], b: Optional[str]) -> bool:
    return a == b

def py_value_type(val) -> Optional[str]:
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "string" if len(val) != 1 else "char"
    return None

# -------------------------------------------------------
# Checker
# -------------------------------------------------------
class Check(Visitor):
    @classmethod
    def run(cls, program: Program) -> Symtab:
        self = cls()
        self._fun_ret_stack: List[Optional[str]] = []
        global_env = Symtab("global")
        program.accept(self, global_env)
        return global_env

    # -------- util: tipo de “algo que puede ser nodo o valor crudo” --------
    def _expr_type(self, x, env) -> Optional[str]:
        if isinstance(x, Node):
            x.accept(self, env)
            return getattr(x, "type", None)
        # valor crudo del parser (int/float/str/bool)
        return py_value_type(x)

    # -------- Scopes --------
    def _scope(self, name: str, parent: Symtab) -> Symtab:
        return Symtab(name, parent=parent)

    # -------- Programa / Bloques --------
    def visit(self, n: Program, env: Symtab):
        for s in n.body:
            s.accept(self, env)

    def visit(self, n: Block, env: Symtab):
        local = self._scope("block", env)
        for s in n.stmts:
            s.accept(self, local)

    # -------- Declaraciones --------
    def visit(self, n: VarDecl, env: Symtab):
        tname = resolve_type(n.type)

        # Función declarada como VarDecl con tipo FuncType
        if isinstance(n.type, FuncType):
            try:
                env.add(n.name, n)
            except Exception as ex:
                error(str(ex), n.lineno); return

            fenv = self._scope(n.name, env)

            for p in n.type.params:
                pname = p.name
                ptype_name = resolve_type(p.type)
                if not is_type(ptype_name, p.type):
                    error(f"Tipo inválido para parámetro '{pname}': {ptype_name}", p.lineno)
                try:
                    fenv.add(pname, p)
                except Exception as ex:
                    error(str(ex), p.lineno)

            self._fun_ret_stack.append(resolve_type(n.type.ret) if n.type.ret else 'void')
            if n.init is not None:
                n.init.accept(self, fenv)
            self._fun_ret_stack.pop()
            return

        # Variable (incluye arrays)
        if not is_type(tname, n.type):
            error(f"Tipo inválido para variable '{n.name}': {tname}", n.lineno)
        try:
            env.add(n.name, n)
        except Exception as ex:
            error(str(ex), n.lineno)

        # Inicializador
        if n.init is not None:
            if isinstance(n.type, ArrayType) and isinstance(n.init, Call) and isinstance(n.init.func, Identifier) and n.init.func.name == "array_init":
                base_expected = resolve_type(n.type.base)

                size_expected = None
                if isinstance(n.type.size, Integer):
                    size_expected = n.type.size.value
                elif isinstance(n.type.size, Literal) and isinstance(n.type.size.value, int):
                    size_expected = n.type.size.value

                count = 0
                for arg in n.init.args:
                    at = self._expr_type(arg, env)
                    if at is not None and base_expected is not None and at != base_expected:
                        error(f"Elemento de array incompatible en '{n.name}': {at} → {base_expected}", n.lineno)
                    count += 1

                if size_expected is not None and count != size_expected:
                    error(f"Tamaño de inicialización incompatible para '{n.name}': {count} elementos, se esperaba {size_expected}", n.lineno)

                n.init.type = tname  # "array[n] base"
            else:
                init_t = self._expr_type(n.init, env)
                if init_t is not None and tname is not None and not types_equal(init_t, tname):
                    error(f"Incompatibilidad en inicialización de '{n.name}': {init_t} → {tname}", n.lineno)

    # -------- Sentencias --------
    def visit(self, n: PrintStmt, env: Symtab):
        for a in n.args:
            self._expr_type(a, env)

    def visit(self, n: ReturnStmt, env: Symtab):
        value_type = None
        if n.expr is not None:
            value_type = self._expr_type(n.expr, env)
        expected = self._fun_ret_stack[-1] if self._fun_ret_stack else None
        if expected is not None:
            if expected == 'void':
                if value_type is not None:
                    error(f"Return con valor en función void (valor {value_type})", n.lineno)
            else:
                if value_type != expected:
                    error(f"Tipo de return inválido: {value_type} → se esperaba {expected}", n.lineno)

    def visit(self, n: IfStmt, env: Symtab):
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del if debe ser boolean", n.lineno)
        if n.then:
            n.then.accept(self, self._scope("then", env))
        if n.otherwise:
            n.otherwise.accept(self, self._scope("else", env))

    def visit(self, n: WhileStmt, env: Symtab):
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del while debe ser boolean", n.lineno)
        if n.body:
            n.body.accept(self, self._scope("while", env))

    def visit(self, n: DoWhileStmt, env: Symtab):
        if n.body:
            n.body.accept(self, self._scope("do", env))
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del do-while debe ser boolean", n.lineno)

    def visit(self, n: ForStmt, env: Symtab):
        local = self._scope("for", env)
        if n.init:
            if isinstance(n.init, Node):
                n.init.accept(self, local)
            else:
                self._expr_type(n.init, local)  # por si el parser metiera crudos
        if n.cond:
            ct = self._expr_type(n.cond, local)
            if ct != "boolean":
                error("La condición del for debe ser boolean", n.lineno)
        if n.step:
            if isinstance(n.step, Node):
                n.step.accept(self, local)
            else:
                self._expr_type(n.step, local)
        if n.body:
            n.body.accept(self, local)

    # -------- Expresiones --------
    def visit(self, n: Identifier, env: Symtab):
        decl = env.get(n.name)
        if decl is None:
            error(f"Identificador no declarado: {n.name}", n.lineno)
            n.type = None
            return
        if isinstance(decl, VarDecl):
            n.type = resolve_type(decl.type)
        elif isinstance(decl, Param):
            n.type = resolve_type(decl.type)
        else:
            n.type = resolve_type(getattr(decl, 'type', None))

    def visit(self, n: Assign, env: Symtab):
        # LHS (debe ser nodo lvalue)
        if isinstance(n.target, Node):
            n.target.accept(self, env)
            lhs_t = getattr(n.target, "type", None)
        else:
            lhs_t = self._expr_type(n.target, env)  # fallback (no debería pasar)
        # RHS (nodo o crudo)
        rhs_t = self._expr_type(n.value, env)

        if lhs_t is not None and rhs_t is not None and not types_equal(lhs_t, rhs_t):
            error(f"Tipos incompatibles en asignación: {lhs_t} = {rhs_t}", n.lineno)
        n.type = lhs_t or rhs_t

    def visit(self, n: BinOper, env: Symtab):
        lt = self._expr_type(n.left, env)
        rt = self._expr_type(n.right, env)
        res = check_binop(n.oper, lt, rt)
        if res is None:
            error(f"Operación inválida: {lt} {n.oper} {rt}", n.lineno)
            n.type = None
        else:
            n.type = res

    def visit(self, n: UnaryOper, env: Symtab):
        et = self._expr_type(n.expr, env)
        res = check_unaryop(n.oper, et)
        if res is None:
            error(f"Operador unario inválido: {n.oper} {et}", n.lineno)
            n.type = None
        else:
            n.type = res

    def visit(self, n: PostfixOper, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error(f"El operador {n.oper} requiere 'integer', llegó {et}", n.lineno)
        n.type = et

    def visit(self, n: PreInc, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error("El operador ++ requiere 'integer'", n.lineno)
        n.type = et

    def visit(self, n: PreDec, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error("El operador -- requiere 'integer'", n.lineno)
        n.type = et

    def visit(self, n: ArrayIndex, env: Symtab):
        at = self._expr_type(n.array, env)
        it = self._expr_type(n.index, env)
        if it != "integer":
            error(f"El índice de arreglo debe ser 'integer', llegó {it}", n.lineno)
        base = array_base_from_name(at)
        if base is None:
            if at is not None:
                error(f"Intento de indexar un valor no-arreglo de tipo {at}", n.lineno)
            n.type = None
        else:
            n.type = base

    def visit(self, n: Call, env: Symtab):
        # array_init: literal de arreglo (se maneja en VarDecl)
        if isinstance(n.func, Identifier) and n.func.name == "array_init":
            for a in n.args:
                if isinstance(a, Node):
                    a.accept(self, env)
            n.type = None
            return

        fn_decl = env.get(n.func.name) if isinstance(n.func, Identifier) else None
        if fn_decl is None or not isinstance(fn_decl, VarDecl) or not isinstance(fn_decl.type, FuncType):
            error(f"Función '{getattr(n.func, 'name', '?')}' no declarada", n.lineno)
            n.type = None
            for a in n.args:
                if isinstance(a, Node):
                    a.accept(self, env)
            return

        params = fn_decl.type.params
        if len(n.args) != len(params):
            error(f"Argumentos inválidos para '{fn_decl.name}': se esperaban {len(params)}, llegaron {len(n.args)}", n.lineno)

        for arg, param in zip(n.args, params):
            at = self._expr_type(arg, env)
            pt = resolve_type(param.type)
            if at is not None and pt is not None and at != pt:
                error(f"Argumento incompatible en '{fn_decl.name}': {at} → {pt}", n.lineno)

        n.type = resolve_type(fn_decl.type.ret) if fn_decl.type.ret else 'void'

    def visit(self, n: Literal, env: Symtab):
        pass
