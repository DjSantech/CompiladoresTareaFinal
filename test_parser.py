# test_parser.py
# ------------------------------------------------------------
# Prueba integral del parser + AST.pretty() con rich.Tree
# Incluye: while, do-while, for, if/else, ++x, --x, arrays, print, return
# ------------------------------------------------------------
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from parser import parse  # usa tu parse(txt) que ya construye el AST

console = Console()

program = r"""
# Declaraciones varias
x    : integer = 0;
y    : integer = 10;
sum  : integer;
arr  : array[3] integer = { 1, 2, 3 };

# Función principal sin parámetros que retorna integer
main : function integer() = {
    print("inicio", x, y);

    # WHILE con ++x y if/else
    while (x < y) {
        ++x;
        if (x % 2 == 0) {
            print("par", x);
        } else {
            print("impar", x);
        }
        arr[0] = arr[0] + x;
    }

    # DO-WHILE con --y
    do {
        --y;
        print("y--", y);
    } while (y > 5);

    # FOR con pre-incremento en el step
    for (i = 0; i < 3; ++i) {
        sum = sum + arr[i];
    }

    print("resultado sum:", sum);
    return sum;
};
"""

def main():
    console.rule("[bold blue]Test de Parser y AST.pretty()[/bold blue]")
    console.print(Panel.fit("Fuente de prueba (extracto):\n" + program[:280] + "...", title="Programa de prueba"))
    try:
        ast = parse(program)
        console.print("[bold green]✓ Parseo exitoso[/bold green]")
        console.print("[bold yellow]Árbol (rich.Tree):[/bold yellow]")
        console.print(ast.pretty())
    except Exception as e:
        console.print(f"[bold red]✗ Error al parsear:[/bold red] {e}")

if __name__ == "__main__":
    main()
