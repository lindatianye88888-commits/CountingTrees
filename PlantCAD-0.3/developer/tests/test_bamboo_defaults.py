import csv,unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk,chinese

class BambooDefaults(unittest.TestCase):
 setUp=fixtures.Rules.setUp
 put=fixtures.Rules.put
 def test_bamboo_has_distinct_valid_kind_and_tree_schedule_group(self):
  p=self.put('kind',6)
  self.assertEqual(chinese(self.rt.call('pl:kind-name',6)),'竹类')
  self.assertEqual(self.rt.call('pl:species-kind',6),6);self.assertIsNone(self.rt.call('pl:plant-error',p))
  self.assertEqual(self.rt.call('pl:table-category',p),'trees');self.assertEqual(self.rt.call('pl:plant-rank',p),0)
  self.assertFalse(self.rt.call('pl:area-kind-p',6))
 def test_species_picker_switches_between_bamboo_and_trees_while_keeping_explicit_ball_role(self):
  for current,chosen,expected in [(0,6,6),(6,0,0),(3,6,3),(4,6,4),(5,6,5)]:
   tiles={'kind':str(current)}
   self.rt.env[Sym('pl:*edit*')]=self.p
   self.rt.env[Sym('pl:*edit-choices*')]=[self.put('kind',chosen)]
   self.rt.builtins['get_tile']=lambda k:tiles.get(k,'')
   self.rt.builtins['set_tile']=lambda k,v:tiles.__setitem__(k,v)
   self.rt.call('pl:edit-name-selected','0');self.assertEqual(tiles['kind'],str(expected))
 def test_catalogue_contains_seventeen_true_bamboo_species(self):
  with (fixtures.ROOT/'src/plantcatalog.tsv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f,delimiter='\t'))
  bamboo=[r for r in rows if r['category']=='6'];self.assertEqual(len(bamboo),17)
  self.assertTrue({'紫竹','凤尾竹','箬竹','刚竹','慈孝竹'}<={r['name'] for r in bamboo})
  self.assertEqual(len({r['id'] for r in rows}),len(rows))
  self.assertFalse({'南天竹','竹柏','棕竹'}&{r['name'] for r in bamboo})
 def test_saved_catalogue_keeps_custom_values_and_merges_bamboo_only_without_duplicates(self):
  def species(id,name,category):return [Pair(Sym('id'),id),Pair(Sym('name'),gbk(name)),Pair(Sym('category'),category)]
  custom=species('CUSTOM','紫竹',6);sameid=species('B2','设计师改名',6)
  defaults=[species('B1','紫竹',6),species('B2','淡竹',6),species('B3','箬竹',6),species('TREE','银杏',0)]
  merged=self.rt.call('pl:catalog-merge-bamboo',[custom,sameid],defaults)
  self.assertEqual(merged,[custom,sameid,defaults[2]])
  self.assertEqual(self.rt.call('pl:catalog-merge-bamboo',merged,defaults),merged)
 def test_new_font_default_is_one_centimetre_and_fill_scale_is_unchanged(self):
  self.rt.builtins['pl:db-get']=lambda k,d:d
  opts=self.rt.call('pl:plot-options');paper=self.rt.call('pl:get',Sym('paper_height'),opts)
  self.assertEqual(paper/10,1);self.assertEqual(self.rt.call('pl:paper-height',paper,100,1000),1000)
  self.assertEqual(self.rt.call('pl:get',Sym('fill_scale'),self.p),.1)
 def test_explicit_legacy_font_and_partial_settings_are_preserved(self):
  saved=[Pair(Sym('scale'),200.),Pair(Sym('paper_height'),2.5)]
  self.rt.builtins['pl:db-get']=lambda k,d:saved
  opts=self.rt.call('pl:plot-options')
  self.assertEqual(self.rt.call('pl:get',Sym('paper_height'),opts),2.5);self.assertEqual(self.rt.call('pl:get',Sym('scale'),opts),200)
  self.assertEqual(saved,[Pair(Sym('scale'),200.),Pair(Sym('paper_height'),2.5)])
