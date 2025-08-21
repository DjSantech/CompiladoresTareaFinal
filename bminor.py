import argparse                # Parseo de argumentos de línea de comandos (CLI)
import sys                     # Salida/terminación del programa y acceso a argv
import os                      # Operaciones de sistema de archivos (paths, listado de directorios)

import lexer                   # Tu módulo lexer.py: expone la función tokenize(txt)


# -------------------------------
# Función para escanear un archivo con el lexer (fase de "scan")
# -------------------------------
def scan(filename):
    print(f" Escaneando archivo: {filename}")

    # Validación: el archivo debe existir antes de abrirlo
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)            # Termina el proceso con código de error

    # Lee todo el archivo fuente en memoria (UTF-8)
    with open(filename, encoding="utf-8") as f:
        data = f.read()
    
    try:
        # Invoca la función pública del lexer para tokenizar e imprimir tabla
        lexer.tokenize(data)
    except Exception as e:
        # Cualquier excepción no controlada se captura y se informa
        print(f"Error durante el escaneo: {e}")
        sys.exit(1)            # Finaliza con error (útil para pipelines/CI)


# -------------------------------
# Función que representa el análisis sintáctico (placeholder)
# Por ahora solo imprime acciones; en el futuro llamará a tu parser real.
# -------------------------------
def parse(filename, dot, png):
    print(f" Parseando archivo: {filename}")

    # Flags opcionales para exportar gráficos del AST (cuando implementes el parser)
    if dot:
        print(" Generando archivo .dot")
    if png:
        print(" Generando archivo .png")


# -------------------------------
# Función que representa el chequeo semántico (placeholder)
# En el futuro debería recorrer el AST y validar tipos/alcances.
# -------------------------------
def check(filename, sym):
    print(f" Chequeando archivo: {filename}")

    # Flag para mostrar una tabla de símbolos (cuando esté implementada)
    if sym:
        print(" Mostrando tabla de símbolos")


# -------------------------------
# Función que representa la generación de código (placeholder)
# En el futuro debería emitir código intermedio/objetivo.
# -------------------------------
def codegen(filename):
    print(f" Generando código para: {filename}")


# -------------------------------
# Utilidad: procesa un path que puede ser archivo único o carpeta.
# Si es carpeta, aplica el comando a TODOS los .bminor dentro (no recursivo).
# -------------------------------
def process_path(command, path, **kwargs):
    # Si el path es una carpeta...
    if os.path.isdir(path):
        for file in os.listdir(path):                         # Itera archivos del directorio
            if file.endswith(".bminor"):                      # Solo fuentes del lenguaje
                filepath = os.path.join(path, file)
                print(f"\n Encontrado archivo: {filepath}")

                # Despacha al subcomando correspondiente
                if command == "scan":
                    scan(filepath)
                elif command == "parse":
                    parse(filepath,
                          kwargs.get("dot", False),
                          kwargs.get("png", False))
                elif command == "check":
                    check(filepath, kwargs.get("sym", False))
                elif command == "codegen":
                    codegen(filepath)
    else:
        # Si es archivo único, simplemente reenvía al subcomando
        if command == "scan":
            scan(path)
        elif command == "parse":
            parse(path,
                  kwargs.get("dot", False),
                  kwargs.get("png", False))
        elif command == "check":
            check(path, kwargs.get("sym", False))
        elif command == "codegen":
            codegen(path)


# -------------------------------
# Punto de entrada principal: define CLI con subcomandos
# -------------------------------
def main():
    # Descripción principal del programa
    parser = argparse.ArgumentParser(description="Compilador bminor")
    # Crea contenedor de subcomandos (scan/parse/check/codegen)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ----- Subcomando: scan -----
    # Escanea un archivo o todos los .bminor de una carpeta
    scan_parser = subparsers.add_parser("scan",
                                        help="Escanea el archivo fuente o todos los de una carpeta")
    scan_parser.add_argument("file", help="Archivo o carpeta .bminor")

    # ----- Subcomando: parse -----
    # Parseo del archivo (placeholder) + flags de exportación gráfica
    parse_parser = subparsers.add_parser("parse",
                                         help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo o carpeta .bminor")
    parse_parser.add_argument("--dot", action="store_true", help="Generar .dot")
    parse_parser.add_argument("--png", action="store_true", help="Generar .png")

    # ----- Subcomando: check -----
    # Chequeo semántico (placeholder) + flag para mostrar la tabla de símbolos
    check_parser = subparsers.add_parser("check",
                                         help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo o carpeta .bminor")
    check_parser.add_argument("--sym", action="store_true", help="Mostrar tabla de símbolos")

    # ----- Subcomando: codegen -----
    # Generación de código (placeholder)
    codegen_parser = subparsers.add_parser("codegen",
                                           help="Genera código")
    codegen_parser.add_argument("file", help="Archivo o carpeta .bminor")

    # Parsea los argumentos de la CLI provistos por el usuario
    args = parser.parse_args()

    # Llama a process_path con los flags relevantes para cada subcomando.
    # getattr(...) devuelve False si el atributo no existe (p. ej., 'dot' no existe en 'scan').
    process_path(
        args.command,
        args.file,
        dot=getattr(args, "dot", False),
        png=getattr(args, "png", False),
        sym=getattr(args, "sym", False)
    )


# Ejecuta main() solo si el archivo se ejecuta directamente (no cuando se importa como módulo)
if __name__ == "__main__":
    main()
