#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conjuntos PRIMEROS y SIGUIENTES (FIRST y FOLLOW) para una Gramática Libre de Contexto (CFG).

USO:
  python Conjuntos_primeros.py ruta/al/archivo.txt

FORMATO DEL ARCHIVO DE GRAMÁTICA:
  - Una producción por línea.
  - Separar lado izquierdo y derecho con "->".
  - Alternativas separadas con "|".
  - Separar TODOS los símbolos por espacios (incluye paréntesis, comas, llaves, etc.).
  - Epsilon puede escribirse como: ε, epsilon, EPS, lambda, Λ o e (todas se normalizan a 'ε').
  - Las líneas que comienzan con '#' son comentarios y se ignoran.
Ejemplo:
  E  -> T E'
  E' -> + T E' | ε
  T  -> F T'
  T' -> * F T' | ε
  F  -> ( E ) | id

NOTAS:
  - Este programa calcula PRIMEROS(X) para cada símbolo X y SIGUIENTES(A) para cada no terminal A.
  - Por convenio, SIGUIENTES(S) del símbolo inicial S contiene el marcador de fin '$'.
  - La gramática puede tener recursión izquierda: NO es problema para FIRST/FOLLOW.
"""

from __future__ import annotations
from typing import Dict, List, Set, Tuple
import sys

# ==============================
#  Constantes y utilidades
# ==============================

ALIAS_EPSILON: Set[str] = {"ε", "epsilon", "EPS", "lambda", "Λ", "e"}
MARCADOR_FIN: str = "$"       # símbolo especial de fin de entrada para FOLLOW(S)
EPS: str = "ε"                # representación canónica de epsilon


def normalizar_token(token: str) -> str:
    """Devuelve el token normalizado: si es un alias de epsilon lo mapea a 'ε'."""
    token = token.strip()
    return EPS if token in ALIAS_EPSILON else token


# ==============================
#  Lectura y representación de la gramática
# ==============================

def parsear_gramatica(lineas: List[str]) -> Tuple[Dict[str, List[List[str]]], str]:
    """
    Parsea líneas de texto y construye la gramática en un diccionario:
      gramática: { NoTerminal: [ [símbolos], [símbolos], ... ] }
    Además devuelve el símbolo inicial (primer LHS encontrado).
    """
    gramatica: Dict[str, List[List[str]]] = {}
    simbolo_inicial: str | None = None

    for cruda in lineas:
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        # Permitir comentarios al final de la línea con '#'
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue

        if "->" not in linea:
            raise ValueError(f"Línea inválida (falta '->'): {cruda!r}")
        lhs, rhs = [x.strip() for x in linea.split("->", 1)]
        if not lhs:
            raise ValueError(f"Lado izquierdo vacío en línea: {cruda!r}")
        if simbolo_inicial is None:
            simbolo_inicial = lhs

        alternativas = [alt.strip() for alt in rhs.split("|")]
        producciones: List[List[str]] = []
        for alt in alternativas:
            # Soportar epsilon explícita o producción vacía
            if alt == "" or alt in ALIAS_EPSILON:
                producciones.append([EPS])
            else:
                tokens = [normalizar_token(t) for t in alt.split()]
                if not tokens:
                    tokens = [EPS]
                producciones.append(tokens)

        gramatica.setdefault(lhs, []).extend(producciones)

    if simbolo_inicial is None:
        raise ValueError("No se encontró ninguna producción en la gramática.")
    return gramatica, simbolo_inicial


def conjuntos_de_simbolos(gramatica: Dict[str, List[List[str]]]) -> Tuple[Set[str], Set[str]]:
    """
    Devuelve (NO_TERMINALES, TERMINALES) deducidos de la gramática.
    - No terminales: claves del diccionario (LHS).
    - Terminales: símbolos que aparecen en RHS y NO son no terminales ni ε.
    """
    no_terminales = set(gramatica.keys())
    simbolos_rhs: Set[str] = set()
    for producciones in gramatica.values():
        for alternativa in producciones:
            simbolos_rhs.update(alternativa)
    terminales = {s for s in simbolos_rhs if s not in no_terminales and s != EPS}
    return no_terminales, terminales


# ==============================
#  Cálculo de PRIMEROS (FIRST)
# ==============================

def calcular_primeros(gramatica: Dict[str, List[List[str]]]) -> Dict[str, Set[str]]:
    """
    Calcula PRIMEROS(X) para cada símbolo X (no terminales y terminales).
    Reglas básicas:
      - PRIMEROS(t) = { t } si t es terminal.
      - Para cada producción A -> X1 X2 ... Xk:
          * Agregar PRIMEROS(X1)  {ε} a PRIMEROS(A).
          * Si X1 ⇒* ε, entonces también mirar X2, etc.
          * Si TODOS X1..Xk ⇒* ε, agregar ε a PRIMEROS(A).
    """
    no_terminales, terminales = conjuntos_de_simbolos(gramatica)
    PRIMEROS: Dict[str, Set[str]] = {A: set() for A in no_terminales}

    # FIRST para terminales y ε
    for t in terminales:
        PRIMEROS[t] = {t}
    PRIMEROS[EPS] = {EPS}

    cambio = True
    while cambio:
        cambio = False
        for A, producciones in gramatica.items():
            for alfa in producciones:
                acumulado: Set[str] = set()
                prefijo_anulable = True

                for X in alfa:
                    # Añadir PRIMEROS(X) sin ε
                    acumulado |= (PRIMEROS.get(X, {X}) - {EPS})
                    if EPS in PRIMEROS.get(X, set()):
                        # Continuamos con el siguiente símbolo
                        continue
                    else:
                        prefijo_anulable = False
                        break

                if prefijo_anulable:
                    acumulado.add(EPS)

                antes = len(PRIMEROS[A])
                PRIMEROS[A] |= acumulado
                if len(PRIMEROS[A]) != antes:
                    cambio = True

    return PRIMEROS


def primeros_de_secuencia(secuencia: List[str], PRIMEROS: Dict[str, Set[str]]) -> Set[str]:
    """
    PRIMEROS de una secuencia de símbolos X1 X2 ... Xk.
    Agrega PRIMEROS(Xi)  {ε} hasta que uno no sea anulable.
    Si todos son anulables, incluir ε.
    """
    resultado: Set[str] = set()
    prefijo_anulable = True

    for X in secuencia:
        resultado |= (PRIMEROS.get(X, {X}) - {EPS})
        if EPS in PRIMEROS.get(X, set()):
            continue
        else:
            prefijo_anulable = False
            break

    if prefijo_anulable:
        resultado.add(EPS)

    return resultado


# ==============================
#  Cálculo de SIGUIENTES (FOLLOW)
# ==============================

def calcular_siguientes(gramatica: Dict[str, List[List[str]]],
                        simbolo_inicial: str,
                        PRIMEROS: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """
    Calcula SIGUIENTES(A) para cada no terminal A.
    Reglas usadas:
      1) Poner '$' en SIGUIENTES(S) donde S es el símbolo inicial.
      2) Para cada producción A -> α B β:
         - Agregar PRIMEROS(β) {ε} a SIGUIENTES(B).
         - Si β ⇒* ε (o β está vacío), agregar también SIGUIENTES(A) a SIGUIENTES(B).
    """
    no_terminales, _ = conjuntos_de_simbolos(gramatica)
    SIGUIENTES: Dict[str, Set[str]] = {A: set() for A in no_terminales}
    SIGUIENTES[simbolo_inicial].add(MARCADOR_FIN)

    cambio = True
    while cambio:
        cambio = False
        for A, producciones in gramatica.items():
            for alfa in producciones:
                n = len(alfa)
                for i, B in enumerate(alfa):
                    if B not in no_terminales:
                        continue  # Solo interesa cuando B es no terminal
                    beta = alfa[i + 1:]

                    if beta:
                        primer_beta = primeros_de_secuencia(beta, PRIMEROS)
                        agregar = primer_beta - {EPS}

                        antes = len(SIGUIENTES[B])
                        SIGUIENTES[B] |= agregar
                        if len(SIGUIENTES[B]) != antes:
                            cambio = True

                        if EPS in primer_beta:
                            antes = len(SIGUIENTES[B])
                            SIGUIENTES[B] |= SIGUIENTES[A]
                            if len(SIGUIENTES[B]) != antes:
                                cambio = True
                    else:
                        # B es el último símbolo: propagar SIGUIENTES(A) -> SIGUIENTES(B)
                        antes = len(SIGUIENTES[B])
                        SIGUIENTES[B] |= SIGUIENTES[A]
                        if len(SIGUIENTES[B]) != antes:
                            cambio = True

    return SIGUIENTES


# ==============================
#  Salida formateada
# ==============================

def formatear_simbolo(s: str) -> str:
    """Envuelve cada símbolo en comillas simples para evitar ambigüedad visual."""
    return f"'{s}'"


def imprimir_conjuntos(titulo: str, conjuntos: Dict[str, Set[str]]) -> None:
    """
    Imprime un diccionario de conjuntos con un formato legible.
    - Ordena por nombre del no terminal.
    - Dentro del conjunto ordena dejando '$' al final.
    - Muestra cada símbolo entre comillas.
    """
    print(titulo)
    for A in sorted(conjuntos.keys()):
        elems_ordenados = sorted(conjuntos[A], key=lambda x: (x == MARCADOR_FIN, x))
        elementos = ", ".join(formatear_simbolo(x) for x in elems_ordenados)
        print(f"  {A:>15}: {{ {elementos} }}")
    print()


# ==============================
#  Utilidades de E/S
# ==============================

def leer_archivo(ruta: str) -> List[str]:
    """Lee y devuelve todas las líneas de un archivo de texto en UTF-8."""
    with open(ruta, "r", encoding="utf-8") as f:
        return f.readlines()


# ==============================
#  Programa principal
# ==============================

def main(argv: List[str]) -> None:
    # Si se pasa una ruta, parsea esa gramática; en caso contrario usa una demo mínima.
    if len(argv) >= 2:
        lineas = leer_archivo(argv[1])
        gramatica, simbolo_inicial = parsear_gramatica(lineas)
    else:
        demo = [
           " S' -> S" ,
            "S -> v = E",
            "S -> E ",
            "E -> v",
            "V -> X",
            "V -> * E"


        ]
        print("Sin archivo de entrada, usando gramática de demostración:\n")
        for ln in demo:
            print(ln)
        print()
        gramatica, simbolo_inicial = parsear_gramatica(demo)

    PRIMEROS = calcular_primeros(gramatica)
    SIGUIENTES = calcular_siguientes(gramatica, simbolo_inicial, PRIMEROS)

    print(f"Símbolo inicial: {simbolo_inicial}\n")
    # Solo imprimimos PRIMEROS de los no terminales definidos por el usuario
    imprimir_conjuntos("PRIMEROS:", {k: v for k, v in PRIMEROS.items() if k in gramatica})
    imprimir_conjuntos("SIGUIENTES:", SIGUIENTES)


if __name__ == "__main__":
    main(sys.argv)
