"""Specification deletion: scope, cancel, locks, failures and metadata consistency."""
import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class ProjectDelete(unittest.TestCase):
 put=fixtures.Rules.put
 def setUp(self):
  fixtures.Rules.setUp(self)
  self.other=self.put('id','OTHER',self.put('spec_no','P002'))
  self.db={'PLANTS':[self.p,self.other],'SPEC_HISTORY':[self.p,self.other],'CURRENT':'P1'}
  self.roles={};self.data={};self.sources={};self.locked=set();self.events=[];self.confirm=1;self.failure=None
  self.rt.env[Sym('pl:*native-ui*')]=True
  self.rt.builtins.update({'pl:db-get':lambda k,d:self.db.get(k,d),'pl:db-put':lambda k,v:self.db.__setitem__(k,v) or v,
   'pl:data-get':lambda e,k:self.data.get(e,{}).get(k),'pl:role':lambda e:self.roles.get(e),
   'pl:source':lambda e:self.sources.get(e),'pl:writable':lambda e:e not in self.locked,
   'pl:ss-list':lambda ss:ss,'ssget':lambda *args:list(self.roles),
   'entget':lambda e:[Pair(5,e)],'pl:native-project-delete-confirm':lambda *args:self.events.append(('confirm',args)) or self.confirm,
   'pl:native-project-erase':self.erase,'pl:sync-drawing':lambda:self.events.append(('sync',self.db['PLANTS'])),
   'pl:fail':lambda m:(_ for _ in ()).throw(ValueError(chinese(m)))})
 def erase(self,handles):
  self.events.append(('erase',handles))
  return self.failure or len(handles)
 def add(self,e,role,p=None,source=None):
  self.roles[e]=role
  if p:self.data[e]={dict(TREE='PLANT',AREA='AREA_PLANT',PROJECT_SOURCE='PROJECT_PLANT')[role]:p}
  if source:self.sources[e]=source
 def tables(self):
  for e,rows in [('MIX',[['P1',[]],['OTHER',[]]]),('ONLY',[['P1',[]]]),('KEEP',[['OTHER',[]]])]:
   self.roles[e]='TABLE';self.data[e]={'TABLE_ROWS':rows}
 def test_plan_includes_all_owned_roles_and_only_selected_specification(self):
  self.add('T','TREE',self.p);self.add('A','AREA',self.p);self.add('X','PROJECT_SOURCE',self.p);self.add('O','TREE',self.other)
  for i,role in enumerate(['LABEL','LEADER','AREA_LABEL','AREA_LEADER','AREA_ARROW','AREA_FILL','FILL_EDGE']):self.add('L'+str(i),role,source='A')
  self.add('OL','LABEL',source='O');self.add('RAW',None);self.tables()
  roots,followers,tables=self.rt.call('pl:project-delete-plan','P1',list(self.roles))
  self.assertEqual(set(roots),{'T','A','X'});self.assertEqual(set(followers),{'L'+str(i) for i in range(7)});self.assertEqual(tables,['ONLY'])
 def test_cancel_preserves_drawing_definitions_history_and_current(self):
  self.add('T','TREE',self.p);self.tables();before=dict(self.db);self.confirm=0
  self.assertIsNone(self.rt.call('pl:delete-project-spec',self.p));self.assertEqual(self.db,before)
  self.assertEqual([e[0] for e in self.events],['confirm'])
 def test_delete_updates_definitions_history_current_and_refreshes_once(self):
  self.add('T','TREE',self.p);self.add('L','LABEL',source='T');self.tables()
  self.assertTrue(self.rt.call('pl:delete-project-spec',self.p))
  self.assertEqual(self.db['PLANTS'],[self.other]);self.assertEqual(self.db['SPEC_HISTORY'],[self.other]);self.assertEqual(self.db['CURRENT'],'OTHER')
  erased=next(e[1] for e in self.events if e[0]=='erase');self.assertEqual(set(erased),{'T','L','ONLY'})
  self.assertEqual([e[0] for e in self.events],['confirm','erase','sync'])
 def test_last_unplaced_specification_can_be_deleted(self):
  self.db['PLANTS']=[self.p];self.db['SPEC_HISTORY']=[self.p]
  self.assertTrue(self.rt.call('pl:delete-project-spec',self.p));self.assertIsNone(self.db['PLANTS']);self.assertEqual(self.db['CURRENT'],'')
  self.assertFalse(any(e[0]=='erase' for e in self.events))
 def test_locked_root_follower_or_affected_mixed_table_blocks_before_confirmation(self):
  self.add('T','TREE',self.p);self.add('L','LABEL',source='T');self.tables()
  for e in ['T','L','MIX','ONLY']:
   self.locked={e};before=dict(self.db)
   with self.assertRaisesRegex(ValueError,'图层已锁定'):self.rt.call('pl:delete-project-spec',self.p)
   self.assertEqual(self.events,[]);self.assertEqual(self.db,before)
 def test_native_failure_does_not_remove_project_specification(self):
  self.add('T','TREE',self.p);self.failure='ERROR: erase failed';before=dict(self.db)
  with self.assertRaisesRegex(ValueError,'erase failed'):self.rt.call('pl:delete-project-spec',self.p)
  self.assertEqual(self.db,before);self.assertFalse(any(e[0]=='sync' for e in self.events))
 def test_missing_native_bridge_or_invalid_confirmation_does_not_modify_data(self):
  before=dict(self.db);self.rt.env[Sym('pl:*native-ui*')]=None
  with self.assertRaisesRegex(ValueError,'原生插件'):self.rt.call('pl:delete-project-spec',self.p)
  self.rt.env[Sym('pl:*native-ui*')]=True;self.confirm='ERROR: dialog failed'
  with self.assertRaisesRegex(ValueError,'dialog failed'):self.rt.call('pl:delete-project-spec',self.p)
  self.assertEqual(self.db,before)
 def test_deleting_noncurrent_spec_keeps_current(self):
  self.rt.call('pl:delete-project-spec',self.other);self.assertEqual(self.db['CURRENT'],'P1')
