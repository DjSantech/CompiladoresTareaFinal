'''
Tree-walking interpreter
'''
import sys
from collections import ChainMap
from rich        import print
from rich.console import Console 

from model       import *
from checker     import *
from typesys     import *

# Veracidad en bminor
def _is_truthy(value):
  if isinstance(value, bool):
    return value
  elif value is None:
    return False
  else:
    return True

# --- DEFINICIÓN DE EXCEPCIONES ---
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

class CallError(Exception):
  pass

# --- VARIABLES GLOBALES ---
consts = {}
builtins = {}

# --- CLASE DE CONTEXTO DE ERRORES ---
class Context:
    def __init__(self):
        self.have_errors = False
        self.error_list = []
        
    def error(self, position, message):
        self.have_errors = True
        self.error_list.append((position, message))
        
        lineno = getattr(position, 'lineno', None)
        
        import errors 
        if hasattr(errors, 'error'):
            errors.error(message, lineno)
        else:
            print(f"Error en {position}: {message}", file=sys.stderr)


class Function:

  def __init__(self, node, env):
    self.node = node
    self.env = env

  @property
  def arity(self) -> int:
    if isinstance(self.node, VarDecl) and isinstance(self.node.type, FuncType):
      return len(self.node.type.params or [])
    return len(getattr(self.node, 'params', []))

  def __call__(self, interp, *args):
    newenv = self.env.new_child()
    
    if isinstance(self.node, VarDecl) and isinstance(self.node.type, FuncType):
      params = self.node.type.params or []
      for param, arg in zip(params, args):
        newenv[param.name] = arg
    else:
      params = getattr(self.node, 'params', [])
      for param, arg in zip(params, args):
        param_name = param.name if hasattr(param, 'name') else param
        newenv[param_name] = arg

    oldenv = interp.env
    interp.env = newenv
    try:
      if isinstance(self.node, VarDecl) and isinstance(self.node.init, Block):
        self.node.init.accept(interp)
      elif hasattr(self.node, 'stmts'):
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
      self.error(node, f"En '{node.oper}' los operandos deben ser numeros")

  def _check_numeric_operand(self, node, value):
    if isinstance(value, (int, float)):
      return True
    else:
      self.error(node, f"En '{node.oper}' el operando debe ser un numero")

  def error(self, position, message):
    self.ctxt.error(position, message)
    raise BminorExit()

  def interpret(self, node):
    for name, cval in consts.items():
      self.check_env[name] = cval
      self.env[name] = cval

    for name, func in builtins.items():
      self.check_env[name] = func
      self.env[name] = func

    try:
      if not self.ctxt.have_errors:
        node.accept(self)
    except BminorExit as e:
      pass

  # ============================================================
  # PROGRAM
  # ============================================================
  def visit(self, node: Program):
    for stmt in node.body:
      stmt.accept(self)

  # ============================================================
  # DECLARATIONS
  # ============================================================
  def visit(self, node: VarDecl):
    if isinstance(node.type, FuncType):
      func = Function(node, self.env)
      self.env[node.name] = func
    else:
      if node.init:
        if hasattr(node.init, 'values'):
          values = [v.accept(self) if hasattr(v, 'accept') else v for v in node.init.values]
          self.env[node.name] = values
        else:
          init_expr = node.init
          if hasattr(init_expr, 'accept'):
            expr = init_expr.accept(self)
          else:
            expr = init_expr
          self.env[node.name] = expr
      else:
        if isinstance(node.type, ArrayType):
          if node.type.size and isinstance(node.type.size, Integer):
            size = node.type.size.value
            self.env[node.name] = [0] * size
          else:
            self.env[node.name] = []
        else:
          self.env[node.name] = 0

  # ============================================================
  # STATEMENTS
  # ============================================================
  def visit(self, node: Block):
    for stmt in node.stmts:
      stmt.accept(self)

  def visit(self, node: PrintStmt):
    for arg in node.args:
      expr = arg.accept(self) if hasattr(arg, 'accept') else arg
      if isinstance(expr, str):
        expr = expr.replace('\\n', '\n')
        expr = expr.replace('\\t', '\t')
      print(expr, end='')

  def visit(self, node: ReturnStmt):
    value = None
    if node.expr:
      value_expr = node.expr
      value = value_expr.accept(self) if hasattr(value_expr, 'accept') else value_expr
    raise ReturnException(value)

  def visit(self, node: IfStmt):
    expr = node.cond.accept(self)
    if _is_truthy(expr):
      node.then.accept(self)
    elif node.otherwise:
      node.otherwise.accept(self)

  def visit(self, node: WhileStmt):
    while _is_truthy(node.cond.accept(self)):
      try:
        node.body.accept(self)
      except BreakException:
        break
      except ContinueException:
        continue

  def visit(self, node: DoWhileStmt):
    while True:
      try:
        node.body.accept(self)
      except BreakException:
        break
      except ContinueException:
        pass
      
      if not _is_truthy(node.cond.accept(self)):
        break

  def visit(self, node: ForStmt):
    if node.init:
      node.init.accept(self)
    
    while True:
      if node.cond and not _is_truthy(node.cond.accept(self)):
        break
      
      try:
        node.body.accept(self)
      except BreakException:
        break
      except ContinueException:
        pass
      
      if node.step:
        node.step.accept(self)

  # ============================================================
  # EXPRESSIONS
  # ============================================================
  def visit(self, node: Assign):
    value = node.value.accept(self) if hasattr(node.value, 'accept') else node.value
    
    if isinstance(node.target, Identifier):
      if node.target.name in self.env:
        self.env[node.target.name] = value
      else:
        self.error(node, f"Variable no definida '{node.target.name}'")
    
    elif isinstance(node.target, ArrayIndex):
      if isinstance(node.target.array, Identifier):
        arr = self.env.get(node.target.array.name)
        if arr is None:
          self.error(node, f"Array no definido '{node.target.array.name}'")
          return value

        index_expr = node.target.index
        if hasattr(index_expr, 'accept'):
            idx = index_expr.accept(self)
        else:
            idx = index_expr
            
        if not isinstance(idx, int):
          self.error(node, f"Índice debe ser entero")
          return value
        if not isinstance(arr, list):
          self.error(node, f"'{node.target.array.name}' no es un array")
          return value
        if idx < 0 or idx >= len(arr):
          self.error(node, f"Índice fuera de rango: {idx}")
          return value
        
        arr[idx] = value
    
    return value

  def visit(self, node: BinOper):
    left  = node.left.accept(self) if hasattr(node.left, 'accept') else node.left
    right = node.right.accept(self) if hasattr(node.right, 'accept') else node.right

    if node.oper == '+':
      (isinstance(left, str) and isinstance(right, str)) or self._check_numeric_operands(node, left, right)
      return left + right

    elif node.oper == '-':
      self._check_numeric_operands(node, left, right)
      return left - right

    elif node.oper == '*':
      self._check_numeric_operands(node, left, right)
      return left * right

    elif node.oper == '/':
      self._check_numeric_operands(node, left, right)
      if right == 0:
          self.error(node, "División por cero")
          return 0
      
      # División entera para enteros
      if isinstance(left, int) and isinstance(right, int):
        return left // right
      return left / right

    elif node.oper == '%':
      self._check_numeric_operands(node, left, right)
      return left % right
    
    elif node.oper == '^':
      self._check_numeric_operands(node, left, right)
      return left ** right

    elif node.oper == '==':
      return left == right

    elif node.oper == '!=':
      return left != right

    elif node.oper == '<':
      self._check_numeric_operands(node, left, right)
      return left < right

    elif node.oper == '>':
      self._check_numeric_operands(node, left, right)
      return left > right

    elif node.oper == '<=':
      self._check_numeric_operands(node, left, right)
      return left <= right

    elif node.oper == '>=':
      self._check_numeric_operands(node, left, right)
      return left >= right
    
    elif node.oper == '||':
      return left if _is_truthy(left) else right
    
    elif node.oper == '&&':
      return right if _is_truthy(left) else left

    else:
      raise NotImplementedError(f"Mal operador {node.oper}")

  def visit(self, node: UnaryOper):
    """Operadores unarios (-, +, !)"""
    expr = node.expr.accept(self) if hasattr(node.expr, 'accept') else node.expr

    if node.oper == '-':
      self._check_numeric_operand(node, expr)
      return -expr
    elif node.oper == '+':
      self._check_numeric_operand(node, expr)
      return +expr
    elif node.oper == '!':
      return not _is_truthy(expr)
    else:
      raise NotImplementedError(f"Mal operador unario {node.oper}")

  def visit(self, node: UnaryOp):
    """Operador unario ! (alternativo)"""
    expr = node.expr.accept(self) if hasattr(node.expr, 'accept') else node.expr
    if node.op == '!':
      return not _is_truthy(expr)
    else:
      raise NotImplementedError(f"Mal operador unario {node.op}")
      
  def visit(self, node: PostfixOper):
    if not isinstance(node.expr, Identifier):
      self.error(node, "Solo se puede usar ++ o -- con variables")
      return None
    
    var_name = node.expr.name
    if var_name not in self.env:
      self.error(node, f"Variable no definida '{var_name}'")
      return None
    
    old_value = self.env[var_name]
    if not isinstance(old_value, (int, float)):
      self.error(node, f"Variable '{var_name}' debe ser numérica")
      return None
    
    if node.oper == '++':
      self.env[var_name] = old_value + 1
    elif node.oper == '--':
      self.env[var_name] = old_value - 1
    
    return old_value

  def visit(self, node: PreInc):
    """Pre-incremento ++x"""
    if not isinstance(node.expr, Identifier):
      self.error(node, "Solo se puede usar ++ con variables")
      return None
    
    var_name = node.expr.name
    if var_name not in self.env:
      self.error(node, f"Variable no definida '{var_name}'")
      return None
    
    old_value = self.env[var_name]
    if not isinstance(old_value, (int, float)):
      self.error(node, f"Variable '{var_name}' debe ser numérica")
      return None
    
    new_value = old_value + 1
    self.env[var_name] = new_value
    return new_value

  def visit(self, node: PreDec):
    """Pre-decremento --x"""
    if not isinstance(node.expr, Identifier):
      self.error(node, "Solo se puede usar -- con variables")
      return None
    
    var_name = node.expr.name
    if var_name not in self.env:
      self.error(node, f"Variable no definida '{var_name}'")
      return None
    
    old_value = self.env[var_name]
    if not isinstance(old_value, (int, float)):
      self.error(node, f"Variable '{var_name}' debe ser numérica")
      return None
    
    new_value = old_value - 1
    self.env[var_name] = new_value
    return new_value

  def visit(self, node: Call):
    callee = node.func.accept(self) if hasattr(node.func, 'accept') else node.func
    
    if not callable(callee):
      self.error(node.func, f'{node.func.name if isinstance(node.func, Identifier) else "expresión"} no es invocable')

    args = []
    for arg in node.args:
        if hasattr(arg, 'accept'):
            args.append(arg.accept(self))
        else:
            args.append(arg)

    if hasattr(callee, 'arity') and callee.arity != -1 and len(args) != callee.arity:
      self.error(node.func, f"Esperado {callee.arity} argumentos, recibido {len(args)}")

    try:
      return callee(self, *args)
    except CallError as err:
      self.error(node.func, str(err))

  def visit(self, node: Identifier):
    """Identificador (variable)"""
    if node.name in self.env:
      value = self.env[node.name]
      
      # Coerción de flotante a entero si se accede numéricamente
      if isinstance(value, float):
          return int(value)
          
      return value
    else:
      self.error(node, f"Variable no definida '{node.name}'")

  def visit(self, node: ArrayIndex):
    arr = self.env.get(node.array.name) if isinstance(node.array, Identifier) else (node.array.accept(self) if hasattr(node.array, 'accept') else node.array)
    
    if not isinstance(arr, list):
      self.error(node, f"No es un array")
    
    index_expr = node.index
    if hasattr(index_expr, 'accept'):
        idx = index_expr.accept(self)
    else:
        idx = index_expr
        
    if not isinstance(idx, int):
      self.error(node, f"Índice debe ser entero")
    
    if idx < 0 or idx >= len(arr):
      self.error(node, f"Índice fuera de rango: {idx}")
    
    return arr[idx]

  def visit(self, node: ArrayInit):
    values = []
    for v in node.values:
      if hasattr(v, 'accept'):
        values.append(v.accept(self))
      else:
        values.append(v)
    return values

  # --- Métodos de literales ---
  def visit(self, node: Integer): return int(node.value)
  def visit(self, node: Float): return float(node.value)
  def visit(self, node: Boolean): return bool(node.value)
  def visit(self, node: Char): return str(node.value)
  def visit(self, node: String): return str(node.value)
  def visit(self, node: Literal): return node.value


# ============================================================
# MAIN - Ejecutar desde línea de comandos
# ============================================================
if __name__ == '__main__':
    import sys
    import traceback
    
    if len(sys.argv) != 2:
        print("Uso: python inter.py <archivo.bminor>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        sys.exit(1)
    
    try:
        from lexer import Lexer
        from parser import Parser
        import errors
    except ImportError as e:
        print(f"Error: No se pueden importar los módulos necesarios: {e}")
        sys.exit(1)
    
    errors.set_source(filename, source_code)
    
    try:
        lexer = Lexer()
        parser = Parser()
        tokens = list(lexer.tokenize(source_code))
        ast = parser.parse(iter(tokens))
        
        if errors.errors_detected():
            sys.exit(1)
        
        if ast is None:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error durante el parsing: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    try:
        ctx = Context()
        interpreter = Interpreter(ctx)
        
        # 1. Carga de declaraciones globales
        interpreter.interpret(ast) 
        
        # 2. LLAMAR EXPLÍCITAMENTE A MAIN
        if 'main' in interpreter.env:
            try:
                main_func = interpreter.env['main']
                if callable(main_func):
                    main_func(interpreter) 
                else:
                    ctx.error(None, "El identificador 'main' no es una función.")
            except BminorExit:
                pass
            except Exception as e:
                print(f"\n❌ Error en tiempo de ejecución en 'main': {e}", file=sys.stderr)
        else:
            print("Advertencia: Función 'main' no encontrada.")

        if ctx.have_errors:
            print("\n❌ Errores durante la ejecución:", file=sys.stderr)
            sys.exit(1)
            
    except BminorExit:
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Ejecución interrumpida por el usuario")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error inesperado durante la ejecución: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
