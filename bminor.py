# bminor.py
import argparse
import sys
import os
import json

# Tu lexer
import lexer

# -> IMPORTANTE: este import asume que tu parser completo está en parser.py
#    Si en cambio usas el archivo que te pasé (parser_filled_commented.py),
#    cambia la siguiente línea por:
#    from parser_filled_commented import Parser
from parser import Parser

# Manejo centralizado de errores
from errors import clear_errors, errors_detected


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
        lexer.tokenize(data)
    except Exception as e:
        print(f"Error durante el escaneo: {e}")
        sys.exit(1)


# -------------------------------
# Parseo (parser real)
# -------------------------------
def parse(filename, dot, png):
    print(f" Parseando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    with open(filename, encoding="utf-8") as f:
        src = f.read()

    # Limpiamos contador de errores
    clear_errors()

    # Construimos lexer+parser y parseamos
    lex = lexer.Lexer()
    par = Parser()

    try:
        ast = par.parse(lex.tokenize(src))
    except Exception as e:
        print(f"Error durante el parseo: {e}")
        sys.exit(1)

    # ¿Hubo errores reportados por errors.error(...)?
    if errors_detected():
        print(" ❌ Errores gramaticales detectados.")
        # Si quieres terminar con error para CI/pipelines:
        # sys.exit(1)
    else:
        print(" ✅ Sin errores gramaticales.")
        # (Opcional) imprime el AST en JSON para debug:
        # from model import Node
        # def ast_to_dict(node):
        #     if isinstance(node, list):
        #         return [ast_to_dict(n) for n in node]
        #     elif hasattr(node, "__dict__"):
        #         return {k: ast_to_dict(v) for k, v in node.__dict__.items()}
        #     else:
        #         return node
        # print(json.dumps(ast_to_dict(ast), ensure_ascii=False, indent=2))

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
    if os.path.isdir(path):
        for file in os.listdir(path):
            if file.endswith(".bminor"):
                filepath = os.path.join(path, file)
                print(f"\n Encontrado archivo: {filepath}")
                if command == "scan":
                    scan(filepath)
                elif command == "parse":
                    parse(filepath, kwargs.get("dot", False), kwargs.get("png", False))
                elif command == "check":
                    check(filepath, kwargs.get("sym", False))
                elif command == "codegen":
                    codegen(filepath)
    else:
        if command == "scan":
            scan(path)
        elif command == "parse":
            parse(path, kwargs.get("dot", False), kwargs.get("png", False))
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
    scan_parser.add_argument("file", help="Archivo o carpeta .bminor")

    parse_parser = subparsers.add_parser("parse", help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo o carpeta .bminor")
    parse_parser.add_argument("--dot", action="store_true", help="Generar .dot")
    parse_parser.add_argument("--png", action="store_true", help="Generar .png")

    check_parser = subparsers.add_parser("check", help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo o carpeta .bminor")
    check_parser.add_argument("--sym", action="store_true", help="Mostrar tabla de símbolos")

    codegen_parser = subparsers.add_parser("codegen", help="Genera código")
    codegen_parser.add_argument("file", help="Archivo o carpeta .bminor")

    args = parser.parse_args()

    process_path(
        args.command,
        args.file,
        dot=getattr(args, "dot", False),
        png=getattr(args, "png", False),
        sym=getattr(args, "sym", False),
    )


if __name__ == "__main__":
    main()
