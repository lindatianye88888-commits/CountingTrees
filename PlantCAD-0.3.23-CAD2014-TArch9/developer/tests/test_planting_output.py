"""Execute production rules for output roles, pattern reuse and table edit units."""
import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class PlantingOutput(fixtures.Rules):
    def test_shrub_ball_has_its_own_symbol_and_label_layers(self):
        p=self.put('kind',3)
        self.assertIsNone(self.rt.call('pl:plant-error',p))
        self.assertEqual(chinese(self.rt.call('pl:tree-layer',p)),'PL_灌木球_圆圈')
        self.assertEqual(chinese(self.rt.call('pl:tree-layer',self.put('style',1,p))),'PL_灌木球_简化')
        self.assertEqual(chinese(self.rt.call('pl:plant-label-layer',p)),'PL_灌木球_标注')
        self.assertIsNotNone(self.rt.call('pl:insert-error',self.put('crown',0.,p)))

    def test_flower_border_and_lawn_allow_area_only_definitions(self):
        for kind,layer in [(4,'PL_花境_填充'),(5,'PL_草地_填充')]:
            p=self.put('kind',kind,self.put('crown',0.))
            self.assertIsNone(self.rt.call('pl:plant-error',p))
            self.assertIsNone(self.rt.call('pl:insert-error',p))
            self.assertTrue(self.rt.call('pl:area-kind-p',kind))
            self.assertEqual(chinese(self.rt.call('pl:fill-layer',p)),layer)

    def test_automatic_pattern_is_stable_and_can_repeat(self):
        a=self.put('species_id','SAME-SPECIES')
        b=self.put('crown',4.5,self.put('species_id','SAME-SPECIES'))
        self.assertEqual(self.rt.call('pl:fill-pattern',a),self.rt.call('pl:fill-pattern',b))
        p=self.put('fill_pattern','ANSI33')
        self.assertEqual(self.rt.call('pl:fill-pattern',p),'ANSI33')
        self.assertEqual(self.rt.call('pl:fill-pattern',self.put('name',gbk('另一个品种'),p)),'ANSI33')

    def test_output_layout_preserves_area_and_inferred_boundary_notice(self):
        self.rt.builtins.update({'pl:area-value':lambda e:12.345,'pl:area-title':lambda e:gbk('麦冬'),
                                'pl:data-get':lambda e,key:1 if key=='AREA_REPAIRED' else None})
        a=chinese(self.rt.call('pl:output-area-text','AREA',[Pair(Sym('layout'),0)]))
        b=chinese(self.rt.call('pl:output-area-text','AREA',[Pair(Sym('layout'),1)]))
        self.assertEqual(a,r'麦冬\P约 12.35 平方米（补线推定）')
        self.assertEqual(b,'麦冬  约 12.35 平方米（补线推定）')

    def test_table_dimensions_round_trip_in_cm_without_changing_identity(self):
        p=self.put('kind',3,self.put('spec_no','B001'))
        before=self.rt.call('pl:output-table-cells',[p,2])
        after=list(before);after[5]='90';after[6]='160'
        result=self.rt.call('pl:table-edited-plant',p,before,after)
        self.assertEqual(self.get('id',result),self.get('id',p))
        self.assertEqual(self.get('spec_no',result),'B001')
        self.assertAlmostEqual(self.get('height',result),.9)
        self.assertAlmostEqual(self.get('crown',result),1.6)
        after=list(before);after[7]='999'
        self.assertEqual(self.rt.call('pl:table-edited-plant',p,before,after),p)

    def test_table_edit_rejects_invalid_dimensions(self):
        p=self.put('kind',3,self.put('spec_no','B001'))
        before=self.rt.call('pl:output-table-cells',[p,2])
        def fail(message):raise ValueError(chinese(message))
        self.rt.builtins['pl:fail']=fail
        for bad in ['-12','abc','{\\H100;900}']:
            after=list(before);after[6]=bad
            with self.assertRaises(ValueError):self.rt.call('pl:table-edited-plant',p,before,after)

    def test_table_legend_uses_area_pattern_or_single_plant_symbol(self):
        area=self.put('quantity_unit',gbk('平方米'),self.put('kind',4))
        self.assertTrue(self.rt.call('pl:output-table-cells',[area,1.25])[-1].startswith('HATCH:'))
        ball=self.put('kind',3)
        self.assertEqual(self.rt.call('pl:output-table-cells',[ball,2])[-1],'PL02_CIRCLE')
        self.assertEqual(self.rt.call('pl:output-table-cells',[self.put('kind',1),2])[-1],'PL02_CIRCLE')

    def test_manual_annotation_name_reuses_unique_project_specification(self):
        writes=[]
        self.rt.builtins.update({'pl:defs':lambda:[self.p], 'pl:data-put':lambda *a:writes.append(a)})
        self.assertEqual(self.rt.call('pl:area-label-name','AREA',self.get('name')),self.p)
        self.assertEqual(writes,[('AREA','AREA_PLANT',self.p)])
        self.rt.builtins['pl:defs']=lambda:[self.p,self.put('id','P2')]
        self.assertFalse(self.rt.call('pl:area-label-name','AREA',self.get('name')))
        self.assertEqual(len(writes),1)

    def test_manual_new_shrub_name_does_not_invent_dimensions(self):
        saved=[]
        self.rt.builtins.update({'pl:defs':lambda:[], 'pl:new-id':lambda:'AREA_NEW',
            'pl:data-get':lambda *a:1,'pl:used-specs':lambda:[], 'pl:next-spec-number':lambda *a:'P050',
            'pl:save-def':lambda p:saved.append(p), 'pl:data-put':lambda *a:True})
        result=self.rt.call('pl:area-label-name','AREA',gbk('新灌木'))
        self.assertEqual(self.get('name',result),gbk('新灌木'))
        self.assertEqual(self.get('kind',result),1)
        self.assertEqual(self.get('quantity_unit',result),gbk('平方米'))
        self.assertTrue(all(self.get(k,result)==0 for k in ['dbh','caliper','height','crown']))

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in PlantingOutput.__dict__:setattr(PlantingOutput,name,None)
if __name__=='__main__':unittest.main()
