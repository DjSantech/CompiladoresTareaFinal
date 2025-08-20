# lexer.py
#
# Analizador Léxico para el lenguaje B-Minor

import sly
import re

class Lexer(sly.Lexer):
    tokens = {
        # Palabras Reservadas
        ARRAY, AUTO, BOOLEAN, CHAR, ELSE, FALSE, FLOAT, FOR, FUNCTION,
        IF, INTEGER, PRINT, RETURN, STRING, TRUE, VOID, WHILE,

        # Operadores compuestos
        LT, LE, GT, GE, EQ, NE,       # Operadores relacionales
        LAND, LOR,                    # Operadores lógicos
        INC, DEC                      # Incremento / Decremento

        # Literales
        ID, CHAR_LITERAL, FLOAT_LITERAL, INTEGER_LITERAL, STRING_LITERAL
    }
    literals = '+-*/%^=()[]{}:;,<>'

    # Caracteres a ignorar
    ignore = ' \t\r'

    # Saltos de línea
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')
    
    # Comentarios
    @_(r'//.*')
    def ignore_cppcomment(self, t):
        pass
    
    @_(r'/\*.*?\*/')
    def COMMENT(self, t):
    self.lineno += t.value.count('\n')
    pass

    
    # Identificador y Palabras reservadas
    ID = r'[_a-zA-Z]\w*'
    ID['array'] = ARRAY
    ID['auto']  = AUTO
    ID['boolean'] = BOOLEAN
    ID['char']  = CHAR
    ID['else']  = ELSE
    ID['false'] = FALSE
    ID['float'] = FLOAT
    ID['for']   = FOR
    ID['function'] = FUNCTION
    ID['if']    = IF
    ID['integer']  = INTEGER
    ID['print']    = PRINT
    ID['return']   = RETURN
    ID['string']   = STRING
    ID['true']     = TRUE
    ID['void']     = VOID
    ID['while']    = WHILE

     # Reglas para operadores
    LT   = r'<'
    LE   = r'<='
    GT   = r'>'
    GE   = r'>='
    EQ   = r'=='
    NE   = r'!='
    LAND = r'&&'
    LOR  = r'\|\|'      # operador OR lógico (||)
    INC  = r'\+\+'
    DEC  = r'--'

    # Números flotantes
    @_(r'\d+\.\d+')
    def FLOAT_LITERAL(self, t):
        t.value = float(t.value)
        return t

    # Números enteros
    @_(r'\d+')
    def INTEGER_LITERAL(self, t):
        try:
            t.value = int(t.value)
        except ValueError:
            print(f"Line {self.lineno}: Número fuera de rango")
            t.value = 0
        return t

    # Caracteres
    @_(r"'(\\.|[^\\'])'")
    def CHAR_LITERAL(self, t):
        val = t.value[1:-1]  # quitar comillas
        escapes = {
            'a': '\a', 'b': '\b', 'e': '\x1b', 'f': '\f',
            'n': '\n', 'r': '\r', 't': '\t', 'v': '\v',
            '\\': '\\', "'": "'", '"': '"',
        }
        if val.startswith('\\'):
            if len(val) == 2 and val[1] in escapes:
                val = escapes[val[1]]
            elif val.startswith('\\0x'):
                try:
                    val = chr(int(val[3:], 16))
                except Exception:
                    print(f"Line {self.lineno}: Secuencia hexadecimal inválida {val}")
                    val = ''
            else:
                print(f"Line {self.lineno}: Secuencia de escape inválida {val}")
                val = ''
        t.value = val
        return t

    # Cadenas de texto
    @_(r'"(\\.|[^\\"])*"')
    def STRING_LITERAL(self, t):
        val = t.value[1:-1]  # quitar comillas
        escapes = {
            'a': '\a','b': '\b','e': '\x1b','f': '\f',
            'n': '\n','r': '\r','t': '\t','v': '\v',
            '\\': '\\',"'": "'",'"': '"',
        }
        def replace_escape(match):
            seq = match.group(1)
            if seq in escapes:
                return escapes[seq]
            elif seq.startswith("0x"):
                try:
                    return chr(int(seq[2:], 16))
                except Exception:
                    print(f"Line {self.lineno}: Secuencia hexadecimal inválida \\{seq}")
                    return ''
            else:
                print(f"Line {self.lineno}: Secuencia de escape inválida \\{seq}")
                return ''
        val = re.sub(r'\\(0x[0-9A-Fa-f]+|.)', replace_escape, val)
        t.value = val
        return t

    # Manejo de errores generales
    def error(self, t):
        print(f"Line {self.lineno}: Caracter invalido = '{t.value[0]}'")
        self.index += 1


def tokenize(txt):
    lexer = Lexer()
    for tok in lexer.tokenize(txt):
        print(tok)


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("usage: python lexer.py filename")
        exit(1)
    tokenize(open(sys.argv[1], encoding='utf-8').read())
