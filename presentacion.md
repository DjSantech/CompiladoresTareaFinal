Cálculo de Conjuntos PRIMEROS y SIGUIENTES (CFG)

Materia: Compiladores
Profesor: Ángel Augusto Zapato
Estudiante: Santiago Guevara Méndez
Fecha: 15 de septiembre de 2025

Resumen

Programa en Python que, dada una gramática libre de contexto (GLC), calcula automáticamente los conjuntos PRIMEROS (FIRST) y SIGUIENTES (FOLLOW) de cada no terminal. Acepta ε (y alias como epsilon, lambda, etc.), infiere terminales/no terminales, maneja recursión izquierda sin problema y añade el marcador de fin $ al FOLLOW del símbolo inicial. La salida se imprime ordenada y con los símbolos entre comillas para evitar ambigüedades.