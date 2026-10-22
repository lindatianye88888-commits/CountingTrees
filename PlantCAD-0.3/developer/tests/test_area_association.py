import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class Association(fixtures.Rules):
 def setUp(self):
  super().setUp();self.data={};self.roles={};self.sources={};self.calls=[]
  self.rt.builtins.update({'pl:role':lambda e:self.roles.get(e),'pl:source':lambda e:self.sources.get(e),
   'pl:plant':lambda e:self.p if e=='TREE' else None,
   'pl:data-get':lambda e,k:self.data.get(e,{}).get(k),
   'pl:data-put':lambda e,k,v:self.data.setdefault(e,{}).__setitem__(k,v) or v})
 def test_managed_name_and_leader_resolve_to_the_exact_source_spec(self):
  for role in ['LABEL','LEADER']:
   self.roles['TEXT']=role;self.sources['TEXT']='TREE'
   self.assertEqual(self.rt.call('pl:annotation-plant','TEXT'),self.p)
 def test_area_text_resolves_to_associated_plant(self):
  self.roles.update(TEXT='AREA_LABEL',AREA='AREA');self.sources['TEXT']='AREA';self.data['AREA']={'AREA_PLANT':self.p}
  self.assertEqual(self.rt.call('pl:annotation-plant','TEXT'),self.p)
 def test_unbound_area_text_has_no_plant(self):
  self.roles.update(TEXT='AREA_LABEL',AREA='AREA');self.sources['TEXT']='AREA'
  self.assertIsNone(self.rt.call('pl:annotation-plant','TEXT'))
 def test_exact_plain_text_matches_project_species(self):
  other=self.put('name',gbk('红叶石楠'))
  self.assertEqual(self.rt.call('pl:label-plant-matches',[gbk('香樟')],[self.p,other]),[self.p])
 def test_partial_species_name_does_not_match(self):
  other=self.put('name',gbk('大叶香樟'))
  self.assertEqual(self.rt.call('pl:label-plant-matches',[gbk('香樟')],[other]),None)
 def test_duplicate_species_sizes_remain_ambiguous_without_number(self):
  other=self.put('crown',4.)
  self.assertEqual(len(self.rt.call('pl:label-plant-matches',[gbk('香樟')],[self.p,other])),2)
 def test_spec_number_has_priority_over_shared_species_name(self):
  p=self.put('spec_no','P1');other=self.put('spec_no','P2',self.put('crown',4.))
  self.assertEqual(self.rt.call('pl:label-plant-matches',[gbk('香樟'),'P2'],[p,other]),[other])
 def test_clicking_area_text_and_boundary_binds_the_area_once(self):
  self.roles.update(A='AREA',TEXT='AREA_LABEL');self.sources['TEXT']='A'
  self.rt.builtins.update({'ssget':lambda *a:'SELECTION','sssetfirst':lambda *a:None,'pl:ss-list':lambda ss:['TEXT','A','TEXT'],
   'pl:bind-area-plant':lambda e,p:self.calls.append(('bind',e,p)) or True,
   'pl:sync-area-labels':lambda:self.calls.append('labels'),'pl:ai-refresh-tables':lambda:self.calls.append('tables')})
  self.rt.call('pl:bind-selected-areas',self.p)
  self.assertEqual(self.calls,[('bind','A',self.p),'labels','tables'])
 def test_original_name_text_is_never_rewritten_by_association(self):
  self.roles['A']='AREA';self.rt.builtins.update({'pl:writable':lambda e:True,'pl:area-value':lambda e:12.5})
  self.rt.call('pl:bind-area-plant','A',self.p)
  self.assertEqual(self.data,{'A':{'AREA_PLANT':self.p}})
 def test_ambiguous_plain_text_does_not_reuse_stale_current_plant(self):
  self.rt.env[Sym('pl:*native-ui*')]=True;self.rt.builtins.update({'boundp':lambda *a:True,
   'entget':lambda e:[Pair(5,e)],'pl:native-label-lines':lambda h:[gbk('香樟')],
   'pl:defs':lambda:[self.p,self.put('crown',4.)],'alert':lambda text:self.calls.append(chinese(text))})
  self.assertIsNone(self.rt.call('pl:plant-from-picked-annotation','TEXT'));self.assertEqual(self.data,{})
  self.assertIn('未匹配到唯一',self.calls[0])

for name in dir(fixtures.Rules):
 if name.startswith('test_') and name not in Association.__dict__:setattr(Association,name,None)
if __name__=='__main__':unittest.main()
