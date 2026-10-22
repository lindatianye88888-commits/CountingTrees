import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class WorkflowFeedback(fixtures.Rules):
 def memory(self,plants=None):
  db={'PLANTS':plants or []}
  self.rt.builtins.update({'pl:db-get':lambda k,d:db.get(k,d),'pl:db-put':lambda k,v:db.__setitem__(k,v) or v,'getvar':lambda key:46000.1})
  return db
 def test_new_tree_has_editable_initial_size(self):
  p=self.rt.call('pl:seed-size',self.p,None)
  self.assertEqual([self.get(k,p) for k in ['crown','height','dbh','caliper']],[3.,4.,12.,0.])
 def test_grass_has_no_required_dimensions_and_keeps_crown_unknown(self):
  p=self.rt.call('pl:seed-size',self.put('kind',2),None)
  self.assertIsNone(self.rt.call('pl:insert-error',p))
  self.assertEqual([self.get(k,p) for k in ['crown','height','dbh','caliper']],[0.,0.,0.,0.])
  self.assertEqual(self.rt.call('pl:diameter',p,1000),150.)
  self.assertEqual(self.label(2,p=p),'香樟')
 def test_accepted_sizes_are_remembered_across_new_specifications(self):
  db=self.memory();p=self.put('species_id','S1',self.put('crown',4.5))
  self.rt.call('pl:remember-size',p)
  fresh=self.put('species_id','S1',self.put('crown',0.))
  result=self.rt.call('pl:seed-size',fresh,db['SIZE_DEFAULTS'])
  self.assertEqual(self.get('crown',result),4.5)
  self.assertEqual(self.get('id',result),self.get('id',fresh))
 def test_remembered_zero_grass_size_does_not_receive_a_tree_default(self):
  db=self.memory();p=self.put('kind',2)
  for key in ['crown','height','dbh','caliper']:p=self.put(key,0.,p)
  self.rt.call('pl:remember-size',p)
  result=self.rt.call('pl:seed-size',self.p,db['SIZE_DEFAULTS'])
  self.assertEqual(self.get('crown',result),0.)
 def test_existing_project_sizes_seed_defaults_after_upgrade(self):
  p=self.put('crown',5.5);self.memory([p])
  defaults=self.rt.call('pl:project-size-defaults')
  result=self.rt.call('pl:seed-size',self.p,defaults)
  self.assertEqual(self.get('crown',result),5.5)
 def test_project_search_groups_classes_and_resolves_displayed_rows(self):
  a=self.put('spec_no','P001',self.put('kind',2))
  b=self.put('spec_no','P002',self.put('kind',0))
  c=self.put('spec_no','P003',self.put('kind',1))
  rows=self.rt.call('pl:project-filter',[a,b,c],-1,'')
  self.assertEqual([self.get('spec_no',p) for p in rows],['P002','P003','P001'])
  self.assertEqual(self.rt.call('pl:project-filter',[a,b,c],-1,'p003'),[c])
  self.assertEqual(self.rt.call('pl:project-filter',[a,b,c],2,gbk('香')),[a])
 def test_unit_calibration_normalizes_m_cm_and_mm_without_moving_geometry(self):
  for distance,expected in [(5,1),(500,100),(5000,1000)]:
   self.assertEqual(self.rt.call('pl:calibrated-units',distance,500.),expected)
  self.assertIsNone(self.rt.call('pl:calibrated-units',0.,500.))
  self.assertIsNone(self.rt.call('pl:calibrated-units',500.,None))
 def test_insunits_adapts_only_known_metadata(self):
  self.assertEqual([self.rt.call('pl:unit-from-insunits',n) for n in [4,6,5,0,1]],[0,1,2,-1,-1])
 def test_physical_edit_allocates_new_identity_and_preserves_old_definition(self):
  original=self.put('spec_no','P001');db=self.memory([original])
  result=self.rt.call('pl:prepare-edited-spec',self.put('crown',5.,original),original,[original])
  self.assertNotEqual(self.get('id',result),self.get('id',original))
  self.assertEqual(self.get('spec_no',result),'P002')
  self.rt.call('pl:save-def',result)
  self.assertEqual(len(db['PLANTS']),2)
  self.assertEqual(self.get('crown',db['PLANTS'][0]),3.)
 def test_drawing_style_change_does_not_create_new_species(self):
  original=self.put('spec_no','P001');self.memory([original])
  result=self.rt.call('pl:prepare-edited-spec',self.put('factor',.7,original),original,[original])
  self.assertEqual(self.get('id',result),self.get('id',original))
  self.assertEqual(self.get('spec_no',result),'P001')
 def test_curved_region_uses_stored_units_and_live_native_area(self):
  self.rt.builtins.update({'pl:role':lambda e:'AREA','pl:data-get':lambda e,k:1000.,'vlax-ename->vla-object':lambda e:e,
   'entget':lambda e:[Pair(0,'REGION')],'boundp':lambda s:False,'vl-catch-all-apply':lambda fn,args:self.rt.call(str(fn),*args),
   'vl-catch-all-error-p':lambda r:False,'vla-get-area':lambda e:12500000.})
  self.assertEqual(self.rt.call('pl:area-value','region'),12.5)
 def test_grass_does_not_open_crown_completion_dialog(self):
  p=self.put('kind',2,self.put('crown',0.))
  self.rt.builtins['pl:edit-dialog']=lambda _:self.fail('Grass should permit no dimensions')
  self.assertEqual(self.rt.call('pl:resolve-placement',p),p)

for name in dir(fixtures.Rules):
 if name.startswith('test_') and name not in WorkflowFeedback.__dict__:setattr(WorkflowFeedback,name,None)
if __name__=='__main__':unittest.main()
