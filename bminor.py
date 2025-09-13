# bminor.py
import argparse
import sys
import os

# Tu lexer
import lexer

# Parser real (asegúrate de que dentro de parser.py importes: from model import *)
from parser import Parser

# Manejo centralizado de errores
from errors import clear_errors, errors_detected

# (para --ast)
from rich.console import Console
_console = Console()


# -------------------------------
# Escaneo (lexer)
# -------------------------------
def scan(filename):
    print(f" Escaneando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    with open(filename, encoding="utf-8") as f:
        data = f.read()

    try:
        # usa la función auxiliar de tu lexer que imprime tabla con tabulate
        lexer.tokenize(data)
    except Exception as e:
        print(f"Error durante el escaneo: {e}")
        sys.exit(1)


# -------------------------------
# Parseo (parser real)
# -------------------------------
def parse_file(filename, dot=False, png=False, ast_flag=False):
    print(f" Parseando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    src = open(filename, encoding="utf-8").read()

    # 1) Tokenizamos a una LISTA (para evitar consumir el generador sin querer)
    tok_lex = lexer.Lexer()
    tokens = list(tok_lex.tokenize(src))
    # print(f"[debug] tokens: {len(tokens)}")  # <- descomenta si quieres ver el conteo

    # 2) Parseamos sobre ese iterador de tokens
    clear_errors()
    par = Parser()
    try:
        ast = par.parse(iter(tokens))
    except Exception as e:
        print(f"Error durante el parseo: {e}")
        sys.exit(1)

    # ¿Hubo errores reportados por errors.error(...)?
    if errors_detected():
        print(" ❌ Errores gramaticales detectados.")
        # sys.exit(1)  # descomenta si quieres fallar duro en CI
    else:
        print(" ✅ Sin errores gramaticales.")

        # Mostrar AST con rich.Tree si lo piden
        if ast_flag:
            try:
                _console.rule("[bold blue]AST (rich.Tree)[/bold blue]")
                _console.print(ast.pretty())
            except AttributeError:
                print("⚠️  ast.pretty() no está disponible. "
                      "Asegúrate de haber añadido pretty() en Node (model.py) "
                      "y de que parser.py importe 'from model import *'.")

    # Placeholders para exportar gráficos si luego los implementas
    if dot:
        print(" (TODO) Generar .dot")
    if png:
        print(" (TODO) Generar .png")


# -------------------------------
# Chequeo semántico (placeholder)
# -------------------------------
def check(filename, sym):
    print(f" Chequeando archivo: {filename}")
    if sym:
        print(" (TODO) Mostrar tabla de símbolos")


# -------------------------------
# Generación de código (placeholder)
# -------------------------------
def codegen(filename):
    print(f" Generando código para: {filename}")


# -------------------------------
# Procesa archivo o carpeta (no recursivo)
# -------------------------------
def process_path(command, path, **kwargs):
    def is_source(name: str) -> bool:
        return name.endswith(".bminor") or name.endswith(".bm")

    if os.path.isdir(path):
        for file in os.listdir(path):
            if is_source(file):
                filepath = os.path.join(path, file)
                print(f"\n Encontrado archivo: {filepath}")
                if command == "scan":
                    scan(filepath)
                elif command == "parse":
                    parse_file(
                        filepath,
                        dot=kwargs.get("dot", False),
                        png=kwargs.get("png", False),
                        ast_flag=kwargs.get("ast", False),
                    )
                elif command == "check":
                    check(filepath, kwargs.get("sym", False))
                elif command == "codegen":
                    codegen(filepath)
    else:
        if not is_source(path):
            print("Advertencia: la ruta no parece .bm/.bminor; se intentará igual.")
        if command == "scan":
            scan(path)
        elif command == "parse":
            parse_file(
                path,
                dot=kwargs.get("dot", False),
                png=kwargs.get("png", False),
                ast_flag=kwargs.get("ast", False),
            )
        elif command == "check":
            check(path, kwargs.get("sym", False))
        elif command == "codegen":
            codegen(path)


# -------------------------------
# CLI
# -------------------------------
def main():
    parser = argparse.ArgumentParser(description="Compilador bminor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Escanea el archivo fuente o todos los de una carpeta")
    scan_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")

    parse_parser = subparsers.add_parser("parse", help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")
    parse_parser.add_argument("--dot", action="store_true", help="Generar .dot")
    parse_parser.add_argument("--png", action="store_true", help="Generar .png")
    parse_parser.add_argument("--ast", action="store_true", help="Imprimir AST con rich.Tree")

    check_parser = subparsers.add_parser("check", help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")
    check_parser.add_argument("--sym", action="store_true", help="Mostrar tabla de símbolos")

    codegen_parser = subparsers.add_parser("codegen", help="Genera código")
    codegen_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")

    args = parser.parse_args()

    process_path(
        args.command,
        args.file,
        dot=getattr(args, "dot", False),
        png=getattr(args, "png", False),
        ast=getattr(args, "ast", False),
        sym=getattr(args, "sym", False),
    )


if __name__ == "__main__":
    main()
