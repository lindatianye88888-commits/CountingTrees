import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk,chinese

class PerformanceFeedback(fixtures.Rules):
    def test_read_only_dialogs_do_not_trigger_drawing_sync(self):
        self.rt.env[Sym('pl:*drawing-changed*')]=None
        for fn in ['pl:library-work','pl:design-start','pl:info-work','pl:count-work']:
            self.assertFalse(self.rt.call('pl:run-needs-sync',Sym(fn)))
        self.rt.env[Sym('pl:*drawing-changed*')]=True
        self.assertTrue(self.rt.call('pl:run-needs-sync',Sym('pl:edit-current-work')))
        self.assertFalse(self.rt.call('pl:run-needs-sync',Sym('pl:sync-drawing')))

    def test_current_plant_selection_is_ui_only_but_spec_edits_are_not(self):
        self.rt.builtins['vlax-ldata-put']=lambda *args:True
        self.rt.env[Sym('pl:*drawing-changed*')]=None
        self.rt.call('pl:db-put','CURRENT','P001')
        self.assertFalse(self.rt.env.get(Sym('pl:*drawing-changed*')))
        self.rt.call('pl:db-put','PLANTS',[self.p])
        self.assertTrue(self.rt.env[Sym('pl:*drawing-changed*')])

    def test_shrub_ball_catalogue_view_uses_real_shrub_species_and_role(self):
        row=[Pair(Sym('id'),'S1'),Pair(Sym('name'),gbk('海桐')),Pair(Sym('category'),2),Pair(Sym('region'),'')]
        selected=self.rt.call('pl:species-filter',[row],10,'','')
        self.assertEqual(len(selected),1)
        self.assertEqual(self.get('placement_kind',selected[0]),3)
        self.assertEqual(self.get('category',selected[0]),2)
        self.assertIn('灌木球',chinese(self.rt.call('pl:species-caption',selected[0])))
        self.assertIn(gbk('灌木球'),self.rt.call('pl:category-names'))

    def test_same_species_can_be_selected_as_shrub_and_ball(self):
        row=[Pair(Sym('id'),'S1'),Pair(Sym('name'),gbk('海桐')),Pair(Sym('category'),2),Pair(Sym('region'),'')]
        ball=self.rt.call('pl:species-filter',[row],10,'','')[0]
        result=self.rt.call('pl:species-merge-selection',[row],[ball],[0])
        self.assertEqual(len(result),2)
        self.assertEqual(self.rt.call('pl:indices-text',result,[ball]),'0')

    def test_project_filter_includes_new_roles(self):
        rows=[self.put('kind',kind,self.put('spec_no',f'P{kind}')) for kind in range(6)]
        self.assertEqual(len(self.rt.call('pl:project-filter',rows,-1,'')),6)
        self.assertEqual(self.rt.call('pl:project-filter',rows,3,''),[rows[3]])

    def test_area_measurement_is_cached_within_sync_only(self):
        calls=[]
        self.rt.builtins['pl:uncached-area-value']=lambda e:calls.append(e) or 12.5
        self.rt.env[Sym('pl:*sync-busy*')]=True
        self.assertEqual(self.rt.call('pl:area-value','A'),12.5)
        self.assertEqual(self.rt.call('pl:area-value','A'),12.5)
        self.assertEqual(calls,['A'])
        self.rt.env[Sym('pl:*sync-busy*')]=None
        self.rt.call('pl:area-value','A')
        self.assertEqual(calls,['A','A'])

    def test_same_scope_count_is_reused_across_schedules(self):
        calls=[]
        self.rt.builtins['pl:output-table-objects']=lambda scope:['A']
        self.rt.builtins['pl:count-rows']=lambda objects:calls.append(objects) or [[None,self.p,1]]
        self.rt.env[Sym('pl:*sync-busy*')]=True
        scope=[Pair(Sym('scope'),'model')]
        self.rt.call('pl:output-counts',scope);self.rt.call('pl:output-counts',scope)
        self.assertEqual(calls,[['A']])

    def test_fill_failure_keeps_created_annotation(self):
        events=[]
        opts=[Pair(Sym('fill'),1),Pair(Sym('bind'),0)]
        self.rt.builtins.update({
            'pl:init-layers':lambda:None,'pl:selected-areas':lambda:['A'],
            'pl:area-output-options':lambda:opts,'pl:current':lambda:self.p,
            'pl:data-get':lambda e,key:self.p if key=='AREA_PLANT' else [0.,0.,0.],
            'getpoint':lambda *args:[1.,2.,0.],'trans':lambda p,*args:p,'initget':lambda *args:True,
            'pl:area-title':lambda e:gbk('海桐'),'pl:area-number':lambda e:'A1',
            'pl:area-label-geometry':lambda *args:[[1.,2.,0.],[3.,2.,0.]],
            'pl:area-output-plant':lambda *args:self.p,
            'pl:data-put':lambda *args:True,'pl:db-put':lambda *args:True,
            'pl:output-area-label':lambda *args:events.append('label'),
            'pl:fill-area':lambda e:events.append('fill') or (_ for _ in []).throw(ValueError('unavailable')),
            'vl-catch-all-error-p':lambda value:isinstance(value,Exception),
            'vl-catch-all-error-message':str,
        })
        def caught(fn,args):
            try:return self.rt.call(str(fn),*(args or []))
            except Exception as error:return error
        self.rt.builtins['vl-catch-all-apply']=caught
        self.rt.call('pl:output-area-work')
        self.assertEqual(events,['label','fill'])
        self.assertFalse(self.rt.env.get(Sym('pl:*failure*')))

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in PerformanceFeedback.__dict__:setattr(PerformanceFeedback,name,None)
if __name__=='__main__':unittest.main()
