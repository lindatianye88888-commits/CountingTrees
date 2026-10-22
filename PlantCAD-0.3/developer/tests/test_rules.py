from pathlib import Path
import re
import unittest
from lisp_harness import Runtime, Sym, Pair, parse, lint, gbk, chinese

ROOT = Path(__file__).resolve().parents[1]

class Rules(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()
        for p in ROOT.joinpath('src').glob('*.lsp'):
            forms = parse(p.read_text(encoding='utf-8'))
            lint(forms, p.name)
            self.rt.load(forms)
        self.p = self.rt.call('pl:empty-plant', 'P1')
        for key, value in [('name', gbk('香樟')), ('dbh', 12.0),
                           ('height', 4.0), ('crown', 3.0)]:
            self.p = self.put(key, value, self.p)

    def put(self, k, v, p=None):
        return self.rt.call('pl:put', Sym(k), v, self.p if p is None else p)

    def get(self, k, p=None):
        return self.rt.call('pl:get', Sym(k), self.p if p is None else p)

    def opts(self, mode, prefix=0, units=0):
        return [Pair(Sym('mode'), mode), Pair(Sym('prefix'), prefix), Pair(Sym('units'), units)]

    def label(self, mode, prefix=0, units=0, p=None):
        return chinese(self.rt.call('pl:label-text', self.p if p is None else p,
                                    self.opts(mode, prefix, units)))

    def test_all_source_structure(self):
        for p in ROOT.joinpath('src').glob('*.lsp'):
            lint(parse(p.read_text(encoding='utf-8')), p.name)

    def test_name_only(self):
        self.assertEqual(self.label(0), '香樟')

    def test_number_below_name(self):
        self.assertEqual(self.label(1), r'香樟\P12')

    def test_optional_diameter_prefix(self):
        self.assertEqual(self.label(1, 1), r'香樟\PD12')
        self.assertEqual(self.label(1, 2, 1), r'香樟\PD=12cm')

    def test_all_specs(self):
        self.assertEqual(self.label(2), r'香樟\PD=12cm  H=400cm  P=300cm')

    def test_missing_dbh_never_uses_crown(self):
        p = self.put('dbh', 0.0)
        self.assertEqual(self.label(1, 2, 1, p), '香樟')

    def test_missing_all_specs_name_only(self):
        p = self.p
        for key in ['dbh', 'height', 'crown']:
            p = self.put(key, 0.0, p)
        self.assertEqual(self.label(2, p=p), '香樟')

    def test_partial_specs(self):
        p = self.put('height', 0.0)
        self.assertEqual(self.label(2, p=p), r'香樟\PD=12cm  P=300cm')

    def test_decimal_dbh(self):
        p = self.put('dbh', 12.5)
        self.assertEqual(self.label(1, p=p), r'香樟\P12.5')

    def test_name_mtext_controls_escaped(self):
        p = self.put('name', gbk(r'品种{A}\P'))
        self.assertEqual(self.label(0, p=p), r'品种\{A\}\\P')

    def test_size_units(self):
        for unit, expected in [(1000.0, 3000.0), (1.0, 3.0), (100.0, 300.0)]:
            with self.subTest(unit=unit):
                self.assertAlmostEqual(self.rt.call('pl:diameter', self.p, unit), expected)

    def test_display_only_preserves_specs(self):
        p = self.put('factor', 0.8)
        self.assertEqual(self.get('dbh', p), 12.0)
        self.assertEqual(self.get('crown', p), 3.0)
        self.assertAlmostEqual(self.rt.call('pl:diameter', p, 1000.0), 2400.0)
        self.assertEqual(self.label(2, p=p), self.label(2))

    def test_real_crown_changes_spec(self):
        p = self.put('crown', 3.5)
        self.assertEqual(self.get('dbh', p), 12.0)
        self.assertAlmostEqual(self.rt.call('pl:diameter', p, 1000.0), 3500.0)
        self.assertIn('P=350cm', self.label(2, p=p))

    def test_custom_block_calibration(self):
        p = self.put('style', 2)
        p = self.put('block', 'MYTREE', p)
        p = self.put('base', 500.0, p)
        self.assertAlmostEqual(self.rt.call('pl:block-scale', p, 1000.0), 6.0)

    def test_style_and_graphic_scale_do_not_split_counts(self):
        p = self.put('style', 1)
        p = self.put('factor', 1.2, p)
        rows = self.rt.call('pl:add-count', self.p, None)
        rows = self.rt.call('pl:add-count', p, rows)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 2)

    def test_dbh_splits_count_rows(self):
        rows = self.rt.call('pl:add-count', self.p, None)
        rows = self.rt.call('pl:add-count', self.put('dbh', 15.0), rows)
        self.assertEqual(len(rows), 2)

    def test_cultivar_names_preserved(self):
        self.assertNotEqual(self.rt.call('pl:count-key', self.p),
                            self.rt.call('pl:count-key', self.put('name', gbk('金桂'))))
        self.assertEqual(chinese(self.rt.call('pl:normal-name', gbk('  金桂1号  '))), '金桂1号')

    def test_external_spaces_unify_names(self):
        rows = self.rt.call('pl:add-count', self.p, None)
        rows = self.rt.call('pl:add-count', self.put('name', gbk(' 香樟 ')), rows)
        self.assertEqual(rows[0][2], 2)

    def test_missing_crown_rejects_insertion(self):
        self.assertIsNotNone(self.rt.call('pl:insert-error', self.put('crown', 0.0)))

    def test_all_categories_allow_individual_symbols(self):
        for k in [1, 2]:
            self.assertIsNone(self.rt.call('pl:insert-error', self.put('kind', k)))

    def test_invalid_factor_and_block_base(self):
        self.assertIsNotNone(self.rt.call('pl:plant-error', self.put('factor', 0.0)))
        p = self.put('style', 2)
        p = self.put('block', 'B1', p)
        p = self.put('base', 0.0, p)
        self.assertIsNotNone(self.rt.call('pl:plant-error', p))

    def test_numeric_input_units_and_negative_rejected(self):
        for s in ['', '12cm', '-12', '+12', '1e3', '1/2', "1'", '1,000', '.', '1..2']:
            with self.subTest(s=s):
                self.assertIsNone(self.rt.call('pl:number-input', s))
        for s, n in [('12', 12.0), ('12.5', 12.5), ('.5', .5), (' 3.5 ', 3.5), ('0', 0.0)]:
            with self.subTest(s=s):
                self.assertAlmostEqual(self.rt.call('pl:number-input', s), n)

    def test_csv_quotes(self):
        self.assertEqual(chinese(self.rt.call('pl:csv-cell', gbk('品种,"A"'))), '"品种,""A"""')

    def test_dxf_updates_preserve_handle_and_location(self):
        ed = [Pair(0, 'INSERT'), Pair(5, 'A12'), [10, 15.0, 20.0, 0.0], Pair(2, 'OLD')]
        changed = self.rt.call('pl:set-dxf', 2, 'NEW', ed)
        self.assertEqual(self.rt.call('pl:set-dxf', 41, 3000.0, changed)[1], Pair(5, 'A12'))
        self.assertEqual(changed[2], [10, 15.0, 20.0, 0.0])

    def test_dcl_keys_case_and_bindings(self):
        dcl = ROOT.joinpath('src/plantcad.dcl').read_text(encoding='utf-8')
        keys = set(re.findall(r'key\s*=\s*"([^\"]+)"', dcl)) | {'accept', 'cancel'}
        code = '\n'.join(p.read_text(encoding='utf-8') for p in ROOT.joinpath('src').glob('*.lsp'))
        refs = set(re.findall(r'\((?:set_tile|action_tile|get_tile|start_list|pl:popup)\s+"([^\"]+)"', code))
        self.assertFalse(refs - keys)
        self.assertTrue({'dbh', 'height', 'crown', 'factor', 'base'} <= keys)
        self.assertIn('(strcase (vl-symbol-name key) T)', code)

    def test_no_external_engine_or_implicit_drawing_save(self):
        code = '\n'.join(p.read_text(encoding='utf-8') for p in ROOT.joinpath('src').glob('*.lsp'))
        self.assertNotRegex(code, r'\((?:command-s|findtrustedfile|showHTMLModalWindow)\b')
        self.assertNotRegex(code.lower(), r'\bacad_dgnlinestylecomp\b')
        forms=parse(code)
        saved=[f[1] for f in forms if isinstance(f,list) and f and f[0]==Sym('defun') and 'qsave' in str(f).lower()]
        self.assertEqual(saved,[Sym('pl:save-project-work')])

    def test_independent_layers_include_geometric_area(self):
        layers = self.rt.call('pl:layers')
        names = [chinese(x[0]) for x in layers]
        self.assertEqual(len(names), 25)
        self.assertEqual(len(set(names)), 25)
        self.assertIn('PL_标注_树木', names)
        self.assertIn('PL_表格_苗木', names)
        self.assertIn('PL_表格_植物名录', names)
        self.assertIn('PL_表格_植物规格', names)
        self.assertIsNone(layers[-1][2])

if __name__ == '__main__':
    unittest.main(verbosity=2)
