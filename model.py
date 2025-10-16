
from dataclasses import dataclass, field
from multimethod import multimeta
from typing import List, Optional, Union

# =====================================================
# Visitor base
# =====================================================
class Visitor(metaclass=multimeta):
    pass

# =====================================================
# Nodos base
# =====================================================
@dataclass
class Node:
    lineno: Optional[int] = None
    def accept(self, v: Visitor, *args, **kwargs):
        return v.visit(self, *args, **kwargs)

    def pretty(self, label=None):
        from rich.tree import Tree
        label = label or self.__class__.__name__
        tree = Tree(label)

        for field, value in self.__dict__.items():
            if field == "lineno":
                continue

            # 1) Mostrar tipos simples en una sola línea: "type: integer"
            if isinstance(value, SimpleType):
                tree.add(f"{field}: {value.name}")
                continue

            # 2) Resto de casos (igual que antes)
            if isinstance(value, Node):
                # mantiene la etiqueta del campo y el nombre de la clase del hijo
                tree.add(value.pretty(f"{field}: {value.__class__.__name__}"))
            elif isinstance(value, list):
                sub = tree.add(f"{field}[]")
                for v in value:
                    if isinstance(v, Node):
                        sub.add(v.pretty())
                    else:
                        sub.add(str(v))
            else:
                tree.add(f"{field}: {value}")

        return tree


@dataclass
class Statement(Node):
    pass

@dataclass
class Expression(Node):
    pass

# =====================================================
# Programa
# =====================================================
@dataclass
class Program(Statement):
    body: List[Statement] = field(default_factory=list)

# =====================================================
# Tipos
# =====================================================
@dataclass
class Type(Node):
    pass

@dataclass
class SimpleType(Type):
    name: str = ""  # 'integer' | 'float' | 'boolean' | 'char' | 'string' | 'void'

@dataclass
class ArrayType(Type):
    base: Type = None
    size: Optional[Expression] = None  # None = []

@dataclass
class FuncType(Type):
    ret: Type = None
    params: List['Param'] = field(default_factory=list)

@dataclass
class Param(Node):
    name: str = ""
    type: Type = None

# =====================================================
# Expresiones
# =====================================================
@dataclass
class Identifier(Expression):
    name: str = ""

@dataclass
class BinOper(Expression):
    oper : str = ""
    left : Expression = None
    right: Expression = None

@dataclass
class UnaryOper(Expression):
    oper : str = ""
    expr : Expression = None

@dataclass
class PostfixOper(Expression):
    oper: str = ""     # '++' or '--'
    expr: Expression = None

@dataclass
class Literal(Expression):
    value : Union[int, float, str, bool, None] = None
    type  : str = None  

@dataclass
class Integer(Literal):
    value : int = 0
    def __post_init__(self):
        assert isinstance(self.value, int), "Value debe ser un 'integer'"
        self.type = 'integer'

@dataclass
class Float(Literal):
    value : float = 0.0
    def __post_init__(self):
        assert isinstance(self.value, float), "Value debe ser un 'float'"
        self.type = 'float'

@dataclass
class Boolean(Literal):
    value : bool = False
    def __post_init__(self):
        assert isinstance(self.value, bool), "Value debe ser un 'boolean'"
        self.type = 'boolean'

@dataclass
class Char(Literal):
    value: str = '\0'
    def __post_init__(self):
        assert isinstance(self.value, str) and len(self.value) == 1, "Value debe ser un 'char' de un caracter"
        self.type = 'char'

@dataclass
class String(Literal):
    value: str = ""
    def __post_init__(self):
        assert isinstance(self.value, str), "Value debe ser un 'string'"
        self.type = 'string'

@dataclass
class Call(Expression):
    func: Identifier = None
    args: List[Expression] = field(default_factory=list)

@dataclass
class ArrayIndex(Expression):
    array: Expression = None     
    index: Expression = None

@dataclass
class Assign(Expression):
    target: Expression = None    
    value : Expression = None

# =====================================================
# Sentencias
# =====================================================
@dataclass
@dataclass
class VarDecl(Statement):
    name: str = ""
    type: Type = None
    init: Optional[Expression] = None

    # Pretty especial: si es función (FuncType) imprimir como FuncDecl(...)
    def pretty(self, label=None):
        from rich.tree import Tree

        # Helper para imprimir nombres de tipos simples
        def _type_name(t: Optional[Type]) -> str:
            if t is None:
                return "void"
            if isinstance(t, SimpleType):
                return t.name
            return t.__class__.__name__

        # Helper para imprimir un parámetro como VarParm / ArrayParm
        def _param_tree(p: "Param") -> Tree:
            if isinstance(p.type, ArrayType):
                base = _type_name(p.type.base)
                t = Tree("ArrayParm")
                t.add(f"name: {p.name}")
                t.add(f"type: {base}")
                # El profe pone None cuando es array [] (sin tamaño literal)
                if p.type.size is None:
                    t.add("size: None")
                else:
                    # Si quieres ser más sofisticado, podrías resolver índices; aquí lo mostramos como subárbol/expr
                    sz = Tree("size")
                    if isinstance(p.type.size, Node):
                        sz.add(p.type.size.pretty())
                    else:
                        sz.add(str(p.type.size))
                    t.add(sz)
                return t
            else:
                t = Tree("VarParm")
                t.add(f"name: {p.name}")
                t.add(f"type: {_type_name(p.type)}")
                return t

        # Si NO es función, delega al pretty genérico de Node (VarDecl normal)
        if not isinstance(self.type, FuncType):
            # Usa el pretty base (que ya imprime type, init, etc.)
            return Node.pretty(self, label or self.__class__.__name__)

        # ---- Es función: imprime como FuncDecl
        root = Tree("FuncDecl")
        root.add(f"name: {self.name}")
        root.add(f"type: {_type_name(self.type.ret)}")  # tipo de retorno

        # parms[]
        parms_node = Tree("parms[]")
        for p in (self.type.params or []):
            parms_node.add(_param_tree(p))
        root.add(parms_node)

        # body: esperamos un Block en init
        body_node = Tree("body")
        if isinstance(self.init, Block):
            body_node.add(self.init.pretty())
        else:
            # Si no hay bloque, muestra lista vacía (como en el estilo del profe)
            body_node.add("[]")
        root.add(body_node)

        return root

@dataclass
class PrintStmt(Statement):
    args: List[Expression] = field(default_factory=list)

@dataclass
class ReturnStmt(Statement):
    expr: Optional[Expression] = None

@dataclass
class Block(Statement):
    stmts: List[Statement] = field(default_factory=list)

@dataclass
class IfStmt(Statement):
    cond: Optional[Expression] = None
    then: Statement = None
    otherwise: Optional[Statement] = None

@dataclass
class ForStmt(Statement):
    init: Optional[Expression] = None
    cond: Optional[Expression] = None
    step: Optional[Expression] = None
    body: Statement = None

@dataclass
class WhileStmt(Statement):
    cond: Optional[Expression] = None
    body: Statement = None

@dataclass
class DoWhileStmt(Statement):
    body: Statement = None
    cond: Optional[Expression] = None

@dataclass
class PreInc(Expression):
    expr: Expression = None

@dataclass
class PreDec(Expression):
    expr: Expression = None
