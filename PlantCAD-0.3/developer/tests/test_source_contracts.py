from pathlib import Path
import unittest
from lisp_harness import parse,Sym
ROOT=Path(__file__).resolve().parents[1]
class SourceContracts(unittest.TestCase):
    def test_internal_lisp_calls_have_correct_argument_counts(self):
        functions={}
        for p in (ROOT/'src').glob('*.lsp'):
            for form in parse(p.read_text(encoding='utf-8')):
                if isinstance(form,list) and form and form[0]==Sym('defun'):
                    self.assertNotIn(form[1],functions,f'Duplicate definition: {form[1]}')
                    functions[form[1]]=form
        def visit(expr):
            if not isinstance(expr,list) or not expr or expr[0]==Sym('quote'): return
            op=expr[0]
            if isinstance(op,Sym) and op in functions:
                signature=functions[op][2]
                count=signature.index(Sym('/')) if Sym('/') in signature else len(signature)
                self.assertEqual(len(expr)-1,count,f'Incorrect call to {op}')
            for x in expr[1:]: visit(x)
        for form in functions.values():
            for expr in form[3:]: visit(expr)

    def test_mutated_variables_are_local_or_explicit_plugin_globals(self):
        def assigned(expr):
            if not isinstance(expr,list) or not expr or expr[0]==Sym('quote'): return []
            result=[]
            if expr[0]==Sym('setq'): result+=expr[1::2]
            if expr[0] in [Sym('foreach'),Sym('vlax-for')]: result.append(expr[1])
            for child in expr[1:]: result+=assigned(child)
            return result
        for p in (ROOT/'src').glob('*.lsp'):
            for form in parse(p.read_text(encoding='utf-8')):
                if isinstance(form,list) and form and form[0]==Sym('defun'):
                    declared=form[2]
                    for expr in form[3:]:
                        for symbol in assigned(expr):
                            if not str(symbol).startswith('pl:*'):
                                self.assertIn(symbol,declared,f'{form[1]}: nonlocal {symbol}')
