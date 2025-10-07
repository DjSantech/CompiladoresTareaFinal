# bminor.py
import argparse
import sys
import os
from pathlib import Path

# Tu lexer y parser
import lexer
from parser import Parser

# Semántico
try:
    from checker import Check
except Exception as e:
    print("Error importando Check desde checker.py:", e)
    print("Verifica que checker.py esté en la misma carpeta y que defina 'class Check' con método 'run'.")
    sys.exit(1)

# Errores
from errors import clear_errors, errors_detected

# (para --ast en parse)
from rich.console import Console
_console = Console()

# Graphviz (impresión de AST)
from astprint import ASTPrinter


# -------------------------------
# Escaneo (lexer)
# -------------------------------
def scan(filename):
    print(f" Escaneando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    data = open(filename, encoding="utf-8").read()
    try:
        tok_lex = lexer.Lexer()      # instancia del lexer
        list(tok_lex.tokenize(data)) # fuerza el escaneo
        print(" ✅ Sin errores léxicos.")
    except Exception as e:
        print(f"Error durante el escaneo: {e}")
        sys.exit(1)


# -------------------------------
# Parseo (parser real)
# -------------------------------
def parse_file(
    filename,
    dot=False,
    png=False,
    ast_flag=False,
    graph=False,
    gv_out=None,
    gv_format="png",
    gv_dot_only=False,
):
    print(f" Parseando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    src = open(filename, encoding="utf-8").read()

    # Tokenizar a lista para no consumir el generador
    tok_lex = lexer.Lexer()
    tokens = list(tok_lex.tokenize(src))

    clear_errors()
    par = Parser()
    try:
        ast = par.parse(iter(tokens))
    except Exception as e:
        print(f"Error durante el parseo: {e}")
        sys.exit(1)

    if errors_detected():
        print(" ❌ Errores gramaticales detectados.")
    else:
        print(" ✅ Sin errores gramaticales.")

        # Árbol con rich.Tree
        if ast_flag:
            try:
                _console.rule("[bold blue]AST (rich.Tree)[/bold blue]")
                _console.print(ast.pretty())
            except AttributeError:
                print("⚠️  ast.pretty() no está disponible. "
                      "Asegúrate de haber añadido pretty() en Node (model.py) "
                      "y de que parser.py importe 'from model import *'.")

        # Grafo con Graphviz (opcional desde parse)
        if graph:
            astprint_file(
                filename,
                out=gv_out or Path(filename).with_suffix("").name + "_AST",
                fmt=gv_format,
                dot_only=gv_dot_only,
                _ast_obj=ast,   # ya tenemos el AST, evitemos reparsear
            )

    # Placeholders para exportar gráficos si luego los implementas
    if dot:
        print(" (TODO) Generar .dot")
    if png:
        print(" (TODO) Generar .png")


# -------------------------------
# ASTPrinter como subcomando dedicado
# -------------------------------
def astprint_file(filename, out=None, fmt="png", dot_only=False, _ast_obj=None):
    """
    Genera el .dot y, salvo que dot_only sea True, también renderiza la imagen.
    Si _ast_obj viene ya construido (por parse_file), se reutiliza.
    """
    print(f" AST-Graphviz de: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    # Si no recibimos el AST, parseamos aquí
    if _ast_obj is None:
        src = open(filename, encoding="utf-8").read()
        tok_lex = lexer.Lexer()
        tokens = list(tok_lex.tokenize(src))
        clear_errors()
        par = Parser()
        try:
            _ast_obj = par.parse(iter(tokens))
        except Exception as e:
            print(f"Error durante el parseo: {e}")
            sys.exit(1)
        if errors_detected():
            print(" ❌ Errores gramaticales detectados.")
            # Puedes salir con error si lo prefieres:
            # sys.exit(1)

    base = out or Path(filename).with_suffix("").name + "_AST"

    try:
        dot_obj = ASTPrinter.render(_ast_obj)

        dot_path = f"{base}.dot"
        with open(dot_path, "w", encoding="utf-8") as f:
            f.write(dot_obj.source)
        print(f" [green]Guardado[/green] {dot_path}")

        if not dot_only:
            out_path = dot_obj.render(base, format=fmt, cleanup=True)
            print(f" [green]Renderizado[/green] {out_path}")
    except Exception as e:
        print("⚠️  No se pudo renderizar con Graphviz.")
        print("    Verifica que el ejecutable 'dot' esté en el PATH (dot -V).")
        print(f"    Detalle: {e}")


# -------------------------------
# Chequeo semántico
# -------------------------------
def check(filename, sym):
    print(f" Chequeando archivo: {filename}")
    if not os.path.exists(filename):
        print(f"Error: el archivo {filename} no existe")
        sys.exit(1)

    # 1) Leer fuente
    src = open(filename, encoding="utf-8").read()

    # 2) Tokenizar a lista (para no consumir el generador dos veces)
    try:
        tok_lex = lexer.Lexer()
    except AttributeError:
        print("Error: no se encontró lexer.Lexer()")
        sys.exit(1)

    tokens = list(tok_lex.tokenize(src))

    # 3) Parsear a AST
    clear_errors()
    try:
        par = Parser()
        ast = par.parse(iter(tokens))
    except Exception as e:
        print(f"Error durante el parseo: {e}")
        sys.exit(1)

    if errors_detected():
        print(" ❌ Errores gramaticales detectados. No se ejecuta el semántico.")
        return

    # 4) Correr el analizador semántico
    try:
        env = Check.run(ast)  # retorna el scope global (Symtab)
    except Exception as e:
        print(f"Error durante el chequeo semántico: {e}")
        sys.exit(1)

    # 5) Reporte
    if errors_detected():
        print(" ❌ Errores semánticos detectados.")
    else:
        print(" ✅ Semántico: OK")

    # 6) (opcional) imprimir símbolos si --sym
    if sym:
        try:
            env.print()  # si tu Symtab tiene .print()
        except Exception:
            try:
                print(env)  # __str__ de Symtab
            except Exception:
                print("⚠️  No pude imprimir la tabla de símbolos (env.print()/__str__).")


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
                        graph=kwargs.get("graph", False),
                        gv_out=kwargs.get("gv_out", None),
                        gv_format=kwargs.get("gv_format", "png"),
                        gv_dot_only=kwargs.get("gv_dot_only", False),
                    )
                elif command == "astprint":
                    astprint_file(
                        filepath,
                        out=kwargs.get("gv_out", None),
                        fmt=kwargs.get("gv_format", "png"),
                        dot_only=kwargs.get("gv_dot_only", False),
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
                graph=kwargs.get("graph", False),
                gv_out=kwargs.get("gv_out", None),
                gv_format=kwargs.get("gv_format", "png"),
                gv_dot_only=kwargs.get("gv_dot_only", False),
            )
        elif command == "astprint":
            astprint_file(
                path,
                out=kwargs.get("gv_out", None),
                fmt=kwargs.get("gv_format", "png"),
                dot_only=kwargs.get("gv_dot_only", False),
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

    # scan
    scan_parser = subparsers.add_parser("scan", help="Escanea el archivo fuente o todos los de una carpeta")
    scan_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")

    # parse
    parse_parser = subparsers.add_parser("parse", help="Parsea el archivo fuente")
    parse_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")
    parse_parser.add_argument("--dot", action="store_true", help="Generar .dot (placeholder)")
    parse_parser.add_argument("--png", action="store_true", help="Generar .png (placeholder)")
    parse_parser.add_argument("--ast", action="store_true", help="Imprimir AST con rich.Tree")
    # Graphviz (opcional desde parse)
    parse_parser.add_argument("--graph", action="store_true", help="Generar gráfico del AST (Graphviz)")
    parse_parser.add_argument("--gv-out", default=None, help="Nombre base de salida para Graphviz (sin extensión)")
    parse_parser.add_argument("--gv-format", default="png", choices=["png", "svg", "pdf"], help="Formato de imagen")
    parse_parser.add_argument("--gv-dot-only", action="store_true", help="Solo guardar el .dot (no renderizar imagen)")

    # astprint (subcomando dedicado)
    astprint_parser = subparsers.add_parser("astprint", help="Genera la imagen del AST con Graphviz")
    astprint_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")
    astprint_parser.add_argument("--gv-out", default=None, help="Nombre base de salida (sin extensión)")
    astprint_parser.add_argument("--gv-format", default="png", choices=["png", "svg", "pdf"], help="Formato de imagen")
    astprint_parser.add_argument("--gv-dot-only", action="store_true", help="Solo guardar el .dot (no renderizar imagen)")

    # check
    check_parser = subparsers.add_parser("check", help="Chequea el archivo fuente")
    check_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")
    check_parser.add_argument("--sym", action="store_true", help="Mostrar tabla de símbolos")

    # codegen
    codegen_parser = subparsers.add_parser("codegen", help="Genera código")
    codegen_parser.add_argument("file", help="Archivo o carpeta .bm/.bminor")

    args = parser.parse_args()

    process_path(
        args.command,
        args.file,
        dot=getattr(args, "dot", False),
        png=getattr(args, "png", False),
        ast=getattr(args, "ast", False),
        graph=getattr(args, "graph", False),
        gv_out=getattr(args, "gv_out", None),
        gv_format=getattr(args, "gv_format", "png"),
        gv_dot_only=getattr(args, "gv_dot_only", False),
        sym=getattr(args, "sym", False),
    )


if __name__ == "__main__":
    main()
