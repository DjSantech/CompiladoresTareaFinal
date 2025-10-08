# astprint.py
# -----------------------------------------------------------------------------
# 1) ASTPrinter (Graphviz)  -> genera .dot + imagen (png/svg/pdf)
# 2) print_prof(ast)        -> imprime el AST en el formato textual “del profe”
# 3) print_rich_tree(ast)   -> helper para imprimir el rich.Tree (si lo quieres desde aquí)
# -----------------------------------------------------------------------------

from graphviz import Digraph
from model import *
from typing import Optional, List

# =============================================================================
# 1) GRAPHVIZ: AST -> Digraph
# =============================================================================

class ASTPrinter(Visitor):
    node_defaults = {
        "shape": "ellipse",
        "color": "purple",
        "style": "filled",
    }
    edge_defaults = {"arrowhead": "normal"}

    def __init__(self):
        self.dot = Digraph("AST")
        self.dot.attr("node", **self.node_defaults)
        self.dot.attr("edge", **self.edge_defaults)
        self._seq = 0

    @property
    def name(self):
        self._seq += 1
        return f"n{self._seq:05d}"

    @classmethod
    def render(cls, n: Node) -> Digraph:
        p = cls()
        n.accept(p)
        return p.dot

    # ---- helpers -------------------------------------------------------------
    def _new(self, label: str, **attrs) -> str:
        nid = self.name
        self.dot.node(nid, label=label, **attrs)
        return nid

    def _edge(self, a: str, b: str, label: Optional[str] = None):
        if label is None:
            self.dot.edge(a, b)
        else:
            self.dot.edge(a, b, label=label)

    def _maybe_child(self, parent_id: str, label: str, value):
        if value is None:
            return
        if isinstance(value, Node):
            self._edge(parent_id, value.accept(self), label)
        else:
            leaf = self._new(str(value))
            self._edge(parent_id, leaf, label)

    # ---- Programa / Bloques --------------------------------------------------
    def visit(self, n: Program):
        me = self._new("Program")
        for s in n.body:
            self._edge(me, s.accept(self))
        return me

    def visit(self, n: Block):
        me = self._new("Block")
        for s in n.stmts:
            self._edge(me, s.accept(self))
        return me

    # ---- Declaraciones / Tipos -----------------------------------------------
    def visit(self, n: VarDecl):
        me = self._new(f"VarDecl\\n{n.name}")
        if n.type is not None:
            self._edge(me, n.type.accept(self), "type")
        if n.init is not None:
            self._edge(me, n.init.accept(self), "init")
        return me

    def visit(self, n: SimpleType):
        return self._new(f"Type\\n{n.name}")

    def visit(self, n: ArrayType):
        me = self._new("ArrayType")
        if n.base is not None:
            self._edge(me, n.base.accept(self), "base")
        self._maybe_child(me, "size", n.size)
        return me

    def visit(self, n: FuncType):
        me = self._new("FuncType")
        if n.ret is not None:
            self._edge(me, n.ret.accept(self), "ret")
        if n.params:
            params_node = self._new("Params")
            self._edge(me, params_node)
            for p in n.params:
                self._edge(params_node, p.accept(self))
        return me

    def visit(self, n: Param):
        me = self._new(f"Param\\n{n.name}")
        if n.type is not None:
            self._edge(me, n.type.accept(self), "type")
        return me

    # ---- Sentencias ----------------------------------------------------------
    def visit(self, n: PrintStmt):
        me = self._new("Print")
        for a in n.args:
            self._edge(me, a.accept(self))
        return me

    def visit(self, n: ReturnStmt):
        me = self._new("Return")
        if n.expr is not None:
            self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: IfStmt):
        me = self._new("If")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        if n.then is not None:
            self._edge(me, n.then.accept(self), "then")
        if n.otherwise is not None:
            self._edge(me, n.otherwise.accept(self), "else")
        return me

    def visit(self, n: ForStmt):
        me = self._new("For")
        if n.init is not None:
            self._edge(me, n.init.accept(self), "init")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        if n.step is not None:
            self._edge(me, n.step.accept(self), "step")
        if n.body is not None:
            self._edge(me, n.body.accept(self), "body")
        return me

    def visit(self, n: WhileStmt):
        me = self._new("While")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        if n.body is not None:
            self._edge(me, n.body.accept(self), "body")
        return me

    def visit(self, n: DoWhileStmt):
        me = self._new("DoWhile")
        if n.body is not None:
            self._edge(me, n.body.accept(self), "body")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        return me

    # ---- Expresiones ---------------------------------------------------------
    def visit(self, n: Assign):
        me = self._new("=")
        self._edge(me, n.target.accept(self), "target")
        self._edge(me, n.value.accept(self), "value")
        return me

    def visit(self, n: Identifier):
        return self._new(f"Id({n.name})")

    def visit(self, n: BinOper):
        me = self._new(n.oper, shape="circle")
        self._edge(me, n.left.accept(self))
        self._edge(me, n.right.accept(self))
        return me

    def visit(self, n: UnaryOper):
        me = self._new(n.oper, shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PostfixOper):
        me = self._new(f"{n.oper}(post)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PreInc):
        me = self._new("++(pre)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PreDec):
        me = self._new("--(pre)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: Call):
        me = self._new("Call")
        if n.func is not None:
            self._edge(me, n.func.accept(self), "func")
        if n.args:
            args_node = self._new("Args")
            self._edge(me, args_node)
            for a in n.args:
                self._edge(args_node, a.accept(self))
        return me

    def visit(self, n: ArrayIndex):
        me = self._new("[]", shape="circle")
        self._edge(me, n.array.accept(self), "array")
        self._maybe_child(me, "index", n.index)
        return me

    def visit(self, n: Literal):
        return self._new(f"{n.value}:{n.type}")

# =============================================================================
# 2) FORMATO “DEL PROFE”: AST -> texto
# =============================================================================

def print_prof(root: Node) -> None:
    """Imprime el AST con el estilo requerido por tu profe."""
    def ind(n): return "    " * n  # 4 espacios
    def q(s: str) -> str: return f"'{s}'"

    # --- helpers de tipos -----------------------------------------------------
    def _type_to_prof(t: Optional[Type]) -> str:
        if t is None:
            return "void"
        if isinstance(t, SimpleType):
            return t.name
        if isinstance(t, ArrayType):
            # El profe no imprime "array" en el tipo, solo la base
            return _type_to_prof(t.base)
        if isinstance(t, FuncType):
            return _type_to_prof(t.ret) if t.ret else "void"
        return "void"

    # --- helpers de valores primitivos ---------------------------------------
    def _esc_char(s: str) -> str:
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("'", "\\'")

    def _esc_string(s: str) -> str:
        return s.replace("\\", "\\\\").replace("\n", "\\n")

    # --- expresiones ----------------------------------------------------------
    def emit_expr(e, lvl: int) -> str:
        # Soporte para primitivos Python por si llegan “crudos”
        if isinstance(e, bool):
            return "True" if e else "False"
        if isinstance(e, int):
            return str(e)
        if isinstance(e, float):
            return str(e)
        if isinstance(e, str):
            return q(e)

        if isinstance(e, Identifier):
            return f"VarLoc(name={q(e.name)})"
        if isinstance(e, ArrayIndex):
            base = e.array.name if isinstance(e.array, Identifier) else "<?>"
            idx = emit_expr(e.index, lvl)  # puede ser Node o primitivo
            return f"ArrayLoc(name={q(base)}, index={idx})"
        if isinstance(e, Integer):
            return f"Integer(value={e.value}, type='integer')"
        if isinstance(e, Float):
            return f"Float(value={e.value}, type='float')"
        if isinstance(e, Boolean):
            val = "True" if e.value else "False"
            return f"Boolean(value={val}, type='boolean')"
        if isinstance(e, Char):
            sv = _esc_char(e.value)
            return f"Char(value='{sv}', type='char')"
        if isinstance(e, String):
            sv = _esc_string(e.value)
            return f"String(value={q(sv)}, type='string')"
        if isinstance(e, BinOper):
            return (
                "BinOp(\n"
                f"{ind(lvl+1)}oper={q(e.oper)},\n"
                f"{ind(lvl+1)}left={emit_expr(e.left, lvl+1)},\n"
                f"{ind(lvl+1)}right={emit_expr(e.right, lvl+1)}\n"
                f"{ind(lvl)})"
            )
        if isinstance(e, UnaryOper):
            return (
                "UnaryOp(\n"
                f"{ind(lvl+1)}oper={q(e.oper)},\n"
                f"{ind(lvl+1)}expr={emit_expr(e.expr, lvl+1)}\n"
                f"{ind(lvl)})"
            )
        if isinstance(e, PreInc) or (isinstance(e, PostfixOper) and e.oper == "++"):
            return f"Increment(expr={emit_expr(e.expr, lvl)})"
        if isinstance(e, PreDec) or (isinstance(e, PostfixOper) and e.oper == "--"):
            return f"Decrement(expr={emit_expr(e.expr, lvl)})"
        if isinstance(e, Call):
            fname = e.func.name if isinstance(e.func, Identifier) else "<?>"
            args = ", ".join(emit_expr(a, lvl) for a in (e.args or []))
            return f"FuncCall(name={q(fname)}, args=[{args}])"
        return "<?>"

    # --- sentencias -----------------------------------------------------------
    def emit_stmt(s: Node, lvl: int) -> str:
        # NUEVO: manejar declaraciones dentro de bloques
        if isinstance(s, VarDecl):
            return emit_vardecl(s, lvl)

        if isinstance(s, PrintStmt):
            xs = ", ".join(emit_expr(a, lvl) for a in s.args) if s.args else ""
            return f"PrintStmt(\n{ind(lvl+1)}exprs=[{xs}]\n{ind(lvl)})"
        if isinstance(s, ReturnStmt):
            if s.expr is None:
                return "ReturnStmt(expr=None)"
            return f"ReturnStmt(\n{ind(lvl+1)}expr={emit_expr(s.expr, lvl+1)}\n{ind(lvl)})"
        if isinstance(s, Assign):
            return (
                "Assignment(\n"
                f"{ind(lvl+1)}loc={emit_expr(s.target, lvl+1)},\n"
                f"{ind(lvl+1)}expr={emit_expr(s.value, lvl+1)}\n"
                f"{ind(lvl)})"
            )
        if isinstance(s, IfStmt):
            cond = emit_expr(s.cond, lvl+1) if s.cond else "None"
            cons = emit_block_as_list(s.then, lvl+1)
            alt  = emit_block_as_list(s.otherwise, lvl+1) if s.otherwise else "None"
            return (
                "IfStmt(\n"
                f"{ind(lvl+1)}cond={cond},\n"
                f"{ind(lvl+1)}cons={cons},\n"
                f"{ind(lvl+1)}alt={alt}\n"
                f"{ind(lvl)})"
            )
        if isinstance(s, ForStmt):
            init = emit_stmt(s.init, lvl+1) if s.init else "None"
            cond = emit_expr(s.cond, lvl+1) if s.cond else "None"
            post = emit_stmt(s.step, lvl+1) if s.step else "None"
            body = emit_block_as_list(s.body, lvl+1)
            return (
                "ForStmt(\n"
                f"{ind(lvl+1)}init={init},\n"
                f"{ind(lvl+1)}cond={cond},\n"
                f"{ind(lvl+1)}post={post},\n"
                f"{ind(lvl+1)}body={body}\n"
                f"{ind(lvl)})"
            )
        if isinstance(s, WhileStmt):
            cond = emit_expr(s.cond, lvl+1) if s.cond else "None"
            body = emit_block_as_list(s.body, lvl+1)
            return (
                "WhileStmt(\n"
                f"{ind(lvl+1)}cond={cond},\n"
                f"{ind(lvl+1)}body={body}\n"
                f"{ind(lvl)})"
            )
        if isinstance(s, DoWhileStmt):
            body = emit_block_as_list(s.body, lvl+1)
            cond = emit_expr(s.cond, lvl+1) if s.cond else "None"
            return (
                "DoWhileStmt(\n"
                f"{ind(lvl+1)}body={body},\n"
                f"{ind(lvl+1)}cond={cond}\n"
                f"{ind(lvl)})"
            )
        # expresión como sentencia (tu gramática lo permite)
        if hasattr(s, "accept") and not isinstance(s, (Block,)):
            return emit_expr(s, lvl)
        return "<?>"

    def emit_block_as_list(b: Optional[Block], lvl: int) -> str:
        if b is None:
            return "[]"
        lines = []
        for st in b.stmts:
            lines.append(ind(lvl) + emit_stmt(st, lvl))
        inner = ",\n".join(lines)
        return "[\n" + inner + "\n" + ind(lvl-1 if lvl>0 else 0) + "]"

    # --- declaraciones --------------------------------------------------------
    def emit_param(p: Param, lvl: int) -> str:
        if isinstance(p.type, ArrayType):
            base = _type_to_prof(p.type.base)
            size_txt = "None"
            return f"ArrayParm(name={q(p.name)}, type={q(base)}, size={size_txt})"
        else:
            t = _type_to_prof(p.type)
            return f"VarParm(name={q(p.name)}, type={q(t)})"

    def emit_vardecl(v: VarDecl, lvl: int) -> str:
        # Función (VarDecl con FuncType + init Block) => FuncDecl
        if isinstance(v.type, FuncType):
            ret = _type_to_prof(v.type.ret)
            parms = ", ".join(emit_param(p, lvl+2) for p in (v.type.params or []))
            body = emit_block_as_list(v.init, lvl+2) if isinstance(v.init, Block) else "[]"
            return (
                "FuncDecl(\n"
                f"{ind(lvl+1)}name={q(v.name)},\n"
                f"{ind(lvl+1)}type={q(ret)},\n"
                f"{ind(lvl+1)}parms=[{parms}],\n"
                f"{ind(lvl+1)}body={body}\n"
                f"{ind(lvl)})"
            )

        # Arreglo
        if isinstance(v.type, ArrayType):
            base = _type_to_prof(v.type.base)
            sizes = []
            if v.type.size is None:
                sizes = []
            else:
                sizes = [emit_expr(v.type.size, lvl+2)]
            if v.init is None:
                init_txt = "None"
            else:
                if isinstance(v.init, Call) and isinstance(v.init.func, Identifier) and v.init.func.name == "array_init":
                    vals = ", ".join(emit_expr(a, lvl+3) for a in v.init.args)
                    init_txt = "[" + vals + "]"
                else:
                    init_txt = emit_expr(v.init, lvl+2)
            return (
                "ArrayDecl(\n"
                f"{ind(lvl+1)}name={q(v.name)},\n"
                f"{ind(lvl+1)}type={q(base)},\n"
                f"{ind(lvl+1)}size={[s for s in sizes] if sizes else []},\n"
                f"{ind(lvl+1)}value={init_txt}\n"
                f"{ind(lvl)})"
            )

        # Variable simple
        t = _type_to_prof(v.type)
        val = "None" if v.init is None else emit_expr(v.init, lvl+1)
        return (
            "VarDecl(\n"
            f"{ind(lvl+1)}name={q(v.name)},\n"
            f"{ind(lvl+1)}type={q(t)},\n"
            f"{ind(lvl+1)}value={val}\n"
            f"{ind(lvl)})"
        )

    # --- raíz -----------------------------------------------------------------
    def emit_program(p: Program) -> str:
        items = []
        for node in p.body:
            if isinstance(node, VarDecl):
                items.append(emit_vardecl(node, 2))
            else:
                items.append(emit_stmt(node, 2))
        inner = ",\n".join(ind(2) + s if not s.startswith(ind(2)) else s for s in items)
        return (
            "Program(\n"
            f"{ind(1)}body=[\n"
            f"{inner}\n"
            f"{ind(1)}]\n"
            ")"
        )

    print(emit_program(root))


# =============================================================================
# 3) Helper: Rich tree (si lo quieres invocar desde aquí)
# =============================================================================
def print_rich_tree(ast: Node) -> None:
    try:
        from rich.console import Console
        Console().print(ast.pretty())
    except Exception:
        print("rich.pretty() no disponible en el AST.")


# =============================================================================
# CLI (Graphviz / Profe / Tree)
# =============================================================================
if __name__ == "__main__":
    import argparse
    from parser import parse

    ap = argparse.ArgumentParser(description="Imprime/Renderiza el AST")
    ap.add_argument("file", help="Fuente .bm/.bminor")
    ap.add_argument("--out", default="AST", help="Nombre base de salida (sin extensión)")
    ap.add_argument("--format", default="png", choices=["png", "svg", "pdf"], help="Formato de imagen")
    ap.add_argument("--dot-only", action="store_true", help="Solo guardar el .dot (no renderizar imagen)")
    ap.add_argument("--fmt", choices=["graphviz", "prof", "tree"], default="graphviz",
                    help="graphviz = .dot/img, prof = formato del profesor, tree = rich.Tree")
    args = ap.parse_args()

    src = open(args.file, encoding="utf-8").read()
    ast = parse(src)

    if args.fmt == "prof":
        print_prof(ast)
    elif args.fmt == "tree":
        print_rich_tree(ast)
    else:
        dot = ASTPrinter.render(ast)
        dot_path = f"{args.out}.dot"
        with open(dot_path, "w", encoding="utf-8") as f:
            f.write(dot.source)
        print(f"[green]Guardado {dot_path}")
        if not args.dot_only:
            out_path = dot.render(args.out, format=args.format, cleanup=True)
            print(f"[green]Renderizado {out_path}")
