# errors.py — Reporte de errores con contexto en terminal
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from rich.console import Console
from rich.markup import escape

_console = Console()

# Estado global muy simple (compat con tu proyecto)
_FILENAME: Optional[str] = None
_LINES: List[str] = []
_HAD_ERRORS: bool = False

@dataclass
class Msg:
    kind: str          # "Léxico" | "Sintáctico" | "Semántico" | ...
    text: str
    lineno: Optional[int] = None
    col: Optional[int] = None

_MSGS: List[Msg] = []


def set_source(filename: str, text: str) -> None:
    """Debes llamarla antes de escanear/parsear para poder mostrar la línea con caret."""
    global _FILENAME, _LINES
    _FILENAME = filename
    _LINES = text.splitlines()


def clear_errors() -> None:
    global _HAD_ERRORS, _MSGS
    _HAD_ERRORS = False
    _MSGS = []


def errors_detected() -> bool:
    return _HAD_ERRORS


def _label_for(kind: str) -> str:
    kind_low = kind.lower()
    if "léx" in kind_low:       # Léxico
        return "[bold magenta]Léxico[/]"
    if "sint" in kind_low:      # Sintáctico
        return "[bold yellow]Sintáctico[/]"
    if "sem" in kind_low:       # Semántico
        return "[bold red]Semántico[/]"
    return f"[bold]{escape(kind)}[/]"


def error(text: str, lineno: Optional[int] = None, col: Optional[int] = None, kind: str = "Error") -> None:
    """Registra e imprime un error con color y contexto."""
    global _HAD_ERRORS
    _HAD_ERRORS = True
    m = Msg(kind=kind, text=text, lineno=lineno, col=col)
    _MSGS.append(m)

    # Encabezado con tipo
    head = _label_for(kind)
    # Localización
    where = ""
    if _FILENAME is not None and lineno is not None:
        where = f"{_FILENAME}:{lineno}"
    elif lineno is not None:
        where = f"línea {lineno}"

    # Imprime
    _console.print(f"{head}: {escape(text)}")
    if where:
        _console.print(f"  [dim]{escape(where)}[/]")

    # Línea de código + caret si hay info
    if lineno is not None and 1 <= lineno <= len(_LINES):
        line = _LINES[lineno - 1]
        _console.print(f"    {escape(line)}")
        if col and col > 0:
            spaces = " " * (col + 3)  # 3 por la sangría "    "
            _console.print(f"{spaces}^", style="bold red")


def warn(text: str, lineno: Optional[int] = None, col: Optional[int] = None, kind: str = "Advertencia") -> None:
    """Advertencias con color tenue."""
    m = Msg(kind=kind, text=text, lineno=lineno, col=col)
    _MSGS.append(m)
    head = "[bold blue]Aviso[/]"
    where = ""
    if _FILENAME is not None and lineno is not None:
        where = f"{_FILENAME}:{lineno}"
    elif lineno is not None:
        where = f"línea {lineno}"
    _console.print(f"{head}: {escape(text)}")
    if where:
        _console.print(f"  [dim]{escape(where)}[/]")


def dump_errors() -> None:
    """Por si quieres al final reimprimir/resumir (opcional)."""
    if not _MSGS:
        _console.print("[green]No se registraron errores[/]")
