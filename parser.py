# grammar.py
import logging
import sly
from rich import print

from lexer  import Lexer
from errors import error, errors_detected
from model  import *


def _L(node, lineno):
	node.lineno = lineno
	return node


class Parser(sly.Parser):
	log = logging.getLogger()
	log.setLevel(logging.ERROR)
	expected_shift_reduce = 1
	debugfile='grammar.txt'

	tokens = Lexer.tokens

	@_("decl_list")
	def prog(self, p):
		return Program(p.decl_list)

	# Declarations

	@_("decl decl_list")
	def decl_list(self, p):
		return [ p.decl ] + p.decl_list

	@_("empty")
	def decl_list(self, p):
		return [ ]

	@_("ID ':' type_simple ';'")
	def decl(self, p):
		...

	@_("ID ':' type_array_sized ';'")
	def decl(self, p):
		...

	@_("ID ':' type_func ';'")
	def decl(self, p):
		...

	@_("decl_init")
	def decl(self, p):
		...

	@_("ID ':' type_simple '=' expr ';'")
	def decl_init(self, p):
		...

	@_("ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'")
	def decl_init(self, p):
		...

	@_("ID ':' type_func '=' '{' opt_stmt_list '}'")
	def decl_init(self, p):
		...
	
	# Statements
	
	@_("stmt_list")
	def opt_stmt_list(self, p):
		...

	@_("empty")
	def opt_stmt_list(self, p):
		...

	@_("stmt stmt_list")
	def stmt_list(self, p):
		...

	@_("stmt")
	def stmt_list(self, p):
		...

	@_("open_stmt")
	@_("closed_stmt")
	def stmt(self, p):
		...

	@_("if_stmt_closed")
	@_("for_stmt_closed")
	@_("simple_stmt")
	def closed_stmt(self, p):
		...
		
	@_("if_stmt_open",
	   "for_stmt_open")
	def open_stmt(self, p):
		...
		
	@_("IF '(' opt_expr ')'")
	def if_cond(self, p):
		...

	@_("if_cond closed_stmt ELSE closed_stmt")
	def if_stmt_closed(self, p):
		...
	
	@_("if_cond stmt")	
	def if_stmt_open(self, p):
		...
		
	@_("if_cond closed_stmt ELSE if_stmt_open")	
	def if_stmt_open(self, p):
		...

	@_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
	def for_header(self, p):
		...

	@_("for_header open_stmt")
	def for_stmt_open(self, p):
		...
		
	@_("for_header closed_stmt")
	def for_stmt_closed(self, p):
		...
		
	# Simple statements are not recursive
	
	@_("print_stmt")
	@_("return_stmt")
	@_("block_stmt")
	@_("decl")
	@_("expr ';'")
	def simple_stmt(self, p):
		...

	@_("PRINT opt_expr_list ';'")
	def print_stmt(self, p):
		...
		
	@_("RETURN opt_expr ';'")
	def return_stmt(self, p):
		...

	@_("'{' stmt_list '}'")
	def block_stmt(self, p):
		...
	
	# Expressions
	
	@_("empty")
	def opt_expr_list(self, p):
		...

	@_("expr_list")
	def opt_expr_list(self, p):
		...
		
	@_("expr ',' expr_list")
	def expr_list(self, p):
		...
		
	@_("expr")
	def expr_list(self, p):
		...

	# TODO
	@_("empty")
	def opt_expr(self, p):
		...

	@_("expr")
	def opt_expr(self, p):
		...

	@_("expr1")
	def expr(self, p):
		...

	@_("lval '=' expr1")
	def expr1(self, p):
		...
		
	@_("expr2")
	def expr1(self, p):
		...

	@_("ID")
	def lval(self, p):
		...

	@_("ID index")
	def lval(self, p):
		...

	@_("expr2 LOR expr3")
	def expr2(self, p):
		...

	@_("expr3")
	def expr2(self, p):
		...

	@_("expr3 LAND expr4")
	def expr3(self, p):
		...

	@_("expr4")
	def expr3(self, p):
		...

	@_("expr4 EQ expr5")
	@_("expr4 NE expr5")
	@_("expr4 LT expr5")
	@_("expr4 LE expr5")
	@_("expr4 GT expr5")
	@_("expr4 GE expr5")
	def expr4(self, p):
		return BinOper(p[1], p.expr4, p.expr5)

	@_("expr5")
	def expr4(self, p):
		...

	@_("expr5 '+' expr6")
	@_("expr5 '-' expr6")
	def expr5(self, p):
		return BinOper(p[1], p.expr5, p.expr6)

	@_("expr6")
	def expr5(self, p):
		...

	@_("expr6 '*' expr7")
	@_("expr6 '/' expr7")
	@_("expr6 '%' expr7")
	def expr6(self, p):
		return BinOper(p[1], p.expr6, p.expr7)

	@_("expr7")
	def expr6(self, p):
		...

	@_("expr7 '^' expr8")
	def expr7(self, p):
		return BinOper(p[1], p.expr7, p.expr8)

	@_("expr8")
	def expr7(self, p):
		...
		
	@_("'-' expr8")
	@_("'!' expr8")
	def expr8(self, p):
		return UnaryOper(p[0], p.expr8)
		
	@_("expr9")
	def expr8(self, p):
		...

	@_("expr9 INC")
	def expr9(self, p):
		...
		
	@_("expr9 DEC")
	def expr9(self, p):
		...
		
	@_("group")
	def expr9(self, p):
		...
		
	@_("'(' expr ')'")
	def group(self, p):
		...
		
	@_("ID '(' opt_expr_list ')'")
	def group(self, p):
		...

	@_("ID index")
	def group(self, p):
		...
	
	@_("factor")
	def group(self, p):
		...
		
	@_("'[' expr ']'")
	def index(self, p):
		...

	@_("ID")
	def factor(self, p):
		...

	@_("INTEGER_LITERAL")
	def factor(self, p):
		return _L(Integer(p.INTEGER_LITERAL), p.lineno)

	@_("FLOAT_LITERAL")
	def factor(self, p):
		return _L(Float(p.FLOAT_LITERAL), p.lineno)

	@_("CHAR_LITERAL")
	def factor(self, p):
		...
		
	@_("STRING_LITERAL")
	def factor(self, p):
		...
		
	@_("TRUE")
	@_("FALSE")
	def factor(self, p):
		return _L(Boolean(p[0] == 'true'), p.lieno)

	# Types

	@_("INTEGER")
	@_("FLOAT")
	@_("BOOLEAN")
	@_("CHAR")
	@_("STRING")
	@_("VOID")
	def type_simple(self, p):
		return p[0]
	
	@_("ARRAY '[' ']' type_simple")
	@_("ARRAY '[' ']' type_array")
	def type_array(self, p):
		...

	@_("ARRAY index type_simple")
	@_("ARRAY index type_array_sized")
	def type_array_sized(self, p):
		...

	@_("FUNCTION type_simple '(' opt_param_list ')'")
	@_("FUNCTION type_array_sized '(' opt_param_list ')'")
	def type_func(self, p):
		...

	@_("empty")
	def opt_param_list(self, p):
		...

	@_("param_list")
	def opt_param_list(self, p):
		...

	@_("param_list ',' param")
	def param_list(self, p):
		...

	@_("param")
	def param_list(self, p):
		...
	
	@_("ID ':' type_simple")
	def param(self, p):
		...

	@_("ID ':' type_array")
	def param(self, p):
		...

	@_("ID ':' type_array_sized")
	def param(self, p):
		...

	@_("")
	def empty(self, p):
		...

	def error(self, p):
		lineno = p.lineno if p else 'EOF'
		value = repr(p.value) if p else 'EOF'
		error(f'Syntax error at {value}', lineno)



# Convertir el AST a una representación JSON para mejor visualización
def ast_to_dict(node):
	if isinstance(node, list):
		return [ast_to_dict(item) for item in node]
	elif hasattr(node, "__dict__"):
		return {key: ast_to_dict(value) for key, value in node.__dict__.items()}
	else:
		return node

def parse(txt):
	l = Lexer()
	p = Parser()

	return p.parse(l.tokenize(txt))

if __name__ == '__main__':
	import sys, json
	
	if sys.platform != 'ios':

		if len(sys.argv) != 2:
			raise SystemExit("Usage: python gparse.py <filename>")

		filename = sys.argv[1]

	else:
		from File_Picker import file_picker_dialog

		filename = file_picker_dialog(
			title='Seleccionar una archivo',
			root_dir='./test',
			file_pattern='^.*[.]bminor'
		)

	if filename:
		txt = open(filename, encoding='utf-8').read()
		ast = parse(txt)
		
		print(ast)