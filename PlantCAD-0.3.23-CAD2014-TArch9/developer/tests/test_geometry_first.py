import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class GeometryFirst(fixtures.Rules):
 def setUp(self):
  super().setUp();self.db={};self.data={};self.calls=[]
  self.rt.builtins.update({'pl:db-get':lambda k,d:self.db.get(k,d),'pl:db-put':lambda k,v:self.db.__setitem__(k,v) or v,
    'pl:data-get':lambda e,k:self.data.get(e,{}).get(k),
    'pl:data-put':lambda e,k,v:self.data.setdefault(e,{}).__setitem__(k,v) or v,
    'entget':lambda e:[Pair(5,e)],'pl:mark':lambda *a:self.calls.append(('mark',a)),
    'pl:units':lambda:1000.,'pl:area-value':lambda e:12.5,'pl:role':lambda e:'AREA',
    'pl:writable':lambda e:True})
 def forbidden(self,*args):self.fail('Geometry requested plant information')
 def session(self,units=True):
  self.rt.env[Sym('pl:*native-ui*')]=True
  self.rt.builtins.update({'boundp':lambda s:True,'pl:current':self.forbidden,'pl:design-start':self.forbidden,'pl:library-work':self.forbidden,
    'pl:area-selection':lambda:['A','B'],
    'pl:native-area-begin':lambda handles,layer:self.calls.append('geometry') or [2],
    'pl:require-units':lambda:self.calls.append('unit_conversion') or units,
    'pl:init-layers':lambda:self.calls.append('layers'),
    'pl:native-area-total':lambda:[25000000.],
    'pl:range-session-loop':lambda:self.calls.append('point_areas'),
    'pl:native-area-end':lambda:self.calls.append('end'),
    'vl-catch-all-apply':lambda fn,args:self.rt.call(str(fn),*(args or [])),
    'vl-catch-all-error-p':lambda r:False})
 def test_geometry_command_does_not_require_a_plant_or_plant_kind(self):
  self.session();self.rt.call('pl:geometry-area-work')
  self.assertEqual(self.calls,['geometry','unit_conversion','layers','point_areas','end'])
  self.assertIsNone(self.rt.env[Sym('pl:*range-kind*')])
 def test_shrub_and_ground_entries_also_work_without_a_current_plant(self):
  for name in ['pl:shrub-work','pl:ground-work']:
   self.calls.clear();self.session();self.rt.call(name)
   self.assertEqual(self.calls,['geometry','unit_conversion','layers','point_areas','end'])
 def test_cancel_unit_conversion_keeps_geometric_calculation_and_releases_session(self):
  self.session(False);self.rt.call('pl:geometry-area-work')
  self.assertEqual(self.calls,['geometry','unit_conversion','end'])
  self.assertEqual(self.db,{})
 def test_register_geometry_stores_only_geometry_identity_and_units(self):
  self.db.update(PLANTS=[self.p],CURRENT='unrelated-tree')
  self.rt.call('pl:register-geometric-area','AB',-1)
  self.rt.call('pl:register-geometric-area','AC',-1)
  self.assertEqual(self.data['AB'],{'AREA_NO':'A1','AREA_KIND':-1,'UNITS':1000.})
  self.assertEqual(self.data['AC']['AREA_NO'],'A2')
  self.assertEqual(self.db['PLANTS'],[self.p]);self.assertEqual(self.db['CURRENT'],'unrelated-tree')
 def test_unassigned_geometry_immediately_has_number_and_area_label(self):
  self.data['AB']={'AREA_NO':'A1'}
  text=chinese(self.rt.call('pl:area-label-text','AB'))
  self.assertEqual(text,r'区域 A1\P12.50 平方米')
 def test_association_changes_only_plant_reference_and_not_measured_geometry(self):
  self.data['AB']={'AREA_NO':'A1','UNITS':1000.,'AREA_KIND':-1}
  self.assertTrue(self.rt.call('pl:bind-area-plant','AB',self.p))
  self.assertEqual(self.data['AB'],{'AREA_NO':'A1','UNITS':1000.,'AREA_KIND':-1,'AREA_PLANT':self.p})
  self.assertEqual(self.rt.call('pl:area-value','AB'),12.5)
  self.assertEqual(chinese(self.rt.call('pl:area-label-text','AB')),r'香樟\P12.50 平方米')
 def test_locked_area_is_not_rebound(self):
  self.rt.builtins['pl:writable']=lambda e:False
  self.assertIsNone(self.rt.call('pl:bind-area-plant','AB',self.p));self.assertEqual(self.data,{})
 def test_unassigned_areas_are_in_statistics_without_creating_plant_records(self):
  self.rt.builtins['pl:plant']=lambda e:None
  self.data={'AB':{'AREA_NO':'A1'},'AC':{'AREA_NO':'A2'}}
  rows=self.rt.call('pl:count-rows',['AB','AC'])
  self.assertEqual(len(rows),2);self.assertEqual(sum(row[2] for row in rows),25.)
  self.assertEqual([chinese(self.get('name',row[1])) for row in rows],['未关联植物']*2)
  self.assertEqual([self.get('spec_no',row[1]) for row in rows],['A1','A2'])
  self.assertEqual(self.db,{})
 def test_legacy_plant_area_still_uses_existing_species(self):
  self.data['AB']={'AREA_PLANT':self.p}
  p=self.rt.call('pl:area-quantity-definition','AB')
  self.assertEqual(self.get('name',p),self.get('name',self.p))
  self.assertEqual(chinese(self.get('quantity_unit',p)),'平方米')

 def batch_setup(self,rows):
  self.rt.env[Sym('pl:*range-kind*')]=-1
  self.rt.builtins.update({'pl:layer-issue':lambda layer:None,'pl:native-area-export-all':lambda layer:rows,
    'handent':lambda handle:handle,'pl:create-area-label':lambda e,point:self.calls.append(('label',e,point)) or e+'_LABEL',
    'pl:all-labels':lambda:[],
    'vl-catch-all-apply':lambda fn,args:self.rt.call(str(fn),*(args or [])),
    'vl-catch-all-error-p':lambda r:False,
    'getpoint':self.forbidden})
 def test_all_regions_are_registered_and_labelled_without_clicking(self):
  self.batch_setup(['AREA_BATCH',['AB',[1.,2.,0.],0,2.5],['AC',[4.,5.,0.],1,3.]])
  self.rt.call('pl:range-session-loop')
  self.assertEqual(self.db['AREA_SEQUENCE'],2)
  self.assertEqual(self.data['AB']['AREA_REPAIRED'],0);self.assertEqual(self.data['AC']['AREA_REPAIRED'],1)
  self.assertEqual(self.data['AC']['AREA_LABEL_RADIUS'],3.)
  self.assertEqual([call for call in self.calls if call[0]=='label'],[('label','AB',[1.,2.,0.]),('label','AC',[4.,5.,0.])])
 def test_repeat_batch_does_not_create_duplicate_labels_or_area_numbers(self):
  self.batch_setup(['AREA_BATCH']);self.rt.call('pl:range-session-loop')
  self.assertEqual(self.db,{});self.assertEqual(self.calls,[])
 def test_fitted_area_retains_provenance_when_reused(self):
  self.batch_setup(['AREA_BATCH',['AB',[1.,2.,0.],0,2.5,1]])
  self.rt.call('pl:range-session-loop')
  self.assertEqual(self.data['AB']['AREA_FITTED'],1)
  self.batch_setup(['AREA_BATCH',['AB',[1.,2.,0.],0,2.5,0]])
  self.rt.call('pl:range-session-loop')
  self.assertEqual(self.data['AB']['AREA_FITTED'],1)
 def test_area_information_reports_measurement_and_fitting(self):
  self.data['AB']={'AREA_NO':'A17','AREA_FITTED':1}
  messages=[]
  self.rt.builtins.update({'entsel':lambda prompt:['AB',[0,0,0]],'alert':lambda text:messages.append(chinese(text))})
  self.rt.call('pl:info-work')
  self.assertIn('A17',messages[0]);self.assertIn('12.50 平方米',messages[0]);self.assertIn('局部拟合',messages[0])
 def test_area_information_follows_area_annotation_to_source(self):
  self.data['AB']={'AREA_NO':'A23'}
  messages=[]
  self.rt.builtins.update({'entsel':lambda prompt:['LABEL',[0,0,0]],'pl:role':lambda e:'AREA_LABEL' if e=='LABEL' else 'AREA','pl:source':lambda e:'AB','alert':lambda text:messages.append(chinese(text))})
  self.rt.call('pl:info-work')
  self.assertIn('A23',messages[0]);self.assertNotIn('局部拟合',messages[0])
 def test_rescan_existing_area_repairs_missing_label_without_renumbering(self):
  self.batch_setup(['AREA_BATCH',['AB',[1.,2.,0.],0,2.5]])
  self.data['AB']={'AREA_NO':'A17','UNITS':1000.,'AREA_REPAIRED':1,'AREA_PLANT':self.p}
  self.rt.call('pl:range-session-loop')
  self.assertEqual(self.data['AB']['AREA_NO'],'A17')
  self.assertEqual(self.data['AB']['AREA_REPAIRED'],1)
  self.assertEqual(self.data['AB']['AREA_PLANT'],self.p)
  self.assertNotIn('AREA_SEQUENCE',self.db)
  self.assertIn(('label','AB',[1.,2.,0.]),self.calls)
 def test_existing_inside_label_is_reused_and_positioned_interior(self):
  self.batch_setup(['AREA_BATCH',['AB',[1.,2.,0.],0,2.5]])
  self.data['AB']={'AREA_NO':'A17','UNITS':1000.}
  self.rt.builtins.update({'pl:all-labels':lambda:['LABEL'],
   'pl:role':lambda e:'AREA_LABEL' if e=='LABEL' else 'AREA',
   'pl:source':lambda e:'AB','entget':lambda e:[Pair(0,'MTEXT' if e=='LABEL' else 'REGION'),Pair(5,e)],
   'entmod':lambda ed:self.calls.append(('update',ed)) or True,'entupd':lambda *args:None})
  self.rt.call('pl:range-session-loop')
  self.assertFalse(any(c[0]=='label' for c in self.calls))
  self.assertTrue(any(c[0]=='update' for c in self.calls))
 def test_repaired_region_label_discloses_inferred_boundary(self):
  self.data['AB']={'AREA_NO':'A1','AREA_REPAIRED':1}
  text=chinese(self.rt.call('pl:area-label-text','AB'))
  self.assertIn('约 12.50',text);self.assertIn('补线推定',text)

for name in dir(fixtures.Rules):
 if name.startswith('test_') and name not in GeometryFirst.__dict__:setattr(GeometryFirst,name,None)
if __name__=='__main__':unittest.main()
