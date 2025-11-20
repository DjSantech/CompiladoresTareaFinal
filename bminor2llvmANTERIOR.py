#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bminor2llvm.py — Genera LLVM IR (llvmlite) a partir del AST de B-Minor.

Suposiciones del proyecto (ajústalas a tus nombres reales):
- parser:  parse(text) -> Program
- checker: check(program) anota tipos/valida semántica
- AST mínimo (duck-typing):
  Program{decls:list}|Program{body:list}
  Function{name:str, params:list[VarDecl], ret_type:Type, body:Block}
  VarDecl{name:str, ty:Type, init:Expr|None, is_global:bool?}
  Block{stmts:list[Stmt]}
  If{cond:Expr, then:Block, else_:Block|None}
  While{cond:Expr, body:Block}
  Return{expr:Expr|None}
  Assign{target: Name|Index, value:Expr}
  Call{name:str, args:list[Expr]}  # o func:Identifier/Name con args
  Binary/BinOper{op:str, left:Expr, right:Expr}     # + - * / %
  Compare{op:str, left:Expr, right:Expr}            # < <= > >= == !=
  Unary/UnaryOper{op:str, expr:Expr}                # + -
  Name/Identifier{id:str|name:str}
  Index/ArrayIndex{base:Expr, index:Expr}           # a[i]
  IntLiteral/Literal{value:int}, BoolLiteral/Literal{value:bool}
  Type{kind:str, elem:Type|None}                    # 'int','bool','void','array'

Detalles IR:
- i32 para int; i1 para bool (se eleva a i32 al imprimir/printf).
- printf("%d\n") global, acceso con GEP [0,0].
- array(n) retorna i32* (puntero a elementos). Las variables arreglo se modelan con un
  slot local de tipo i32* (o T*); es decir, el slot en LLVM es i32** y se “storea” un i32*.
"""

from __future__ import annotations
import argparse
from typing import Any, Dict, List, Optional

# ===== Importa tus componentes =====
from parser import parse
from checker import check
# (Opcional) tokens, etc.
# from lexer import *   # si lo necesitas

from llvmlite import ir

I32 = ir.IntType(32)
I1  = ir.IntType(1)
I8  = ir.IntType(8)


class CompileError(Exception):
    pass


# ===== Utilidades de tipos =====

def is_int_type(ty: Any) -> bool:
    return getattr(ty, "kind", None) == "int"

def is_bool_type(ty: Any) -> bool:
    return getattr(ty, "kind", None) == "bool"

def is_void_type(ty: Any) -> bool:
    return getattr(ty, "kind", None) == "void"

def is_array_type(ty: Any) -> bool:
    return getattr(ty, "kind", None) == "array"

def ir_type_from_bminor(ty: Any) -> ir.Type:
    if ty is None:
        return ir.VoidType()
    if is_int_type(ty):
        return I32
    if is_bool_type(ty):
        return I1
    if is_array_type(ty):
        elem_ir = ir_type_from_bminor(getattr(ty, "elem", None))
        return elem_ir.as_pointer()       # array(T) → T*
    if is_void_type(ty):
        return ir.VoidType()
    # Por sencillez: si el objeto trae 'elem' asumimos pointer a elem
    if hasattr(ty, "elem"):
        return ir_type_from_bminor(getattr(ty, "elem")).as_pointer()
    raise CompileError(f"Tipo B-Minor no soportado: {ty}")


# ===== Contexto de función =====

class FunctionContext:
    def __init__(self, func: ir.Function, builder: ir.IRBuilder, printf: ir.Function, fmt_str: ir.GlobalVariable):
        self.func = func
        self.builder = builder
        self.printf = printf
        self.fmt_str = fmt_str
        # name -> alloca (slot). El slot siempre es un puntero a almacenamiento:
        #   - int/bool: i32*/i1*
        #   - arrays (variables que guardan punteros): i32** (slot que guarda un i32*)
        self.locals: Dict[str, ir.AllocaInstr] = {}
        # Bloque dedicado a allocas (para que mem2reg pueda elevar)
        self.allocas_bb = func.append_basic_block('entry_allocas')
        self.allocas_builder = ir.IRBuilder(self.allocas_bb)
        self.allocas_builder.branch(builder.block)

    def create_alloca(self, name: str, ty: ir.Type, count: Optional[ir.Value] = None):
        with self.allocas_builder.goto_block(self.allocas_bb):
            if count is None:
                return self.allocas_builder.alloca(ty, name=name)
            return self.allocas_builder.alloca(ty, count, name=name)

    def get_or_alloca(self, name: str, ty: ir.Type):
        """
        Crea o retorna el slot para 'name'. Si ya existe y el tipo no coincide,
        intentamos ser tolerantes en punteros (i32* vs cualquier T* → bitcast al almacenar).
        """
        slot = self.locals.get(name)
        if slot is None:
            slot = self.create_alloca(name, ty)
            self.locals[name] = slot
            return slot

        # Si ya existe, no forzar igualdad estricta. Dejamos que _store_compat haga bitcast.
        return slot


# ===== Compilador principal =====

class LLVMCompiler:
    def __init__(self):
        self.module = ir.Module(name="bminor_module")
        # printf: i32 (i8*, ...)
        self.printf_ty = ir.FunctionType(I32, [I8.as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, self.printf_ty, name="printf")
        # "%d\n\0"
        arr_t = ir.ArrayType(I8, 4)
        self.fmt_str = ir.GlobalVariable(self.module, arr_t, name="fmt_dnl")
        self.fmt_str.global_constant = True
        self.fmt_str.initializer = ir.Constant(arr_t, bytearray(b"%d\n\x00"))

        self.context: Optional[FunctionContext] = None
        self.functions: Dict[str, ir.Function] = {}
        self.has_top_level = False
        self.globals: Dict[str, ir.GlobalVariable] = {}

        # main implícito
        self._implicit_main_fn: Optional[ir.Function] = None

    # ---- helpers de conversión tipo/valor ----

    def _as_i32(self, v: ir.Value) -> ir.Value:
        # bool->i32, i32->i32
        if isinstance(v.type, ir.IntType) and v.type.width == 32:
            return v
        if isinstance(v.type, ir.IntType) and v.type.width == 1:
            return self.context.builder.zext(v, I32)
        raise CompileError(f"Se esperaba int/bool para i32, llegó {v.type}")

    def _as_i1(self, v: ir.Value) -> ir.Value:
        # i1->i1; i32->i1 (v!=0)
        if isinstance(v.type, ir.IntType) and v.type.width == 1:
            return v
        if isinstance(v.type, ir.IntType) and v.type.width == 32:
            return self.context.builder.icmp_unsigned('!=', v, ir.Constant(I32, 0))
        raise CompileError(f"Se esperaba int/bool para condición, llegó {v.type}")

    def _printf_i32(self, ival: ir.Value):
        b = self.context.builder
        fmt_ptr = b.gep(self.fmt_str, [ir.Constant(I32, 0), ir.Constant(I32, 0)], inbounds=True)
        b.call(self.printf, [fmt_ptr, self._as_i32(ival)])

    def _store_compat(self, value: ir.Value, slot: ir.AllocaInstr):
        """
        Guarda 'value' en 'slot' manejando:
          - enteros/bools (conversión a i32/i1 según slot)
          - punteros (bitcast si es necesario)
        """
        pointee = slot.type.pointee  # tipo del dato almacenado en el slot

        if isinstance(pointee, ir.IntType):
            # slot: i32* o i1*
            if isinstance(pointee, ir.IntType) and pointee.width == 1:
                # bool
                if isinstance(value.type, ir.IntType) and value.type.width == 1:
                    self.context.builder.store(value, slot)
                elif isinstance(value.type, ir.IntType) and value.type.width == 32:
                    v1 = self._as_i1(value)
                    self.context.builder.store(v1, slot)
                else:
                    raise CompileError(f"No puedo guardar {value.type} en bool")
            else:
                # i32
                if isinstance(value.type, ir.IntType):
                    v32 = self._as_i32(value)
                    self.context.builder.store(v32, slot)
                else:
                    raise CompileError(f"No puedo guardar {value.type} en int")
            return

        if isinstance(pointee, ir.PointerType):
            # slot: T**  (e.g., i32** para variables arreglo)
            if isinstance(value.type, ir.PointerType):
                # value: U*
                if value.type != pointee:
                    vcast = self.context.builder.bitcast(value, pointee)
                    self.context.builder.store(vcast, slot)
                else:
                    self.context.builder.store(value, slot)
                return
            raise CompileError(f"No puedo guardar {value.type} en {pointee}")

        # Otros casos no contemplados
        raise CompileError(f"Slot pointee no soportado: {pointee}")

    # ---- API pública ----

    def _iter_program_decls(self, program: Any) -> List[Any]:
        if hasattr(program, "decls"):
            return list(getattr(program, "decls"))
        if hasattr(program, "body"):
            return list(getattr(program, "body"))
        return []

    def compile_program(self, program: Any) -> str:
        decls = self._iter_program_decls(program)

        # 1) declarar funciones + globales
        for d in decls:
            if self._is_func(d):
                self._declare_function(d)
            elif self._is_global_vardecl(d):
                self._declare_global(d)

        # 2) sintetizar main si hace falta
        if self.has_top_level or 'main' not in self.functions:
            self._declare_implicit_main()

        # 3) definir funciones / inicializar globales no const / emitir top-level
        for d in decls:
            if self._is_func(d):
                self._define_function(d)
            elif self._is_global_vardecl(d):
                self._init_global_if_needed(d)
            else:
                self._emit_in_implicit_main(d)

        # 4) cerrar main implícito
        self._finish_implicit_main()

        return str(self.module)

    # ---- reconocimiento de nodos ----

    def _is_func(self, node: Any) -> bool:
        return hasattr(node, "body") and hasattr(node, "params") and hasattr(node, "name")

    def _is_vardecl(self, node: Any) -> bool:
        return hasattr(node, "name") and (hasattr(node, "ty") or hasattr(node, "type")) and hasattr(node, "init")

    def _is_global_vardecl(self, node: Any) -> bool:
        return self._is_vardecl(node) and bool(getattr(node, "is_global", True))

    # ---- declaraciones ----

    def _declare_function(self, f: Any):
        ret_ty = getattr(f, "ret_type", None)
        ret_ir = ir_type_from_bminor(ret_ty)
        # Elevamos bool de retorno a i32 por simplicidad C-like
        if isinstance(ret_ir, ir.IntType) and ret_ir.width == 1:
            ret_ir = I32

        arg_tys: List[ir.Type] = []
        params = getattr(f, "params", [])
        for p in params:
            p_ty = getattr(p, "ty", getattr(p, "type", None))
            p_ir = ir_type_from_bminor(p_ty)
            # Para llamadas, si es i1 lo pasamos como i32
            if isinstance(p_ir, ir.IntType) and p_ir.width == 1:
                p_ir = I32
            arg_tys.append(p_ir)

        fnty = ir.FunctionType(ret_ir if not isinstance(ret_ir, ir.VoidType) else ir.VoidType(), arg_tys)
        fn = ir.Function(self.module, fnty, name=f.name)
        for i, p in enumerate(params):
            fn.args[i].name = getattr(p, "name", getattr(p, "id", f"arg{i}"))
        self.functions[f.name] = fn

    def _declare_global(self, v: Any):
        # Soportamos int/bool globals (no arreglos a puntero directo)
        vty = getattr(v, "ty", getattr(v, "type", None))
        ty_ir = ir_type_from_bminor(vty)
        if isinstance(ty_ir, ir.PointerType):
            # Globals array como puntero no inicializado → manejar por código en main
            gv = ir.GlobalVariable(self.module, ty_ir, name=v.name)
            gv.linkage = 'common'
            self.globals[v.name] = gv
            return
        gv = ir.GlobalVariable(self.module, ty_ir, name=v.name)
        gv.linkage = 'common'
        if isinstance(ty_ir, ir.IntType):
            gv.initializer = ir.Constant(ty_ir, 0)
        self.globals[v.name] = gv

    def _init_global_if_needed(self, v: Any):
        init = getattr(v, "init", None)
        if init is None:
            return
        g = self.globals.get(v.name)
        if g is None:
            return
        # Solo literales simples en globales (sino, se hace en main implícito)
        if self._is_int_lit(init):
            if isinstance(g.type.pointee, ir.IntType) and g.type.pointee.width == 1:
                g.initializer = ir.Constant(I1, 1 if int(init.value) != 0 else 0)
            else:
                g.initializer = ir.Constant(I32, int(init.value))
        elif self._is_bool_lit(init):
            if isinstance(g.type.pointee, ir.IntType) and g.type.pointee.width == 1:
                g.initializer = ir.Constant(I1, 1 if init.value else 0)
            else:
                g.initializer = ir.Constant(I32, 1 if init.value else 0)
        else:
            self.has_top_level = True
            pend = getattr(self, "_emit_pending_global_assign", [])
            pend.append(v)
            self._emit_pending_global_assign = pend

    def _declare_implicit_main(self):
        if 'main' in self.functions:
            # Creamos contexto de main real cuando lo definamos
            return
        fnty = ir.FunctionType(I32, [])
        fn = ir.Function(self.module, fnty, name="main")
        self.functions['main'] = fn
        self._implicit_main_fn = fn
        entry = fn.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        self.context = FunctionContext(fn, builder, self.printf, self.fmt_str)
        body = fn.append_basic_block('toplevel')
        builder.branch(body)
        self.context.builder = ir.IRBuilder(body)

    def _finish_implicit_main(self):
        if self._implicit_main_fn is None:
            return
        if self.context and self.context.func is self._implicit_main_fn and not self.context.builder.block.is_terminated:
            pend = getattr(self, "_emit_pending_global_assign", [])
            for v in pend:
                g = self.globals[v.name]
                val = self._as_i32(self._eval_expr(v.init))
                if isinstance(g.type.pointee, ir.IntType) and g.type.pointee.width == 1:
                    val = self._as_i1(val)
                self.context.builder.store(val, g)
            self.context.builder.ret(ir.Constant(I32, 0))
            self.context = None
            self._implicit_main_fn = None

    def _emit_in_implicit_main(self, node: Any):
        if self._implicit_main_fn is None:
            return
        if not self.context or self.context.func is not self._implicit_main_fn:
            return
        self.has_top_level = True
        self._emit_stmt(node)

    # ---- definición de función ----

    def _define_function(self, f: Any):
        fn = self.functions[f.name]
        entry = fn.append_basic_block('entry')
        entry_builder = ir.IRBuilder(entry)
        prev_ctx = self.context
        ctx = FunctionContext(fn, entry_builder, self.printf, self.fmt_str)
        body = fn.append_basic_block('body')
        entry_builder.branch(body)
        ctx.builder = ir.IRBuilder(body)
        self.context = ctx

        # params → locales (guardamos como i32 o puntero, según tipo IR del arg)
        for a in fn.args:
            aty = a.type
            slot = ctx.get_or_alloca(a.name, aty)  # slot de tipo 'aty*'
            # Para guardar el valor del argumento, el slot real debe ser puntero a 'aty'
            # get_or_alloca creó alloca(aty) → devuelve aty*, correcto
            ctx.builder.store(a, slot)

        # declara locales para VarDecl (solo reserva; init después)
        for st in getattr(f.body, "stmts", []):
            if self._is_vardecl(st) and not getattr(st, "is_global", False):
                self._declare_local(st)

        # emite cuerpo
        for st in getattr(f.body, "stmts", []):
            self._emit_stmt(st)

        # asegurar retorno
        if not ctx.builder.block.is_terminated:
            if isinstance(fn.function_type.return_type, ir.VoidType):
                ctx.builder.ret_void()
            else:
                ctx.builder.ret(ir.Constant(I32, 0))

        self.context = prev_ctx

    def _declare_local(self, v: Any):
        vty = getattr(v, "ty", getattr(v, "type", None))
        ty_ir = ir_type_from_bminor(vty)

        # Si la variable es "arreglo" (representado como puntero a elemento),
        # el slot debe ser de tipo (T*)*, o sea, i32** si elem es i32.
        if isinstance(ty_ir, ir.PointerType):
            slot = self.context.get_or_alloca(v.name, ty_ir.as_pointer())
            if v.init is not None:
                # Soportar init con array(n) → devuelve i32*; guardarlo en el i32**
                arr_ptr = self._eval_array_builtin_from_init(v.init)
                self._store_compat(arr_ptr, slot)
            return

        # Escalares
        slot = self.context.get_or_alloca(v.name, ty_ir)
        if v.init is not None:
            val = self._eval_expr(v.init)
            self._store_compat(val, slot)

    # ---- Statements ----

    def _emit_stmt(self, st: Any):
        # VarDecl locales ya reservadas en _declare_local
        if self._is_vardecl(st) and not getattr(st, "is_global", False):
            return

        # If (tiene cond y then; y opcional else_)
        if hasattr(st, "cond") and hasattr(st, "then") and hasattr(st, "else_"):
            self._emit_if(st); return

        # While (cond y body, sin else_)
        if hasattr(st, "cond") and hasattr(st, "body") and not hasattr(st, "else_"):
            self._emit_while(st); return

        # Return
        if hasattr(st, "expr") and type(st).__name__ in ("Return", "ReturnStmt"):
            self._emit_return(st); return

        # Assign
        if hasattr(st, "target") and hasattr(st, "value"):
            self._emit_assign(st); return

        # Expresión suelta (Call, etc.)
        if hasattr(st, "op") or hasattr(st, "name") or hasattr(st, "args"):
            _ = self._eval_expr(st); return

        # Block
        if hasattr(st, "stmts"):
            for s in getattr(st, "stmts", []):
                self._emit_stmt(s)
            return

    def _emit_if(self, node: Any):
        b = self.context.builder
        func = self.context.func
        then_bb = func.append_basic_block('then')
        else_bb = func.append_basic_block('else')
        cont_bb = func.append_basic_block('endif')

        cond = self._as_i1(self._as_i32(self._eval_expr(node.cond)))
        b.cbranch(cond, then_bb, else_bb)

        b.position_at_end(then_bb)
        self._emit_stmt(node.then)
        if not b.block.is_terminated:
            b.branch(cont_bb)

        b.position_at_end(else_bb)
        if getattr(node, "else_", None):
            self._emit_stmt(node.else_)
        if not b.block.is_terminated:
            b.branch(cont_bb)

        b.position_at_end(cont_bb)

    def _emit_while(self, node: Any):
        b = self.context.builder
        func = self.context.func
        test_bb = func.append_basic_block('while_test')
        body_bb = func.append_basic_block('while_body')
        done_bb = func.append_basic_block('while_done')

        b.branch(test_bb)

        b.position_at_end(test_bb)
        cond = self._as_i1(self._as_i32(self._eval_expr(node.cond)))
        b.cbranch(cond, body_bb, done_bb)

        b.position_at_end(body_bb)
        self._emit_stmt(node.body)
        if not b.block.is_terminated:
            b.branch(test_bb)

        b.position_at_end(done_bb)

    def _emit_return(self, node: Any):
        if node.expr is None:
            if isinstance(self.context.func.function_type.return_type, ir.VoidType):
                self.context.builder.ret_void()
            else:
                self.context.builder.ret(ir.Constant(I32, 0))
            return
        v = self._eval_expr(node.expr)
        ret_ty = self.context.func.function_type.return_type
        if isinstance(ret_ty, ir.IntType) and ret_ty.width == 1:
            v = self._as_i1(self._as_i32(v))
            self.context.builder.ret(v)
        elif isinstance(ret_ty, ir.IntType) and ret_ty.width == 32:
            self.context.builder.ret(self._as_i32(v))
        elif isinstance(ret_ty, ir.VoidType):
            self.context.builder.ret_void()
        else:
            raise CompileError(f"Tipo de retorno no soportado: {ret_ty}")

    def _emit_assign(self, node: Any):
        val = self._eval_expr(node.value)
        tgt = node.target

        # Nombre simple: Name/Identifier
        idname = None
        if hasattr(tgt, "id"):
            idname = tgt.id
        elif hasattr(tgt, "name"):
            idname = tgt.name

        if idname is not None:
            # ¿local?
            slot = self.context.locals.get(idname)
            # ¿global?
            if slot is None and idname in self.globals:
                g = self.globals[idname]
                # g: puntero a tipo del global (i32*/i1*/T*)
                # almacenamos valor compatible
                if isinstance(g.type.pointee, ir.PointerType):
                    # global puntero → espera U*, val debe ser puntero
                    if not isinstance(val.type, ir.PointerType):
                        raise CompileError(f"Asignación incompatible a global puntero '{idname}'")
                    vcast = val
                    if val.type != g.type.pointee:
                        vcast = self.context.builder.bitcast(val, g.type.pointee)
                    self.context.builder.store(vcast, g)
                elif isinstance(g.type.pointee, ir.IntType):
                    # escalar
                    vfinal = self._as_i32(val)
                    if g.type.pointee.width == 1:
                        vfinal = self._as_i1(vfinal)
                    self.context.builder.store(vfinal, g)
                else:
                    raise CompileError("Global no soportado")
                return

            # si no existe local, créalo “on-the-fly” como i32 (escalares) o como puntero si RHS es puntero
            if slot is None:
                if isinstance(val.type, ir.PointerType):
                    # variable arreglo no declarada antes → crear slot i32** y guardar i32*
                    slot = self.context.get_or_alloca(idname, val.type.as_pointer())
                else:
                    slot = self.context.get_or_alloca(idname, I32)

            # guardar con compatibilidad
            self._store_compat(val, slot)
            return

        # Index: a[i] = v
        if hasattr(tgt, "base") and hasattr(tgt, "index"):
            base_ptr = self._array_base_ptr(tgt.base)      # i32*
            idx = self._as_i32(self._eval_expr(tgt.index))
            elem_ptr = self.context.builder.gep(base_ptr, [idx], inbounds=True)
            self.context.builder.store(self._as_i32(val), elem_ptr)
            return

        raise CompileError("Asignación no soportada")

    # ---- Expresiones ----

    def _eval_expr(self, e: Any) -> ir.Value:
        # Literales
        if self._is_int_lit(e):
            return ir.Constant(I32, int(getattr(e, "value")))
        if self._is_bool_lit(e):
            return ir.Constant(I1, 1 if getattr(e, "value") else 0)

        # Name / Identifier
        if hasattr(e, "id") or hasattr(e, "name"):
            nm = getattr(e, "id", getattr(e, "name", None))
            # local
            slot = self.context.locals.get(nm)
            if slot is not None:
                return self.context.builder.load(slot, name=nm + "_val")
            # global
            if nm in self.globals:
                g = self.globals[nm]
                return self.context.builder.load(g, name=nm + "_gval")
            # si no existe, créalo escalar i32 implícito
            slot = self.context.get_or_alloca(nm, I32)
            return self.context.builder.load(slot, name=nm + "_val")

        # Index: a[i]
        if hasattr(e, "base") and hasattr(e, "index"):
            base_ptr = self._array_base_ptr(e.base)  # i32*
            idx = self._as_i32(self._eval_expr(e.index))
            elem_ptr = self.context.builder.gep(base_ptr, [idx], inbounds=True)
            return self.context.builder.load(elem_ptr, name="elem")

        # Unary (+/-)
        if hasattr(e, "op") and hasattr(e, "expr") and not hasattr(e, "left"):
            v = self._as_i32(self._eval_expr(e.expr))
            if e.op == '+':
                return v
            if e.op == '-':
                return self.context.builder.sub(ir.Constant(I32, 0), v, name="neg")
            raise CompileError(f"Unario no soportado: {e.op}")

        # Binary (+ - * / %)
        if hasattr(e, "op") and hasattr(e, "left") and hasattr(e, "right") and e.op not in ('<','<=','>','>=','==','!='):
            lhs = self._as_i32(self._eval_expr(e.left))
            rhs = self._as_i32(self._eval_expr(e.right))
            b = self.context.builder
            if e.op == '+':  return b.add(lhs, rhs, name="add")
            if e.op == '-':  return b.sub(lhs, rhs, name="sub")
            if e.op == '*':  return b.mul(lhs, rhs, name="mul")
            if e.op == '/':  return b.sdiv(lhs, rhs, name="sdiv")
            if e.op == '%':  return b.srem(lhs, rhs, name="srem")
            raise CompileError(f"Binario no soportado: {e.op}")

        # Compare (< <= > >= == !=)
        if hasattr(e, "op") and e.op in ('<','<=','>','>=','==','!='):
            lhs = self._as_i32(self._eval_expr(getattr(e, "left")))
            rhs = self._as_i32(self._eval_expr(getattr(e, "right")))
            pred = e.op
            return self.context.builder.icmp_signed(pred, lhs, rhs, name="cmp")

        # Call
        if hasattr(e, "name") and hasattr(e, "args"):
            if e.name == "print":
                if len(e.args) != 1:
                    raise CompileError("print(expr) espera 1 argumento")
                val = self._eval_expr(e.args[0])
                self._printf_i32(val)
                return ir.Constant(I32, 0)
            if e.name == "array":
                if len(e.args) != 1:
                    raise CompileError("array(n) espera 1 argumento")
                return self._eval_array_builtin(e.args[0])

            if e.name not in self.functions:
                raise CompileError(f"Función desconocida '{e.name}'")
            fn = self.functions[e.name]
            args = [self._as_i32(self._eval_expr(a)) for a in e.args]
            return self.context.builder.call(fn, args, name="call_"+e.name)

        # Call con func:Identifier/Name
        if hasattr(e, "func") and hasattr(e, "args"):
            # built-in array(n)
            if hasattr(e.func, "name") and getattr(e.func, "name") == "array":
                if len(e.args) != 1:
                    raise CompileError("array(n) espera 1 argumento")
                return self._eval_array_builtin(e.args[0])
            # built-in print(...)
            if hasattr(e.func, "name") and getattr(e.func, "name") == "print":
                if len(e.args) != 1:
                    raise CompileError("print(expr) espera 1 argumento")
                val = self._eval_expr(e.args[0])
                self._printf_i32(val)
                return ir.Constant(I32, 0)

            # usuario
            fname = getattr(e.func, "name", getattr(e.func, "id", None))
            if fname not in self.functions:
                raise CompileError(f"Función desconocida '{fname}'")
            fn = self.functions[fname]
            args = [self._as_i32(self._eval_expr(a)) for a in e.args]
            return self.context.builder.call(fn, args, name="call_"+fname)

        # Block como expresión (devuelve 0)
        if hasattr(e, "stmts"):
            for s in getattr(e, "stmts", []):
                self._emit_stmt(s)
            return ir.Constant(I32, 0)

        raise CompileError(f"Expr no soportada: {type(e).__name__}")

    # ---- arrays ----

    def _eval_array_builtin_from_init(self, init_expr: Any) -> ir.Value:
        """
        Permite inicializar variables arreglo con:
          a: array[n] int; a = array(n);
        donde 'init_expr' es típicamente Call(func=Identifier('array'), args=[n]).
        """
        # Si ya viene como Call('array', [n]) úsalo; si no, evalúa como expr normal.
        if hasattr(init_expr, "name") and getattr(init_expr, "name") == "array" and hasattr(init_expr, "args"):
            return self._eval_array_builtin(init_expr.args[0])
        if hasattr(init_expr, "func") and hasattr(init_expr.func, "name") and init_expr.func.name == "array":
            if len(init_expr.args) != 1:
                raise CompileError("array(n) espera 1 argumento")
            return self._eval_array_builtin(init_expr.args[0])
        # Si no es la forma esperada, evalúa y espera i32*
        val = self._eval_expr(init_expr)
        if not isinstance(val.type, ir.PointerType):
            raise CompileError("Inicialización de arreglo requiere puntero (array(n))")
        return val

    def _eval_array_builtin(self, n_expr: Any) -> ir.Value:
        """
        array(n): reserva 'n' elementos i32 como alloca dinámica → i32*
        """
        n_i32 = self._as_i32(self._eval_expr(n_expr))
        # alloca i32, n  -> i32*
        return self.context.create_alloca('arr', I32, count=n_i32)

    def _array_base_ptr(self, base_expr: Any) -> ir.Value:
        """
        Devuelve el i32* almacenado en la variable arreglo 'a'.
        Es decir, carga desde el slot i32** para obtener i32*.
        """
        # base debe ser Name/Identifier
        nm = getattr(base_expr, "id", getattr(base_expr, "name", None))
        if nm is None:
            raise CompileError("Indexación soporta solo identificador simple como base")

        slot = self.context.locals.get(nm)
        if slot is None:
            # Si no existe, crea un slot i32** y espera futura asignación a array(n)
            slot = self.context.get_or_alloca(nm, I32.as_pointer().as_pointer())

        # slot: i32** → load → i32*
        ptr = self.context.builder.load(slot, name=nm + "_ptr")
        if not isinstance(ptr.type, ir.PointerType) or not isinstance(ptr.type.pointee, ir.IntType):
            # Aceptamos cualquier T*, pero si no es i32*, hacemos bitcast a i32*
            if isinstance(ptr.type, ir.PointerType):
                ptr = self.context.builder.bitcast(ptr, I32.as_pointer())
            else:
                raise CompileError("Base de arreglo no es puntero")
        return ptr

    # ---- detectores de literales ----

    def _is_int_lit(self, node: Any) -> bool:
        return (type(node).__name__ in ("IntLiteral", "Integer")
                or (hasattr(node, "value") and isinstance(getattr(node, "value"), int)))

    def _is_bool_lit(self, node: Any) -> bool:
        return (type(node).__name__ in ("BoolLiteral",)
                or (hasattr(node, "value") and isinstance(getattr(node, "value"), bool)))


# ===== CLI =====

def _dump_ast(program: Any):
    """
    Impresión muy simple del AST por introspección, por si tu modelo no trae .dump().
    """
    from collections import deque

    def node_label(x):
        tn = type(x).__name__
        if hasattr(x, "name"):
            return f"{tn}({getattr(x,'name')})"
        if hasattr(x, "id"):
            return f"{tn}({getattr(x,'id')})"
        if hasattr(x, "value"):
            return f"{tn}({getattr(x,'value')})"
        return tn

    q = deque([(program, 0)])
    lines = []
    while q:
        n, d = q.popleft()
        lines.append("  " * d + node_label(n))
        # hijos aproximados
        for attr in ("decls", "body", "stmts", "params", "args"):
            if hasattr(n, attr):
                lst = getattr(n, attr) or []
                for ch in lst:
                    if hasattr(ch, "__dict__"):
                        q.append((ch, d + 1))
        for attr in ("then", "else_", "cond", "expr", "left", "right", "base", "index", "init", "type", "ty", "ret_type", "func"):
            if hasattr(n, attr):
                ch = getattr(n, attr)
                if ch is not None and hasattr(ch, "__dict__"):
                    q.append((ch, d + 1))
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="Archivo .bminor")
    ap.add_argument("--no-sema", action="store_true", help="No ejecutar checker semántico.")
    ap.add_argument("--parser", default=None, help="Ruta módulo parser (p.ej. pkg.parser_mod).")
    ap.add_argument("--checker", default=None, help="Ruta módulo checker (p.ej. pkg.checker_mod).")
    ap.add_argument("--dump-ast", action="store_true", help="Imprime un volcado simple del AST y sale.")
    args = ap.parse_args()

    # Carga dinámica si se pasa por CLI
    global parse, check
    if args.parser:
        mod = __import__(args.parser, fromlist=['*'])
        parse = getattr(mod, "parse")
    if args.checker:
        mod = __import__(args.checker, fromlist=['*'])
        check = getattr(mod, "check")

    if parse is None:
        raise SystemExit("Debes proveer un parser válido (argumento --parser o modifica los imports).")

    with open(args.source, "r", encoding="utf-8") as f:
        src = f.read()

    program = parse(src)

    if args.dump_ast:
        try:
            # Si tu Program tiene .dump(), úsalo
            if hasattr(program, "dump"):
                program.dump()
            else:
                _dump_ast(program)
        except Exception:
            _dump_ast(program)
        return

    if check is not None and not args.no_sema:
        check(program)

    comp = LLVMCompiler()
    ir_txt = comp.compile_program(program)
    print(ir_txt)


if __name__ == "__main__":
    main()
