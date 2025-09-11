
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
    type  : str = None  # nombre legible del tipo

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
    array: Expression = None     # normalmente Identifier
    index: Expression = None

@dataclass
class Assign(Expression):
    target: Expression = None    # Identifier | ArrayIndex
    value : Expression = None

# =====================================================
# Sentencias
# =====================================================
@dataclass
class VarDecl(Statement):
    name: str = ""
    type: Type = None
    init: Optional[Expression] = None

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
