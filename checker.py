# checker.py — Análisis semántico minimal–sólido para bminor2llvm
from typing import Optional, List, Dict
from errors  import error, errors_detected
from model   import *           # Program, VarDecl, Assign, Identifier, BinOper, etc.
from symtab  import Symtab
from typesys import typenames, check_binop, check_unaryop

# ----------------------------
# Helpers de tipos
# ----------------------------
ALIASES = {"int": "integer", "bool": "boolean"}

def resolve_type(t: Optional[Type]) -> Optional[str]:
    if t is None:
        return None
    if isinstance(t, SimpleType):
        name = t.name.lower() if isinstance(t.name, str) else t.name
        return ALIASES.get(name, name)
    if isinstance(t, ArrayType):
        base = resolve_type(t.base)
        size_repr = ""
        if hasattr(t, "size") and t.size is not None:
            size_repr = getattr(t.size, "value", None)
            size_repr = str(size_repr) if size_repr is not None else ""
        return f"array[{size_repr}] {base}".strip()
    if isinstance(t, FuncType):
        r = resolve_type(t.ret) if t.ret else "void"
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
    if isinstance(val, bool):  return "boolean"
    if isinstance(val, int):   return "integer"
    if isinstance(val, float): return "float"
    if isinstance(val, str):   return "string" if len(val) != 1 else "char"
    return None

# ----------------------------
# Checker con despacho único
# ----------------------------
class Check(Visitor):
    @classmethod
    def run(cls, program: Program) -> Symtab:
        self = cls()
        self._fun_ret_stack: List[Optional[str]] = []
        self._fun_name_stack: List[str] = []
        self._saw_return_stack: List[bool] = []
        self._loop_depth: int = 0
        self._inits: Dict[int, Dict[str, bool]] = {}
        self._lhs_mode: bool = False
        global_env = Symtab("global")
        program.accept(self, global_env)
        return global_env

    # ---- tracking de inicialización ----
    def _init_map(self, env: Symtab) -> Dict[str, bool]:
        m = self._inits.get(id(env))
        if m is None:
            m = {}
            self._inits[id(env)] = m
        return m

    def _set_initialized(self, env: Symtab, name: str, value: bool = True):
        decl_env = self._find_decl_env(env, name)
        if decl_env is None:
            return
        self._init_map(decl_env)[name] = value

    def _is_initialized(self, env: Symtab, name: str) -> Optional[bool]:
        e = env
        while e is not None:
            m = self._inits.get(id(e))
            if m and name in m:
                return m[name]
            e = getattr(e, "parent", None)
        return None

    def _find_decl_env(self, env: Symtab, name: str) -> Optional[Symtab]:
        e = env
        while e is not None:
            try:
                _ = e.table[name]
                return e
            except Exception:
                pass
            e = getattr(e, "parent", None)
        return None

    def _expr_type(self, x, env) -> Optional[str]:
        if isinstance(x, Node):
            x.accept(self, env)
            return getattr(x, "type", None)
        return py_value_type(x)

    def _scope(self, name: str, parent: Symtab) -> Symtab:
        return Symtab(name, parent=parent)

    # ----------------------------
    # Único punto de entrada
    # ----------------------------
    def visit(self, n: Node, env: Symtab):
        method = getattr(self, f"_visit_{n.__class__.__name__}", None)
        if method is not None:
            return method(n, env)
        # fallback para nodos no mapeados (break/continue, etc.)
        cname = n.__class__.__name__
        if cname == "BreakStmt":
            if self._loop_depth <= 0:
                error("break fuera de un bucle", getattr(n, "lineno", None))
        elif cname == "ContinueStmt":
            if self._loop_depth <= 0:
                error("continue fuera de un bucle", getattr(n, "lineno", None))
        # sin tipo asignado

    # ----------------------------
    # Nodos
    # ----------------------------
    def _visit_Program(self, n: Program, env: Symtab):
        for s in n.body:
            s.accept(self, env)

    def _visit_Block(self, n: Block, env: Symtab):
        local = self._scope("block", env)
        for s in n.stmts:
            s.accept(self, local)

    def _visit_VarDecl(self, n: VarDecl, env: Symtab):
        tname = resolve_type(n.type)

        # --- Declaración de función (VarDecl con FuncType)
        if isinstance(n.type, FuncType):
            if not isinstance(n.init, Block):
                error(f"Falta cuerpo de función '{n.name}'", n.lineno)

            try:
                env.add(n.name, n)
            except Exception as ex:
                error(str(ex), n.lineno)

            fenv = self._scope(n.name, env)

            seen = set()
            for p in n.type.params:
                pname = p.name
                ptype = resolve_type(p.type)
                if not is_type(ptype, p.type):
                    error(f"Tipo inválido para parámetro '{pname}': {ptype}", p.lineno)
                if pname in seen:
                    error(f"Parámetro duplicado '{pname}'", p.lineno)
                seen.add(pname)
                try:
                    fenv.add(pname, p)
                    self._set_initialized(fenv, pname, True)
                except Exception as ex:
                    error(str(ex), p.lineno)

            expected_ret = resolve_type(n.type.ret) if n.type.ret else "void"
            self._fun_ret_stack.append(expected_ret)
            self._fun_name_stack.append(n.name)
            self._saw_return_stack.append(False)

            if isinstance(n.init, Block):
                n.init.accept(self, fenv)

            saw_ret = self._saw_return_stack.pop()
            self._fun_name_stack.pop()
            exp = self._fun_ret_stack.pop()
            if exp != "void" and not saw_ret:
                error(f"La función '{n.name}' no retorna un valor (retorno {exp})", n.lineno)
            return

        # --- Declaración de variable / arreglo ---
        if not is_type(tname, n.type):
            error(f"Tipo inválido para variable '{n.name}': {tname}", n.lineno)

        if isinstance(n.type, ArrayType):
            if isinstance(getattr(n.type, "size", None), Literal):
                val = n.type.size.value
                if isinstance(val, int) and val < 0:
                    error(f"Tamaño de array negativo en '{n.name}'", n.lineno)

        try:
            env.add(n.name, n)
        except Exception as ex:
            error(str(ex), n.lineno)

        if n.init is not None:
            if isinstance(n.type, ArrayType) and isinstance(n.init, Call) and isinstance(n.init.func, Identifier) and n.init.func.name == "array_init":
                base_expected = resolve_type(n.type.base)
                for arg in n.init.args:
                    at = self._expr_type(arg, env)
                    if at is not None and base_expected is not None and at != base_expected:
                        error(f"Elemento de array incompatible en '{n.name}': {at} → {base_expected}", n.lineno)
                n.init.type = resolve_type(n.type)
                self._set_initialized(env, n.name, True)
            else:
                init_t = self._expr_type(n.init, env)
                if init_t is not None and tname is not None and not types_equal(init_t, tname):
                    if not (isinstance(n.type, ArrayType) and init_t == "__array_ptr__"):
                        error(f"Incompatibilidad en inicialización de '{n.name}': {init_t} → {tname}", n.lineno)
                self._set_initialized(env, n.name, True)
        else:
            self._set_initialized(env, n.name, False)

    def _visit_PrintStmt(self, n: PrintStmt, env: Symtab):
        for a in n.args:
            if isinstance(a, Identifier):
                init = self._is_initialized(env, a.name)
                if init is False:
                    error(f"Uso de variable antes de asignación: {a.name}", a.lineno)
            self._expr_type(a, env)

    def _visit_ReturnStmt(self, n: ReturnStmt, env: Symtab):
        value_type = None
        if n.expr is not None:
            value_type = self._expr_type(n.expr, env)
        expected = self._fun_ret_stack[-1] if self._fun_ret_stack else None
        if expected is not None:
            if expected == "void":
                if value_type is not None:
                    error(f"Return con valor en función void (valor {value_type})", n.lineno)
            else:
                if value_type != expected:
                    error(f"Tipo de return inválido: {value_type} → se esperaba {expected}", n.lineno)
                self._saw_return_stack[-1] = True

    def _visit_IfStmt(self, n: IfStmt, env: Symtab):
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del if debe ser boolean", n.lineno)
        if n.then:
            n.then.accept(self, self._scope("then", env))
        if n.otherwise:
            n.otherwise.accept(self, self._scope("else", env))

    def _visit_WhileStmt(self, n: WhileStmt, env: Symtab):
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del while debe ser boolean", n.lineno)
        self._loop_depth += 1
        if n.body:
            n.body.accept(self, self._scope("while", env))
        self._loop_depth -= 1

    def _visit_DoWhileStmt(self, n: DoWhileStmt, env: Symtab):
        self._loop_depth += 1
        if n.body:
            n.body.accept(self, self._scope("do", env))
        self._loop_depth -= 1
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del do-while debe ser boolean", n.lineno)

    def _visit_ForStmt(self, n: ForStmt, env: Symtab):
        local = self._scope("for", env)
        self._loop_depth += 1
        if n.init:
            if isinstance(n.init, Node):
                n.init.accept(self, local)
            else:
                self._expr_type(n.init, local)
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
        self._loop_depth -= 1

    def _visit_Identifier(self, n: Identifier, env: Symtab):
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
            n.type = resolve_type(getattr(decl, "type", None))
        if not self._lhs_mode:
            init = self._is_initialized(env, n.name)
            if init is False:
                error(f"Uso de variable antes de asignación: {n.name}", n.lineno)

    def _visit_Assign(self, n: Assign, env: Symtab):
        self._lhs_mode = True
        if isinstance(n.target, Node):
            n.target.accept(self, env)
        else:
            self._expr_type(n.target, env)
        self._lhs_mode = False

        lhs_t = getattr(n.target, "type", None)
        rhs_t = self._expr_type(n.value, env)

        if lhs_t is not None and rhs_t is not None and not types_equal(lhs_t, rhs_t):
            if not (lhs_t and lhs_t.startswith("array") and rhs_t == "__array_ptr__"):
                error(f"Tipos incompatibles en asignación: {lhs_t} = {rhs_t}", n.lineno)

        if isinstance(n.target, Identifier):
            self._set_initialized(env, n.target.name, True)

        n.type = lhs_t or rhs_t

    def _visit_BinOper(self, n: BinOper, env: Symtab):
        lt = self._expr_type(n.left, env)
        rt = self._expr_type(n.right, env)
        res = check_binop(n.oper, lt, rt)
        if res is None:
            error(f"Operación inválida: {lt} {n.oper} {rt}", n.lineno)
            n.type = None
        else:
            n.type = res

    def _visit_UnaryOper(self, n: UnaryOper, env: Symtab):
        et = self._expr_type(n.expr, env)
        res = check_unaryop(n.oper, et)
        if res is None:
            error(f"Operador unario inválido: {n.oper} {et}", n.lineno)
            n.type = None
        else:
            n.type = res

    def _visit_PostfixOper(self, n: PostfixOper, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error(f"El operador {n.oper} requiere 'integer', llegó {et}", n.lineno)
        n.type = et

    def _visit_PreInc(self, n: PreInc, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error("El operador ++ requiere 'integer'", n.lineno)
        n.type = et

    def _visit_PreDec(self, n: PreDec, env: Symtab):
        et = self._expr_type(n.expr, env)
        if et != "integer":
            error("El operador -- requiere 'integer'", n.lineno)
        n.type = et

    def _visit_ArrayIndex(self, n: ArrayIndex, env: Symtab):
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

    def _visit_Call(self, n: Call, env: Symtab):
        # Built-ins
        if isinstance(n.func, Identifier):
            fname = n.func.name
            if fname == "print":
                for a in n.args:
                    self._expr_type(a, env)
                n.type = "void"
                return
            if fname == "array":
                if len(n.args) != 1:
                    error("array(n) espera 1 argumento", n.lineno)
                _ = self._expr_type(n.args[0], env)
                n.type = "__array_ptr__"
                return


        if isinstance(n.func, Identifier) and n.func.name == "array_length":
            if len(n.args) != 1:
                error("array_length espera 1 argumento", n.lineno)
            # Forzamos el tipo de retorno a integer para que i < array_length(...) sea boolean
            _ = self._expr_type(n.args[0], env)   # opcional: valida que sea array
            n.type = "integer"
            return
        
        # Función de usuario
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

        n.type = resolve_type(fn_decl.type.ret) if fn_decl.type.ret else "void"

    def _visit_Literal(self, n: Literal, env: Symtab):
        pass

# ----------------------------
# API que espera bminor2llvm.py
# ----------------------------
def check(program):
    return Check.run(program)
