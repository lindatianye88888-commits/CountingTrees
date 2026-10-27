"""User-facing order, cancellation and exact specification selection for area leaders."""
import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk

class AreaLeaderPicks(fixtures.Rules):
    def geometry(self,points):
        points=iter(points);self.prompts=[]
        self.rt.builtins.update({'abs':abs,'getpoint':lambda *args:self.prompts.append(args) or next(points),
            'trans':lambda p,*args:p,'pl:area-number':lambda e:'A1'})
        return self.rt.call('pl:area-label-geometry','A',[2.,2.,0.])

    def test_first_point_is_elbow_second_point_sets_left_tail(self):
        self.assertEqual(self.geometry([[-5.,4.,0.],[-20.,8.,0.]]),[[-5.,4.,0.],[-20.,4.,0.]])
        self.assertEqual(self.prompts[1][0],[-5.,4.,0.])

    def test_tail_can_point_right_and_is_horizontal(self):
        self.assertEqual(self.geometry([[3.,4.,0.],[20.,-8.,2.]]),[[3.,4.,0.],[20.,4.,0.]])

    def test_zero_length_horizontal_tail_reprompts(self):
        self.assertEqual(self.geometry([[3.,4.,0.],[3.,8.,0.],[10.,7.,0.]]),[[3.,4.,0.],[10.,4.,0.]])
        self.assertEqual(len(self.prompts),3)

    def test_enter_at_either_point_skips_region(self):
        self.assertIsNone(self.geometry([None]))
        self.assertIsNone(self.geometry([[3.,4.,0.],None]))

    def workflow(self,geometry=True,chosen=True):
        events=[];opts=[Pair(Sym('layout'),0),Pair(Sym('fill'),1),Pair(Sym('bind'),0)]
        self.rt.builtins.update({'pl:import-area-label-edits':lambda:None,'pl:init-layers':lambda:None,
            'pl:selected-areas':lambda:['A'],'pl:area-output-options':lambda:opts,'pl:current':lambda:self.p,
            'pl:data-get':lambda e,k:{'AREA_PLANT':self.p,'AREA_ANCHOR':[2.,2.,0.]}.get(k),
            'pl:area-label-geometry':lambda *args:events.append('picks') or ([[-5.,4.,0.],[-20.,4.,0.]] if geometry else None),
            'pl:area-output-plant':lambda *args:events.append('species') or (self.p if chosen else None),
            'pl:data-put':lambda *args:events.append('bind'),'pl:db-put':lambda *args:True,
            'pl:output-area-label':lambda *args:events.append(('label',args)),
            'pl:try-fill-area':lambda *args:events.append('fill')})
        self.rt.call('pl:output-area-work');return events

    def test_geometry_is_picked_before_species_and_fill(self):
        events=self.workflow();self.assertEqual(events[:3],['picks','species','bind'])
        self.assertEqual(events[-1],'fill')
        args=events[3][1];self.assertEqual(args[2],[-20.,4.,0.])
        self.assertEqual(self.get('elbow',args[3]),[-5.,4.,0.]);self.assertEqual(self.get('layout',args[3]),0)

    def test_cancelled_picks_leave_original_binding_label_and_fill(self):
        self.assertEqual(self.workflow(geometry=False),['picks'])

    def test_cancelled_species_leave_original_binding_label_and_fill(self):
        self.assertEqual(self.workflow(chosen=False),['picks','species'])

    def accept(self,name,defs,picked=None):
        self.done=[];self.alerts=[]
        self.rt.env[Sym('pl:*area-species-picked*')]=picked
        self.rt.builtins.update({'get_tile':lambda k:gbk(name),'pl:defs':lambda:defs,
            'done_dialog':lambda n:self.done.append(n),'alert':lambda s:self.alerts.append(s)})
        self.rt.call('pl:area-species-accept')
        return self.rt.env.get(Sym('pl:*area-species-result*'))

    def test_same_name_keeps_exact_selected_specification(self):
        large=self.put('id','P2',self.put('crown',5.))
        result=self.accept('香樟',[self.p,large],large)
        self.assertEqual(result,['plant',large]);self.assertEqual(self.done,[1])

    def test_ambiguous_typed_name_requires_explicit_specification(self):
        self.assertIsNone(self.accept('香樟',[self.p,self.put('id','P2')]))
        self.assertEqual(self.done,[]);self.assertTrue(self.alerts)

    def test_typing_different_name_does_not_silently_keep_selected_species(self):
        self.assertEqual(self.accept('红叶石楠',[self.p],self.p),['name',gbk('红叶石楠')])

    def test_unique_number_resolves_exact_existing_specification(self):
        p=self.put('spec_no','P123')
        self.assertEqual(self.accept('P123',[self.p,p]),['plant',p])

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in AreaLeaderPicks.__dict__:setattr(AreaLeaderPicks,name,None)
if __name__=='__main__':unittest.main()
