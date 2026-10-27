"""Production symbol proportions and fixed project parameter columns."""
import test_rules as fixtures
from lisp_harness import Pair,Sym,chinese,gbk

class NamedLegends(fixtures.Rules):
    def test_legend_uses_the_drawing_symbol_text_proportion(self):
        opts=[Pair(Sym('scale'),100.),Pair(Sym('paper_height'),2.5),Pair(Sym('show_number'),1)]
        self.rt.builtins['pl:db-get']=lambda key,default=None:opts
        value=self.rt.call('pl:table-legend-layout',self.p)
        self.assertAlmostEqual(value[0],.25/3.)
        self.assertEqual(value[2],self.get('name'))
        self.assertEqual(value[3],'12');self.assertEqual(value[4],'')
        p=self.put('kind',3)
        ball=self.rt.call('pl:table-legend-layout',p)
        self.assertEqual(ball[1],3);self.assertEqual(ball[3:5],['',''])

    def test_custom_block_uses_its_base_diameter_for_whole_symbol_scaling(self):
        self.rt.builtins['pl:db-get']=lambda key,default=None:default
        a=self.rt.call('pl:table-legend-layout',self.p)
        b=self.rt.call('pl:table-legend-layout',self.put('base',20.,self.put('style',2)))
        self.assertAlmostEqual(b[0],a[0]*20.)

    def test_all_six_plant_types_have_the_same_eight_columns(self):
        columns=chinese(self.rt.call('pl:project-columns')).split('\t')
        self.assertEqual(len(columns),8)
        for kind in range(6):
            p=self.put('kind',kind)
            if kind in (1,2,4,5):p=self.put('quantity_unit',gbk('平方米'),p)
            row=[chinese(s) for s in self.rt.call('pl:project-list-row',p).split('\t')]
            self.assertEqual(len(row),8)
            self.assertEqual(row[2],'香樟')
            self.assertEqual(row[3:7],['400','300','12','——'])
            self.assertEqual(row[7],chinese(self.get('quantity_unit',p)))

    def test_missing_area_specifications_do_not_shift_later_columns(self):
        p=self.put('name',gbk('手工灌木'),self.put('kind',1,self.rt.call('pl:empty-plant','AREA_ONLY')))
        p=self.put('quantity_unit',gbk('平方米'),p)
        row=[chinese(s) for s in self.rt.call('pl:project-list-row',p).split('\t')]
        self.assertEqual(row[2],'手工灌木');self.assertEqual(row[3:7],['','','——','——'])
        self.assertEqual(row[7],'平方米')
