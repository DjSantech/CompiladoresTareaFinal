# checker.py — Análisis semántico para tu model.py
from typing import Optional, List, Tuple, Dict
from errors  import error, errors_detected
from model   import *           # Program, VarDecl, Assign, Identifier, BinOper, etc.
from symtab  import Symtab
from typesys import typenames, check_binop, check_unaryop

# -------------------------------------------------------
# Helpers de tipos y utilidades
# -------------------------------------------------------
def resolve_type(t: Optional[Type]) -> Optional[str]:
    if t is None:
        return None
    if isinstance(t, SimpleType):
        return t.name
    if isinstance(t, ArrayType):
        base = resolve_type(t.base)
        # Nota: la semántica exige tamaño entero literal no-negativo; se valida aparte.
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
        self._fun_ret_stack: List[Optional[str]] = []     # pila de tipos de retorno esperados
        self._fun_name_stack: List[str] = []              # pila de nombres de función
        self._saw_return_stack: List[bool] = []           # si hubo return en función no-void
        self._loop_depth: int = 0                         # para break/continue
        # tracking de inicialización por scope (id(scope) -> {name: bool})
        self._inits: Dict[int, Dict[str, bool]] = {}
        self._lhs_mode: bool = False                      # true cuando visitamos el LHS de una asignación
        global_env = Symtab("global")
        program.accept(self, global_env)
        return global_env

    # -------- inicialización tracking --------
    def _init_map(self, env: Symtab) -> Dict[str, bool]:
        m = self._inits.get(id(env))
        if m is None:
            m = {}
            self._inits[id(env)] = m
        return m

    def _set_initialized(self, env: Symtab, name: str, value: bool = True):
        # asigna en el scope donde está declarado el símbolo
        decl_env = self._find_decl_env(env, name)
        if decl_env is None:
            # no declarado: el error ya lo reportará visit(Identifier)
            return
        self._init_map(decl_env)[name] = value

    def _is_initialized(self, env: Symtab, name: str) -> Optional[bool]:
        # busca hacia arriba
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
                sym = e.table[name]  # asumiendo .table dict interno
                return e
            except Exception:
                pass
            e = getattr(e, "parent", None)
        return None

    # -------- util: tipo de “algo que puede ser nodo o valor crudo” --------
    def _expr_type(self, x, env) -> Optional[str]:
        if isinstance(x, Node):
            x.accept(self, env)
            return getattr(x, "type", None)
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

        # --- Declaración de función (VarDecl con FuncType)
        if isinstance(n.type, FuncType):
            # Regla especial para main: retorno debe ser void
            if n.name == "main":
                ret = resolve_type(n.type.ret) if n.type.ret else "void"
                if ret != "void":
                    error("Tipo de retorno inválido para 'main' (debe ser void)", n.lineno)
                # Si además quieres forzar 0 parámetros, descomenta:
                # if n.type.params:
                #     error("'main' no debe recibir parámetros", n.lineno)

            # Debe tener cuerpo (Block) → error 23
            if not isinstance(n.init, Block):
                error(f"Falta cuerpo de función '{n.name}'", n.lineno)

            # Registrar la función en el scope
            try:
                env.add(n.name, n)
            except Exception as ex:
                error(str(ex), n.lineno)   # dup de nombre (var/func) → errores 1 ó 7
                # aun así seguimos para intentar detectar más errores

            # Scope de función
            fenv = self._scope(n.name, env)

            # Parámetros (duplicados y tipos válidos)
            seen_params = set()
            for p in n.type.params:
                pname = p.name
                ptype_name = resolve_type(p.type)
                if not is_type(ptype_name, p.type):
                    error(f"Tipo inválido para parámetro '{pname}': {ptype_name}", p.lineno)
                # En arrays en parámetros, típicamente sin tamaño
                if isinstance(p.type, ArrayType) and p.type.size is not None:
                    # puedes elegir si lo prohíbes (estilo C) o lo permites; aquí lo reportamos
                    error(f"Parámetro arreglo '{pname}' no debe tener tamaño explícito", p.lineno)
                # duplicado explícito (además del Symtab)
                if pname in seen_params:
                    error(f"Parámetro duplicado '{pname}'", p.lineno)
                seen_params.add(pname)

                try:
                    fenv.add(pname, p)
                    # parámetros se consideran inicializados
                    self._set_initialized(fenv, pname, True)
                except Exception as ex:
                    error(str(ex), p.lineno)

            # Empujar contexto de función
            expected_ret = resolve_type(n.type.ret) if n.type.ret else 'void'
            self._fun_ret_stack.append(expected_ret)
            self._fun_name_stack.append(n.name)
            self._saw_return_stack.append(False)

            # Visitar cuerpo
            if isinstance(n.init, Block):
                n.init.accept(self, fenv)

            # Si no-void y no hubo return → error 22
            saw_return = self._saw_return_stack.pop()
            self._fun_name_stack.pop()
            exp = self._fun_ret_stack.pop()
            if exp != "void" and not saw_return:
                error(f"La función '{n.name}' no retorna un valor (retorno {exp})", n.lineno)
            return

        # --- Declaración de variable o arreglo ---
        # Tipo válido
        if not is_type(tname, n.type):
            error(f"Tipo inválido para variable '{n.name}': {tname}", n.lineno)

        # Si es arreglo, validar tamaño (debe ser entero literal no-negativo)
        if isinstance(n.type, ArrayType):
            if n.type.size is not None:
                if not isinstance(n.type.size, Integer) and not (isinstance(n.type.size, Literal) and isinstance(n.type.size.value, int)):
                    error(f"Tamaño de array inválido para '{n.name}': debe ser entero literal", n.lineno)
                else:
                    size_val = n.type.size.value if isinstance(n.type.size, Literal) else None
                    if size_val is not None and size_val < 0:
                        error(f"Tamaño de array negativo en '{n.name}'", n.lineno)

        # Insertar en el scope (duplicados → error 1)
        try:
            env.add(n.name, n)
        except Exception as ex:
            error(str(ex), n.lineno)

        # Inicialización
        if n.init is not None:
            # Inicialización de arreglo: array_init(...)
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
                # considerar el arreglo "inicializado"
                self._set_initialized(env, n.name, True)
            else:
                init_t = self._expr_type(n.init, env)
                if init_t is not None and tname is not None and not types_equal(init_t, tname):
                    error(f"Incompatibilidad en inicialización de '{n.name}': {init_t} → {tname}", n.lineno)
                # queda inicializada
                self._set_initialized(env, n.name, True)
        else:
            # declarada pero no inicializada
            self._set_initialized(env, n.name, False)

    # -------- Sentencias --------
    def visit(self, n: PrintStmt, env: Symtab):
        for a in n.args:
            # Si es identificador y no está inicializado → error 20
            if isinstance(a, Identifier):
                init = self._is_initialized(env, a.name)
                if init is False:
                    error(f"Uso de variable antes de asignación: {a.name}", a.lineno)
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
                # marcar que vimos un return con valor
                self._saw_return_stack[-1] = True

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
        self._loop_depth += 1
        if n.body:
            n.body.accept(self, self._scope("while", env))
        self._loop_depth -= 1

    def visit(self, n: DoWhileStmt, env: Symtab):
        self._loop_depth += 1
        if n.body:
            n.body.accept(self, self._scope("do", env))
        self._loop_depth -= 1
        if n.cond:
            ct = self._expr_type(n.cond, env)
            if ct != "boolean":
                error("La condición del do-while debe ser boolean", n.lineno)

    def visit(self, n: ForStmt, env: Symtab):
        local = self._scope("for", env)
        self._loop_depth += 1
        if n.init:
            if isinstance(n.init, Node):
                # Si init es Assign y el LHS es un Identifier, marcar como inicializada
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

    # -------- Expresiones --------
    def visit(self, n: Identifier, env: Symtab):
        decl = env.get(n.name)
        if decl is None:
            error(f"Identificador no declarado: {n.name}", n.lineno)
            n.type = None
            return

        # tipo
        if isinstance(decl, VarDecl):
            n.type = resolve_type(decl.type)
        elif isinstance(decl, Param):
            n.type = resolve_type(decl.type)
        else:
            n.type = resolve_type(getattr(decl, 'type', None))

        # uso antes de asignación (solo si es lectura; en LHS no debe disparar)
        if not self._lhs_mode:
            init = self._is_initialized(env, n.name)
            if init is False:
                error(f"Uso de variable antes de asignación: {n.name}", n.lineno)

    def visit(self, n: Assign, env: Symtab):
        # LHS
        self._lhs_mode = True
        if isinstance(n.target, Node):
            n.target.accept(self, env)
        else:
            self._expr_type(n.target, env)
        self._lhs_mode = False

        lhs_t = getattr(n.target, "type", None)
        # RHS
        rhs_t = self._expr_type(n.value, env)

        if lhs_t is not None and rhs_t is not None and not types_equal(lhs_t, rhs_t):
            error(f"Tipos incompatibles en asignación: {lhs_t} = {rhs_t}", n.lineno)

        # si el target es un identificador simple, queda inicializado
        if isinstance(n.target, Identifier):
            self._set_initialized(env, n.target.name, True)

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
        # Los literales ya llevan su 'type' configurado por el constructor.
        pass

    # -------- Soporte opcional: Break/Continue fuera de bucle --------
    # Si tus nodos existen en model.py como BreakStmt/ContinueStmt, estos
    # visit serán usados. Si no existen, no pasará nada.
    def visit(self, n: Node, env: Symtab):
        # Fallback genérico para nodos sin método específico
        cname = n.__class__.__name__
        if cname == "BreakStmt":
            if self._loop_depth <= 0:
                error("break fuera de un bucle", getattr(n, "lineno", None))
        elif cname == "ContinueStmt":
            if self._loop_depth <= 0:
                error("continue fuera de un bucle", getattr(n, "lineno", None))
        # Para cualquier otro nodo desconocido, no hacemos nada.
