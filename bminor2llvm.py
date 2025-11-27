#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bminor2llvm.py — Generador de LLVM IR corregido
CORRECCIONES PRINCIPALES:
1. Inicialización correcta de arrays en loops (store 0)
2. Asignación correcta de board[curr_pos] = 1
3. Asignación correcta de board[curr_pos] = step en loops
4. Condición correcta en is_valid_move (llamar a in_board)
5. Manejo mejorado de arrays globales y locales
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
    sys.exit("Uso: python bminor2llvm.py archivo.bminor")

filename = argv[0]

parser_mod  = _import_mod(parser_mod_name)
checker_mod = _import_mod(checker_mod_name)
model_mod   = _import_mod("model")
errors_mod  = _import_mod("errors")

if parser_mod is None or not hasattr(parser_mod, "parse"):
    sys.exit("Debes proveer un parser válido.")
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
UnaryOp       = getattr(model_mod, "UnaryOp")  # ← AGREGAR ESTO
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

def set_source(fname: str, txt: str):
    if errors_mod is not None and hasattr(errors_mod, "set_source"):
        errors_mod.set_source(fname, txt)

def errors_detected() -> bool:
    if errors_mod is not None and hasattr(errors_mod, "errors_detected"):
        return errors_mod.errors_detected()
    return False

# ===== IR Emitter =====
class IREmitter:
    def __init__(self):
        self.lines: List[str] = []
        self.tmp_counter = 0
        self.blk_counter = 0

    def tmp(self) -> str:
        self.tmp_counter += 1
        return f"%t{self.tmp_counter}"

    def label(self, base: str) -> str:
        self.blk_counter += 1
        return f"{base}{self.blk_counter}"

    def emit(self, line: str):
        self.lines.append(line)

    def header(self):
        self.emit('declare i32 @printf(i8*, ...)')
        self.emit('declare i8* @malloc(i32)')
        self.emit('')
        self.emit('@.fmt_int   = private unnamed_addr constant [4 x i8] c"%d\\0A\\00"')
        self.emit('@.fmt_float = private unnamed_addr constant [4 x i8] c"%f\\0A\\00"')
        self.emit('@.fmt_char  = private unnamed_addr constant [4 x i8] c"%c\\0A\\00"')
        self.emit('@.fmt_str   = private unnamed_addr constant [4 x i8] c"%s\\0A\\00"')
        self.emit('')

    def finalize(self) -> str:
        return "\n".join(self.lines) + "\n"

# ===== Tipos =====
LLVM_INT    = "i32"
LLVM_BOOL   = "i1"
LLVM_CHAR   = "i8"
LLVM_FLOAT  = "double"
LLVM_STRING = "i8*"

def get_size(t) -> int:
    llty = type_to_llvm(t)
    if llty == LLVM_FLOAT: return 8
    if llty == LLVM_INT or llty == LLVM_BOOL: return 4
    if llty == LLVM_CHAR: return 1
    return 4

def type_to_llvm(t) -> str:
    if isinstance(t, SimpleType):
        name = (t.name or "").lower()
    elif isinstance(t, str):
        name = t.lower()
    else:
        name = None
    if name in ("int", "integer"): return LLVM_INT
    if name in ("bool", "boolean"): return LLVM_BOOL
    if name == "char": return LLVM_CHAR
    if name == "float": return LLVM_FLOAT
    if name == "string": return LLVM_STRING
    if name == "void": return "void"
    return LLVM_INT

def param_type_to_llvm(t) -> str:
    if isinstance(t, ArrayType):
        return f"{type_to_llvm(t.base)}*"
    return type_to_llvm(t)

@dataclass
class ValueRef:
    ty: str
    name: str

class Scope:
    def __init__(self, parent: Optional["Scope"]=None):
        self.parent = parent
        self.vars: Dict[str, ValueRef] = {}
    def get(self, name: str) -> Optional[ValueRef]:
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        return None
    def set(self, name: str, val: ValueRef):
        self.vars[name] = val

# ===== Codegen =====
class Codegen:
    def __init__(self, emitter: IREmitter):
        self.ir = emitter
        self.globals: Dict[str, Tuple[str, str]] = {}
        self.fn_ret_ty: Optional[str] = None
        self.current_fn_end_label: Optional[str] = None
        self.current_fn_name: Optional[str] = None
        self.fn_param_index: Dict[str, Dict[str, int]] = {}
        self.cur_fn_name: Optional[str] = None
        self.cur_fn_params: List[str] = []
        self.fn_sigs: Dict[str, Tuple[str, List[str]]] = {}
        self.arr_len: Dict[str, ValueRef] = {}

    def gen_program(self, prog: Program):
        self.ir.header()
        
        # Recolectar firmas
        for s in prog.body:
            if isinstance(s, VarDecl) and isinstance(s.type, FuncType):
                ret_ll = type_to_llvm(s.type.ret) if s.type.ret else "void"
                params_ll = [param_type_to_llvm(p.type) for p in (s.type.params or [])]
                self.fn_sigs[s.name] = (ret_ll, params_ll)

        # Globales
        for s in prog.body:
            if isinstance(s, VarDecl) and not isinstance(s.type, FuncType):
                self._gen_global_decl(s)

        # Funciones
        for s in prog.body:
            if isinstance(s, VarDecl) and isinstance(s.type, FuncType):
                self._gen_function(s)

    def _gen_global_decl(self, d: VarDecl):
        """Genera la declaración y posible inicialización de una variable global."""
        ty = d.type
        
        if isinstance(ty, ArrayType):
            base_llty = type_to_llvm(ty.base)
            
            # Array con tamaño literal
            if ty.size and isinstance(ty.size, Integer):
                n = int(ty.size.value)
                gname = f"@{d.name}"
                self.globals[d.name] = (f"[{n} x {base_llty}]", gname)
                
                # Procesar inicializador
                init_values = None
                if hasattr(d.init, 'values'):
                    init_values = d.init.values
                elif isinstance(d.init, list):
                    init_values = d.init
                elif hasattr(d.init, 'elements'):
                    init_values = d.init.elements
                elif hasattr(d.init, 'items'):
                    init_values = d.init.items
                
                # Generar inicializador
                if init_values is not None:
                    initializers = []
                    for val_node in init_values:
                        if isinstance(val_node, Integer):
                            val = str(int(val_node.value))
                        elif isinstance(val_node, UnaryOper) and val_node.oper == '-':
                            if isinstance(val_node.expr, Integer):
                                val = str(-int(val_node.expr.value))
                            else:
                                val = "0"
                        else:
                            val = "0"
                        initializers.append(f"{base_llty} {val}")
                    
                    # Rellenar con ceros si faltan elementos
                    while len(initializers) < n:
                        initializers.append(f"{base_llty} 0")
                    
                    initializer_str = "[" + ", ".join(initializers) + "]"
                else:
                    initializer_str = "zeroinitializer"

                self.ir.emit(f'{gname} = global [{n} x {base_llty}] {initializer_str}')
                self.arr_len[d.name] = ValueRef(LLVM_INT, str(n))
                return
            
            # Array sin tamaño literal (puntero)
            else:
                gname = f"@{d.name}"
                self.globals[d.name] = (f"{base_llty}*", gname)
                self.ir.emit(f'{gname} = global {base_llty}* null')
                return
        
        # Escalar global
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

    def _gen_function(self, fdecl: VarDecl):
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
            p_llty = param_type_to_llvm(p.type)
            params_sig.append(f"{p_llty} %{p.name}")

        self.ir.emit(f"define {ret_llty} {fname}({', '.join(params_sig)}) "+"{")
        fn_scope = Scope()

        for p in (ftype.params or []):
            p_llty = param_type_to_llvm(p.type)
            slot = self.ir.tmp()
            self.ir.emit(f"  {slot} = alloca {p_llty}")
            self.ir.emit(f"  store {p_llty} %{p.name}, {p_llty}* {slot}")
            fn_scope.set(p.name, ValueRef(ty=p_llty, name=slot))

        self.current_fn_end_label = self.ir.label("endfn.")
        if isinstance(fdecl.init, Block):
            self._gen_block(fdecl.init, fn_scope)
        
        # Agregar branch incondicional al label final (por si no hay return explícito)
        self.ir.emit(f"  br label %{self.current_fn_end_label}")
        self.ir.emit(f"{self.current_fn_end_label}:")
        if ret_llty == "void":
            self.ir.emit("  ret void")
        else:
            self.ir.emit(f"  ret {ret_llty} 0")

        self.ir.emit("}")
        self.ir.emit("")  # Línea en blanco entre funciones
        
        self.fn_ret_ty = None
        self.current_fn_end_label = None
        self.current_fn_name = None
        self.cur_fn_name = None
        self.cur_fn_params = []

    def _gen_block(self, block: Block, scope: Scope):
        for s in block.stmts:
            if isinstance(s, VarDecl) and not isinstance(s.type, FuncType):
                self._gen_local_vardecl(s, scope)
            elif isinstance(s, PrintStmt):
                for a in s.args:
                    v = self._gen_expr(a, scope)
                    self._gen_print(v)
            elif isinstance(s, ReturnStmt):
                if s.expr is None:
                    self.ir.emit(f"  br label %{self.current_fn_end_label}")
                else:
                    v = self._gen_expr(s.expr, scope)
                    self.ir.emit(f"  ret {v.ty} {v.name}")
                return
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
                _ = self._gen_expr(s, scope)

    def _gen_local_vardecl(self, d: VarDecl, scope: Scope):
        if isinstance(d.type, ArrayType):
            base_llty = type_to_llvm(d.type.base)
            elem_sz = get_size(d.type.base)
            
            # Array estático [N x T]
            if d.type.size and isinstance(d.type.size, Integer):
                n = int(d.type.size.value)
                slot_arr = self.ir.tmp()
                self.ir.emit(f"  {slot_arr} = alloca [{n} x {base_llty}]")
                scope.set(d.name, ValueRef(ty=f"[{n} x {base_llty}]", name=slot_arr))
                self.arr_len[d.name] = ValueRef(LLVM_INT, str(n))
                return

            # Array dinámica
            slot_ptr = self.ir.tmp()
            self.ir.emit(f"  {slot_ptr} = alloca {base_llty}*")
            
            n_reg = "0"
            if d.type.size is not None:
                nval = self._gen_expr(d.type.size, scope)
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
            
            # Si n_reg es "0", usar valor por defecto
            if n_reg == "0":
                n_reg = "64"
            
            bytes_cnt = self.ir.tmp()
            self.ir.emit(f"  {bytes_cnt} = mul i32 {n_reg}, {elem_sz}")
            
            raw = self.ir.tmp()
            self.ir.emit(f"  {raw} = call i8* @malloc(i32 {bytes_cnt})")
            cast = self.ir.tmp()
            self.ir.emit(f"  {cast} = bitcast i8* {raw} to {base_llty}*")
            self.ir.emit(f"  store {base_llty}* {cast}, {base_llty}** {slot_ptr}")
            
            len_slot = self.ir.tmp()
            self.ir.emit(f"  {len_slot} = alloca i32")
            self.ir.emit(f"  store i32 {n_reg}, i32* {len_slot}")
            self.arr_len[d.name] = ValueRef(f"{LLVM_INT}*", len_slot)
            scope.set(d.name, ValueRef(ty=f"{base_llty}*", name=slot_ptr))

            init_values = getattr(d.init, "values", None)
            if init_values is not None:
                arr_ptr = self.ir.tmp()
                self.ir.emit(f"  {arr_ptr} = load {base_llty}*, {base_llty}** {slot_ptr}")
                for idx, elt in enumerate(init_values):
                    val = self._gen_expr(elt, scope)
                    gep = self.ir.tmp()
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
            
        # Variable escalar
        llty = type_to_llvm(d.type)
        slot = self.ir.tmp()
        self.ir.emit(f"  {slot} = alloca {llty}")
        scope.set(d.name, ValueRef(llty, slot))

        if getattr(d, "init", None) is not None:
            v = self._gen_expr(d.init, scope)
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
            self.ir.emit(f"  store {llty} 0, {llty}* {slot}")

    def _as_i1(self, v: ValueRef) -> ValueRef:
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
        head = self.ir.label("for.head.")
        body = self.ir.label("for.body.")
        end  = self.ir.label("for.end.")
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{head}:")
        c = self._as_i1(self._gen_expr(n.cond, scope))
        self.ir.emit(f"  br i1 {c.name}, label %{body}, label %{end}")
        self.ir.emit(f"{body}:")
        self._gen_block(n.body if isinstance(n.body, Block) else Block(stmts=[n.body]), Scope(scope))
        self.ir.emit(f"  br label %{head}")
        self.ir.emit(f"{end}:")

    def _gen_dowhile(self, n: DoWhileStmt, scope: Scope):
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

    def _gen_expr(self, e, scope: Scope) -> ValueRef:
        # Literales
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
            strlen = len(e.value) + 1
            self.ir.emit(f"  {ptr} = getelementptr inbounds [{strlen} x i8], [{strlen} x i8]* {gname}, i32 0, i32 0")
            return ValueRef(LLVM_STRING, ptr)
        
        # Identificador
        if isinstance(e, Identifier):
            v = scope.get(e.name)
            if v is not None:
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load {v.ty}, {v.ty}* {v.name}")
                return ValueRef(v.ty, reg)
            if e.name in self.globals:
                llty, g = self.globals[e.name]
                reg = self.ir.tmp()
                self.ir.emit(f"  {reg} = load {llty}, {llty}* {g}")
                return ValueRef(llty, reg)
            return ValueRef(LLVM_INT, "0")

        # Asignación
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
            
            # Asignación a array
            elif isinstance(e.target, ArrayIndex):
                idx_node = e.target
                
                # Array global [N x T]
                if isinstance(idx_node.array, Identifier) and idx_node.array.name in self.globals:
                    gty, gname = self.globals[idx_node.array.name]
                    if gty.startswith('['):
                        elem_ty = gty.split(' x ')[-1].rstrip(']')
                        idx = self._gen_expr(idx_node.index, scope)
                        gep = self.ir.tmp()
                        self.ir.emit(f"  {gep} = getelementptr inbounds {gty}, {gty}* {gname}, i32 0, i32 {idx.name}")
                        val = self._gen_expr(e.value, scope)
                        castv = val.name
                        if val.ty != elem_ty:
                            tmp = self.ir.tmp()
                            if val.ty in (LLVM_BOOL, LLVM_CHAR):
                                self.ir.emit(f"  {tmp} = zext {val.ty} {val.name} to i32")
                            elif val.ty == LLVM_FLOAT and elem_ty == LLVM_INT:
                                self.ir.emit(f"  {tmp} = fptosi double {val.name} to i32")
                            else:
                                self.ir.emit(f"  {tmp} = add i32 0, 0")
                            castv = tmp
                        self.ir.emit(f"  store {elem_ty} {castv}, {elem_ty}* {gep}")
                        return ValueRef(elem_ty, castv)
                
                # Array local [N x T]
                v = scope.get(idx_node.array.name)
                if v and v.ty.startswith('['):
                    elem_ty = v.ty.split(' x ')[-1].rstrip(']')
                    idx = self._gen_expr(idx_node.index, scope)
                    gep = self.ir.tmp()
                    self.ir.emit(f"  {gep} = getelementptr inbounds {v.ty}, {v.ty}* {v.name}, i32 0, i32 {idx.name}")
                    val = self._gen_expr(e.value, scope)
                    self.ir.emit(f"  store {elem_ty} {val.name}, {elem_ty}* {gep}")
                    return ValueRef(elem_ty, val.name)
                
                # Puntero T*
                base_ptr, elem_ty = self._gen_array_ptr(idx_node, scope)
                idx = self._gen_expr(idx_node.index, scope)
                gep = self.ir.tmp()
                self.ir.emit(f"  {gep} = getelementptr inbounds {elem_ty}, {elem_ty}* {base_ptr}, i32 {idx.name}")
                val = self._gen_expr(e.value, scope)
                self.ir.emit(f"  store {elem_ty} {val.name}, {elem_ty}* {gep}")
                return val
            
            return self._gen_expr(e.value, scope)

        # Acceso a array
        if isinstance(e, ArrayIndex):
            if isinstance(e.array, Identifier):
                # Array global [N x T]
                if e.array.name in self.globals:
                    gty, gname = self.globals[e.array.name]
                    if gty.startswith('['):
                        T = gty.split(' x ')[-1].rstrip(']')
                        idx = self._gen_expr(e.index, scope)
                        gep = self.ir.tmp()
                        self.ir.emit(f"  {gep} = getelementptr inbounds {gty}, {gty}* {gname}, i32 0, i32 {idx.name}")
                        reg = self.ir.tmp()
                        self.ir.emit(f"  {reg} = load {T}, {T}* {gep}")
                        return ValueRef(T, reg)
                
                # Array local [N x T]
                v = scope.get(e.array.name)
                if v and v.ty.startswith('['):
                    T = v.ty.split(' x ')[-1].rstrip(']')
                    idx = self._gen_expr(e.index, scope)
                    gep = self.ir.tmp()
                    self.ir.emit(f"  {gep} = getelementptr inbounds {v.ty}, {v.ty}* {v.name}, i32 0, i32 {idx.name}")
                    reg = self.ir.tmp()
                    self.ir.emit(f"  {reg} = load {T}, {T}* {gep}")
                    return ValueRef(T, reg)
                
                # Puntero T*
                if v and v.ty.endswith('*'):
                    baseT = v.ty[:-1]
                    loaded = self.ir.tmp()
                    self.ir.emit(f"  {loaded} = load {v.ty}, {v.ty}* {v.name}")
                    idx = self._gen_expr(e.index, scope)
                    gep = self.ir.tmp()
                    self.ir.emit(f"  {gep} = getelementptr inbounds {baseT}, {baseT}* {loaded}, i32 {idx.name}")
                    reg = self.ir.tmp()
                    self.ir.emit(f"  {reg} = load {baseT}, {baseT}* {gep}")
                    return ValueRef(baseT, reg)

        # Llamada a función
        if isinstance(e, Call):
            callee = e.func.name if isinstance(e.func, Identifier) else "unknown"
            argvals: List[ValueRef] = []
            
            for a in e.args:
                if isinstance(a, Identifier):
                    v = scope.get(a.name)
                    # Array local estático [N x T]
                    if v and v.ty.startswith('['):
                        ptr = self.ir.tmp()
                        elem_ty = v.ty.split(' x ')[-1].rstrip(']')
                        self.ir.emit(f"  {ptr} = getelementptr inbounds {v.ty}, {v.ty}* {v.name}, i32 0, i32 0")
                        argvals.append(ValueRef(f"{elem_ty}*", ptr))
                        continue
                    # Array puntero T*
                    if v and v.ty.endswith('*'):
                        loaded_ptr = self.ir.tmp()
                        self.ir.emit(f"  {loaded_ptr} = load {v.ty}, {v.ty}* {v.name}")
                        argvals.append(ValueRef(v.ty, loaded_ptr))
                        continue
                    # Array global [N x T]
                    if a.name in self.globals:
                        gty, gname = self.globals[a.name]
                        if gty.startswith('['):
                            ptr = self.ir.tmp()
                            elem_ty = gty.split(' x ')[-1].rstrip(']')
                            self.ir.emit(f"  {ptr} = getelementptr inbounds {gty}, {gty}* {gname}, i32 0, i32 0")
                            argvals.append(ValueRef(f"{elem_ty}*", ptr))
                            continue
                
                argvals.append(self._gen_expr(a, scope))

            if callee in self.fn_sigs:
                ret_llty, param_lltys = self.fn_sigs[callee]
                fname = f"@{callee}"
                
                call_args = []
                for val_ref, sig_ty in zip(argvals, param_lltys):
                    call_args.append(f"{sig_ty} {val_ref.name}")
                
                call_str = f"call {ret_llty} {fname}({', '.join(call_args)})"
                
                if ret_llty != "void":
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = {call_str}")
                    return ValueRef(ret_llty, r)
                else:
                    self.ir.emit(f"  {call_str}")
                    return ValueRef("void", "")
            
            return ValueRef(LLVM_INT, "0")

        # Operador unario
        if isinstance(e, UnaryOper):
            v = self._gen_expr(e.expr, scope)
            if e.oper == '-':
                if v.ty == LLVM_FLOAT:
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = fsub double 0.0, {v.name}")
                    return ValueRef(v.ty, r)
                r = self.ir.tmp()
                self.ir.emit(f"  {r} = sub {v.ty} 0, {v.name}")
                return ValueRef(v.ty, r)
            if e.oper == '+':
                return v
            if e.oper == '!' or e.oper == 'NOT':
                as1 = self._as_i1(v)
                r = self.ir.tmp()
                self.ir.emit(f"  {r} = xor i1 {as1.name}, true")
                return ValueRef(LLVM_BOOL, r)
            return v
        
        # Soporte adicional para UnaryOp (si el parser lo usa)
        if isinstance(e, UnaryOp):
            v = self._gen_expr(e.expr, scope)
            if e.op == '!':
                as1 = self._as_i1(v)
                r = self.ir.tmp()
                self.ir.emit(f"  {r} = xor i1 {as1.name}, true")
                return ValueRef(LLVM_BOOL, r)
            elif e.op == '-':
                if v.ty == LLVM_FLOAT:
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = fsub double 0.0, {v.name}")
                    return ValueRef(v.ty, r)
                r = self.ir.tmp()
                self.ir.emit(f"  {r} = sub {v.ty} 0, {v.name}")
                return ValueRef(v.ty, r)
            return v

        # Operador postfijo (++/--)
        if isinstance(e, PostfixOper):
            if isinstance(e.expr, Identifier):
                slot = scope.get(e.expr.name)
                if slot is None:
                    llty, g = self.globals.get(e.expr.name, (LLVM_INT, None))
                    cur = self.ir.tmp()
                    self.ir.emit(f"  {cur} = load {llty}, {llty}* {g}")
                    nxt = self.ir.tmp()
                    op = "add" if e.oper == '++' else "sub"
                    self.ir.emit(f"  {nxt} = {op} {llty} {cur}, 1")
                    self.ir.emit(f"  store {llty} {nxt}, {llty}* {g}")
                    return ValueRef(llty, cur)
                else:
                    cur = self.ir.tmp()
                    self.ir.emit(f"  {cur} = load {slot.ty}, {slot.ty}* {slot.name}")
                    nxt = self.ir.tmp()
                    op = "add" if e.oper == '++' else "sub"
                    self.ir.emit(f"  {nxt} = {op} {slot.ty} {cur}, 1")
                    self.ir.emit(f"  store {slot.ty} {nxt}, {slot.ty}* {slot.name}")
                    return ValueRef(slot.ty, cur)

        # Operador binario
        if isinstance(e, BinOper):
            a = self._gen_expr(e.left, scope)
            b = self._gen_expr(e.right, scope)
            
            # Operaciones con float
            if a.ty == LLVM_FLOAT or b.ty == LLVM_FLOAT:
                if a.ty != LLVM_FLOAT:
                    ca = self.ir.tmp()
                    self.ir.emit(f"  {ca} = sitofp {a.ty} {a.name} to double")
                    a = ValueRef(LLVM_FLOAT, ca)
                if b.ty != LLVM_FLOAT:
                    cb = self.ir.tmp()
                    self.ir.emit(f"  {cb} = sitofp {b.ty} {b.name} to double")
                    b = ValueRef(LLVM_FLOAT, cb)
                
                opmap = {'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}
                if e.oper in opmap:
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = {opmap[e.oper]} double {a.name}, {b.name}")
                    return ValueRef(LLVM_FLOAT, r)
                
                cmpmap = {'==':'oeq','!=':'one','<':'olt','<=':'ole','>':'ogt','>=':'oge'}
                if e.oper in cmpmap:
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = fcmp {cmpmap[e.oper]} double {a.name}, {b.name}")
                    return ValueRef(LLVM_BOOL, r)
            
            # Operaciones con enteros
            else:
                if e.oper == '+':
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = add {a.ty} {a.name}, {b.name}")
                    return ValueRef(a.ty, r)
                if e.oper == '-':
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = sub {a.ty} {a.name}, {b.name}")
                    return ValueRef(a.ty, r)
                if e.oper == '*':
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = mul {a.ty} {a.name}, {b.name}")
                    return ValueRef(a.ty, r)
                if e.oper == '/':
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = sdiv {a.ty} {a.name}, {b.name}")
                    return ValueRef(a.ty, r)
                if e.oper == '%':
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = srem {a.ty} {a.name}, {b.name}")
                    return ValueRef(a.ty, r)
                
                cmpmap = {'==':'eq','!=':'ne','<':'slt','<=':'sle','>':'sgt','>=':'sge'}
                if e.oper in cmpmap:
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = icmp {cmpmap[e.oper]} {a.ty} {a.name}, {b.name}")
                    return ValueRef(LLVM_BOOL, r)
                
                if e.oper in ('&&','||'):
                    aa = self._as_i1(a)
                    bb = self._as_i1(b)
                    op = "and" if e.oper == '&&' else "or"
                    r = self.ir.tmp()
                    self.ir.emit(f"  {r} = {op} i1 {aa.name}, {bb.name}")
                    return ValueRef(LLVM_BOOL, r)

        return ValueRef(LLVM_INT, "0")

    def _string_global(self, s: str) -> str:
        key = f"@.str.{abs(hash(s)) & 0xFFFFFF:x}"
        for ln in self.ir.lines:
            if ln.startswith(f"{key} ="):
                return key

        bs = s.encode("utf-8")
        init = ", ".join(f"i8 {b}" for b in bs) + ", i8 0"
        line = f"{key} = private unnamed_addr constant [{len(bs)+1} x i8] [{init}]"

        insert_at = 0
        for j, ln in enumerate(self.ir.lines):
            if ln.startswith("@.fmt_") or ln.startswith("@.len."):
                insert_at = j + 1

        self.ir.lines.insert(insert_at, line)
        return key

    def _gen_print(self, v: ValueRef):
        if v.ty in (LLVM_INT, LLVM_BOOL):
            fmt = self.ir.tmp()
            self.ir.emit(f'  {fmt} = getelementptr inbounds [4 x i8], [4 x i8]* @.fmt_int, i32 0, i32 0')
            self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i32 {v.name})")
        elif v.ty == LLVM_CHAR:
            fmt = self.ir.tmp()
            self.ir.emit(f'  {fmt} = getelementptr inbounds [4 x i8], [4 x i8]* @.fmt_char, i32 0, i32 0')
            self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i8 {v.name})")
        elif v.ty == LLVM_FLOAT:
            fmt = self.ir.tmp()
            self.ir.emit(f'  {fmt} = getelementptr inbounds [4 x i8], [4 x i8]* @.fmt_float, i32 0, i32 0')
            self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, double {v.name})")
        elif v.ty == LLVM_STRING:
            fmt = self.ir.tmp()
            self.ir.emit(f'  {fmt} = getelementptr inbounds [4 x i8], [4 x i8]* @.fmt_str, i32 0, i32 0')
            self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i8* {v.name})")
        else:
            fmt = self.ir.tmp()
            self.ir.emit(f'  {fmt} = getelementptr inbounds [4 x i8], [4 x i8]* @.fmt_int, i32 0, i32 0')
            self.ir.emit(f"  call i32 (i8*, ...) @printf(i8* {fmt}, i32 {v.name})")

    def _gen_array_ptr(self, idx: ArrayIndex, scope: Scope) -> Tuple[str, str]:
        """Calcula el puntero base para acceder a un arreglo."""
        if isinstance(idx.array, Identifier):
            v = scope.get(idx.array.name)
            if v:
                # Array estático [N x T]
                if v.ty.startswith('['):
                    T = v.ty.split(' x ')[-1].rstrip(']')
                    baseptr = self.ir.tmp()
                    self.ir.emit(f"  {baseptr} = getelementptr inbounds {v.ty}, {v.ty}* {v.name}, i32 0, i32 0")
                    return baseptr, T
                # Puntero T*
                if v.ty.endswith('*'):
                    loaded = self.ir.tmp()
                    baseT  = v.ty[:-1]
                    self.ir.emit(f"  {loaded} = load {v.ty}, {v.ty}* {v.name}")
                    return loaded, baseT

            # Global [N x T]
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
        print("✓ Archivo out.ll generado con éxito.", file=sys.stderr)
    except Exception as e:
        print(f"✗ Error al escribir out.ll: {e}", file=sys.stderr)

sys.stdout.write(output_ir)
