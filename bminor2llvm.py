#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bminor2llvm.py — Generador de LLVM IR (texto) desde el AST de B-Minor.

Uso:
    python bminor2llvm.py programa.bminor > out.ll
    clang out.ll -O2 -o prog && ./prog

Notas:
- Importa tu parser.parse() y opcionalmente checker.check().
- Soporta: tipos primitivos, asignación, +,-,*,/,%, comparaciones, &&,||,!, if/else,
  while, do-while, for, return, funciones por valor, print(...), arreglos e indexación [].
- Cambios clave de esta versión:
  (A) Arreglos locales con tamaño NO literal (p. ej. [N], [N*N]) se reservan con malloc
      en tiempo de ejecución (puntero base T* almacenado en un slot).
  (B) Llamadas a funciones respetan el tipo de retorno declarado (void, boolean/i1, etc.).
  (C) CORRECCIÓN: Se reemplazó scope.add_var por scope.set para corregir el AttributeError.
  (D) CORRECCIÓN: Se reestructuró _gen_local_vardecl para distinguir correctamente entre SimpleType y ArrayType.
"""

from __future__ import annotations
import importlib
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ===== Import dinámico =====
def _import_mod(name: str):
    try:
        return importlib.import_module(name)
    except Exception as ex:
        print(f"; Aviso: no se pudo importar '{name}': {ex}", file=sys.stderr)
        return None

# Defaults CLI
parser_mod_name  = "parser"
checker_mod_name = "checker"

argv = sys.argv[1:]
i = 0
while i < len(argv):
    if argv[i] == "--parser" and i + 1 < len(argv):
        parser_mod_name = argv[i + 1]
        argv.pop(i); argv.pop(i)
        continue
    if argv[i] == "--checker" and i + 1 < len(argv):
        checker_mod_name = argv[i + 1]
        argv.pop(i); argv.pop(i)
        continue
    i += 1

if not argv:
    sys.exit("Uso: python bminor2llvm.py archivo.bminor [--parser parser_mod] [--checker checker_mod]")

filename = argv[0]

# Import de proyecto del usuario
parser_mod  = _import_mod(parser_mod_name)
checker_mod = _import_mod(checker_mod_name)
model_mod   = _import_mod("model")
errors_mod  = _import_mod("errors")

if parser_mod is None or not hasattr(parser_mod, "parse"):
    sys.exit("Debes proveer un parser válido (argumento --parser o modifica los imports).")
parse = getattr(parser_mod, "parse")

check = getattr(checker_mod, "check", None) if checker_mod is not None else None

# AST nodes
Program       = getattr(model_mod, "Program")
VarDecl       = getattr(model_mod, "VarDecl")
Param         = getattr(model_mod, "Param")
Block         = getattr(model_mod, "Block")
PrintStmt     = getattr(model_mod, "PrintStmt")
ReturnStmt    = getattr(model_mod, "ReturnStmt")
IfStmt        = getattr(model_mod, "IfStmt")
WhileStmt     = getattr(model_mod, "WhileStmt")
DoWhileStmt   = getattr(model_mod, "DoWhileStmt")
ForStmt       = getattr(model_mod, "ForStmt")
Assign        = getattr(model_mod, "Assign")
BinOper       = getattr(model_mod, "BinOper")
UnaryOper     = getattr(model_mod, "UnaryOper")
PostfixOper   = getattr(model_mod, "PostfixOper")
Identifier    = getattr(model_mod, "Identifier")
Literal       = getattr(model_mod, "Literal")
Integer       = getattr(model_mod, "Integer")
Float         = getattr(model_mod, "Float")
Boolean       = getattr(model_mod, "Boolean")
Char          = getattr(model_mod, "Char")
String        = getattr(model_mod, "String")
ArrayIndex    = getattr(model_mod, "ArrayIndex")
Call          = getattr(model_mod, "Call")
SimpleType    = getattr(model_mod, "SimpleType")
ArrayType     = getattr(model_mod, "ArrayType")
FuncType      = getattr(model_mod, "FuncType")

# ===== Errores (opcional) =====
def set_source(fname: str, txt: str):
    if errors_mod is not None and hasattr(errors_mod, "set_source"):
        errors_mod.set_source(fname, txt)

def errors_detected() -> bool:
    if errors_mod is not None and hasattr(errors_mod, "errors_detected"):
        return errors_mod.errors_detected()
    return False

# ===== IR Emitter =====
class IREmitter:
    """Clase responsable de generar y formatear el código LLVM IR."""
    def __init__(self):
        self.lines: List[str] = []
        self.tmp_counter = 0
        self.blk_counter = 0

    def tmp(self) -> str:
        """Genera un registro temporal único (p. ej., %t1, %t2)."""
        self.tmp_counter += 1
        return f"%t{self.tmp_counter}"

    def label(self, base: str) -> str:
        """Genera una etiqueta de bloque básica (p. ej., while.head.1)."""
        self.blk_counter += 1
        return f"{base}{self.blk_counter}"

    def emit(self, line: str):
        """Añade una línea de código IR a la lista."""
        self.lines.append(line)

    def header(self):
        """Genera las declaraciones y constantes iniciales."""
        # decl comunes
        self.emit('declare i32 @printf(i8*, ...)')
        self.emit('declare i8* @malloc(i32)') # Asegura que malloc esté declarado si se usa
        self.emit('')
        # formatos
        self.emit('@.fmt_int   = private unnamed_addr constant [4 x i8] c"%d\\0A\\00"')
        self.emit('@.fmt_float = private unnamed_addr constant [4 x i8] c"%f\\0A\\00"')
        self.emit('@.fmt_char  = private unnamed_addr constant [4 x i8] c"%c\\0A\\00"')
        self.emit('@.fmt_str   = private unnamed_addr constant [4 x i8] c"%s\\0A\\00"')
        self.emit('')

    def gep_cstr(self, name: str) -> str:
        """Genera un GEP para obtener un puntero a una constante de cadena."""
        p = self.tmp()
        self.emit(f'{p} = getelementptr inbounds ([4 x i8], [4 x i8]* {name}, i32 0, i32 0)')
        return p

    def finalize(self) -> str:
        """Devuelve el código LLVM IR final como una sola cadena."""
        return "\n".join(self.lines) + "\n"

# ===== Tipos =====
LLVM_INT    = "i32"
LLVM_BOOL   = "i1"
LLVM_CHAR   = "i8"
LLVM_FLOAT  = "double"
LLVM_STRING = "i8*"

# Función auxiliar para obtener el tamaño en bytes
def get_size(t) -> int:
    llty = type_to_llvm(t)
    if llty == LLVM_FLOAT: return 8
    if llty == LLVM_INT or llty == LLVM_BOOL: return 4 # Bminor usa 4 bytes para i32/i1
    if llty == LLVM_CHAR: return 1
    return 4

def type_to_llvm(t) -> str:
    """Convierte un tipo de AST a su representación en LLVM IR."""
    if isinstance(t, SimpleType):
        name = (t.name or "").lower()
    elif isinstance(t, str):
        name = t.lower()
    else:
        name = None

    if name in ("int", "integer"):
        return LLVM_INT
    if name in ("bool", "boolean"):
        return LLVM_BOOL
    if name == "char":
        return LLVM_CHAR
    if name == "float":
        return LLVM_FLOAT
    if name == "string":
        return LLVM_STRING
    if name == "void":
        return "void"
    return LLVM_INT

def param_type_to_llvm(t) -> str:
    """Devuelve el tipo LLVM para un parámetro de función."""
    if isinstance(t, ArrayType):
        return f"{type_to_llvm(t.base)}*" # Arreglos se pasan como punteros
    return type_to_llvm(t)

# ===== Scope / valores =====
@dataclass
class ValueRef:
    ty: str     # Tipo LLVM (e.g., i32, i32*, [8 x i32])
    name: str   # Nombre del registro o valor (e.g., %t1, @gname, 5)

class Scope:
    """Maneja el alcance de las variables locales y sus slots de memoria."""
    def __init__(self, parent: Optional["Scope"]=None):
        self.parent = parent
        self.vars: Dict[str, ValueRef] = {}
    def get(self, name: str) -> Optional[ValueRef]:
        """Busca una variable en el scope actual y padres."""
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        return None
    def set(self, name: str, val: ValueRef):
        """Asigna (o añade) una variable al scope actual. (CORRECCIÓN: Reemplaza add_var)"""
        self.vars[name] = val

# ===== Codegen =====
class Codegen:
    """Generador principal de código LLVM IR."""
    def __init__(self, emitter: IREmitter):
        self.ir = emitter
        self.globals: Dict[str, Tuple[str, str]] = {}  # name -> (llvm_ty, @gname)
        self.fn_ret_ty: Optional[str] = None
        self.current_fn_end_label: Optional[str] = None
        self.current_fn_name: Optional[str] = None         
        self.fn_param_index: Dict[str, Dict[str, int]] = {}
        self.cur_fn_name: Optional[str] = None
        self.cur_fn_params: List[str] = []

        # firma de funciones: name -> (ret_llty, [param_llty])
        self.fn_sigs: Dict[str, Tuple[str, List[str]]] = {}
        self.arr_len: Dict[str, ValueRef] = {} # Guarda la longitud de los arreglos dinámicos/locales

    def gen_program(self, prog: Program):
        """Punto de entrada: genera globales, y luego funciones."""
        self.ir.header()

        # 0) recolectar firmas de funciones (para llamadas con tipo real)
        for s in prog.body:
            if isinstance(s, VarDecl) and isinstance(s.type, FuncType):
                ret_ll = type_to_llvm(s.type.ret) if s.type.ret else "void"
                params_ll = [param_type_to_llvm(p.type) for p in (s.type.params or [])] # Usa param_type_to_llvm
                self.fn_sigs[s.name] = (ret_ll, params_ll)

        # 1) declarar globales (no funciones)
        for s in prog.body:
            if isinstance(s, VarDecl) and not isinstance(s.type, FuncType):
                self._gen_global_decl(s)

        # 2) definir funciones
        for s in prog.body:
            if isinstance(s, VarDecl) and isinstance(s.type, FuncType):
                self._gen_function(s)


    # ---- Globales
    def _gen_global_decl(self, d: VarDecl):
        """Genera la declaración y posible inicialización de una variable global."""
        ty = d.type
        if isinstance(ty, ArrayType):
            base_llty = type_to_llvm(ty.base)
            
            # Caso 1: Arreglo con tamaño literal (como KNIGHT_DX/DY)
            if ty.size and isinstance(ty.size, Integer):
                n = int(ty.size.value)
                gname = f"@{d.name}"
                self.globals[d.name] = (f"[{n} x {base_llty}]", gname)

                # CORRECCIÓN 1: Lógica para inicializar con valores fijos
                init_values = getattr(d.init, "values", None) # Asumiendo que d.init tiene 'values'
                if init_values is not None:
                    initializers = []
                    for val_node in init_values:
                        # Asume que los inicializadores son enteros (Integer)
                        val = str(int(val_node.value)) if isinstance(val_node, Integer) else "0" 
                        initializers.append(f"{base_llty} {val}")
                    initializer_str = "{" + ", ".join(initializers) + "}"
                else:
                    initializer_str = "zeroinitializer"
                # FIN CORRECCIÓN 1

                self.ir.emit(f'{gname} = global [{n} x {base_llty}] {initializer_str}')
                self.arr_len[d.name] = ValueRef(LLVM_INT, str(n))
                return
            
            # Caso 2: Arreglo sin tamaño literal (para evitar que se genere i8* null)
            else:
                gname = f"@{d.name}"
                self.globals[d.name] = (f"{base_llty}*", gname) # Registra como puntero de su tipo base
                self.ir.emit(f'{gname} = global {base_llty}* null') # Inicializa puntero a null
            return
        
       
        # Caso 3: Escalar global
        llty = type_to_llvm(ty)
        gname = f"@{d.name}"
        self.globals[d.name] = (llty, gname)
        init = "0"
        if isinstance(d.init, Literal):
            if llty == LLVM_INT:
                init = str(int(d.init.value))
            elif llty == LLVM_BOOL:
                init = "1" if bool(d.init.value) else "0"
            elif llty == LLVM_CHAR:
                init = str(ord(d.init.value))
            elif llty == LLVM_FLOAT:
                init = f"{float(d.init.value)}"
        self.ir.emit(f'{gname} = global {llty} {init}')

    # ---- Funciones
    def _gen_function(self, fdecl: VarDecl):
        """Genera el encabezado, parámetros (allocas) y cuerpo de la función."""
        ftype: FuncType = fdecl.type
        ret_llty = type_to_llvm(ftype.ret) if ftype.ret else "void"
        self.fn_ret_ty = ret_llty
        fname = f"@{fdecl.name}"
        self.current_fn_name = fdecl.name
        self.fn_param_index[fdecl.name] = { p.name: i for i, p in enumerate(ftype.params or []) }
        self.cur_fn_name = fdecl.name
        self.cur_fn_params = [p.name for p in (ftype.params or [])]

        
        params_sig = []

        for p in (ftype.params or []):
            p_llty = param_type_to_llvm(p.type)   # Usa el tipo correcto para arreglos (T*)
            params_sig.append(f"{p_llty} %{p.name}")

        self.ir.emit(f"define {ret_llty} {fname}({', '.join(params_sig)}) "+"{")
        fn_scope = Scope()

        # params → allocas (guarda los punteros a los slots)
        for p in (ftype.params or []):
            p_llty = param_type_to_llvm(p.type) 
            slot = self.ir.tmp()
            self.ir.emit(f"  {slot} = alloca {p_llty}")
            self.ir.emit(f"  store {p_llty} %{p.name}, {p_llty}* {slot}")
            fn_scope.set(p.name, ValueRef(ty=p_llty, name=slot))

        self.current_fn_end_label = self.ir.label("endfn.")
        if isinstance(fdecl.init, Block):
            self._gen_block(fdecl.init, fn_scope)
        
        # Etiqueta de finalización de función (necesaria para el control de flujo)
        self.ir.emit(f"{self.current_fn_end_label}:")
        if ret_llty == "void":
            self.ir.emit("  ret void")
        else:
            self.ir.emit(f"  ret {ret_llty} 0") # Retorno por defecto si no hay return explícito

        self.ir.emit("}\n")
        self.fn_ret_ty = None
        self.current_fn_end_label = None
        self.current_fn_name = None
        self.cur_fn_name = None
        self.cur_fn_params = []


    # ---- Bloques/sentencias
    def _gen_block(self, block: Block, scope: Scope):
        """Genera IR para cada sentencia dentro de un bloque."""
        for s in block.stmts:
            if isinstance(s, VarDecl) and not isinstance(s.type, FuncType):
                self._gen_local_vardecl(s, scope)
            elif isinstance(s, PrintStmt):
                for a in s.args:
                    v = self._gen_expr(a, scope)
                    self._gen_print(v)
            elif isinstance(s, ReturnStmt):
                if s.expr is None:
                    # Inserción de un salto al final de la función, el ret se genera allí.
                    self.ir.emit(f"  br label %{self.current_fn_end_label}")
                else:
                    v = self._gen_expr(s.expr, scope)
                    self.ir.emit(f"  ret {v.ty} {v.name}")
                return # Detiene la generación de IR en este camino del bloque
            elif isinstance(s, IfStmt):
                self._gen_if(s, scope)
            elif isinstance(s, WhileStmt):
                self._gen_while(s, scope)
            elif isinstance(s, DoWhileStmt):
                self._gen_dowhile(s, scope)
            elif isinstance(s, ForStmt):
                self._gen_for(s, scope)
            elif isinstance(s, Block):
                self._gen_block(s, Scope(scope))
            else:
                # cualquier expr/assign/call como stmt
                _ = self._gen_expr(s, scope)

    def _gen_local_vardecl(self, d: VarDecl, scope: Scope):
        """Genera código para la declaración de una variable local (escalar o arreglo)."""
        
        # 1. ARREGLOS (ArrayType)
        if isinstance(d.type, ArrayType):
            base_llty = type_to_llvm(d.type.base)
            elem_sz = get_size(d.type.base)
            
            # Caso 1a: Tamaño literal -> alloca [N x T] (Arreglo estático)
            if d.type.size and isinstance(d.type.size, Integer):
                n = int(d.type.size.value)
                slot_arr = self.ir.tmp()
                self.ir.emit(f"  {slot_arr} = alloca [{n} x {base_llty}]")
                # El tipo de ValueRef es el tipo ALLOCA: [N x T]
                scope.set(d.name, ValueRef(ty=f"[{n} x {base_llty}]", name=slot_arr))
                self.arr_len[d.name] = ValueRef(LLVM_INT, str(n))
                # Nota: La inicialización estática no se maneja aquí.
                return

            # Caso 1b: Array dinámica (malloc)
            slot_ptr = self.ir.tmp()
            self.ir.emit(f"  {slot_ptr} = alloca {base_llty}*")
            
            # Determinar N (número de elementos) y bytes
            n_reg = "0"
            bytes_cnt = "0"
            
            init_values = getattr(d.init, "values", None)
            
            if d.type.size is not None:
                # Tamaño NO literal (Ej: N*N)
                nval = self._gen_expr(d.type.size, scope)
                # Asegura que nval sea i32 (CORRECCIÓN: Asegura que el valor de N*N se use)
                if nval.ty != LLVM_INT:
                    fix = self.ir.tmp()
                    if nval.ty in (LLVM_BOOL, LLVM_CHAR):
                        self.ir.emit(f"  {fix} = zext {nval.ty} {nval.name} to i32")
                    elif nval.ty == LLVM_FLOAT:
                        self.ir.emit(f"  {fix} = fptosi double {nval.name} to i32")
                    else:
                        self.ir.emit(f"  {fix} = add i32 0, 0")
                    nval = ValueRef(LLVM_INT, fix)
                n_reg = nval.name
                bytes_cnt = self.ir.tmp()
                self.ir.emit(f"  {bytes_cnt} = mul i32 {n_reg}, {elem_sz}")
            
            # Generar malloc si hay tamaño
            if bytes_cnt != "0":
                raw = self.ir.tmp()
                self.ir.emit(f"  {raw} = call i8* @malloc(i32 {bytes_cnt})")
                cast = self.ir.tmp()
                self.ir.emit(f"  {cast} = bitcast i8* {raw} to {base_llty}*")
                self.ir.emit(f"  store {base_llty}* {cast}, {base_llty}** {slot_ptr}")
                
                # Guardar N en un slot i32 para array_length(...)
                len_slot = self.ir.tmp()
                self.ir.emit(f"  {len_slot} = alloca i32")
                self.ir.emit(f"  store i32 {n_reg}, i32* {len_slot}")
                self.arr_len[d.name] = ValueRef(f"{LLVM_INT}*", len_slot)
                # El tipo de ValueRef es el puntero base: T*
                scope.set(d.name, ValueRef(ty=f"{base_llty}*", name=slot_ptr))

            # Inicialización por lista si aplica
            if init_values is not None:
                arr_ptr = self.ir.tmp()
                self.ir.emit(f"  {arr_ptr} = load {base_llty}*, {base_llty}** {slot_ptr}")
                for idx, elt in enumerate(init_values):
                    val = self._gen_expr(elt, scope)
                    gep = self.ir.tmp()
                    # CORRECCIÓN: GEP usa el índice (idx) para escribir.
                    self.ir.emit(f"  {gep} = getelementptr inbounds {base_llty}, {base_llty}* {arr_ptr}, i32 {idx}")
                    castv = val.name
                    if val.ty != base_llty:
                        tmp = self.ir.tmp()
                        if val.ty in (LLVM_BOOL, LLVM_CHAR):
                            self.ir.emit(f"  {tmp} = zext {val.ty} {val.name} to i32")
                        elif val.ty == LLVM_FLOAT and base_llty == LLVM_INT:
                            self.ir.emit(f"  {tmp} = fptosi double {val.name} to i32")
                        else:
                            self.ir.emit(f"  {tmp} = add i32 0, 0")
                        castv = tmp
                    self.ir.emit(f"  store {base_llty} {castv}, {base_llty}* {gep}")
            
            return
            
        # 2. ESCALARES (SimpleType)
        llty = type_to_llvm(d.type)
        slot = self.ir.tmp()
        self.ir.emit(f"  {slot} = alloca {llty}")
        # El tipo de ValueRef es el tipo BASE: T
        scope.set(d.name, ValueRef(llty, slot))

        if getattr(d, "init", None) is not None:
            v = self._gen_expr(d.init, scope)
            # Normaliza tipos comunes (ej: i1/i8/double -> i32 cuando corresponde)
            if v.ty != llty:
                cast = v.name
                if v.ty in (LLVM_BOOL, LLVM_CHAR) and llty == LLVM_INT:
                    cast = self.ir.tmp()
                    self.ir.emit(f"  {cast} = zext {v.ty} {v.name} to i32")
                elif v.ty == LLVM_FLOAT and llty == LLVM_INT:
                    cast = self.ir.tmp()
                    self.ir.emit(f"  {cast} = fptosi double {v.name} to i32")
                v = ValueRef(llty, cast)
            self.ir.emit(f"  store {llty} {v.name}, {llty}* {slot}")
        else:
            # inicializa en 0 por defecto
            self.ir.emit(f"  store {llty} 0, {llty}* {slot}")

        return
    def _declare_malloc(self):
        """Asegura que @malloc(i32) esté declarado en el IR."""
        # Nota: Movido al header de IREmitter para simplicidad.
        pass 
        

    # Las siguientes funciones auxiliares (excepto _declare_malloc) no se modificaron, 
    # pero se incluyen aquí para la integridad del archivo.
    
    # [Resto de funciones (desde _declare_len_global hasta la línea final) no modificado.]
    def _declare_len_global(self, gname):
        decl = f"{gname} = global i32 0"

        # Evitar duplicados
        if any(ln.startswith(gname) for ln in self.ir.lines):
            return

        # Insertar después de TODOS los @.fmt_
        insert_at = 0
        for j, ln in enumerate(self.ir.lines):
            if ln.startswith("@.fmt_"):
                insert_at = j + 1

        self.ir.lines.insert(insert_at, decl)

    def _try_arg_length(self, arg_node, scope: "Scope") -> Optional["ValueRef"]:
    # 1) Si es un identificador y conocemos su longitud (self.arr_len)
        if isinstance(arg_node, Identifier) and arg_node.name in self.arr_len:
            v = self.arr_len[arg_node.name]  # puede ser i32* (slot) o i32 (inmediato)
            if v.ty.endswith("*"):  # i32*
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load i32, i32* {v.name}")
                return ValueRef(LLVM_INT, reg)
            return ValueRef(LLVM_INT, v.name)

        # 2) Si es un acceso a arreglo a[i], intenta usar la base
        if isinstance(arg_node, ArrayIndex) and isinstance(arg_node.array, Identifier):
            base = arg_node.array.name
            if base in self.arr_len:
                v = self.arr_len[base]
                if v.ty.endswith("*"):
                    reg = self.ir.tmp()
                    self.ir.emit(f"  {reg} = load i32, i32* {v.name}")
                    return ValueRef(LLVM_INT, reg)
                return ValueRef(LLVM_INT, v.name)

        # 3) Si es global con tamaño literal (p.ej. @A = global [N x i32] ...)
        if isinstance(arg_node, Identifier) and arg_node.name in self.globals:
            gty, _ = self.globals[arg_node.name]
            if gty.startswith('[') and ' x ' in gty:
                N = gty.split(' x ')[0].lstrip('[')
                return ValueRef(LLVM_INT, N)

        return None

    def _eval_size_expr(self, size_expr, scope: Scope) -> str:
        """Genera IR para evaluar una expresión de tamaño (p. ej. N, N*N) y devuelve el registro i32."""
        if size_expr is None:
            return "0"
        v = self._gen_expr(size_expr, scope)
        # aseguramos i32
        if v.ty != LLVM_INT:
            tmp = self.ir.tmp()
            if v.ty == LLVM_BOOL or v.ty == LLVM_CHAR:
                self.ir.emit(f"  {tmp} = zext {v.ty} {v.name} to i32")
            elif v.ty == LLVM_FLOAT:
                self.ir.emit(f"  {tmp} = fptosi double {v.name} to i32")
            else:
                # best effort
                self.ir.emit(f"  {tmp} = add i32 0, 0")
            return tmp
        return v.name

    # ---- IF / WHILE / FOR helpers
    def _as_i1(self, v: ValueRef) -> ValueRef:
        """Convierte cualquier valor a i1 (booleano)."""
        if v.ty == LLVM_BOOL:
            return v
        if v.ty == LLVM_INT or v.ty == LLVM_CHAR:
            cmpv = self.ir.tmp()
            self.ir.emit(f"  {cmpv} = icmp ne {v.ty} {v.name}, 0")
            return ValueRef(LLVM_BOOL, cmpv)
        if v.ty == LLVM_FLOAT:
            cmpv = self.ir.tmp()
            self.ir.emit(f"  {cmpv} = fcmp one double {v.name}, 0.0")
            return ValueRef(LLVM_BOOL, cmpv)
        return ValueRef(LLVM_BOOL, "true")

    def _gen_if(self, n: IfStmt, scope: Scope):
        """Genera IR para la sentencia if/else."""
        cond = self._as_i1(self._gen_expr(n.cond, scope))
        thenL = self.ir.label("then.")
        elseL = self.ir.label("else.")
        endL  = self.ir.label("endif.")
        self.ir.emit(f"  br i1 {cond.name}, label %{thenL}, label %{elseL}")
        self.ir.emit(f"{thenL}:")
        self._gen_block(n.then if isinstance(n.then, Block) else Block(stmts=[n.then]), Scope(scope))
        self.ir.emit(f"  br label %{endL}")
        self.ir.emit(f"{elseL}:")
        if n.otherwise:
            self._gen_block(n.otherwise if isinstance(n.otherwise, Block) else Block(stmts=[n.otherwise]), Scope(scope))
        self.ir.emit(f"  br label %{endL}")
        self.ir.emit(f"{endL}:")

    def _gen_while(self, n: WhileStmt, scope: Scope):
        """Genera IR para la sentencia while."""
        head = self.ir.label("while.head.")
        body = self.ir.label("while.body.")
        end  = self.ir.label("while.end.")
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{head}:")
        c = self._as_i1(self._gen_expr(n.cond, scope))
        self.ir.emit(f"  br i1 {c.name}, label %{body}, label %{end}")
        self.ir.emit(f"{body}:")
        self._gen_block(n.body if isinstance(n.body, Block) else Block(stmts=[n.body]), Scope(scope))
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{end}:")

    def _gen_dowhile(self, n: DoWhileStmt, scope: Scope):
        """Genera IR para la sentencia do-while."""
        bodyL = self.ir.label("do.body.")
        head  = self.ir.label("do.head.")
        end   = self.ir.label("do.end.")
        self.ir.emit(f"  br label %{bodyL}")
        self.ir.emit(f"{bodyL}:")
        self._gen_block(n.body if isinstance(n.body, Block) else Block(stmts=[n.body]), Scope(scope))
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{head}:")
        c = self._as_i1(self._gen_expr(n.cond, scope))
        self.ir.emit(f"  br i1 {c.name}, label %{bodyL}, label %{end}")
        self.ir.emit(f"{end}:")

    def _gen_for(self, n: ForStmt, scope: Scope):
        """Genera IR para la sentencia for."""
        init_scope = Scope(scope)
        if getattr(n, "init", None) is not None:
            _ = self._gen_expr(n.init, init_scope)
        head = self.ir.label("for.head.")
        body = self.ir.label("for.body.")
        step = self.ir.label("for.step.")
        end  = self.ir.label("for.end.")
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{head}:")
        cond = self._as_i1(self._gen_expr(n.cond, init_scope)) if getattr(n, "cond", None) is not None else ValueRef(LLVM_BOOL, "true")
        self.ir.emit(f"  br i1 {cond.name}, label %{body}, label %{end}")
        self.ir.emit(f"{body}:")
        self._gen_block(n.body if isinstance(n.body, Block) else Block(stmts=[n.body]), Scope(init_scope))
        self.ir.emit(f"  br label %{step}")
        self.ir.emit(f"{step}:")
        if getattr(n, "step", None) is not None:
            _ = self._gen_expr(n.step, init_scope)
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{end}:")

    # ---- Expresiones
    def _gen_expr(self, e, scope: Scope) -> ValueRef:
        """Genera IR para una expresión, devolviendo su valor y tipo (ValueRef)."""
        if isinstance(e, Integer):
            return ValueRef(LLVM_INT, str(int(e.value)))
        if isinstance(e, Boolean):
            return ValueRef(LLVM_BOOL, "1" if bool(e.value) else "0")
        if isinstance(e, Char):
            return ValueRef(LLVM_CHAR, str(ord(e.value)))
        if isinstance(e, Float):
            return ValueRef(LLVM_FLOAT, f"{float(e.value)}")
        if isinstance(e, String):
            gname = self._string_global(e.value)
            ptr = self.ir.tmp()
            self.ir.emit(f"  {ptr} = getelementptr inbounds [{len(e.value)+1} x i8], [{len(e.value)+1} x i8]* {gname}, i32 0, i32 0")
            return ValueRef(LLVM_STRING, ptr)
        if isinstance(e, Identifier):
            v = scope.get(e.name)
            if v is not None:
                reg = self.ir.tmp()
                # La carga usa el tipo base (v.ty) y el slot (v.name)
                # v.ty es i32/double para escalares o i32*/double* para arreglos
                # v.name es el %slot
                self.ir.emit(f"  {reg} = load {v.ty}, {v.ty}* {v.name}")
                return ValueRef(v.ty, reg)
            if e.name in self.globals:
                llty, g = self.globals[e.name]
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load {llty}, {llty}* {g}")
                return ValueRef(llty, reg)
            return ValueRef(LLVM_INT, "0")

        if isinstance(e, Assign):
            if isinstance(e.target, Identifier):
                slot = scope.get(e.target.name)
                if slot is None and e.target.name in self.globals:
                    llty, g = self.globals[e.target.name]
                    val = self._gen_expr(e.value, scope)
                    self.ir.emit(f"  store {llty} {val.name}, {llty}* {g}")
                    return val
                elif slot is not None:
                    val = self._gen_expr(e.value, scope)
                    self.ir.emit(f"  store {slot.ty} {val.name}, {slot.ty}* {slot.name}")
                    return val
            
            elif isinstance(e.target, ArrayIndex):
                idx_node = e.target
                base_ptr, elem_ty = self._gen_array_ptr(idx_node, scope)
                idx = self._gen_expr(idx_node.index, scope)
                gep = self.ir.tmp()    
                self.ir.emit(
                    f"  {gep} = getelementptr inbounds {elem_ty}, {elem_ty}* {base_ptr}, i32 {idx.name}"
                )
                val = self._gen_expr(e.value, scope)

                # normalizar tipo del valor si viene como i1/char/float
                castv = val.name
                if val.ty != elem_ty:
                    if val.ty == LLVM_BOOL or val.ty == LLVM_CHAR:
                        tmp = self.ir.tmp()
                        self.ir.emit(f"  {tmp} = zext {val.ty} {val.name} to i32")
                        castv = tmp
                    elif val.ty == LLVM_FLOAT and elem_ty == LLVM_INT:
                        # Conversión de flotante a entero (fptosi)
                        tmp = self.ir.tmp()
                        self.ir.emit(f"  {tmp} = fptosi double {val.name} to i32")
                        castv = tmp

                self.ir.emit(f"  store {elem_ty} {castv}, {elem_ty}* {gep}")
                return ValueRef(elem_ty, castv)
            
            return self._gen_expr(e.value, scope)

        if isinstance(e, ArrayIndex):
            base_ptr, elem_ty = self._gen_array_ptr(e, scope)
            idx = self._gen_expr(e.index, scope)
            gep = self.ir.tmp()
            # CORRECCIÓN: GEP usa el índice (idx.name) para la lectura.
            self.ir.emit(f"  {gep} = getelementptr inbounds {elem_ty}, {elem_ty}* {base_ptr}, i32 {idx.name}")
            reg = self.ir.tmp()
            self.ir.emit(f"  {reg} = load {elem_ty}, {elem_ty}* {gep}")
            return ValueRef(elem_ty, reg)

        if isinstance(e, Call):
            # intrínseco print(...)
            if isinstance(e.func, Identifier) and e.func.name == "print":
                for a in e.args:
                    self._gen_print(self._gen_expr(a, scope))
                return ValueRef(LLVM_INT, "0")

            # intrínseco array_length(x) -> i32
            if isinstance(e.func, Identifier) and e.func.name == "array_length":
                target = e.args[0] if e.args else None
                return self._get_array_length(target, scope)

            # llamada normal a función de usuario
            callee  = e.func.name if isinstance(e.func, Identifier) else "unknown"
            argvals = [self._gen_expr(a, scope) for a in e.args]

            # INYECTAR LONGITUDES: Una sola vez, inmediatamente antes del call
            for i, arg_node in enumerate(e.args):
                L = self._try_arg_length(arg_node, scope)  # ValueRef(i32) o None
                if L is not None:
                    gname = f"@.len.{callee}.p{i}"
                    self._declare_len_global(gname)
                    self.ir.emit(f"  store i32 {L.name}, i32* {gname}")

            arglist = ", ".join(f"{v.ty} {v.name}" for v in argvals)
            ret_ll, _ = self.fn_sigs.get(callee, (LLVM_INT, []))
            if ret_ll == "void":
                self.ir.emit(f"  call void @{callee}({arglist})")
                return ValueRef(LLVM_INT, "0")
            r = self.ir.tmp()
            self.ir.emit(f"  {r} = call {ret_ll} @{callee}({arglist})")
            return ValueRef(ret_ll, r)


        if isinstance(e, UnaryOper):
            """Genera IR para operadores unarios (-, +, !)."""
            v = self._gen_expr(e.expr, scope)
            if e.oper == '-':
                if v.ty == LLVM_FLOAT:
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = fsub double 0.0, {v.name}"); return ValueRef(v.ty, r)
                r = self.ir.tmp(); self.ir.emit(f"  {r} = sub {v.ty} 0, {v.name}"); return ValueRef(v.ty, r)
            if e.oper == '+':
                return v
            if e.oper == '!':
                as1 = self._as_i1(v)
                r = self.ir.tmp(); self.ir.emit(f"  {r} = xor i1 {as1.name}, true"); return ValueRef(LLVM_BOOL, r)

        if isinstance(e, PostfixOper):
            """Genera IR para operadores postfijos (++, --)."""
            if isinstance(e.expr, Identifier):
                slot = scope.get(e.expr.name)
                if slot is None:
                    llty, g = self.globals.get(e.expr.name, (LLVM_INT, None))
                    cur = self.ir.tmp(); self.ir.emit(f"  {cur} = load {llty}, {llty}* {g}")
                    nxt = self.ir.tmp(); op = "add" if e.oper == '++' else "sub"
                    self.ir.emit(f"  {nxt} = {op} {llty} {cur}, 1")
                    self.ir.emit(f"  store {llty} {nxt}, {llty}* {g}")
                    return ValueRef(llty, cur)
                else:
                    cur = self.ir.tmp(); self.ir.emit(f"  {cur} = load {slot.ty}, {slot.ty}* {slot.name}")
                    nxt = self.ir.tmp(); op = "add" if e.oper == '++' else "sub"
                    self.ir.emit(f"  {nxt} = {op} {slot.ty} {cur}, 1")
                    self.ir.emit(f"  store {slot.ty} {nxt}, {slot.ty}* {slot.name}")
                    return ValueRef(slot.ty, cur)

        if isinstance(e, BinOper):
            """Genera IR para operadores binarios (+, -, *, /, %, ==, <, etc.)."""
            a = self._gen_expr(e.left, scope)
            b = self._gen_expr(e.right, scope)
            if a.ty == LLVM_FLOAT or b.ty == LLVM_FLOAT:
                if a.ty != LLVM_FLOAT:
                    ca = self.ir.tmp(); self.ir.emit(f"  {ca} = sitofp {a.ty} {a.name} to double"); a = ValueRef(LLVM_FLOAT, ca)
                if b.ty != LLVM_FLOAT:
                    cb = self.ir.tmp(); self.ir.emit(f"  {cb} = sitofp {b.ty} {b.name} to double"); b = ValueRef(LLVM_FLOAT, cb)
                opmap = {'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}
                if e.oper in opmap:
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = {opmap[e.oper]} double {a.name}, {b.name}"); return ValueRef(LLVM_FLOAT, r)
                cmpmap = {'==':'oeq','!=':'one','<':'olt','<=':'ole','>':'ogt','>=':'oge'}
                if e.oper in cmpmap:
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = fcmp {cmpmap[e.oper]} double {a.name}, {b.name}"); return ValueRef(LLVM_BOOL, r)
            else:
                if e.oper == '+':
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = add {a.ty} {a.name}, {b.name}"); return ValueRef(a.ty, r)
                if e.oper == '-':
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = sub {a.ty} {a.name}, {b.name}"); return ValueRef(a.ty, r)
                if e.oper == '*':
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = mul {a.ty} {a.name}, {b.name}"); return ValueRef(a.ty, r)
                if e.oper == '/':
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = sdiv {a.ty} {a.name}, {b.name}"); return ValueRef(a.ty, r)
                if e.oper == '%':
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = srem {a.ty} {a.name}, {b.name}"); return ValueRef(a.ty, r)
                cmpmap = {'==':'eq','!=':'ne','<':'slt','<=':'sle','>':'sgt','>=':'sge'}
                if e.oper in cmpmap:
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = icmp {cmpmap[e.oper]} {a.ty} {a.name}, {b.name}"); return ValueRef(LLVM_BOOL, r)
                if e.oper in ('&&','||'):
                    aa = self._as_i1(a); bb = self._as_i1(b)
                    op = "and" if e.oper == '&&' else "or"
                    r = self.ir.tmp(); self.ir.emit(f"  {r} = {op} i1 {aa.name}, {bb.name}"); return ValueRef(LLVM_BOOL, r)

        return ValueRef(LLVM_INT, "0")

    def _string_global(self, s: str) -> str:
        """Genera una constante global para un literal de cadena."""
        key = f"@.str.{abs(hash(s)) & 0xFFFFFF:x}"
        # Si ya existe, solo devuelve el nombre
        for ln in self.ir.lines:
            if ln.startswith(f"{key} ="):
                return key

        bs = s.encode("utf-8")
        init = ", ".join(f"i8 {b}" for b in bs) + ", i8 0"
        line = f"{key} = private unnamed_addr constant [{len(bs)+1} x i8] [{init}]"

        # Inserta después de los @.fmt_ y de los @.len
        insert_at = 0
        for j, ln in enumerate(self.ir.lines):
            if ln.startswith("@.fmt_") or ln.startswith("@.len."):
                insert_at = j + 1

        self.ir.lines.insert(insert_at, line)
        return key


    def _gen_print(self, v: ValueRef):
        """Genera la llamada a @printf para imprimir un valor."""
        if v.ty in (LLVM_INT, LLVM_BOOL):
            fmt = self.ir.gep_cstr("@.fmt_int");   self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i32 {v.name})")
        elif v.ty == LLVM_CHAR:
            fmt = self.ir.gep_cstr("@.fmt_char");  self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i8 {v.name})")
        elif v.ty == LLVM_FLOAT:
            fmt = self.ir.gep_cstr("@.fmt_float"); self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, double {v.name})")
        elif v.ty == LLVM_STRING:
            fmt = self.ir.gep_cstr("@.fmt_str");   self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i8* {v.name})")
        else:
            fmt = self.ir.gep_cstr("@.fmt_int");   self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i32 {v.name})")

    def _gen_array_ptr(self, idx: ArrayIndex, scope: Scope) -> Tuple[str, str]:
        """Calcula el puntero base (GEP) para acceder a un arreglo."""
        if isinstance(idx.array, Identifier):
            v = scope.get(idx.array.name)
            if v:
                # Caso 1: alocado estáticamente [N x T]
                if v.ty.startswith('['):
                    T = v.ty.split(' x ')[-1].rstrip(']')
                    baseptr = self.ir.tmp()
                    self.ir.emit(f"  {baseptr} = getelementptr inbounds {v.ty}, {v.ty}* {v.name}, i32 0, i32 0")
                    return baseptr, T
                # Caso 2: puntero T* (malloc o parámetro)
                if v.ty.endswith('*'):
                    loaded = self.ir.tmp()
                    baseT  = v.ty[:-1]
                    self.ir.emit(f"  {loaded} = load {v.ty}, {v.ty}* {v.name}")
                    return loaded, baseT

            # Caso 3: global [N x T]
            if idx.array.name in self.globals:
                gty, gname = self.globals[idx.array.name]
                if gty.startswith('['):
                    T = gty.split(' x ')[-1].rstrip(']')
                    baseptr = self.ir.tmp()
                    self.ir.emit(f"  {baseptr} = getelementptr inbounds {gty}, {gty}* {gname}, i32 0, i32 0")
                    return baseptr, T

        # Fallback
        base = self.ir.tmp()
        self.ir.emit(f"  {base} = bitcast i8* null to i32*")
        return base, LLVM_INT
    
    def _get_array_length(self, arr_node, scope: Scope) -> ValueRef:
        """Devuelve la longitud de un arreglo local, global o pasado como parámetro."""
        name = None
        if isinstance(arr_node, Identifier):
            name = arr_node.name
        elif isinstance(arr_node, ArrayIndex) and isinstance(arr_node.array, Identifier):
            name = arr_node.array.name

        # 1) Si la longitud fue guardada (local o dinámica)
        if name and name in self.arr_len:
            v = self.arr_len[name]
            if v.ty.endswith("*"):                 # i32*
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load i32, i32* {v.name}")
                return ValueRef(LLVM_INT, reg)
            return ValueRef(LLVM_INT, v.name)

        # 2) Si es global de tamaño fijo [N x T]
        if name and name in self.globals:
            gty, _ = self.globals[name]
            if gty.startswith('[') and ' x ' in gty:
                N = gty.split(' x ')[0].lstrip('[')
                return ValueRef(LLVM_INT, N)
        
        # 3) Longitud de parámetro (leyendo del global @.len.<fn>.p<i>)
        if name and self.cur_fn_name and name in self.cur_fn_params:
            idx = self.cur_fn_params.index(name)
            gname = f"@.len.{self.cur_fn_name}.p{idx}"
            self._declare_len_global(gname)
            r = self.ir.tmp()
            self.ir.emit(f"  {r} = load i32, i32* {gname}")
            return ValueRef(LLVM_INT, r)


        # 4) Desconocido (ej: parámetro sin tamaño)
        return ValueRef(LLVM_INT, "0")



# ===== Carga + compile =====
txt = open(filename, encoding="utf-8").read()
set_source(filename, txt)
ast = parse(txt)
em = IREmitter()
cg = Codegen(em)
cg.gen_program(ast)
output_ir = em.finalize()

if check is not None:
    try:
        with open("out.ll", "w", encoding="utf-8") as f:
            f.write(output_ir)
        print("Archivo out.ll generado con éxito en codificación UTF-8.", file=sys.stderr)
    except Exception as e:
        print(f"Error al escribir out.ll: {e}", file=sys.stderr)

sys.stdout.write(em.finalize())