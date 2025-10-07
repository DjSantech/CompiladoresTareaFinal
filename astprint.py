# astprint.py
# -----------------------------------------------------------------------------
# Generador de visualización del AST usando Graphviz.
# Recorre el árbol sintáctico (nodos de model.py) con un Visitor y construye
# un grafo dirigido (Digraph) donde cada nodo del AST es un nodo del grafo.
# Incluye un ejecutable por CLI que:
#   - Parse a un archivo fuente (.bm/.bminor)
#   - Genera el .dot correspondiente
#   - Opcionalmente renderiza una imagen (png/svg/pdf)
# -----------------------------------------------------------------------------

from graphviz import Digraph
from model import *


class ASTPrinter(Visitor):
    # Atributos por defecto para nodos y aristas del grafo
    node_defaults = {
        "shape": "ellipse",   # Forma por defecto de los nodos
        "color": "purple",    # Color de relleno
        "style": "filled",    # Estilo del nodo (relleno)
    }
    edge_defaults = {"arrowhead": "normal"}  # Aristas con flecha

    def __init__(self):
        # Inicializa el grafo y configura atributos globales
        self.dot = Digraph("AST")
        self.dot.attr("node", **self.node_defaults)
        self.dot.attr("edge", **self.edge_defaults)
        self._seq = 0  # Contador interno para generar ids únicos de nodos

    @property
    def name(self):
        # Genera un id único para cada nodo del grafo (n00001, n00002, ...)
        self._seq += 1
        return f"n{self._seq:05d}"

    @classmethod
    def render(cls, n: Node) -> Digraph:
        # Construye un ASTPrinter, visita el nodo raíz y devuelve el Digraph
        p = cls()
        n.accept(p)
        return p.dot

    # -------------------------------------------------------------------------
    # Helpers (utilidades internas)
    # -------------------------------------------------------------------------
    def _new(self, label: str, **attrs) -> str:
        """Crea un nodo en el grafo con 'label' y atributos opcionales."""
        nid = self.name
        self.dot.node(nid, label=label, **attrs)
        return nid

    def _edge(self, a: str, b: str, label: str | None = None):
        """Crea una arista entre 'a' y 'b'. Si 'label' no es None, la usa como etiqueta."""
        if label is None:
            self.dot.edge(a, b)
        else:
            self.dot.edge(a, b, label=label)

    def _maybe_child(self, parent_id: str, label: str, value):
        """
        Conecta 'parent_id' con 'value' si existe.
        - Si 'value' es un Node, se visita y se conecta.
        - Si es un valor primitivo (int/str/etc.), se crea un nodo hoja con ese valor.
        """
        if value is None:
            return
        if isinstance(value, Node):
            self._edge(parent_id, value.accept(self), label)
        else:
            leaf = self._new(str(value))
            self._edge(parent_id, leaf, label)

    # -------------------------------------------------------------------------
    # Programa / Bloques
    # -------------------------------------------------------------------------
    def visit(self, n: Program):
        # Nodo raíz "Program" que conecta con la secuencia de declaraciones/sentencias
        me = self._new("Program")
        for s in n.body:
            self._edge(me, s.accept(self))
        return me

    def visit(self, n: Block):
        # Bloque de sentencias { ... }
        me = self._new("Block")
        for s in n.stmts:
            self._edge(me, s.accept(self))
        return me

    # -------------------------------------------------------------------------
    # Declaraciones / Tipos
    # -------------------------------------------------------------------------
    def visit(self, n: VarDecl):
        # Declaración de variable con nombre y opcionalmente tipo e inicialización
        me = self._new(f"VarDecl\\n{n.name}")
        if n.type is not None:
            self._edge(me, n.type.accept(self), "type")
        if n.init is not None:
            self._edge(me, n.init.accept(self), "init")
        return me

    def visit(self, n: SimpleType):
        # Tipo simple (integer, float, boolean, char, string, void)
        return self._new(f"Type\\n{n.name}")

    def visit(self, n: ArrayType):
        # Tipo arreglo: base y tamaño (size puede ser nodo o primitivo)
        me = self._new("ArrayType")
        if n.base is not None:
            self._edge(me, n.base.accept(self), "base")
        # size puede ser un nodo Expression o un valor primitivo (p.ej., int)
        self._maybe_child(me, "size", n.size)
        return me

    def visit(self, n: FuncType):
        # Tipo función: tipo de retorno y lista de parámetros
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
        # Parámetro formal: nombre y tipo
        me = self._new(f"Param\\n{n.name}")
        if n.type is not None:
            self._edge(me, n.type.accept(self), "type")
        return me

    # -------------------------------------------------------------------------
    # Sentencias
    # -------------------------------------------------------------------------
    def visit(self, n: PrintStmt):
        # Sentencia print con lista de argumentos
        me = self._new("Print")
        for a in n.args:
            self._edge(me, a.accept(self))
        return me

    def visit(self, n: ReturnStmt):
        # Sentencia return con expresión opcional
        me = self._new("Return")
        if n.expr is not None:
            self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: IfStmt):
        # Sentencia if con condicional, rama then y rama else opcional
        me = self._new("If")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        if n.then is not None:
            self._edge(me, n.then.accept(self), "then")
        if n.otherwise is not None:
            self._edge(me, n.otherwise.accept(self), "else")
        return me

    def visit(self, n: ForStmt):
        # Sentencia for con init/cond/step y cuerpo
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
        # Sentencia while con condición y cuerpo
        me = self._new("While")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        if n.body is not None:
            self._edge(me, n.body.accept(self), "body")
        return me

    def visit(self, n: DoWhileStmt):
        # Sentencia do-while con cuerpo y condición
        me = self._new("DoWhile")
        if n.body is not None:
            self._edge(me, n.body.accept(self), "body")
        if n.cond is not None:
            self._edge(me, n.cond.accept(self), "cond")
        return me

    # -------------------------------------------------------------------------
    # Expresiones
    # -------------------------------------------------------------------------
    def visit(self, n: Assign):
        # Asignación: target = value
        me = self._new("=")
        self._edge(me, n.target.accept(self), "target")
        self._edge(me, n.value.accept(self), "value")
        return me

    def visit(self, n: Identifier):
        # Identificador simple
        return self._new(f"Id({n.name})")

    def visit(self, n: BinOper):
        # Operador binario (e.g., +, -, *, /, %, &&, ||, ==, <, etc.)
        # Se dibuja con forma circular para distinguir operadores
        me = self._new(n.oper, shape="circle")
        self._edge(me, n.left.accept(self))
        self._edge(me, n.right.accept(self))
        return me

    def visit(self, n: UnaryOper):
        # Operador unario (e.g., -x, !x)
        me = self._new(n.oper, shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PostfixOper):
        # Operador postfijo (x++, x--)
        me = self._new(f"{n.oper}(post)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PreInc):
        # Operador prefijo ++x
        me = self._new("++(pre)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: PreDec):
        # Operador prefijo --x
        me = self._new("--(pre)", shape="circle")
        self._edge(me, n.expr.accept(self))
        return me

    def visit(self, n: Call):
        # Llamada a función con nombre y lista de argumentos
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
        # Indexación de arreglo: array[index]
        me = self._new("[]", shape="circle")
        self._edge(me, n.array.accept(self), "array")
        # index puede ser nodo o un primitivo
        self._maybe_child(me, "index", n.index)
        return me

    def visit(self, n: Literal):
        # Literal: muestra el valor y el tipo legible
        return self._new(f"{n.value}:{n.type}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    from parser import parse

    # CLI para generar el grafo del AST desde un archivo fuente
    ap = argparse.ArgumentParser(description="Imprime el AST con Graphviz")
    ap.add_argument("file", help="Fuente .bm/.bminor")
    ap.add_argument("--out", default="AST", help="Nombre base de salida (sin extensión)")
    ap.add_argument("--format", default="png", choices=["png", "svg", "pdf"], help="Formato de imagen")
    ap.add_argument("--dot-only", action="store_true", help="Solo guardar el .dot (no renderizar imagen)")
    args = ap.parse_args()

    # Carga, parseo y render del AST a grafo
    src = open(args.file, encoding="utf-8").read()
    ast = parse(src)
    dot = ASTPrinter.render(ast)

    # Guardado del .dot siempre
    dot_path = f"{args.out}.dot"
    with open(dot_path, "w", encoding="utf-8") as f:
        f.write(dot.source)
    print(f"[green]Guardado {dot_path}")

    # Render opcional del grafo a imagen
    if not args.dot_only:
        out_path = dot.render(args.out, format=args.format, cleanup=True)
        print(f"[green]Renderizado {out_path}")
