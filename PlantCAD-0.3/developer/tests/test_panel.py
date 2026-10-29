from pathlib import Path
import unittest
import test_rules as fixtures
from lisp_harness import Sym, Pair, chinese

class PanelRules(fixtures.Rules):
    def panel_state(self,p,units=1000):
        self.rt.builtins.update({
            'pl:current':lambda:p,
            'pl:units':lambda:units,
            'pl:db-get':lambda key,default:default,
            'pl:layer-issue':lambda name:None,
        })
        result=self.rt.call('pl:ui-state')
        return {row[0]:row[1] for row in result[1:]}

    def test_panel_reports_current_species_spec_crown_and_units(self):
        p=self.put('spec_no','P007')
        state=self.panel_state(p)
        self.assertEqual(state['spec_no'],'P007')
        self.assertEqual(chinese(state['name']),'香樟')
        self.assertEqual(state['crown_m'],3.)
        self.assertEqual(state['units_per_m'],1000.)

    def test_missing_crown_remains_unknown_and_panel_requests_completion(self):
        state=self.panel_state(self.put('crown',0.))
        self.assertEqual(state['crown_m'],0.)
        self.assertIn('冠幅',chinese(state['hint']))

    def resolve_setup(self,p,result):
        writes=[]
        self.rt.builtins['vl-catch-all-apply']=lambda fn,args:self.rt.call(str(fn),*(args or []))
        self.rt.builtins['vl-catch-all-error-p']=lambda result:False
        def edit(value):
            self.assertTrue(self.rt.env[Sym('pl:*require-crown*')])
            self.assertEqual(value,p)
            return result
        self.rt.builtins['pl:edit-dialog']=edit
        self.rt.builtins['pl:save-def']=lambda value:writes.append(('spec',value))
        self.rt.builtins['pl:db-put']=lambda key,value:writes.append((key,value))
        return writes

    def test_placement_opens_exact_current_spec_and_saves_completion(self):
        p=self.put('crown',0.)
        complete=self.put('crown',4.5,p)
        writes=self.resolve_setup(p,complete)
        self.assertEqual(self.rt.call('pl:resolve-placement',p),complete)
        self.assertEqual(writes,[('spec',complete),('CURRENT',self.get('id',complete))])
        self.assertIsNone(self.rt.env[Sym('pl:*require-crown*')])

    def test_cancel_missing_crown_does_not_save_or_insert(self):
        p=self.put('crown',0.)
        writes=self.resolve_setup(p,None)
        self.assertIsNone(self.rt.call('pl:resolve-placement',p))
        self.assertEqual(writes,[])
        self.assertIsNone(self.rt.env[Sym('pl:*require-crown*')])

    def test_valid_crown_needs_no_completion_dialog(self):
        self.rt.builtins['pl:edit-dialog']=lambda _:self.fail('Unexpected editor')
        self.assertEqual(self.rt.call('pl:resolve-placement',self.p),self.p)

    def test_hidden_frozen_and_locked_layers_have_distinct_actionable_failures(self):
        for flags,color,expected in [(4,3,'锁定'),(1,3,'冻结'),(0,-3,'关闭'),(0,3,None)]:
            self.rt.builtins['tblsearch']=lambda *args,f=flags,c=color:[Pair(70,f),Pair(62,c)]
            result=self.rt.call('pl:layer-issue','TEST')
            if expected:self.assertIn(expected,chinese(result))
            else:self.assertIsNone(result)

    def test_hidden_tree_layer_warning_does_not_imply_area_is_blocked(self):
        self.panel_state(self.p)
        self.rt.builtins['pl:layer-issue']=lambda name:__import__('lisp_harness').gbk('目标图层已关闭')
        result=self.rt.call('pl:ui-state');state={row[0]:row[1] for row in result[1:]}
        self.assertIn('几何面积识别不受树木图层影响',chinese(state['hint']))

    def test_circle_and_simple_symbol_previews_are_closed_and_within_view(self):
        shapes=[]
        for style in [0,1]:
            lines=self.rt.call('pl:preview-lines',style,180,90)
            self.assertEqual(len(lines),48)
            self.assertEqual(lines[0][:2],lines[-1][2:])
            self.assertTrue(all(0<=v<=180 if i%2==0 else 0<=v<=90 for line in lines for i,v in enumerate(line)))
            shapes.append(lines)
        self.assertNotEqual(shapes[0],shapes[1])

    def test_native_preview_receives_real_block_scale_and_paper_text_height(self):
        captured=[]
        self.rt.env[Sym('pl:*native-ui*')]=True
        self.rt.builtins['boundp']=lambda symbol:True
        self.rt.builtins['getvar']=lambda key:{'TILEMODE':1,'CVPORT':2}[key]
        self.rt.builtins['pl:db-get']=lambda key,default:default
        self.rt.builtins['pl:preview-point']=lambda *args:captured.append(args) or [12.,34.,0.]
        self.assertEqual(self.rt.call('pl:pick-placement',self.p,1000.),[12.,34.,0.])
        self.assertEqual(captured[0][0],'PL02_CIRCLE')
        self.assertEqual(captured[0][1],3000.)
        self.assertEqual(captured[0][2],1000.)
        self.assertEqual(chinese(captured[0][3]),'香樟')

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in PanelRules.__dict__:
        setattr(PanelRules,name,None)

if __name__=='__main__': unittest.main()
