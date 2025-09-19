# astprint.py
from graphviz import Digraph
from model import *

class ASTPrinter(Visitor):
    node_defaults = {
        "shape": "box",
        "color": "deepskyblue",
        "style": "filled",
    }
    edge_defaults = {"arrowhead": "none"}

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

    # ------------------------
    # Helpers
    # ------------------------
    def _new(self, label: str, **attrs) -> str:
        nid = self.name
        self.dot.node(nid, label=label, **attrs)
        return nid

    def _edge(self, a: str, b: str, label: str | None = None):
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

    # ------------------------
    # Programa / Bloques
    # ------------------------
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

    # ------------------------
    # Declaraciones / Tipos
    # ------------------------
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
        # size puede ser un nodo Expression o un primitivo (int). Soportar ambos:
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

    # ------------------------
    # Sentencias
    # ------------------------
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

    # ------------------------
    # Expresiones
    # ------------------------
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
        # antes: self._edge(me, n.index.accept(self), "index")
        self._maybe_child(me, "index", n.index)
        return me


    def visit(self, n: Literal):
        return self._new(f"{n.value}:{n.type}")


if __name__ == "__main__":
    import argparse
    from parser import parse

    ap = argparse.ArgumentParser(description="Imprime el AST con Graphviz")
    ap.add_argument("file", help="Fuente .bm/.bminor")
    ap.add_argument("--out", default="AST", help="Nombre base de salida (sin extensión)")
    ap.add_argument("--format", default="png", choices=["png", "svg", "pdf"], help="Formato de imagen")
    ap.add_argument("--dot-only", action="store_true", help="Solo guardar el .dot (no renderizar imagen)")
    args = ap.parse_args()

    src = open(args.file, encoding="utf-8").read()
    ast = parse(src)

    dot = ASTPrinter.render(ast)

    dot_path = f"{args.out}.dot"
    with open(dot_path, "w", encoding="utf-8") as f:
        f.write(dot.source)
    print(f"[green]Guardado[/green] {dot_path}")

    if not args.dot_only:
        out_path = dot.render(args.out, format=args.format, cleanup=True)
        print(f"[green]Renderizado[/green] {out_path}")
