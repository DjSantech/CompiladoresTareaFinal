#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
traductorG.py — Generador de LLVM IR (texto) desde el AST de B-Minor.

Implementación COMPLETA de traducción de Nodos AST a LLVM IR.
CORRECCIÓN FINAL:
1. Se utiliza 'scope.add(name, value)' para insertar símbolos.
2. Se implementa la generación de código para model.ForStmt.
3. Se corrige la lógica de BinaryOp.
4. **CORRECCIÓN DEFENSIVA:** Se añade manejo directo para <class 'int'> y otros
   literales nativos de Python que puedan filtrarse en _gen_expr.
"""

from __future__ import annotations
import importlib
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import re 
import struct 

# ====================================================================
# CONFIGURACIÓN Y TIPOS LLVM
# ====================================================================

# Convenciones de tipo LLVM
LLVM_VOID = 'void'
LLVM_INT = 'i32'
LLVM_FLOAT = 'double'
LLVM_BOOL = 'i1'
LLVM_CHAR = 'i8'
LLVM_STRING = 'i8*'

@dataclass
class ValueRef:
    """Representa un valor temporal o un registro LLVM."""
    ty: str          # Tipo LLVM (e.g., 'i32', 'i1', 'i32*')
    name: str        # Nombre del registro (e.g., '%t1', '10', '@N')

@dataclass
class SlotRef(ValueRef):
    """Representa un slot de memoria (alloca o global)."""
    pass

@dataclass
class TypeInfo:
    """Información del tipo de B-Minor (para la tabla de símbolos)."""
    llty: str
    is_array: bool = field(default=False)
    is_ptr: bool = field(default=False)
    size_expr: Optional[Any] = field(default=None)

# ====================================================================
# BLOQUE DE IMPORTACIÓN 
# ====================================================================

try:
    # 1. Importar Módulos
    parser = importlib.import_module("parser")
    symtab = importlib.import_module("symtab") 
    checker = importlib.import_module("checker")
    model = importlib.import_module("model") 
    
    # 2. Cargar y Renombrar Nodos AST (usando los nombres reales de model.py)
    Scope = symtab.Symtab 
    Node = model.Node
    Program = model.Program
    
    Decl = model.VarDecl        
    Expr = model.Expression     
    Stmt = model.Statement      
    IntLiteral = model.Integer  
    FloatLiteral = model.Float 
    CharLiteral = model.Char       
    StringLiteral = model.String    
    Assign = model.Assign
    BinaryOp = model.BinOper    
    UnOper = model.UnaryOper    
    
    Type = model.Type
    SimpleType = model.SimpleType 
    ArrayType = model.ArrayType   
    FuncType = model.FuncType
    Identifier = model.Identifier
    ArrayIndex = model.ArrayIndex
    Call = model.Call
    
except Exception as ex:
    print(f"; Error: Asegúrate de que 'parser.py', 'model.py', 'symtab.py' y 'checker.py' estén en el mismo directorio: {ex}", file=sys.stderr)
    sys.exit(1)


# ====================================================================
# CLASE IREMITTER (Gestión del Código LLVM IR)
# ====================================================================

class IREmitter:
    """Clase para generar y formatear el código LLVM IR."""
    def __init__(self):
        self.temp_counter = 0
        self.label_counter = 0
        self.lines: List[str] = []
        self.header: List[str] = []
        self.string_literals: Dict[str, Tuple[str, str]] = {} 

    def tmp(self):
        """Genera un nuevo registro temporal (ej. %t1)."""
        self.temp_counter += 1
        return f"%t{self.temp_counter}"

    def label(self, prefix: str):
        """Genera una nueva etiqueta (ej. %for.head.1)."""
        self.label_counter += 1
        return f"%{prefix}.{self.label_counter}"

    def emit(self, line: str):
        """Añade una línea de código a la sección actual."""
        self.lines.append(line)

    def emit_header(self, line: str):
        """Añade una línea al encabezado (declaraciones y globales)."""
        self.header.append(line)

    def finalize(self) -> str:
        """Combina el encabezado y el cuerpo en un solo string."""
        config = [
            'target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"',
            'target triple = "x86_64-pc-linux-gnu"'
        ]
        return "\n".join(config) + "\n\n" + "\n".join(self.header) + "\n\n" + "\n".join(self.lines)

# ====================================================================
# CLASE CODEGEN (El Traductor Principal)
# ====================================================================

class Codegen:
    def __init__(self, ir: IREmitter):
        self.ir = ir
        self.globals: Dict[str, Tuple[str, str]] = {} 
        self.type_map: Dict[str, str] = {
            'integer': LLVM_INT, 'boolean': LLVM_BOOL,
            'char': LLVM_CHAR, 'void': LLVM_VOID, 'float': LLVM_FLOAT,
            'string': LLVM_STRING
        }
        self.current_fn_ret_ty: str = LLVM_VOID

    def _get_llvm_type(self, bminor_type: Type) -> str:
        """Convierte tipo B-Minor a tipo LLVM IR."""
        base_name = ''
        if isinstance(bminor_type, ArrayType):
             base_name = bminor_type.base.name
        elif isinstance(bminor_type, SimpleType): 
             base_name = bminor_type.name
        elif isinstance(bminor_type, FuncType):
             base_name = bminor_type.ret.name if bminor_type.ret else 'void' 
        else:
             base_name = 'integer' 

        base_llty = self.type_map.get(base_name.lower(), LLVM_INT)

        if isinstance(bminor_type, ArrayType):
            # Arrays se manejan como punteros a su tipo base (T*)
            return base_llty + "*"
            
        return base_llty

    # -----------------------------------------------------------
    # GENERACIÓN DE DECLARACIONES
    # -----------------------------------------------------------

    def _gen_global_vardecl(self, n: Decl):
        """Genera código para una declaración de variable global."""
        llty = self._get_llvm_type(n.type).rstrip('*') 
        name = f"@{n.name}"
        
        init_val = None
        if n.init:
            if isinstance(n.init, IntLiteral):
                init_val = str(n.init.value)
                llty = LLVM_INT
            elif isinstance(n.init, FloatLiteral):
                init_val = f"0x{int.from_bytes(struct.pack('>d', n.init.value), 'big'):X}"
                llty = LLVM_FLOAT
            elif isinstance(n.init, CharLiteral):
                init_val = str(ord(n.init.value) if isinstance(n.init.value, str) else n.init.value)
                llty = LLVM_CHAR
            else:
                pass 
            
        if isinstance(n.type, SimpleType):
            default_val = '0'
            if llty == LLVM_FLOAT: default_val = '0.0'
            if llty == LLVM_BOOL: default_val = 'false'
            
            final_val = init_val if init_val is not None else default_val

            self.ir.emit_header(f"{name} = global {llty} {final_val}")
            self.globals[n.name] = (llty, name)
            
        elif isinstance(n.type, ArrayType):
            size_val = n.type.size.value if hasattr(n.type.size, 'value') else 0 
            base_ty = self._get_llvm_type(n.type.base).rstrip('*')
            array_ty = f"[{size_val} x {base_ty}]"
            
            self.ir.emit_header(f"{name} = global {array_ty} zeroinitializer")
            self.globals[n.name] = (array_ty, name)
        else:
            raise NotImplementedError(f"Declaración global de tipo no soportado: {n.type}")


    def _gen_local_vardecl(self, n: Decl, scope: Scope):
        """Genera alloca y store para variables locales."""
        name = n.name
        llty = self._get_llvm_type(n.type).rstrip('*')
        is_array = isinstance(n.type, ArrayType)
        
        if is_array and n.type.size:
            if hasattr(n.type.size, 'value'):
                # Array estático: alloca [N x T]
                size_val = n.type.size.value
                base_ty = self._get_llvm_type(n.type.base).rstrip('*')
                alloca_ty = f"[{size_val} x {base_ty}]"
                
                slot_name = self.ir.tmp()
                self.ir.lines.insert(1, f"  {slot_name} = alloca {alloca_ty}, align 4")
                scope.add(name, SlotRef(alloca_ty, slot_name)) 
            else:
                # Array dinámico (VLA) o Array sin tamaño: alloca T*
                base_ty = self._get_llvm_type(n.type.base).rstrip('*')
                ptr_ty = f"{base_ty}*" 
                
                slot_name = self.ir.tmp()
                self.ir.lines.insert(1, f"  {slot_name} = alloca {ptr_ty}, align 8") 
                scope.add(name, SlotRef(ptr_ty, slot_name))
        else:
            # Variable simple
            slot_name = self.ir.tmp()
            self.ir.lines.insert(1, f"  {slot_name} = alloca {llty}, align 4")
            scope.add(name, SlotRef(llty, slot_name))

            if n.init:
                init_val = self._gen_expr(n.init, scope)
                self.ir.emit(f"  store {init_val.ty} {init_val.name}, {init_val.ty}* {slot_name}, align 4")


    def _gen_fn_decl(self, n: model.FuncDecl, global_scope: Scope):
        """Genera código para la definición de una función."""
        self.ir.lines = [] 
        self.ir.temp_counter = 0 
        self.ir.label_counter = 0

        fn_name = n.name
        ret_ty = self._get_llvm_type(n.type.ret) if n.type.ret else LLVM_VOID
        self.current_fn_ret_ty = ret_ty
        
        # 1. Definir los parámetros LLVM
        llvm_params = []
        for i, param in enumerate(n.type.params or []):
            p_llty = self._get_llvm_type(param.type)
            llvm_params.append(f"{p_llty} %p{i}")
        
        fn_sig = f"define {ret_ty} @{fn_name}({', '.join(llvm_params)}) {{"
        self.ir.emit(fn_sig)
        
        # 2. Bloque de entrada
        self.ir.emit("entry:")
        fn_scope = Scope("function", parent=global_scope)

        # 3. Almacenar parámetros en slots alloca (para poder re-asignar)
        param_stores = []
        for i, param in enumerate(n.type.params or []):
            p_name = param.name
            p_llty = self._get_llvm_type(param.type)
            
            slot_name = self.ir.tmp()
            param_stores.append(f"  {slot_name} = alloca {p_llty}, align 8")
            fn_scope.add(p_name, SlotRef(p_llty, slot_name))

            param_stores.append(f"  store {p_llty} %p{i}, {p_llty}* {slot_name}, align 8")

        self.ir.lines[1:1] = param_stores 

        # 4. Procesar declaraciones locales y cuerpo
        if isinstance(n.init, model.Block):
            # Usar el mismo scope de función para las declaraciones de Block
            for stmt in n.init.stmts:
                if isinstance(stmt, Decl):
                    self._gen_local_vardecl(stmt, fn_scope)
                else:
                    self._gen_stmt(stmt, fn_scope)
        
        # 5. Asegurar un 'ret' al final si es void
        if ret_ty == LLVM_VOID and (not self.ir.lines or not self.ir.lines[-1].strip().startswith('ret')):
             self.ir.emit(f"  ret {LLVM_VOID}")
        
        # 6. Mover el cuerpo generado al header
        self.ir.emit_header("}".join(self.ir.lines) + "}") # Cierra la función

    # -----------------------------------------------------------
    # FUNCIÓN PRINCIPAL DE RECORRIDO DEL AST
    # -----------------------------------------------------------
    
    def gen_program(self, ast: model.Program):
        """Genera código LLVM IR para todo el programa."""
        
        # 0. Definir declaraciones externas (runtime)
        if not any("declare i32 @printf" in h for h in self.ir.header):
            self.ir.emit_header("declare i32 @printf(i8*, ...)")
            self.ir.emit_header("declare i8* @malloc(i32)") 
        
        # 1. Scope Global
        global_scope = Scope("global")

        # 2. Primera pasada: Declaraciones globales
        for node in ast.body:
            if isinstance(node, Decl) and not isinstance(node.type, FuncType):
                self._gen_global_vardecl(node)
                global_scope.add(node.name, node)
        
        # 3. Segunda pasada: Definiciones de funciones
        for node in ast.body:
            if isinstance(node, Decl) and isinstance(node.type, FuncType):
                global_scope.add(node.name, node)
                self._gen_fn_decl(node, global_scope)


    # -----------------------------------------------------------
    # GENERACIÓN DE EXPRESIONES
    # -----------------------------------------------------------

    def _gen_array_ptr(self, e: ArrayIndex, scope: Scope) -> Tuple[str, str]:
        """Obtiene el puntero base y el tipo del elemento para Array Index."""
        arr_name = e.array.name
        slot = scope.get(arr_name)
        
        if slot is None:
            raise Exception(f"Array '{arr_name}' no declarado.")
        
        if slot.ty.startswith('['): 
            # Array estático local ([N x T]*) o global ([N x T]@)
            elem_ty = slot.ty.split(' x ')[1].strip(']')
            base_ptr = self.ir.tmp()
            # Apunta al primer elemento [0] del array estático
            self.ir.emit(f"  {base_ptr} = getelementptr inbounds {slot.ty}, {slot.ty}* {slot.name}, i32 0, i32 0")
            return base_ptr, elem_ty
        
        elif slot.ty.endswith('**') or slot.ty.endswith('*') and slot.ty != LLVM_STRING:
            # Array dinámico (T* almacenado en slot T**) o parámetro array (T*)
            load_ty = slot.ty
            base_ptr = self.ir.tmp()
            self.ir.emit(f"  {base_ptr} = load {load_ty}, {load_ty}* {slot.name}")
            elem_ty = load_ty.strip('*')
            return base_ptr, elem_ty
            
        raise Exception(f"Tipo de slot inesperado para array {arr_name}: {slot.ty}")
        
    def _gen_expr(self, e: Expr, scope: Scope) -> ValueRef:
        """Genera código para evaluar una expresión."""

        if e is None:
            # Una expresión nula (como el 'init' o 'step' vacío en un for)
            # no genera código IR ni devuelve un valor utilizable.
            # Retornamos un valor 'void' temporal que será ignorado.
            return ValueRef(LLVM_VOID, "")
        
        # --- CORRECCIÓN DEFENSIVA: Manejar literales nativos de Python ---
        if isinstance(e, int):
            return ValueRef(LLVM_INT, str(e))
        if isinstance(e, float):
            float_hex = f"0x{int.from_bytes(struct.pack('>d', e), 'big'):X}"
            return ValueRef(LLVM_FLOAT, float_hex) 
        if isinstance(e, bool):
             return ValueRef(LLVM_BOOL, 'true' if e else 'false')
        if isinstance(e, str) and len(e) == 1:
            return ValueRef(LLVM_CHAR, str(ord(e)))
        # -----------------------------------------------------------------

        if isinstance(e, Assign):
            # ... (Lógica de asignación sin cambios)
            val_ref = self._gen_expr(e.value, scope)
            target = e.target
            slot_ptr = None
            
            if isinstance(target, ArrayIndex):
                idx_node = target
                base_ptr, elem_ty = self._gen_array_ptr(idx_node, scope)
                idx = self._gen_expr(idx_node.index, scope) 
                gep = self.ir.tmp()    
                self.ir.emit(f"  {gep} = getelementptr inbounds {elem_ty}, {elem_ty}* {base_ptr}, {LLVM_INT} {idx.name}")
                slot_ptr = gep 
            
            elif isinstance(target, Identifier):
                slot = scope.get(target.name)
                is_global = target.name in self.globals

                if is_global:
                    slot_ptr = self.globals[target.name][1]
                    if self.globals[target.name][0].startswith('['): # Es un array global [N x T]
                        raise NotImplementedError("Asignación directa a array global completo no soportada.")
                elif slot is not None and isinstance(slot, SlotRef):
                    slot_ptr = slot.name 
                else:
                    raise Exception(f"Variable '{target.name}' no declarada o no es un l-value válido.")
            
            else:
                raise NotImplementedError(f"Objetivo de asignación no implementado: {type(target)}")
            
            self.ir.emit(f"  store {val_ref.ty} {val_ref.name}, {val_ref.ty}* {slot_ptr}")
            return val_ref
        
        # --- Literales ---
        if isinstance(e, IntLiteral):
            return ValueRef(LLVM_INT, str(e.value))
        
        if isinstance(e, FloatLiteral):
            float_hex = f"0x{int.from_bytes(struct.pack('>d', e.value), 'big'):X}"
            return ValueRef(LLVM_FLOAT, float_hex) 
        
        if isinstance(e, CharLiteral):
            char_code = ord(e.value) if isinstance(e.value, str) else e.value
            return ValueRef(LLVM_CHAR, str(char_code)) 

        if isinstance(e, StringLiteral):
            # ... (Lógica de StringLiteral sin cambios)
            val = e.value
            llvm_val = ""
            for char in val + '\00': 
                if char == '\00': llvm_val += "\\00"
                elif char == '\\': llvm_val += "\\\\"
                elif char == '\"': llvm_val += "\\\""
                elif char == '\n': llvm_val += "\\0A"
                elif char == '\t': llvm_val += "\\09"
                elif 32 <= ord(char) <= 126: llvm_val += char
                else: llvm_val += f"\\{ord(char):02X}"

            llty = f"[{len(val) + 1} x {LLVM_CHAR}]" 
            
            if llvm_val not in self.ir.string_literals:
                gname = self.ir.tmp().replace('%', '@.str')
                self.ir.emit_header(f"{gname} = private unnamed_addr constant {llty} c\"{llvm_val}\"")
                self.ir.string_literals[llvm_val] = (gname, llty)
            else:
                gname, llty = self.ir.string_literals[llvm_val]
            
            ptr_reg = self.ir.tmp()
            self.ir.emit(f"  {ptr_reg} = getelementptr inbounds {llty}, {llty}* {gname}, {LLVM_INT} 0, {LLVM_INT} 0")
            
            return ValueRef(LLVM_STRING, ptr_reg) 
            
        # --- Identificador ---
        if isinstance(e, Identifier):
            name = e.name
            
            if name in self.globals:
                llty, g = self.globals[name]
                # Si es un array global ([N x T]), devuelve puntero al primer elemento (T*)
                if llty.startswith('['):
                    base_ty = llty.split(' x ')[1].strip(']')
                    ptr_reg = self.ir.tmp()
                    self.ir.emit(f"  {ptr_reg} = getelementptr inbounds {llty}, {llty}* {g}, i32 0, i32 0")
                    return ValueRef(base_ty + '*', ptr_reg)
                
                # Carga de valor de variable global simple
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load {llty}, {llty}* {g}")
                return ValueRef(llty, reg)

            slot = scope.get(name)
            if slot is not None and isinstance(slot, SlotRef):
                # Si es un array local ([N x T]*), devuelve puntero al primer elemento (T*)
                if slot.ty.startswith('['):
                    base_ty = slot.ty.split(' x ')[1].strip(']')
                    ptr_reg = self.ir.tmp()
                    self.ir.emit(f"  {ptr_reg} = getelementptr inbounds {slot.ty}, {slot.ty}* {slot.name}, i32 0, i32 0")
                    return ValueRef(base_ty + '*', ptr_reg)

                # Carga de valor (simple T o puntero T*)
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load {slot.ty}, {slot.ty}* {slot.name}")
                return ValueRef(slot.ty.rstrip('*'), reg)
            
            raise Exception(f"Identificador '{name}' no encontrado en el scope.")
        
        # --- Array Index ---
        if isinstance(e, ArrayIndex):
            base_ptr, elem_ty = self._gen_array_ptr(e, scope)
            idx = self._gen_expr(e.index, scope) 
            gep = self.ir.tmp()
            self.ir.emit(f"  {gep} = getelementptr inbounds {elem_ty}, {elem_ty}* {base_ptr}, {LLVM_INT} {idx.name}")
            reg = self.ir.tmp()
            self.ir.emit(f"  {reg} = load {elem_ty}, {elem_ty}* {gep}")
            return ValueRef(elem_ty, reg)

        # --- Operaciones Unarias, Binarias, Call, Inc/Dec ---
        if isinstance(e, UnOper):
            expr_ref = self._gen_expr(e.expr, scope)
            res = self.ir.tmp()
            if e.oper == '!':
                self.ir.emit(f"  {res} = xor i1 {expr_ref.name}, true")
                return ValueRef(LLVM_BOOL, res)
            elif e.oper == '-':
                if expr_ref.ty == LLVM_INT:
                    self.ir.emit(f"  {res} = sub {LLVM_INT} 0, {expr_ref.name}")
                elif expr_ref.ty == LLVM_FLOAT:
                    self.ir.emit(f"  {res} = fsub {LLVM_FLOAT} -0.0, {expr_ref.name}")
                return ValueRef(expr_ref.ty, res)
        
        if isinstance(e, BinaryOp):
            left_ref = self._gen_expr(e.left, scope)
            right_ref = self._gen_expr(e.right, scope)
            op = e.oper 
            llty = left_ref.ty 
            res = self.ir.tmp()
            
            is_float = llty == LLVM_FLOAT
            
            if op in ('+', '-', '*', '/'):
                 instr = ''
                 if is_float:
                     instr = f"f{'add' if op=='+' else ('sub' if op=='-' else ('mul' if op=='*' else 'div'))}"
                 else:
                     instr = f"{'add' if op=='+' else ('sub' if op=='-' else ('mul' if op=='*' else 'sdiv'))}"
                 self.ir.emit(f"  {res} = {instr} {llty} {left_ref.name}, {right_ref.name}")
            elif op == '%':
                self.ir.emit(f"  {res} = srem {llty} {left_ref.name}, {right_ref.name}")
            
            elif op in ('<', '>', '<=', '>=', '==', '!='):
                comp_cond = ''
                comp_type = ''

                if is_float:
                    comp_type = 'fcmp'
                    if op == '<': comp_cond = 'olt'
                    elif op == '>': comp_cond = 'ogt'
                    elif op == '<=': comp_cond = 'ole'
                    elif op == '>=': comp_cond = 'oge'
                    elif op == '==': comp_cond = 'oeq'
                    else: comp_cond = 'one' # !=
                else:
                    comp_type = 'icmp'
                    if op == '<': comp_cond = 'slt' # Signed Less Than
                    elif op == '>': comp_cond = 'sgt' # Signed Greater Than
                    elif op == '<=': comp_cond = 'sle' # Signed Less or Equal
                    elif op == '>=': comp_cond = 'sge' # Signed Greater or Equal
                    elif op == '==': comp_cond = 'eq'
                    else: comp_cond = 'ne' # !=
                
                # Emitir la instrucción LLVM IR correcta: <icmp/fcmp> <condición>
                self.ir.emit(f"  {res} = {comp_type} {comp_cond} {llty} {left_ref.name}, {right_ref.name}")
                llty = LLVM_BOOL
                
            elif op == '&&':
                self.ir.emit(f"  {res} = and {LLVM_BOOL} {left_ref.name}, {right_ref.name}")
                llty = LLVM_BOOL
            elif op == '||':
                self.ir.emit(f"  {res} = or {LLVM_BOOL} {left_ref.name}, {right_ref.name}")
                llty = LLVM_BOOL
            
            return ValueRef(llty, res)

        if isinstance(e, Call):
            # ... (Lógica de Call sin cambios)
            fn_name = e.func.name
            fn_decl = scope.get(fn_name)
            
            ret_ty = self._get_llvm_type(fn_decl.type.ret if fn_decl and hasattr(fn_decl.type, 'ret') else model.SimpleType("integer"))
            
            arg_refs = [self._gen_expr(arg, scope) for arg in e.args]
            args_llvm = [f"{r.ty} {r.name}" for r in arg_refs]
            
            if ret_ty == LLVM_VOID:
                self.ir.emit(f"  call {ret_ty} @{fn_name}({', '.join(args_llvm)})")
                return ValueRef(LLVM_VOID, "") 
            else:
                res = self.ir.tmp()
                self.ir.emit(f"  {res} = call {ret_ty} @{fn_name}({', '.join(args_llvm)})")
                return ValueRef(ret_ty, res)
        
        # Postfix/Prefix (asume que ya están reducidos a Assign/Call por el checker/parser si es necesario)
        if isinstance(e, (model.PostfixOper, model.PreInc, model.PreDec)):
            # CORRECCIÓN: Usar 'e.expr' para acceder a la variable/expresión
            return self._gen_expr(model.Assign(e.expr, BinaryOp(e.expr, e.oper[0], model.Integer(1))), scope)
        raise NotImplementedError(f"Expresión no implementada: {type(e)}")


    # -----------------------------------------------------------
    # GENERACIÓN DE SENTENCIAS
    # -----------------------------------------------------------

    def _gen_stmt(self, s: Stmt, scope: Scope):
        """Genera código para una sentencia."""
        
        # --- Asignación/Call/Expr con efecto secundario ---
        if isinstance(s, (Assign, Call, model.PostfixOper, model.PreInc, model.PreDec)):
            self._gen_expr(s, scope) 
            return
            
        # --- Sentencia IF ---
        if isinstance(s, model.IfStmt):
            then_lbl = self.ir.label("if.then")
            end_lbl = self.ir.label("if.end")
            
            cond_ref = self._gen_expr(s.cond, scope)
            
            if s.otherwise:
                else_lbl = self.ir.label("if.else")
                self.ir.emit(f"  br i1 {cond_ref.name}, label {then_lbl}, label {else_lbl}")
            else:
                self.ir.emit(f"  br i1 {cond_ref.name}, label {then_lbl}, label {end_lbl}")
            
            self.ir.emit(f"{then_lbl}:")
            self._gen_stmt(s.then, scope)
            self.ir.emit(f"  br label {end_lbl}")
            
            if s.otherwise:
                self.ir.emit(f"{else_lbl}:")
                self._gen_stmt(s.otherwise, scope)
                self.ir.emit(f"  br label {end_lbl}")

            self.ir.emit(f"{end_lbl}:")
            return

        # --- Sentencia WHILE ---
        if isinstance(s, model.WhileStmt):
            head_lbl = self.ir.label("while.head")
            body_lbl = self.ir.label("while.body")
            end_lbl = self.ir.label("while.end")

            self.ir.emit(f"  br label {head_lbl}")
            
            self.ir.emit(f"{head_lbl}:")
            cond_ref = self._gen_expr(s.cond, scope)
            self.ir.emit(f"  br i1 {cond_ref.name}, label {body_lbl}, label {end_lbl}")

            self.ir.emit(f"{body_lbl}:")
            self._gen_stmt(s.body, scope)
            self.ir.emit(f"  br label {head_lbl}") 

            self.ir.emit(f"{end_lbl}:")
            return

        # --- Sentencia FOR ---
        if isinstance(s, model.ForStmt):
            # Etiquetas necesarias
            head_lbl = self.ir.label("for.head")
            body_lbl = self.ir.label("for.body")
            step_lbl = self.ir.label("for.step")
            end_lbl = self.ir.label("for.end")
            
            # 1. Inicialización (Opcional)
            if s.init:
                self._gen_expr(s.init, scope)
            
            self.ir.emit(f"  br label {head_lbl}")
            
            # 2. Cabeza del ciclo (Condición)
            self.ir.emit(f"{head_lbl}:")
            if s.cond:
                cond_ref = self._gen_expr(s.cond, scope)
                self.ir.emit(f"  br i1 {cond_ref.name}, label {body_lbl}, label {end_lbl}")
            else:
                self.ir.emit(f"  br label {body_lbl}")

            # 3. Cuerpo del ciclo
            self.ir.emit(f"{body_lbl}:")
            self._gen_stmt(s.body, scope)
            self.ir.emit(f"  br label {step_lbl}")

            # 4. Paso (Incremento/Decremento - Opcional)
            self.ir.emit(f"{step_lbl}:")
            if s.step:
                self._gen_expr(s.step, scope)
            self.ir.emit(f"  br label {head_lbl}") 

            # 5. Fin del ciclo
            self.ir.emit(f"{end_lbl}:")
            return
        
        # --- Sentencia RETURN ---
        if isinstance(s, model.ReturnStmt):
            if s.expr is None:
                self.ir.emit(f"  ret {LLVM_VOID}")
            else:
                val_ref = self._gen_expr(s.expr, scope)
                self.ir.emit(f"  ret {val_ref.ty} {val_ref.name}")
            return

        # --- Sentencia BLOCK ---
        if isinstance(s, model.Block):
            # Crea un nuevo scope anidado para el bloque
            block_scope = Scope("block", parent=scope) 
            
            for stmt in s.stmts:
                # Las declaraciones dentro de un bloque son locales a ese bloque
                if isinstance(stmt, Decl):
                    self._gen_local_vardecl(stmt, block_scope)
                else:
                    self._gen_stmt(stmt, block_scope)
            return

        # --- Sentencia de Impresión (PrintStmt) ---
        if isinstance(s, model.PrintStmt): 
            # ... (Lógica de PrintStmt sin cambios)
            val_ref = self._gen_expr(s.args[0], scope)
            
            fmt_name = "@.fmt_i32" # Valor por defecto
            
            if val_ref.ty == LLVM_INT or val_ref.ty == LLVM_BOOL or val_ref.ty == LLVM_CHAR:
                fmt_name = "@.fmt_i32"
                if not any(fmt_name in h for h in self.ir.header):
                     self.ir.emit_header(f"{fmt_name} = private unnamed_addr constant [4 x i8] c\"%d\\0A\\00\"")
            elif val_ref.ty == LLVM_FLOAT:
                 fmt_name = "@.fmt_double"
                 if not any(fmt_name in h for h in self.ir.header):
                     self.ir.emit_header(f"{fmt_name} = private unnamed_addr constant [4 x i8] c\"%f\\0A\\00\"")
            elif val_ref.ty == LLVM_STRING:
                 fmt_name = "@.fmt_i8p"
                 if not any(fmt_name in h for h in self.ir.header):
                     self.ir.emit_header(f"{fmt_name} = private unnamed_addr constant [4 x i8] c\"%s\\0A\\00\"")
            
            fmt_ptr = self.ir.tmp()
            self.ir.emit(f"  {fmt_ptr} = getelementptr inbounds [4 x i8], [4 x i8]* {fmt_name}, {LLVM_INT} 0, {LLVM_INT} 0")
            
            arg_ty = val_ref.ty
            arg_name = val_ref.name
            
            if arg_ty == LLVM_BOOL or arg_ty == LLVM_CHAR:
                ext_reg = self.ir.tmp()
                self.ir.emit(f"  {ext_reg} = zext {arg_ty} {arg_name} to {LLVM_INT}")
                arg_ty = LLVM_INT
                arg_name = ext_reg
            elif arg_ty == LLVM_FLOAT:
                fext_reg = self.ir.tmp()
                self.ir.emit(f"  {fext_reg} = fpext {LLVM_FLOAT} {arg_name} to double")
                arg_ty = 'double'
                arg_name = fext_reg
            
            self.ir.emit(f"  call {LLVM_INT} (i8*, ...) @printf(i8* {fmt_ptr}, {arg_ty} {arg_name})")
            return


        raise NotImplementedError(f"Sentencia no implementada: {type(s)}")


# ====================================================================
# Carga + compile
# ====================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {sys.argv[0]} programa.bminor", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]

    try:
        with open(filename, encoding="utf-8") as f:
            txt = f.read()

        errors = importlib.import_module("errors")
        errors.set_source(filename, txt) 

        ast = parser.parse(txt)
        checker.check(ast)

        if errors.errors_detected():
             print(f"; Terminando debido a {len(errors._MSGS)} errores.", file=sys.stderr)
             sys.exit(1)

        em = IREmitter()
        cg = Codegen(em)
        
        cg.gen_program(ast) 

        output_ir = em.finalize() 

        print(output_ir) 
            
        print(f"; Archivo out.ll generado con éxito a partir de {filename}.", file=sys.stderr)

    except NotImplementedError as e:
        print(f"\n; --- ERROR DE IMPLEMENTACIÓN LLVM FALTANTE ---", file=sys.stderr)
        print(f"; {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Aquí se capturan errores de Symtab (SymbolConflictError, SymbolDefinedError) o cualquier otro error inesperado.
        print(f"\n; --- ERROR DE COMPILACIÓN GENERAL ---", file=sys.stderr)
        print(f"; {e}", file=sys.stderr)
        sys.exit(1)