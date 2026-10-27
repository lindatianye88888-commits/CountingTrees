import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class ProjectImport(fixtures.Rules):
 def setUp(self):
  super().setUp();self.db={};self.data={};self.roles={};self.sources={};self.records={};self.locked=set();self.types={};self.calls=[];self.seq=0
  self.rt.env[Sym('pl:*native-ui*')]=True
  self.rt.builtins.update({'pl:db-get':lambda k,d:self.db.get(k,d),'pl:db-put':lambda k,v:self.db.__setitem__(k,v) or v,
   'equal':lambda a,b,fuzz=0:abs(a-b)<=fuzz if isinstance(a,(int,float)) and isinstance(b,(int,float)) else a==b,
   'pl:data-get':lambda e,k:self.data.get(e,{}).get(k),'pl:data-put':lambda e,k,v:self.data.setdefault(e,{}).__setitem__(k,v) or v,
   'pl:role':lambda e:self.roles.get(e),'pl:source':lambda e:self.sources.get(e),
   'pl:plant':lambda e:self.data.get(e,{}).get('PLANT') if self.roles.get(e)=='TREE' else None,
   'entget':lambda e:[Pair(0,self.types.get(e,'TEXT')),Pair(5,e)],'handent':lambda h:h,
   'pl:writable':lambda e:e not in self.locked,'pl:mark':lambda e,r,h:self.roles.__setitem__(e,r),
   'pl:ss-list':lambda ss:ss,'ssget':lambda *args:list(self.roles),'pl:catalog':lambda:[],
   'pl:native-project-record':lambda h:self.records.get(h),'pl:new-id':self.newid,
   'mapcar':lambda fn,items:[self.rt.call(str(fn),item) for item in (items or [])],
   'pl:remember-size':lambda p:p,'pl:edit-dialog':lambda p:self.calls.append(('confirm',p)) or p,
   'pl:import-area-label-edits':lambda:self.calls.append('area_edits'),
   'pl:sync-drawing':lambda:self.calls.append(('sync',list(self.rt.call('pl:defs') or []))),
   'pl:all-trees':lambda:[e for e in self.roles if self.roles[e]=='TREE'],
   'pl:all-areas':lambda:[e for e in self.roles if self.roles[e]=='AREA'],
   'pl:area-value':lambda e:self.data.get(e,{}).get('AREA_VALUE')})
 def newid(self):
  self.seq+=1;return 'NEW'+str(self.seq)
 def source(self,e,role,p,source=None):
  self.roles[e]=role
  if role=='TREE':self.data[e]={'PLANT':p};self.types[e]='INSERT'
  elif role=='AREA':self.data[e]={'AREA_PLANT':p,'AREA_VALUE':3.13}
  if source:self.sources[e]=source
 def record(self,name,area=0,block=0,spec='',dbh=-1,caliper=-1,height=-1,crown=-1):
  return ['PROJECT_RECORD',gbk(name),spec,area,block,dbh,caliper,height,crown]
 def test_mixed_tree_ball_area_and_linked_labels_are_collected_once_each(self):
  ball=self.put('id','BALL',self.put('spec_no','B01',self.put('kind',3)))
  area=self.put('id','AREA',self.put('quantity_unit',gbk('平方米'),self.put('kind',1)))
  self.source('T','TREE',self.p);self.source('B','TREE',ball);self.source('A','AREA',area)
  for e,role,target in [('TL','LABEL','T'),('BL','LABEL','B'),('AL','AREA_LABEL','A'),('AF','AREA_FILL','A')]:self.source(e,role,None,target)
  result=self.rt.call('pl:collect-project-objects',['TL','T','BL','B','AL','AF','A'])
  self.assertEqual(result,[3,3,0]);self.assertEqual(len(self.rt.call('pl:defs')),3)
  self.assertEqual(sum(isinstance(c,tuple) and c[0]=='sync' for c in self.calls),1)
  self.assertFalse(any(isinstance(c,tuple) and c[0]=='confirm' for c in self.calls))
 def test_repeat_selection_does_not_duplicate_specs_or_quantities(self):
  self.source('T','TREE',self.p)
  self.rt.call('pl:collect-project-objects',['T']);self.rt.call('pl:collect-project-objects',['T'])
  self.assertEqual(len(self.rt.call('pl:defs')),1)
  self.assertEqual(self.rt.call('pl:count-rows',['T'])[0][2],1)
 def test_plain_area_annotation_adds_species_but_no_displayed_quantity(self):
  self.records['TEXT']=self.record('海桐',area=1)
  self.rt.call('pl:collect-project-objects',['TEXT'])
  self.assertEqual(chinese(self.rt.call('pl:defs')[0][1].cdr),'海桐')
  self.assertIsNone(self.rt.call('pl:quantity-data','TEXT'))
  records=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'model')])
  self.assertEqual(len(records),1);self.assertIsNone(records[0][1])
  self.assertEqual(chinese(self.rt.call('pl:output-table-cells',records[0])[7]),'待关联')
 def test_same_name_plain_text_is_confirmed_once_and_gets_one_pending_row(self):
  self.records.update(X=self.record('海桐'),Y=self.record('海桐'))
  self.rt.call('pl:collect-project-objects',['X','Y'])
  self.assertEqual(len([c for c in self.calls if isinstance(c,tuple) and c[0]=='confirm']),1)
  rows=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'model')])
  self.assertEqual(len(rows),1)
 def test_plain_tree_block_counts_as_one_and_bare_diameter_does_not_become_count(self):
  self.records['B']=self.record('银杏',block=1,dbh=12)
  self.rt.call('pl:collect-project-objects',['B'])
  p,n=self.rt.call('pl:quantity-data','B');self.assertEqual(n,1);self.assertEqual(self.get('dbh',p),12)
 def test_pending_name_does_not_add_row_when_same_spec_has_counted_geometry(self):
  self.db['PLANTS']=[self.p];self.source('T','TREE',self.p);self.records['X']=self.record('香樟')
  self.rt.call('pl:collect-project-objects',['X','T'])
  rows=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'model')])
  self.assertEqual(len(rows),1);self.assertEqual(rows[0][1],1)
 def test_name_becomes_measured_area_without_a_duplicate_pending_unit_row(self):
  shrub=self.put('kind',1);self.db['PLANTS']=[shrub];self.records['X']=self.record('香樟')
  self.rt.call('pl:collect-project-objects',['X']);self.source('A','AREA',shrub)
  rows=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'model')])
  self.assertEqual(len(rows),1);self.assertEqual(rows[0][1],3.13)
  self.assertEqual(chinese(self.get('quantity_unit',rows[0][0])),'平方米')
 def test_selected_table_does_not_gain_plants_from_outside_its_scope(self):
  self.records.update(X=self.record('海桐'),Y=self.record('紫珠'))
  self.rt.call('pl:collect-project-objects',['X','Y'])
  rows=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'selected'),Pair(Sym('handles'),['Y'])])
  self.assertEqual(len(rows),1);self.assertEqual(chinese(self.get('name',rows[0][0])),'紫珠')
 def test_category_filter_keeps_pending_names_in_their_own_table(self):
  self.records['X']=self.record('海桐',area=1);self.rt.call('pl:collect-project-objects',['X'])
  rows=self.rt.call('pl:output-table-records','count',[Pair(Sym('scope'),'model'),Pair(Sym('category'),'trees')])
  self.assertEqual(rows,None)
 def test_cancel_unknown_species_leaves_no_binding_or_definition(self):
  self.records['X']=self.record('陌生品种');self.rt.builtins['pl:edit-dialog']=lambda p:None
  self.assertEqual(self.rt.call('pl:collect-project-objects',['X']),[0,0,1]);self.assertEqual(self.data,{})
  self.assertIsNone(self.rt.call('pl:defs'));self.assertFalse(any(isinstance(c,tuple) and c[0]=='sync' for c in self.calls))
 def test_locked_source_is_skipped_without_registering_species(self):
  self.records['X']=self.record('海桐');self.locked.add('X')
  self.assertEqual(self.rt.call('pl:collect-project-objects',['X']),[0,0,1]);self.assertEqual(self.data,{})
 def test_locked_linked_table_stops_before_any_import(self):
  self.roles['TABLE']='TABLE';self.locked.add('TABLE');self.records['X']=self.record('海桐')
  self.rt.builtins['pl:fail']=lambda m:(_ for _ in ()).throw(ValueError(chinese(m)))
  with self.assertRaisesRegex(ValueError,'表格图层已锁定'):self.rt.call('pl:collect-project-objects',['X'])
  self.assertEqual(self.data,{});self.assertNotIn('area_edits',self.calls)
 def test_explicit_diameter_selects_correct_existing_size(self):
  other=self.put('id','OTHER',self.put('dbh',18))
  self.db['PLANTS']=[self.p,other]
  self.records['B']=self.record('香樟',block=1,dbh=18)
  self.rt.call('pl:collect-project-objects',['B'])
  self.assertEqual(self.get('id',self.rt.call('pl:annotation-plant','B')),'OTHER')
  self.assertFalse(any(isinstance(c,tuple) and c[0]=='confirm' for c in self.calls))
 def test_unknown_sizes_are_zero_and_not_copied_from_current_plant(self):
  self.db.update(PLANTS=[self.p],CURRENT='P1');self.records['X']=self.record('海桐',area=1)
  self.rt.call('pl:collect-project-objects',['X']);p=self.rt.call('pl:annotation-plant','X')
  self.assertEqual([self.get(k,p) for k in ['dbh','height','crown']],[0,0,0])
 def test_ambiguous_plain_name_requires_selection_of_existing_specification(self):
  other=self.put('id','OTHER',self.put('spec_no','P002',self.put('dbh',18)))
  self.db['PLANTS']=[self.p,other];self.records['X']=self.record('香樟')
  self.rt.builtins['pl:native-project-match']=lambda *args:[1]
  self.rt.call('pl:collect-project-objects',['X'])
  self.assertEqual(self.get('id',self.rt.call('pl:annotation-plant','X')),'OTHER')
  self.assertEqual(len(self.rt.call('pl:defs')),2)
  self.assertFalse(any(isinstance(c,tuple) and c[0]=='confirm' for c in self.calls))
 def test_ambiguous_specification_cancel_keeps_drawing_unmodified(self):
  self.db['PLANTS']=[self.p,self.put('id','OTHER',self.put('dbh',18))];self.records['X']=self.record('香樟')
  self.rt.builtins['pl:native-project-match']=lambda *args:[-1]
  self.assertEqual(self.rt.call('pl:collect-project-objects',['X']),[0,0,1]);self.assertEqual(self.data,{})
 def test_imported_names_remain_visible_in_project_schedules(self):
  self.records['X']=self.record('海桐');self.rt.call('pl:collect-project-objects',['X'])
  p=self.rt.call('pl:annotation-plant','X');self.db['AI_USED_IDS']=[self.get('id',p)]
  self.rt.builtins['pl:ai-model-trees']=lambda:[]
  self.assertEqual(self.rt.call('pl:ai-visible-defs'),[p])
 def test_changed_plain_name_is_recognized_on_next_collection(self):
  self.records['X']=self.record('海桐');self.rt.call('pl:collect-project-objects',['X'])
  self.records['X']=self.record('紫珠');self.rt.call('pl:collect-project-objects',['X'])
  self.assertEqual(chinese(self.get('name',self.rt.call('pl:annotation-plant','X'))),'紫珠')
 def test_project_edits_are_used_by_imported_block_statistics(self):
  self.records['B']=self.record('银杏',block=1);self.rt.call('pl:collect-project-objects',['B'])
  p=self.rt.call('pl:annotation-plant','B');updated=self.put('height',6,self.put('name',gbk('新银杏'),p));self.db['PLANTS']=[updated]
  self.assertEqual(self.rt.call('pl:quantity-data','B'),[updated,1])
 def test_no_selection_performs_no_sync_or_area_edit_import(self):
  self.assertEqual(self.rt.call('pl:collect-project-objects',None),[0,0,0]);self.assertEqual(self.calls,[])
 def test_name_only_project_can_generate_total_and_selected_tables(self):
  self.records['X']=self.record('海桐');self.rt.call('pl:collect-project-objects',['X'])
  self.rt.builtins['pl:area-text']=lambda value:'0.00'
  created=[];self.rt.builtins['pl:output-table-create']=lambda *args:created.append(args)
  self.rt.call('pl:count-all-work');self.rt.call('pl:count-selected-work')
  self.assertEqual(len(created),2)
  self.assertEqual(self.rt.call('pl:get',Sym('handles'),self.db['LAST_COUNT_SCOPE']),['X'])
  self.assertEqual(self.db['LAST_COUNT'],None)

for name in dir(fixtures.Rules):
 if name.startswith('test_') and name not in ProjectImport.__dict__:setattr(ProjectImport,name,None)
if __name__=='__main__':unittest.main()
