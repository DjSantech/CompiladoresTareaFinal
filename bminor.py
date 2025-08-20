import argparse
import sys
import os

import lexer   

# Función para escanear un archivo con el lexer
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


# Función que representa el análisis sintáctico (parser)
def parse(filename, dot, png):
    print(f" Parseando archivo: {filename}")

    if dot:
        print(" Generando archivo .dot")
    if png:
        print(" Generando archivo .png")


# Función que representa la fase de chequeo semántico
def check(filename, sym):
    print(f" Chequeando archivo: {filename}")

    if sym:
        print(" Mostrando tabla de símbolos")


# Función que representa la fase de generación de código
def codegen(filename):
    print(f" Generando código para: {filename}")


# Nueva función: permite procesar un archivo o todos los de una carpeta
def process_path(command, path, **kwargs):
    # Si el path es una carpeta
    if os.path.isdir(path):
        for file in os.listdir(path):
            if file.endswith(".bminor"):  # solo archivos .bminor
                filepath = os.path.join(path, file)
                print(f"\n Encontrado archivo: {filepath}")

                # Ejecuta el comando en cada archivo
                if command == "scan":
                    scan(filepath)
                elif command == "parse":
                    parse(filepath, kwargs.get("dot", False), kwargs.get("png", False))
                elif command == "check":
                    check(filepath, kwargs.get("sym", False))
                elif command == "codegen":
                    codegen(filepath)
    else:
        # Si es archivo único
        if command == "scan":
            scan(path)
        elif command == "parse":
            parse(path, kwargs.get("dot", False), kwargs.get("png", False))
        elif command == "check":
            check(path, kwargs.get("sym", False))
        elif command == "codegen":
            codegen(path)


# Función principal
def main():
    parser = argparse.ArgumentParser(description="Compilador bminor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: scan
    scan_parser = subparsers.add_parser("scan", help="Escanea el archivo fuente o todos los de una carpeta")
    scan_parser.add_argument("file", help="Archivo o carpeta .bminor")

    # Subcomando: parse
    parse_parser = subparsers.add_parser("parse", help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo o carpeta .bminor")
    parse_parser.add_argument("--dot", action="store_true", help="Generar .dot")
    parse_parser.add_argument("--png", action="store_true", help="Generar .png")

    # Subcomando: check
    check_parser = subparsers.add_parser("check", help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo o carpeta .bminor")
    check_parser.add_argument("--sym", action="store_true", help="Mostrar tabla de símbolos")

    # Subcomando: codegen
    codegen_parser = subparsers.add_parser("codegen", help="Genera código")
    codegen_parser.add_argument("file", help="Archivo o carpeta .bminor")

    args = parser.parse_args()

    # Llama a la función process_path que maneja archivo o carpeta
    process_path(args.command, args.file, dot=getattr(args, "dot", False), png=getattr(args, "png", False), sym=getattr(args, "sym", False))


if __name__ == "__main__":
    main()
