# lexer.py
#
# Analizador Léxico para el lenguaje B-Minor
from tabulate import tabulate
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
        INC, DEC,                     # Incremento / Decremento

        # Literales
        ID, CHAR_LITERAL, FLOAT_LITERAL, INTEGER_LITERAL, STRING_LITERAL
    }
    literals = '+-*/%^=()[]{}:;,<>'

    # Caracteres a ignorar
    ignore = ' \t\r'

    MAX_INT = 2**63 - 1
    MIN_INT = -2**63

    
    # Saltos de línea
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    # Comentarios
    @_(r'//.*')
    def ignore_cppcomment(self, t):
        pass

    @_(r'/\*')
    def COMMENT(self, t):
        # Buscar el cierre '*/' desde la posición actual
        data = self.text
        start = self.index  # ya estamos después de '/*'
        end = data.find('*/', start)

        if end == -1:
            # No se cerró el comentario: contar saltos de línea y reportar error
            fragment = data[start:]
            self.lineno += fragment.count('\n')
            print(f"Line {t.lineno}: Comentario de bloque sin cierre '/*'")
            # Consumir todo para detener el escaneo dentro del comentario abierto
            self.index = len(data)
            return

        # Comentario bien cerrado: actualizar líneas y saltar el bloque
        fragment = data[start:end]
        self.lineno += fragment.count('\n')
        self.index = end + 2  # saltar '*/'
        # No devolvemos token (se ignora el comentario)

    # Identificador y Palabras reservadas
    ID = r'[_a-zA-Z]\w*'
    ID['array'] = ARRAY
    ID['auto'] = AUTO
    ID['boolean'] = BOOLEAN
    ID['char'] = CHAR
    ID['else'] = ELSE
    ID['false'] = FALSE
    ID['float'] = FLOAT
    ID['for'] = FOR
    ID['function'] = FUNCTION
    ID['if'] = IF
    ID['integer'] = INTEGER
    ID['print'] = PRINT
    ID['return'] = RETURN
    ID['string'] = STRING
    ID['true'] = TRUE
    ID['void'] = VOID
    ID['while'] = WHILE

    # Reglas para operadores
    LE = r'<='
    GE = r'>='
    EQ = r'=='
    NE = r'!='
    LAND = r'&&'
    LOR = r'\|\|'
    INC = r'\+\+'
    DEC = r'--'
    LT = r'<'
    GT = r'>'

    # Número float mal formado
    @_(r'\d+\.(?=[A-Za-z_])\w*')
    def MALFORMED_FLOAT(self, t):
        # t.value es la secuencia completa, p.ej. "12.s1"
        m = re.match(r'\d+\.([A-Za-z_])', t.value)
        off = m.group(1) if m else '?'
        print(f"Line {t.lineno}: Número float mal formado. "
            f"Se encontró '{off}' inmediatamente después del punto decimal en '{t.value}'. "
            f"Se esperaban dígitos (ej. 12.3).")
        # ignorar el token mal formado
        return


    # Números flotantes
    @_(r'\d+\.\d+')
    def FLOAT_LITERAL(self, t):
        t.value = float(t.value)
        return t



    @_(r'\d+')
    def INTEGER_LITERAL(self, t):
        val = int(t.value)
        if val > self.MAX_INT:
            print(
                f"Line {t.lineno}: Error léxico. Entero demasiado grande: {t.value} "
                f"(máximo permitido {self.MAX_INT})"
            )
            return None  # no generar token
        t.value = val
        return t

    
   
    @_(r"'([^\\\n']|\\.)*'")
    def CHAR_LITERAL(self, t):
        val = t.value[1:-1]  # contenido entre comillas

        escapes = {
            'a': '\a', 'b': '\b', 'e': '\x1b', 'f': '\f',
            'n': '\n', 'r': '\r', 't': '\t', 'v': '\v',
            '\\': '\\', "'": "'", '"': '"',
        }

        
        if not val.startswith('\\') and len(val) != 1:
            print(f"Line {t.lineno}: Carácter inválido: demasiado largo ('{val}'). "
                f"Solo se permite un carácter o una secuencia de escape.")
            return None

        # Con escape
        if val.startswith('\\'):
            # \uXXXX → no soportado
            if val.startswith('u'):
                print(f"Line {t.lineno}: Secuencia Unicode no soportada en char: \\{val} "
                    f"(solo ASCII o \\0xHH).")
                return None

            # Escapes simples: \n, \t, \\, \', \" ... exactamente 2 chars
            if len(val) == 2 and val[1] in escapes:
                t.value = escapes[val[1]]
                return t

            # Hex tipo \0xHH...
            if val.startswith('0x'):
                hexpart = val[2:]
                if not re.fullmatch(r'[0-9A-Fa-f]+', hexpart):
                    print(f"Line {t.lineno}: Secuencia hexadecimal inválida: \\{val}")
                    return None
                code = int(hexpart, 16)
                # Limitar a ASCII si quieres (0x00–0x7F):
                if code > 0x7F:
                    print(f"Line {t.lineno}: Código fuera de ASCII en char: \\0x{hexpart}")
                    return None
                t.value = chr(code)
                return t

            # Cualquier otro escape es inválido
            print(f"Line {t.lineno}: Secuencia de escape inválida: \\{val}")
            return None

        # Caso válido: un único carácter sin escape
        t.value = val
        return t


    @_(r'"([^"\n\\]|\\.)*(\n|$)')
    def STRING_UNCLOSED(self, t):
        print(f"Line {t.lineno}: Error léxico. Cadena sin cierre '\"'")
        # Avanzar el índice hasta después de lo que consumió
        self.index = t.index + len(t.value)
        return None


    # Cadenas de texto
    @_(r'"(\\.|[^\\"])*"')
    def STRING_LITERAL(self, t):
        val = t.value[1:-1]  # quitar comillas

        #  Verificación: si hay salto de línea sin escape → error
        if "\n" in val or "\r" in val:
            print(f"Line {t.lineno}: Error léxico. "
                f"Las cadenas no pueden contener saltos de línea sin escape.")
            t.value = ""   # opcional: limpiar valor
            return None    # no devolver token

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
    tokens = [(tok.type, repr(tok.value), tok.lineno) for tok in lexer.tokenize(txt)]
    headers = ["TOKEN", "VALOR", "LÍNEA"]
    print(tabulate(tokens, headers=headers, tablefmt="grid"))


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("usage: python lexer.py filename")
        exit(1)
    tokenize(open(sys.argv[1], encoding='utf-8').read())
