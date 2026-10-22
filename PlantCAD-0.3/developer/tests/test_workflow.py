import math
import re
import unittest
from pathlib import Path
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class WorkflowRules(fixtures.Rules):
    def setUp(self):
        super().setUp()
        self.rt.builtins.update({
            'abs':abs,'rem':lambda a,b:a%b,
            'last':lambda xs:xs[-1],
            'caar':lambda xs:xs[0][0],
            'cadar':lambda xs:xs[0][1],
            'equal':lambda a,b,fuzz=0: all(abs(x-y)<=fuzz for x,y in zip(a,b)) and len(a)==len(b) if fuzz and isinstance(a,list) and isinstance(b,list) else a==b,
        })
        self.box=[[0.,0.],[10.,0.],[10.,10.],[0.,10.]]

    def test_open_path_exact_and_non_exact_spacing(self):
        self.assertEqual(self.rt.call('pl:line-stations',10.,2.,None),[0.,2.,4.,6.,8.,10.])
        self.assertEqual(self.rt.call('pl:line-stations',10.,3.,None),[0.,3.,6.,9.])

    def test_closed_path_has_no_duplicate_endpoint(self):
        self.assertEqual(self.rt.call('pl:line-stations',10.,2.,True),[0.,2.,4.,6.,8.])

    def test_path_invalid_or_excessive_count_is_rejected_before_mutation(self):
        for length,step in [(0,2),(10,0),(10,-1),(100000,0.1)]:
            self.assertIsNone(self.rt.call('pl:line-stations',length,step,None))

    def test_polygon_validity_rejects_bow_tie_and_repeated_vertex(self):
        self.assertTrue(self.rt.call('pl:simple-polygon',self.box))
        for poly in [[[0,0],[10,10],[0,10],[10,0]],[[0,0],[10,0],[10,0],[0,10]],[[0,0],[1,0],[2,0]]]:
            self.assertFalse(self.rt.call('pl:simple-polygon',poly))

    def test_polygon_rejects_nonadjacent_touching_edges(self):
        p=[[0,0],[10,0],[10,10],[5,0],[0,10]]
        self.assertFalse(self.rt.call('pl:simple-polygon',p))

    def test_inside_polygon_handles_boundary_and_concavity(self):
        p=[[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]]
        for pt in [[1,7],[7,1],[0,0],[3,4]]:
            self.assertTrue(self.rt.call('pl:inside-polygon',pt,p),pt)
        for pt in [[7,7],[-1,4],[9,0]]:
            self.assertFalse(self.rt.call('pl:inside-polygon',pt,p),pt)

    def test_grid_points_stay_in_concave_boundary(self):
        p=[[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]]
        points=self.rt.call('pl:polygon-grid',p,2.)
        self.assertTrue(points)
        self.assertEqual(len(points),len(set(map(tuple,points))))
        self.assertTrue(all(x<=3 or y<=3 for x,y in points))

    def test_grid_spacing_and_extent(self):
        points=self.rt.call('pl:polygon-grid',self.box,2.)
        self.assertEqual(len(points),25)
        self.assertEqual(points[0],[1.,1.])
        self.assertEqual(points[-1],[9.,9.])

    def test_grid_limits_and_empty_result(self):
        self.assertEqual(self.rt.call('pl:polygon-grid',self.box,.001),Sym('limit'))
        self.assertFalse(self.rt.call('pl:polygon-grid',self.box,100.))
        self.assertIsNone(self.rt.call('pl:polygon-grid',self.box,0.))

    def test_area_is_independent_of_winding_and_survey_coordinate_origin(self):
        for offset in [0.,1e9]:
            p=[[x+offset,y-offset] for x,y in self.box]
            for poly in [p,list(reversed(p))]:
                self.assertAlmostEqual(self.rt.call('pl:polygon-area',poly),100.)

    def test_negative_coordinate_grid(self):
        p=[[x-10,y-10] for x,y in self.box]
        points=self.rt.call('pl:polygon-grid',p,2.)
        self.assertEqual(points[0],[-9.,-9.])
        self.assertEqual(points[-1],[-1.,-1.])

    def test_fractional_area_quantities_do_not_merge_with_tree_counts(self):
        area=self.put('quantity_unit',gbk('平方米'))
        rows=self.rt.call('pl:add-quantity',self.p,1,None)
        rows=self.rt.call('pl:add-quantity',area,12.5,rows)
        rows=self.rt.call('pl:add-quantity',area,3.25,rows)
        self.assertEqual(len(rows),2)
        self.assertEqual([r[2] for r in rows],[1,15.75])
        self.assertEqual(self.rt.call('pl:ai-quantity-rows',rows)[1][-2:],['15.75',gbk('平方米')])

    def test_count_reads_live_quantity_and_skips_invalid_boundary(self):
        self.rt.builtins['pl:quantity-data']=lambda e: {
            'tree':[self.p,1],
            'area':[self.put('quantity_unit',gbk('平方米')),2.75],
            'open_boundary':None
        }[e]
        rows=self.rt.call('pl:count-rows',['tree','area','open_boundary'])
        self.assertEqual([r[2] for r in rows],[1,2.75])

    def test_number_label_uses_current_spec_id(self):
        self.assertEqual(self.label(3,p=self.put('spec_no','P009')),'P009')

    def test_every_floating_menu_action_routes_to_a_real_command(self):
        root=Path(__file__).resolve().parents[2]
        ui=(root/'bridge/src/PlantCADWorkbench.cs').read_text(encoding='utf-8')
        routes=(root/'bridge/src/PlantCADPanel.cs').read_text(encoding='utf-8')
        actions=re.findall(r'new\[\]\{"[^"]+","([^"]+)"\}',ui)
        mapping=dict(re.findall(r'\{"([^"]+)","(PLANTCAD[A-Z]+)"\}',routes))
        self.assertGreaterEqual(len(actions),35)
        for action in actions:
            if action=='reload':continue
            self.assertIn(action,mapping)
            self.assertTrue('c:'+mapping[action].lower() in self.rt.funcs or '[CommandMethod("'+mapping[action]+'"' in (root/'bridge/src/PlantCADBridge.cs').read_text(encoding='utf-8'),mapping[action])

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in WorkflowRules.__dict__:
        setattr(WorkflowRules,name,None)

if __name__=='__main__':unittest.main()
