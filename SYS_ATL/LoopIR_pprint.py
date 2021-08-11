import re
import textwrap
from collections import ChainMap

from .prelude import *
from .LoopIR import UAST, front_ops, LoopIR
from .LoopIR_effects import Effects as E
from .LoopIR import T

# google python formatting project
# to save myself the trouble of being overly clever
from yapf.yapflib.yapf_api import FormatCode
# run the function FormatCode to transform
# one string into a formatted string

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
#   Notes on Layout Schemes...

"""
  functions should return a list of strings, one for each line

  standard inputs
  tab     - holds a string of white-space
  prec    - the operator precedence of the surrounding text
            if this string contains a lower precedence operation then
            we must wrap it in parentheses.
"""

# We expect pprint to install functions on the IR rather than
# expose functions; therefore hide all variables as local
__all__ = []


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Operator Precedence

op_prec = {
    "or":     10,
    #
    "and":    20,
    #
    "<":      30,
    ">":      30,
    "<=":     30,
    ">=":     30,
    "==":     30,
    #
    "+":      40,
    "-":      40,
    #
    "*":      50,
    "/":      50,
    "%":      50,
    #
    # unary minus
    "~":      60,
}

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# UAST Pretty Printing


@extclass(UAST.proc)
@extclass(UAST.fnarg)
@extclass(UAST.stmt)
@extclass(UAST.expr)
@extclass(UAST.type)
@extclass(UAST.w_access)
def __str__(self):
    return UAST_PPrinter(self).str()
del __str__


class UAST_PPrinter:
    def __init__(self, node):
        self._node = node

        self.env = ChainMap()
        self._tab = ""
        self._lines = []

        if isinstance(node, UAST.proc):
            self.pproc(node)
        elif isinstance(node, UAST.fnarg):
            self.addline(self.pfnarg(node))
        elif isinstance(node, UAST.stmt):
            self.pstmts([node])
        elif isinstance(node, UAST.expr):
            self.addline(self.pexpr(node))
        elif isinstance(node, UAST.type):
            self.addline(self.ptype(node))
        elif isinstance(node, UAST.w_access):
            if type(node) is UAST.Interval:
                lo = self.pexpr(node.lo) if node.lo else "None"
                hi = self.pexpr(node.hi) if node.hi else "None"
                self.addline(f"Interval({lo},{hi})")
            elif type(node) is UAST.Point:
                self.addline(f"Point({self.pexpr(node.pt)})")
            else: assert False, "bad case"
        else:
            assert False, f"cannot print a {type(node)}"

    def str(self):
        if (isinstance(self._node, UAST.type) or
            isinstance(self._node, UAST.w_access)):
            assert len(self._lines) == 1
            return self._lines[0]

        fmtstr, linted = FormatCode("\n".join(self._lines))
        if isinstance(self._node, LoopIR.proc):
            assert linted, "generated unlinted code..."
        return fmtstr

    def push(self,only=None):
        if only is None:
            self.env.new_child()
            self._tab = self._tab + "  "
        elif only == 'env':
            self.env.new_child()
        elif only == 'tab':
            self._tab = self._tab + "  "
        else:
            assert False, f"BAD only parameter {only}"

    def pop(self):
        self.env.parents
        self._tab = self._tab[:-2]

    def addline(self, line):
        self._lines.append(f"{self._tab}{line}")

    def new_name(self, nm):
        strnm   = str(nm)
        if strnm not in self.env:
            self.env[strnm] = strnm
            return strnm
        else:
            s = self.env[strnm]
            m = re.match('^(.*)_([0-9]*)$', s)
            # either post-pend a _1 or increment the post-pended counter
            if not m:
                s = s + "_1"
            else:
                s = f"{m[1]}_{int(m[2]) + 1}"
            self.env[strnm] = s
            return s

    def get_name(self, nm):
        strnm = str(nm)
        if strnm in self.env:
            return self.env[strnm]
        else:
            return repr(nm)

    def pproc(self, p):
        name = p.name or "_anon_"
        args = [ self.pfnarg(a) for a in p.args ]
        self.addline(f"def {name}({','.join(args)}):")

        self.push()
        if p.instr:
            instr_lines = p.instr.split('\n')
            instr_lines = ([f'# @instr {instr_lines[0]}']+
                           [f'#        {l}' for l in instr_lines[1:] ])
            for l in instr_lines:
                self.addline(l)
        for pred in p.preds:
            self.addline(f"assert {self.pexpr(pred)}")
        self.pstmts(p.body)
        self.pop()

    def pfnarg(self, a):
        mem = f" @{a.mem.name()}" if a.mem else ""
        return f"{self.new_name(a.name)} : {a.type}{mem}"

    def pstmts(self, body):
        for stmt in body:
            if type(stmt) is UAST.Pass:
                self.addline("pass")
            elif type(stmt) is UAST.Assign or type(stmt) is UAST.Reduce:
                op = "=" if type(stmt) is UAST.Assign else "+="

                rhs = self.pexpr(stmt.rhs)

                if len(stmt.idx) > 0:
                    idx = [self.pexpr(e) for e in stmt.idx]
                    lhs = f"{self.get_name(stmt.name)}[{','.join(idx)}]"
                else:
                    lhs = self.get_name(stmt.name)

                self.addline(f"{lhs} {op} {rhs}")
            elif type(stmt) is LoopIR.WriteConfig:
                cname   = stmt.config.name()
                rhs     = self.pexpr(stmt.rhs)
                self.addline(f"{cname}.{stmt.field} = {rhs}")
            elif type(stmt) is UAST.FreshAssign:
                rhs = self.pexpr(stmt.rhs)
                self.addline(f"{self.new_name(stmt.name)} = {rhs}")
            elif type(stmt) is UAST.Alloc:
                mem = f" @{stmt.mem.name()}" if stmt.mem else ""
                self.addline(f"{self.new_name(stmt.name)} : {stmt.type}{mem}")
            elif type(stmt) is UAST.Call:
                pname   = stmt.f.name or "_anon_"
                args    = [ self.pexpr(a) for a in p.args ]
                self.addline(f"{pname}({','.join(args)})")
            elif type(stmt) is UAST.If:
                cond = self.pexpr(stmt.cond)
                self.addline(f"if {cond}:")
                self.push()
                self.pstmts(stmt.body)
                self.pop()
                if len(stmt.orelse) > 0:
                    self.addline("else:")
                    self.push()
                    self.pstmts(stmt.orelse)
                    self.pop()
            elif type(stmt) is UAST.ForAll:
                cond = self.pexpr(stmt.cond)
                self.push(only='env')
                self.addline(f"for {self.new_name(stmt.iter)} in {cond}:")
                self.push(only='tab')
                self.pstmts(stmt.body)
                self.pop()
            else:
                assert False, "unrecognized stmt type"

    def pexpr(self, e, prec=0):
        if type(e) is UAST.Read:
            if len(e.idx) > 0:
                idx = [self.pexpr(i) for i in e.idx]
                return f"{self.get_name(e.name)}[{','.join(idx)}]"
            else:
                return self.get_name(e.name)
        elif type(e) is UAST.Const:
            return str(e.val)
        elif type(e) is UAST.BinOp:
            local_prec = op_prec[e.op]
            # increment rhs by 1 to account for left-associativity
            lhs = self.pexpr(e.lhs, prec=local_prec)
            rhs = self.pexpr(e.rhs, prec=local_prec+1)
            s = f"{lhs} {e.op} {rhs}"
            # if we have a lower precedence than the environment...
            if local_prec < prec:
                s = f"({s})"
            return s
        elif type(e) is UAST.USub:
            return f"-{self.pexpr(e.arg,prec=op_prec['~'])}"
        elif type(e) is UAST.ParRange:
            return f"par({self.pexpr(e.lo)},{self.pexpr(e.hi)})"
        elif type(e) is UAST.WindowExpr:
            def pacc(w):
                if type(w) is UAST.Point:
                    return self.pexpr(w.pt)
                elif type(w) is UAST.Interval:
                    lo = self.pexpr(w.lo) if w.lo else ""
                    hi = self.pexpr(w.hi) if w.hi else ""
                    return f"{lo}:{hi}"
                else: assert False, "bad case"
            return (f"{self.get_name(e.name)}"+
                    f"[{', '.join([ pacc(w) for w in e.idx ])}]")
        elif type(e) is UAST.StrideExpr:
            return f"stride({self.get_name(e.name)}, {e.dim})"
        elif type(e) is UAST.BuiltIn:
            pname   = e.f.name() or "_anon_"
            args    = [ self.pexpr(a) for a in e.args ]
            return f"{pname}({','.join(args)})"
        elif type(e) is LoopIR.ReadConfig:
            cname   = e.config.name()
            return f"{cname}.{e.field}"
        else:
            assert False, "unrecognized expr type"

    def ptype(self, t):
        if type(t) is UAST.Num:
            return "R"
        elif type(t) is UAST.F32:
            return "f32"
        elif type(t) is UAST.F64:
            return "f64"
        elif type(t) is UAST.INT8:
            return "i8"
        elif type(t) is UAST.INT32:
            return "i32"
        elif type(t) is UAST.Bool:
            return "bool"
        elif type(t) is UAST.Int:
            return "int"
        elif type(t) is UAST.Index:
            return "index"
        elif type(t) is UAST.Tensor:
            base = str(t.basetype())
            if t.is_window:
                base = f"[{base}]"
            rngs = ",".join([self.pexpr(r) for r in t.shape()])
            return f"{base}[{rngs}]"
        else:
            assert False, "impossible type case"

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# LoopIR Pretty Printing

@extclass(LoopIR.proc)
@extclass(LoopIR.fnarg)
@extclass(LoopIR.stmt)
@extclass(LoopIR.expr)
@extclass(LoopIR.type)
def __str__(self):
    return LoopIR_PPrinter(self).str()
del __str__


class LoopIR_PPrinter:
    def __init__(self, node):
        self._node = node

        self.env = ChainMap()
        self._tab = ""
        self._lines = []

        if isinstance(node, LoopIR.proc):
            self.pproc(node)
        elif isinstance(node, LoopIR.fnarg):
            self.addline(self.pfnarg(node))
        elif isinstance(node, LoopIR.stmt):
            self.pstmt(node)
        elif isinstance(node, LoopIR.expr):
            self.addline(self.pexpr(node))
        elif isinstance(node, LoopIR.type):
            self.addline(self.ptype(node))
        elif isinstance(node, LoopIR.w_access):
            if type(node) is LoopIR.Interval:
                self.addline(f"Interval({self.pexpr(node.lo)},"+
                             f"{self.pexpr(node.hi)})")
            elif type(node) is LoopIR.Point:
                self.addline(f"Point({self.pexpr(node.pt)})")
            else: assert False, "bad case"
        else:
            assert False, f"cannot print a {type(node)}"

    def str(self):
        if (isinstance(self._node, LoopIR.type) or
            isinstance(self._node, LoopIR.w_access)):
            assert len(self._lines) == 1
            return self._lines[0]

        fmtstr, linted = FormatCode("\n".join(self._lines))
        if isinstance(self._node, LoopIR.proc):
            assert linted, "generated unlinted code..."
        return fmtstr

    def push(self,only=None):
        if only is None:
            self.env.new_child()
            self._tab = self._tab + "  "
        elif only == 'env':
            self.env.new_child()
        elif only == 'tab':
            self._tab = self._tab + "  "
        else:
            assert False, f"BAD only parameter {only}"

    def pop(self):
        self.env.parents
        self._tab = self._tab[:-2]

    def addline(self, line):
        self._lines.append(f"{self._tab}{line}")

    def new_name(self, nm):
        strnm   = str(nm)
        if strnm not in self.env:
            self.env[strnm] = strnm
            return strnm
        else:
            s = self.env[strnm]
            m = re.match('^(.*)_([0-9]*)$', s)
            # either post-pend a _1 or increment the post-pended counter
            if not m:
                s = s + "_1"
            else:
                s = f"{m[1]}_{int(m[2]) + 1}"
            self.env[strnm] = s
            return s

    def get_name(self, nm):
        strnm = str(nm)
        if strnm in self.env:
            return self.env[strnm]
        else:
            return repr(nm)

    def pproc(self, p):
        assert p.name

        args = [ self.pfnarg(a) for a in p.args ]

        self.addline(f"def {p.name}({','.join(args)}):")

        self.push()
        if p.instr:
            instr_lines = p.instr.split('\n')
            instr_lines = ([f'# @instr {instr_lines[0]}']+
                           [f'#        {l}' for l in instr_lines[1:] ])
            for l in instr_lines:
                self.addline(l)
        for pred in p.preds:
            self.addline(f"assert {self.pexpr(pred)}")
        for proc in p.body:
            self.pstmt(proc)
        self.pop()

    def pfnarg(self, a):
        if a.type == T.index:
            return f"{self.new_name(a.name)} : index"
        else:
            mem = f" @{a.mem.name()}" if a.mem else ""
            return f"{self.new_name(a.name)} : {self.ptype(a.type)} {mem}"

    def pstmt(self, stmt):
        if type(stmt) is LoopIR.Pass:
            self.addline("pass")
        elif type(stmt) is LoopIR.Assign or type(stmt) is LoopIR.Reduce:
            op = "=" if type(stmt) is LoopIR.Assign else "+="

            rhs = self.pexpr(stmt.rhs)

            if len(stmt.idx) > 0:
                idx = [self.pexpr(e) for e in stmt.idx]
                lhs = f"{self.get_name(stmt.name)}[{','.join(idx)}]"
            else:
                lhs = self.get_name(stmt.name)

            self.addline(f"{lhs} {op} {rhs}")
        elif type(stmt) is LoopIR.WriteConfig:
            cname   = stmt.config.name()
            rhs     = self.pexpr(stmt.rhs)
            self.addline(f"{cname}.{stmt.field} = {rhs}")
        elif type(stmt) is LoopIR.WindowStmt:
            rhs = self.pexpr(stmt.rhs)
            self.addline(f"{self.new_name(stmt.lhs)} = {rhs}")
        elif type(stmt) is LoopIR.Alloc:
            mem = f" @{stmt.mem.name()}" if stmt.mem else ""
            self.addline(f"{self.new_name(stmt.name)} : "+
                         f"{self.ptype(stmt.type)}{mem}")
        elif type(stmt) is LoopIR.Free:
            mem = f" @{stmt.mem._name}" if stmt.mem else ""
            self.addline(f"free({self.get_name(stmt.name)})")
        elif type(stmt) is LoopIR.Call:
            args    = [ self.pexpr(a) for a in stmt.args ]
            self.addline(f"{stmt.f.name}({','.join(args)})")
        elif type(stmt) is LoopIR.If:
            cond = self.pexpr(stmt.cond)
            self.addline(f"if {cond}:")
            self.push()
            for p in stmt.body:
                self.pstmt(p)
            self.pop()
            if len(stmt.orelse) > 0:
                self.addline(f"else:")
                self.push()
                for p in stmt.orelse:
                    self.pstmt(p)
                self.pop()

        elif type(stmt) is LoopIR.ForAll:
            hi = self.pexpr(stmt.hi)
            self.push(only='env')
            self.addline(f"for {self.new_name(stmt.iter)} in par(0, {hi}):")
            self.push(only='tab')
            for p in stmt.body:
                self.pstmt(p)
            self.pop()
        else:
            assert False, f"unrecognized stmt: {type(stmt)}"

    def pexpr(self, e, prec=0):
        if type(e) is LoopIR.Read:
            if len(e.idx) > 0:
                idx = [self.pexpr(i) for i in e.idx]
                return f"{self.get_name(e.name)}[{','.join(idx)}]"
            else:
                return self.get_name(e.name)
        elif type(e) is LoopIR.Const:
            return str(e.val)
        elif type(e) is LoopIR.USub:
            return f'-{self.pexpr(e.arg, op_prec["~"])}'
        elif type(e) is LoopIR.BinOp:
            local_prec = op_prec[e.op]
            # increment rhs by 1 to account for left-associativity
            lhs = self.pexpr(e.lhs, prec=local_prec)
            rhs = self.pexpr(e.rhs, prec=local_prec+1)
            s = f"{lhs} {e.op} {rhs}"
            # if we have a lower precedence than the environment...
            if local_prec < prec:
                s = f"({s})"
            return s
        elif type(e) is LoopIR.WindowExpr:
            return (f"{self.get_name(e.name)}"+
                    f"[{', '.join([ self.pwacc(w) for w in e.idx ])}]")
        elif type(e) is LoopIR.StrideExpr:
            return f"stride({self.get_name(e.name)}, {e.dim})"
        elif type(e) is LoopIR.BuiltIn:
            pname   = e.f.name() or "_anon_"
            args    = [ self.pexpr(a) for a in e.args ]
            return f"{pname}({','.join(args)})"
        elif type(e) is LoopIR.ReadConfig:
            cname   = e.config.name()
            return f"{cname}.{e.field}"
        else:
            assert False, f"unrecognized expr: {type(e)}"

    def pwacc(self, w):
        if type(w) is LoopIR.Point:
            return self.pexpr(w.pt)
        elif type(w) is LoopIR.Interval:
            return f"{self.pexpr(w.lo)}:{self.pexpr(w.hi)}"
        else: assert False, "bad case"

    def ptype(self, t):
        if type(t) is T.Num:
            return "R"
        elif type(t) is T.F32:
            return "f32"
        elif type(t) is T.F64:
            return "f64"
        elif type(t) is T.INT8:
            return "i8"
        elif type(t) is T.INT32:
            return "i32"
        elif type(t) is T.Bool:
            return "bool"
        elif type(t) is T.Int:
            return "int"
        elif type(t) is T.Index:
            return "index"
        elif type(t) is T.Error:
            return "err"
        elif type(t) is T.Tensor:
            base = str(t.basetype())
            if t.is_window:
                base = f"[{base}]"
            rngs = ",".join([self.pexpr(r) for r in t.shape()])
            return f"{base}[{rngs}]"
        elif type(t) is T.Window:
            return (f"Window(src_type={t.src_type},as_tensor={t.as_tensor},"+
                    f"src_buf={t.src_buf},"+
                    f"idx=[{', '.join([ self.pwacc(w) for w in t.idx ])}])")
        else:
            assert False, "impossible type case"
