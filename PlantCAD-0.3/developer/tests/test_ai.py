from pathlib import Path
import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk,chinese
class AIRules(fixtures.Rules):
    def setUp(self):
        super().setUp()
        self.rt.builtins['pl:fail']=lambda message: (_ for _ in ()).throw(ValueError(chinese(message)))
        self.p=self.put('spec_no','P001')
        self.database={'AI_USED_IDS':None,'PLANTS':[self.p]}
        self.plants={'A1':self.p}
        self.states={'A1':['original']}
        self.rt.env[Sym('pl:*ai-plans*')]=None
        self.rt.builtins.update({
            'pl:catalog':lambda:None,'pl:defs':lambda:self.database['PLANTS'],
            'pl:used-specs':lambda:self.database['PLANTS']+self.database.get('SPEC_HISTORY',[]),
            'pl:db-get':lambda k,d:self.database.get(k,d),
            'pl:db-put':lambda k,v:self.database.__setitem__(k,v) or v,
            'pl:ai-model-trees':lambda:list(self.plants),
            'pl:plant':lambda e:self.plants[e],
            'pl:ai-targets':lambda args:list(self.plants),
            'pl:writable':lambda e:True,'pl:layer-open':lambda layer:True,
            'pl:data-get':lambda e,k:1000 if k=='UNITS' else None,
            'pl:ai-state':lambda e:self.states[e].copy(),
            'pl:ai-view':lambda e,p:[['handle',e],['spec',self.get('spec_no',p)]],
            'getvar':lambda k:46000.,
            'entget':lambda e:[] if e not in self.plants else [Pair(5,e)]
        })
    def args(self,changes=None,plan_id='a'*32):
        return [['plan_id',plan_id],['changes',[[k,v] for k,v in (changes or {'crown':5.}).items()]]]
    def species(self,name='银杏',category=1):
        return [Pair(Sym('id'),'GINKGO'),Pair(Sym('name'),gbk(name)),Pair(Sym('category'),category)]
    def test_native_id_generation_never_requires_dxf_header_as_system_variable(self):
        self.rt.builtins['getvar']=lambda key:46000. if key=='DATE' else None
        first=self.rt.call('pl:new-id');second=self.rt.call('pl:new-id')
        self.assertNotEqual(first,second)
        self.assertEqual(self.database['SEQUENCE'],2)
    def test_style_display_and_move_keep_physical_values(self):
        changed=self.rt.call('pl:ai-change-plant',self.p,[['style','simple'],['factor',.8],['dx_m',-2.]])
        for key in ['id','spec_no','dbh','height','crown']:
            self.assertEqual(self.get(key,changed),self.get(key,self.p))
        self.assertEqual(self.get('style',changed),1)
    def test_invalid_size_and_unknown_fields_rejected(self):
        for changes in [[['crown',0.]], [['dbh',-1.]], [['crown','5']], [['script','(erase)']]]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.rt.call('pl:ai-change-plant',self.p,changes)
    def test_exact_species_lookup_sets_name_identity_and_kind(self):
        self.rt.builtins['pl:catalog']=lambda:[self.species()]
        p=self.rt.call('pl:ai-change-plant',self.p,[['name',gbk(' 银杏 ')]])
        p=self.rt.call('pl:ai-species',p,self.p,[['name',gbk('银杏')]])
        self.assertEqual(self.get('species_id',p),'GINKGO')
        self.assertEqual(chinese(self.get('name',p)),'银杏')
    def test_unknown_species_requires_explicit_category(self):
        p=self.put('name',gbk('新植物'))
        with self.assertRaises(ValueError):
            self.rt.call('pl:ai-species',p,self.p,[['name',gbk('新植物')]])
        result=self.rt.call('pl:ai-species',p,self.p,[['name',gbk('新植物')],['new_species_category',2]])
        self.assertTrue(self.get('species_id',result).startswith('AI_NEW_'))
    def test_duplicate_species_name_requires_id(self):
        rows=[self.species(),self.species()]
        rows[1]=self.rt.call('pl:put',Sym('id'),'SECOND',rows[1])
        self.rt.builtins['pl:catalog']=lambda:rows
        p=self.put('name',gbk('银杏'))
        with self.assertRaises(ValueError):
            self.rt.call('pl:ai-species',p,self.p,[['name',gbk('银杏')]])
    def test_preview_is_read_only_and_reserves_one_number_for_batch(self):
        self.plants['A2']=self.p
        self.states['A2']=['original']
        original=self.database.copy()
        output=self.rt.call('pl:ai-preview',self.args())
        self.assertTrue(self.rt.call('pl:ai-get','ok',output[1:]))
        plan=self.rt.env[Sym('pl:*ai-plans*')][0]
        proposed=[entry[2] for entry in plan[2]]
        self.assertEqual([self.get('spec_no',p) for p in proposed],['P002','P002'])
        self.assertEqual(self.get('id',proposed[0]),self.get('id',proposed[1]))
        self.assertEqual(self.database,original)
    def test_preview_style_keeps_original_number(self):
        self.rt.call('pl:ai-preview',self.args({'style':'simple'}))
        proposed=self.rt.env[Sym('pl:*ai-plans*')][0][2][0][2]
        self.assertEqual(self.get('spec_no',proposed),'P001')
    def test_changed_object_rejects_apply_before_any_mutation(self):
        self.rt.call('pl:ai-preview',self.args())
        self.states['A1']=['changed']
        with self.assertRaisesRegex(ValueError,'变化'):
            self.rt.call('pl:ai-apply',[['plan_id','a'*32]])
        self.assertEqual(self.database['AI_USED_IDS'],None)
    def test_changed_plot_options_invalidates_plan(self):
        self.rt.call('pl:ai-preview',self.args())
        self.database['PLOT_OPTIONS']=[Pair(Sym('scale'),200)]
        with self.assertRaisesRegex(ValueError,'数据已变化'):
            self.rt.call('pl:ai-apply',[['plan_id','a'*32]])
    def test_visible_defs_remove_former_used_keep_planned_and_current(self):
        removed=self.put('id','OLD')
        planned=self.put('id','PLANNED')
        self.database['PLANTS']=[self.p,removed,planned]
        self.database['AI_USED_IDS']=['P1','OLD']
        visible=self.rt.call('pl:ai-visible-defs')
        self.assertEqual([self.get('id',p) for p in visible],['P1','PLANNED'])
    def test_quantity_rows_keep_dimensions_and_unit(self):
        rows=self.rt.call('pl:ai-quantity-rows',self.rt.call('pl:add-count',self.p,None))
        self.assertEqual([chinese(v) for v in rows[0]],['P001','香樟','12','——','400','300','1','株'])
for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in AIRules.__dict__: setattr(AIRules,name,None)
