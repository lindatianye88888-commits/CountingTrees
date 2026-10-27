"""Coexisting add-ons keep occupied short commands; PlantCAD keeps full commands."""
from pathlib import Path
import unittest
from lisp_harness import Runtime, Sym, parse

ROOT = Path(__file__).resolve().parents[1]

class CommandCompatibility(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()
        self.forms = []
        for name in ['plantcad.lsp', 'plantcad-design.lsp', 'plantcad-ui.lsp']:
            self.forms += parse((ROOT/'src'/name).read_text(encoding='utf-8'))
        self.rt.load(self.forms)
        self.native = set()
        self.rt.env[Sym("pl:*enable-short-commands*")]=True
        self.rt.builtins.update({
            'boundp':lambda symbol:symbol in self.rt.env,
            'getcname': lambda name: name if name in self.native else None,
            'atoms-family': lambda fmt, names: [name if name.lower() in self.rt.funcs else None for name in names],
            'read': lambda text: Sym(text.lower()),
            'eval': self.define,
        })

    def define(self, form):
        form[2] = form[2] or []  # NIL and () are the same list in native AutoLISP.
        self.rt.load([form])

    def test_free_short_command_dispatches_to_full_name_and_survives_reload(self):
        self.rt.builtins['c:plantcadset'] = lambda: 'plantcad'
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.assertEqual(self.rt.call('c:plset'), 'plantcad')
        self.rt.load(self.forms)
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.assertEqual(self.rt.call('c:plset'), 'plantcad')

    def test_existing_lisp_command_is_preserved(self):
        self.rt.load(parse('(defun c:PLSET () "other add-on")'))
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.assertEqual(self.rt.call('c:plset'), 'other add-on')
        self.assertIn('c:plantcadset', self.rt.funcs)

    def test_existing_native_command_is_preserved(self):
        self.native.add('PLSET')
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.assertNotIn('c:plset', self.rt.funcs)
        self.assertIn('c:plantcadset', self.rt.funcs)

    def test_addon_that_replaces_an_alias_is_preserved_on_reload(self):
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.rt.load(parse('(defun c:PLSET () "later add-on")'))
        self.rt.load(self.forms)
        self.rt.call('pl:register-command', 'PLSET', 'PLANTCADSET')
        self.assertEqual(self.rt.call('c:plset'), 'later add-on')

    def test_all_public_commands_are_namespaced_and_optional_aliases_resolve(self):
        full = {str(f[1]) for f in self.forms if isinstance(f,list) and f and f[0]==Sym('defun') and str(f[1]).startswith('c:')}
        aliases = {('c:'+f[2]).lower() for f in self.forms if isinstance(f,list) and f and f[0]==Sym('pl:register-command')}
        self.assertTrue(aliases<=full)
        self.assertEqual(len(full), 29)
        self.assertTrue(all(name.startswith('c:plantcad') for name in full))

    def test_default_install_does_not_register_short_commands(self):
        self.rt.env.pop(Sym('pl:*enable-short-commands*'))
        self.rt.call('pl:register-command','PLSET','PLANTCADSET')
        self.assertNotIn('c:plset',self.rt.funcs)

if __name__ == '__main__':
    unittest.main()
