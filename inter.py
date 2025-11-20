# interp.py
'''
Tree-walking interpreter
'''
from collections import ChainMap
from rich        import print

from model       import *
from checker     import Checker
from builtins    import builtins, consts, CallError
from typesys     import CObject, Number, String, Bool, Nil, Array


# Veracidad en bminor
def _is_truthy(value):
  if isinstance(value, bool):
    return value
  elif value is None:
    return False
  else:
    return True

class ReturnException(Exception):
  def __init__(self, value):
    self.value = value

class BreakException(Exception):
  pass

class ContinueException(Exception):
  pass

class BminorExit(BaseException):
  pass

class AttributeError(Exception):
  pass


class Function:

  def __init__(self, node, env):
    self.node = node
    self.env = env

  @property
  def arity(self) -> int:
    return len(self.node.params)

  def __call__(self, interp, *args):
    newenv = self.env.new_child()
    for name, arg in zip(self.node.params, args):
      newenv[name] = arg

    oldenv = interp.env
    interp.env = newenv
    try:
      self.node.stmts.accept(interp)
      result = None
    except ReturnException as e:
      result = e.value
    finally:
      interp.env = oldenv
    return result

  def bind(self, instance):
    env = self.env.new_child()
    env['this'] = instance
    return Function(self.node, env)


class Interpreter(Visitor):

  def __init__(self, ctxt):
    self.ctxt      = ctxt
    self.env       = ChainMap()
    self.check_env = ChainMap()
    self.localmap  = { }

  def _check_numeric_operands(self, node, left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
      return True
    else:
      self.error(node, f"En '{node.op}' los operandos deben ser numeros")

  def _check_numeric_operand(self, node, value):
    if isinstance(value, (int, float)):
      return True
    else:
      self.error(node, f"En '{node.op}' el operando debe ser un numero")

  def error(self, position, message):
    self.ctxt.error(position, message)
    raise MiniCExit()

  # Punto de entrada alto-nivel
  def interpret(self, node):

    for name, cval in consts.items():
      self.check_env[name] = cval
      self.env[name] = cval

    for name, func in builtins.items():
      self.check_env[name] = func
      self.env[name] = func

    try:
      Checker.check(node, self.check_env, self)
      if not self.ctxt.have_errors:
        node.accept(self)
    except BminorExit as e:
      pass

  # Declarations

  def visit(self, node: FuncDecl):
    func = Function(node, self.env)
    self.env[node.name] = func

  def visit(self, node: VarDecl):
    if node.expr:
      expr = node.expr.accept(self)
    else:
      expr = None
    self.env[node.name] = expr

  # Statements

  def visit(self, node: Print):
    expr = node.expr.accept(self)
    if isinstance(expr, str):
      expr = expr.replace('\\n', '\n')
      expr = expr.replace('\\t', '\t')
    print(expr, end='')

  def visit(self, node: WhileStmt):
    while _is_truthy(node.expr.accept(self)):
      try:
        node.stmt.accept(self)
      except BreakException:
        return
      except ContinueException:
        raise NotImplementedError

  def visit(self, node: IfStmt):
    expr = node.expr.accept(self)
    if _is_truthy(expr):
      node.then_stmt.accept(self)
    elif node.else_stmt:
      node.else_stmt.accept(self)

  def visit(self, node: ReturnStmt):
    # Ojo: node.expr es opcional
    value = 0 if not node.expr else node.expr.accept(self)
    raise ReturnException(value)

  # Expressions

  def visit(self, node: BinOp):
    left  = node.left.accept(self)
    right = node.right.accept(self)

    if node.op == '+':
      (isinstance(left, str) and isinstance(right, str)) or self._check_numeric_operands(node, left, right)
      return left + right

    elif node.op == '-':
      self._check_numeric_operands(node, left, right)
      return left - right

    elif node.op == '*':
      self._check_numeric_operands(node, left, right)
      return left * right

    elif node.op == '/':
      self._check_numeric_operands(node, left, right)
      if isinstance(left, int) and isinstance(right, int):
        return left // right

      return left / right

    elif node.op == '%':
      self._check_numeric_operands(node, left, right)
      return left % right

    elif node.op == '==':
      return left == right

    elif node.op == '!=':
      return left != right

    elif node.op == '<':
      self._check_numeric_operands(node, left, right)
      return left < right

    elif node.op == '>':
      self._check_numeric_operands(node, left, right)
      return left > right

    elif node.op == '<=':
      self._check_numeric_operands(node, left, right)
      return left <= right

    elif node.op == '>=':
      self._check_numeric_operands(node, left, right)
      return left >= right

    else:
      raise NotImplementedError(f"Mal operador {node.op}")

  def visit(self, node: LogicalOpExpr):
    left = node.left.accept(self)
    if node.op == '||':
      return left if _is_truthy(left) else node.right.accept(self)
    if node.op == '&&':
      return node.right.accept(self) if _is_truthy(left) else left
    raise NotImplementedError(f"Mal operador {node.op}")

  def visit(self, node: UnaryOp):
    """
    Método para manejar las operaciones unarias (-, !)
    """
    right = node.right.accept(self)

    if node.op == '-':
      self._check_numeric_operand(node, right)
      return -right
    elif node.op == '!':
      return not _is_truthy(right)
    else:
      raise NotImplementedError(f"Mal operador unario {node.op}")

  def visit(self, node: VarAssignmentExpr):
    """
    Método para manejar las asignaciones de variables.
    """
    value = node.expr.accept(self)
    # Busca la variable en el entorno, en BMinor solo se asignan variables existentes.
    if node.name in self.env:
      self.env[node.name] = value
      return value
    
    # Esto no debería pasar si el Checker funciona correctamente, pero es una buena práctica.
    self.error(node, f"Variable no definida '{node.name}'")


  def visit(self, node: FuncCall):
    callee = node.func.accept(self)
    if not callable(callee):
      self.error(node.func, f'{self.ctxt.find_source(node.func)!r} no es invocable')

    args = [ arg.accept(self) for arg in node.args ]

    if callee.arity != -1 and len(args) != callee.arity:
      self.error(node.func, f"Experado {callee.arity} argumentos")

    try:
      return callee(self, *args)
    except CallError as err:
      self.error(node.func, str(err))