# lexer.py
#
# Analizador Léxico para el lenguaje B-Minor

from tabulate import tabulate     # Imprimir la tabla de tokens en formato "grid"
import sly                        # SLY: framework tipo Lex/Yacc para Python
import re                         # Expresiones regulares (validaciones/reemplazos)

class Lexer(sly.Lexer):           # El lexer hereda de sly.Lexer
    tokens = {                    # Conjunto de tipos de tokens simbólicos que producirá el lexer
        # Palabras Reservadas
        ARRAY, AUTO, BOOLEAN, CHAR, ELSE, FALSE, FLOAT, FOR, FUNCTION,
        IF, INTEGER, PRINT, RETURN, STRING, TRUE, VOID, WHILE,

        # Operadores compuestos
        LT, LE, GT, GE, EQ, NE,   # Relacionales: < <= > >= == !=
        LAND, LOR,                # Lógicos: && ||
        INC, DEC,                 # ++ --

        # Literales (tokens con valor asociado)
        ID, CHAR_LITERAL, FLOAT_LITERAL, INTEGER_LITERAL, STRING_LITERAL
    }
    literals = '+-*/%^=()[]{}:;,<>'  # Caracteres sueltos que se devuelven como tokens tal cual

    # Caracteres a ignorar globalmente (no generan tokens)
    ignore = ' \t\r'               # Espacio, tab y retorno de carro (CR). \n se maneja aparte

    # Límites de enteros para simular un tipo entero (aquí 64 bits con signo)
    MAX_INT = 2**63 - 1
    MIN_INT = -2**63

    # -----------------------------
    # Reglas especiales (decoradas) 
    # -----------------------------

    @_(r'\n+')                     # Captura uno o más saltos de línea
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')  # Actualiza el número de línea del lexer

    @_(r'//.*')                    # Comentario de una línea tipo C++
    def ignore_cppcomment(self, t):
        pass                       # Se ignora completamente

    @_(r'/\*')                     # Inicio de comentario de bloque
    def COMMENT(self, t):
        # Buscar el cierre '*/' desde la posición actual del texto
        data = self.text           # Texto completo que está analizando el lexer
        start = self.index         # Posición actual (después de haber leído '/*')
        end = data.find('*/', start)  # Busca el índice donde cierra el bloque

        if end == -1:              # Si no se encontró el cierre
            fragment = data[start:]                 # Resto del archivo (desde el inicio del comentario)
            self.lineno += fragment.count('\n')     # Ajusta líneas por el bloque no cerrado
            print(f"Line {t.lineno}: Comentario de bloque sin cierre '/*'")  # Reporta error
            self.index = len(data)                  # Consume hasta EOF para no seguir dentro del comentario
            return

        # Si está bien cerrado, solo ajusta líneas y salta el bloque
        fragment = data[start:end]                  # Contenido del comentario
        self.lineno += fragment.count('\n')         # Suma los saltos dentro del comentario
        self.index = end + 2                        # Avanza el índice luego de '*/'
        # No devuelve token: se ignora

    # -----------------------------
    # Identificadores y reservadas
    # -----------------------------
    ID = r'[_a-zA-Z]\w*'           # Regex para identificadores: letra/guion_bajo seguido de alfanumérico/_
    # A continuación se mapean lexemas específicos a tokens de palabra reservada:
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

    # -----------------------------
    # Operadores compuestos
    # -----------------------------
    LE   = r'<='                   # <=
    GE   = r'>='                   # >=
    EQ   = r'=='                   # ==
    NE   = r'!='                   # !=
    LAND = r'&&'                   # &&
    LOR  = r'\|\|'                 # ||  (hay que escapar la barra en regex)
    INC  = r'\+\+'                 # ++  (escapar + en regex)
    DEC  = r'--'                   # --
    LT   = r'<'                    # <
    GT   = r'>'                    # >

    # -----------------------------
    # Errores específicos primero
    # -----------------------------

    @_(r'\d+\.(?=[A-Za-z_])\w*')   # Coincide con "12.s1" (letra/underscore inmediatamente tras '.')
    def MALFORMED_FLOAT(self, t):
        # t.value = ejemplo "12.s1"; extrae el primer char ilegal después del punto
        m = re.match(r'\d+\.([A-Za-z_])', t.value)
        off = m.group(1) if m else '?'              # Carácter que causa el error
        print(f"Line {t.lineno}: Número float mal formado. "
              f"Se encontró '{off}' inmediatamente después del punto decimal en '{t.value}'. "
              f"Se esperaban dígitos (ej. 12.3).")
        return                                     # No genera token (descarta y continúa)

    # -----------------------------
    # Literales numéricos
    # -----------------------------

    @_(r'\d+\.\d+')                # Flotantes válidos: uno o más dígitos, punto, uno o más dígitos
    def FLOAT_LITERAL(self, t):
        t.value = float(t.value)   # Convierte a float de Python (solo para comodidad)
        return t

    @_(r'\d+')                     # Enteros: uno o más dígitos
    def INTEGER_LITERAL(self, t):
        val = int(t.value)         # Convierte a int de Python
        if val > self.MAX_INT:     # Valida overflow según el límite configurado
            print(
                f"Line {t.lineno}: Error léxico. Entero demasiado grande: {t.value} "
                f"(máximo permitido {self.MAX_INT})"
            )
            return None            # No devuelve token (reporta error y sigue)
        t.value = val              # Asigna el valor entero al token
        return t

    # -----------------------------
    # Literales de carácter
    # -----------------------------

    @_(r"'([^\\\n']|\\.)*'")       # Coincide: 'x' o secuencias con escape; no permite salto de línea
    def CHAR_LITERAL(self, t):
        val = t.value[1:-1]        # Quita comillas simples -> contenido del char

        # Tabla de escapes soportados (coincide con strings)
        escapes = {
            'a': '\a', 'b': '\b', 'e': '\x1b', 'f': '\f',
            'n': '\n', 'r': '\r', 't': '\t', 'v': '\v',
            '\\': '\\', "'": "'", '"': '"',
        }

        # Si no es escape y tiene más de 1 carácter -> error (p.ej., 'ab')
        if not val.startswith('\\') and len(val) != 1:
            print(f"Line {t.lineno}: Carácter inválido: demasiado largo ('{val}'). "
                  f"Solo se permite un carácter o una secuencia de escape.")
            return None

        # Manejo de escapes
        if val.startswith('\\'):
            # \uXXXX (Unicode) no soportado para char en este lenguaje
            if val.startswith('u'):
                print(f"Line {t.lineno}: Secuencia Unicode no soportada en char: \\{val} "
                      f"(solo ASCII o \\0xHH).")
                return None

            # Escapes simples de longitud 2: \n, \t, \\, \', \"
            if len(val) == 2 and val[1] in escapes:
                t.value = escapes[val[1]]  # Reemplaza por el carácter real
                return t

            # Hex tipo \0xHH...
            if val.startswith('0x'):
                hexpart = val[2:]                               # Parte hexadecimal
                if not re.fullmatch(r'[0-9A-Fa-f]+', hexpart):  # Valida formato hexadecimal
                    print(f"Line {t.lineno}: Secuencia hexadecimal inválida: \\{val}")
                    return None
                code = int(hexpart, 16)                         # Convierte a código numérico
                if code > 0x7F:                                 # Restringe a ASCII
                    print(f"Line {t.lineno}: Código fuera de ASCII en char: \\0x{hexpart}")
                    return None
                t.value = chr(code)                             # Carácter resultante
                return t

            # Cualquier otro escape no reconocido
            print(f"Line {t.lineno}: Secuencia de escape inválida: \\{val}")
            return None

        # Caso válido: un único carácter (sin escape)
        t.value = val
        return t

    # -----------------------------
    # Cadenas sin cierre
    # -----------------------------

    @_(r'"([^"\n\\]|\\.)*(\n|$)')  # Abre con " y no aparece otra " antes de fin de línea/archivo
    def STRING_UNCLOSED(self, t):
        print(f"Line {t.lineno}: Error léxico. Cadena sin cierre '\"'")  # Reporta el error
        # Avanza el índice hasta lo consumido para evitar que el primer " caiga en error()
        self.index = t.index + len(t.value)
        return None

    # -----------------------------
    # Cadenas de texto válidas
    # -----------------------------

    @_(r'"(\\.|[^\\"])*"')         # " ... " con escapes permitidos (no incluye comillas sin escape)
    def STRING_LITERAL(self, t):
        val = t.value[1:-1]        # Quita comillas dobles

        # Si llega un salto de línea real dentro -> error (no debería pasar con la regex, pero por si acaso)
        if "\n" in val or "\r" in val:
            print(f"Line {t.lineno}: Error léxico. "
                  f"Las cadenas no pueden contener saltos de línea sin escape.")
            t.value = ""
            return None

        # Mapeo de escapes igual que en char
        escapes = {
            'a': '\a','b': '\b','e': '\x1b','f': '\f',
            'n': '\n','r': '\r','t': '\t','v': '\v',
            '\\': '\\',"'" : "'",'"': '"',
        }

        # Función auxiliar para reemplazar escapes dentro del string
        def replace_escape(match):
            seq = match.group(1)               # Lo que sigue después del backslash
            if seq in escapes:                 # Escapes simples: \n, \t, etc.
                return escapes[seq]
            elif seq.startswith("0x"):         # Hex tipo \0xHH...
                try:
                    return chr(int(seq[2:], 16))
                except Exception:
                    print(f"Line {self.lineno}: Secuencia hexadecimal inválida \\{seq}")
                    return ''
            else:                              # Escape desconocido (p.ej., \q)
                print(f"Line {self.lineno}: Secuencia de escape inválida \\{seq}")
                return ''

        # Reemplaza todas las secuencias \X por su valor (o '' si fueron inválidas)
        val = re.sub(r'\\(0x[0-9A-Fa-f]+|.)', replace_escape, val)
        t.value = val
        return t

    # -----------------------------
    # Manejo de cualquier otro carácter no reconocido
    # -----------------------------
    def error(self, t):
        print(f"Line {self.lineno}: Caracter invalido = '{t.value[0]}'")  # Reporta el símbolo ilegal
        self.index += 1                          # Avanza un carácter y continúa el análisis

# -----------------------------------------
# Función auxiliar para tokenizar e imprimir
# -----------------------------------------
def tokenize(txt):
    lexer = Lexer()                              # Instancia del lexer
    tokens = [(tok.type, repr(tok.value), tok.lineno)   # Construye filas (tipo, valor, línea)
              for tok in lexer.tokenize(txt)]   # tokeniza el texto completo
    headers = ["TOKEN", "VALOR", "LÍNEA"]       # Encabezados de la tabla
    print(tabulate(tokens, headers=headers, tablefmt="grid"))  # Imprime en formato tabla

# -----------------------------------------
# Punto de entrada si se ejecuta como script
# -----------------------------------------
if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:                      # Verifica uso correcto
        print("usage: python lexer.py filename")
        exit(1)
    tokenize(open(sys.argv[1], encoding='utf-8').read())  # Lee archivo y tokeniza
