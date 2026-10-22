"""Small test evaluator for this project's PURE AutoLISP rules.

It executes the actual .lsp source, not Python copies of the rules.
This is NOT AutoCAD, DCL, COM, DWG persistence, or a general Lisp runtime.
Strings emulate the legacy Windows CP936 byte representation where needed.
"""
from dataclasses import dataclass
import math
import re

class Sym(str):
    pass

@dataclass(frozen=True)
class Pair:
    car: object
    cdr: object

def tokens(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ';':
            i = text.find('\n', i)
            if i == -1:
                break
        elif c in "()'":
            out.append(c); i += 1
        elif c == '"':
            i += 1; value = ''
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                    if i >= len(text):
                        raise SyntaxError('unterminated string escape')
                    value += {'n': '\n', 'r': '\r', 't': '\t'}.get(text[i], text[i])
                else:
                    value += text[i]
                i += 1
            if i >= len(text):
                raise SyntaxError('unterminated string')
            out.append(('string', value)); i += 1
        else:
            j = i
            while i < len(text) and not text[i].isspace() and text[i] not in "();'\"":
                i += 1
            out.append(text[j:i])
    return out

def parse(text):
    stream, i = tokens(text), 0
    def one():
        nonlocal i
        if i >= len(stream):
            raise SyntaxError('unexpected end')
        token = stream[i]; i += 1
        if token == '(':
            items = []
            while i < len(stream) and stream[i] != ')':
                if stream[i] == '.':
                    if len(items) != 1:
                        raise SyntaxError('only simple dotted pairs expected')
                    i += 1; tail = one()
                    if i >= len(stream) or stream[i] != ')':
                        raise SyntaxError('invalid dotted pair')
                    i += 1; return Pair(items[0], tail)
                items.append(one())
            if i >= len(stream):
                raise SyntaxError('unclosed list')
            i += 1; return items
        if token == ')':
            raise SyntaxError('unexpected closing parenthesis')
        if token == "'":
            return [Sym('quote'), one()]
        if isinstance(token, tuple):
            # Model legacy bytes as Latin-1 code points to permit byte-oriented substr/chr.
            return token[1].encode('gbk').decode('latin1')
        if re.fullmatch(r'[+-]?\d+', token):
            return int(token)
        if re.fullmatch(r'[+-]?(?:\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?', token):
            return float(token)
        if token.lower() == 'nil': return None
        if token.lower() == 't': return True
        return Sym(token.lower())
    forms = []
    while i < len(stream):
        forms.append(one())
    return forms

def truth(x):
    return x is not None and x is not False and x != []

def car(x):
    if x is None or x == []: return None
    return x.car if isinstance(x, Pair) else x[0]

def cdr(x):
    if x is None or x == []: return None
    return x.cdr if isinstance(x, Pair) else x[1:]

def cons(a, b):
    return [a] + (b or []) if b is None or isinstance(b, list) else Pair(a, b)

def nth(i, xs):
    if i < 0: raise ValueError('AutoLISP nth: negative index')
    return xs[i] if xs and i < len(xs) else None

def assoc(k, xs):
    return next((p for p in xs or [] if car(p) == k), None)

class Runtime:
    def __init__(self):
        self.env = {Sym('nil'): None, Sym('t'): True, Sym('pi'): math.pi}
        self.funcs = {}
        self.builtins = {
            'car': car, 'cdr': cdr, 'cadr': lambda x: car(cdr(x)),
            'caddr': lambda x: car(cdr(cdr(x))),
            'cons': cons, 'list': lambda *xs: list(xs),
            'append': lambda *xs: sum((x or [] for x in xs), []),
            'nth': nth, 'assoc': assoc, 'length': lambda x: len(x or []),
            'subst': lambda new, old, xs: [new if v == old else v for v in xs],
            'member': lambda x, xs: xs[xs.index(x):] if xs and x in xs else None,
            'strcat': lambda *xs: ''.join(xs), 'strlen': len,
            'substr': lambda s, start, n=None: s[start-1:] if n is None else s[start-1:start-1+n],
            'strcase': lambda s, low=None: gbk(chinese(s).lower() if truth(low) else chinese(s).upper()),
            'vl-string-trim': lambda chars, s: s.strip(chars),
            'vl-string-right-trim': lambda chars, s: s.rstrip(chars),
            'vl-string-search': lambda pattern, s: s.find(pattern) if pattern in s else None,
            'vl-string->list': lambda s: [ord(c) for c in s], 'chr': chr,
            'atof': float, 'atoi': int, 'itoa': str,
            'numberp': lambda n: isinstance(n,(int,float)) and not isinstance(n,bool),
            'listp': lambda v: v is None or isinstance(v,(list,Pair)),
            'type': lambda v: Sym('str') if isinstance(v,str) and not isinstance(v,Sym) else Sym('list') if isinstance(v,(list,Pair)) else Sym('other'),
            'fix': lambda n: int(n), 'rtos': lambda n, mode, prec: format(n, f'.{prec}f'),
            '+': lambda *xs: sum(xs), '*': lambda *xs: math.prod(xs),
            '-': lambda a, *xs: a - sum(xs) if xs else -a,
            '/': lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b,
            '1+': lambda x: x+1, '1-': lambda x: x-1,
            'max': max, 'min': min, 'cos': math.cos, 'sin': math.sin,
            '=': lambda a, b: a == b, '/=': lambda a, b: a != b,
            'eq': lambda a, b: a == b, 'equal': lambda a, b: a == b,
            '<': lambda a, b: a < b, '>': lambda a, b: a > b,
            '<=': lambda a, b: a <= b, '>=': lambda a, b: a >= b,
            'null': lambda x: not truth(x), 'not': lambda x: not truth(x),
            'princ': lambda *xs: None, 'reverse': lambda xs: list(reversed(xs or [])),
            'logand': lambda a, b: a & b,
            'boundp': lambda symbol: symbol in self.env,
            'rem': lambda a, b: a % b,
        }

    def load(self, forms):
        for form in forms:
            if isinstance(form, list) and form and form[0] == Sym('defun'):
                self.funcs[str(form[1])] = (form[2], form[3:])

    def call(self, name, *args):
        name = name.lower()
        if name in self.builtins:
            return self.builtins[name](*args)
        signature, body = self.funcs[name]
        if Sym('/') in signature:
            idx = signature.index(Sym('/')); params, locals_ = signature[:idx], signature[idx+1:]
        else:
            params, locals_ = signature, []
        if len(params) != len(args):
            raise TypeError(f'{name}: {len(args)} arguments for {len(params)} parameters')
        bindings = dict(zip(params, args)); bindings.update({x: None for x in locals_})
        missing = object(); saved = {x: self.env.get(x, missing) for x in bindings}
        self.env.update(bindings)
        try:
            result = None
            for form in body:
                result = self.eval(form)
            return result
        finally:
            for x, old in saved.items():
                if old is missing: self.env.pop(x, None)
                else: self.env[x] = old

    def eval(self, x):
        if isinstance(x, Sym): return self.env.get(x)
        if not isinstance(x, list): return x
        if not x: return None
        op, args = str(x[0]), x[1:]
        if op == 'quote': return args[0]
        if op == 'setq':
            value = None
            for i in range(0, len(args), 2):
                value = self.eval(args[i+1]); self.env[args[i]] = value
            return value
        if op == 'if':
            return self.eval(args[1]) if truth(self.eval(args[0])) else self.eval(args[2]) if len(args) == 3 else None
        if op == 'progn':
            result = None
            for a in args: result = self.eval(a)
            return result
        if op == 'cond':
            for case in args:
                result = self.eval(case[0])
                if truth(result):
                    for a in case[1:]: result = self.eval(a)
                    return result
            return None
        if op == 'and':
            return all(truth(self.eval(a)) for a in args)
        if op == 'or':
            return any(truth(self.eval(a)) for a in args)
        if op == 'foreach':
            result = None
            for value in self.eval(args[1]) or []:
                self.env[args[0]] = value
                for a in args[2:]: result = self.eval(a)
            return result
        if op == 'while':
            result = None
            for _ in range(100000):
                if not truth(self.eval(args[0])): return result
                for a in args[1:]: result = self.eval(a)
            raise RuntimeError('while exceeded test harness limit')
        if op == 'repeat':
            result = None
            for _ in range(self.eval(args[0])):
                for a in args[1:]: result = self.eval(a)
            return result
        return self.call(op, *[self.eval(a) for a in args])

def gbk(s):
    return s.encode('gbk').decode('latin1')

def chinese(s):
    return s.encode('latin1').decode('gbk')

def lint(forms, filename):
    errors = []
    def visit(x, quoted=False):
        if not isinstance(x, list) or not x: return
        if x[0] == Sym('quote'): return
        op = str(x[0])
        if op == 'if' and len(x) not in (3, 4): errors.append(f'if arity {len(x)-1}')
        if op == 'setq' and len(x) % 2 != 1: errors.append('setq requires symbol/value pairs')
        if op == 'defun' and (len(x) < 4 or not isinstance(x[2], list)): errors.append('invalid defun')
        if op == 'cond':
            for case in x[1:]:
                if not isinstance(case, list) or not case: errors.append('invalid cond case')
        for child in x[1:]: visit(child)
    for form in forms: visit(form)
    if errors: raise AssertionError(f'{filename}: {errors}')
