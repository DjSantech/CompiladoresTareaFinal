
import argparse
import sys
import os


import lexer   
# Función para escanear un archivo con el lexer
def scan(filename):
    # Muestra en consola el nombre del archivo que se va a analizar
    print(f" Escaneando archivo: {filename}")

    # Verifica que el archivo exista, si no existe termina el programa con error
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    # Abre el archivo en modo lectura con codificación UTF-8
    with open(filename, encoding="utf-8") as f:
        # Lee todo el contenido del archivo en la variable "data"
        data = f.read()
    
    try:
        # Llama a la función tokenize del lexer, que analiza el contenido leído
        lexer.tokenize(data)  
    except Exception as e:
        # Si ocurre un error en el análisis, lo muestra y termina con código de error
        print(f"Error durante el escaneo: {e}")
        sys.exit(1)


# Función que representa el análisis sintáctico (parser)
def parse(filename, dot, png):
    # Indica en consola qué archivo está siendo parseado
    print(f" Parseando archivo: {filename}")

    # Si el usuario pidió generar archivo .dot, se muestra un aviso
    if dot:
        print(" Generando archivo .dot")

    # Si el usuario pidió generar archivo .png, se muestra un aviso
    if png:
        print(" Generando archivo .png")


# Función que representa la fase de chequeo semántico
def check(filename, sym):
    # Muestra que se está chequeando el archivo
    print(f" Chequeando archivo: {filename}")

    # Si el usuario pidió ver la tabla de símbolos, se indica en consola
    if sym:
        print(" Mostrando tabla de símbolos")


# Función que representa la fase de generación de código
def codegen(filename):
    # Muestra que se está generando código para el archivo
    print(f" Generando código para: {filename}")


# Función principal que gestiona los comandos del compilador
def main():
    # Se crea un objeto parser que manejará los argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Compilador bminor - frontend")

    # Crea un conjunto de subcomandos (scan, parse, etc.)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: scan
    scan_parser = subparsers.add_parser("scan", help="Escanea el archivo fuente")
    scan_parser.add_argument("file", help="Archivo .bminor")  # archivo obligatorio

    # Subcomando: parse
    parse_parser = subparsers.add_parser("parse", help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo .bminor")
    parse_parser.add_argument("dot", action="store_true", help="Generar .dot")
    parse_parser.add_argument("png", action="store_true", help="Generar .png")

    # Subcomando: check
    check_parser = subparsers.add_parser("check", help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo .bminor")
    check_parser.add_argument("sym", action="store_true", help="Mostrar tabla de símbolos")

    # Subcomando: codegen
    codegen_parser = subparsers.add_parser("codegen", help="Genera código")
    codegen_parser.add_argument("file", help="Archivo .bminor")

    # Procesa los argumentos recibidos desde la terminal
    args = parser.parse_args()

    # Según el comando recibido, llama a la función correspondiente
    if args.command == "scan":
        scan(args.file)
    elif args.command == "parse":
        parse(args.file, args.dot, args.png)
    elif args.command == "check":
        check(args.file, args.sym)
    elif args.command == "codegen":
        codegen(args.file)


# Si se ejecuta directamente este archivo (no importado como módulo), corre main()
if __name__ == "__main__":
    main()
