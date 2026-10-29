"""Schedule classification, species scope and legacy edit compatibility."""
import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk,chinese

class SplitSchedules(fixtures.Rules):
    def scope(self,**values):
        return [Pair(Sym(k),v) for k,v in {'scope':'model',**values}.items()]

    def test_display_order_keeps_canonical_import_order(self):
        cells=self.rt.call('pl:output-table-cells',[self.p,3])
        display=self.rt.call('pl:table-display-row',cells)
        self.assertEqual([chinese(s) for s in self.rt.call('pl:output-table-headers')[:3]],['编号','图例','植物名称'])
        self.assertEqual(display,[cells[0],cells[9],*cells[1:9]])
        self.assertEqual([display[0],*display[2:]],cells[:9])

    def test_categories_partition_all_kinds_without_changing_records(self):
        records=[[self.put('kind',k,self.put('id',str(k))),k+1] for k in range(7)]
        self.rt.builtins['pl:output-counts']=lambda scope:[[None,*row] for row in records]
        self.rt.builtins['pl:output-table-objects']=lambda scope:[]
        groups=self.rt.call('pl:table-split-groups',records,'category',self.scope())
        self.assertEqual(len(groups),3)
        partitions=[self.rt.call('pl:output-table-records','count',g[1]) for g in groups]
        self.assertEqual([[self.get('kind',r[0]) for r in group] for group in partitions],[[0,6],[3],[1,2,4,5]])
        self.assertEqual(sum(r[1] for part in partitions for r in part),28)

    def test_species_splits_keep_multiple_specifications_together(self):
        a=self.put('species_id','SPECIES_1',self.put('spec_no','P001'))
        b=self.put('crown',5,self.put('spec_no','P002',a))
        c=self.put('species_id','SPECIES_2',self.put('name',gbk('海桐')))
        records=[[a,2],[b,4],[c,1]]
        self.rt.builtins['pl:output-counts']=lambda scope:[[None,*row] for row in records]
        self.rt.builtins['pl:output-table-objects']=lambda scope:[]
        groups=self.rt.call('pl:table-split-groups',records,'species',self.scope(handles=['A','B']))
        self.assertEqual(len(groups),2)
        result=self.rt.call('pl:output-table-records','count',groups[0][1])
        self.assertEqual(result,records[:2])
        self.assertEqual(self.rt.call('pl:get',Sym('handles'),groups[0][1]),['A','B'])

    def test_unassigned_species_use_normalized_name_and_empty_classes_are_skipped(self):
        a=self.put('kind',3,self.put('species_id','',self.put('name',gbk('海桐'))))
        b=self.put('spec_no','P002',a)
        self.assertEqual(len(self.rt.call('pl:table-split-groups',[[a,2],[b,4]],'species',self.scope())),1)
        self.assertEqual(len(self.rt.call('pl:table-split-groups',[[a,2]],'category',self.scope())),1)

    def test_filtered_tables_share_source_statistics_cache(self):
        calls=[]
        self.rt.env[Sym('pl:*sync-busy*')]=True
        self.rt.builtins['pl:output-table-objects']=lambda scope:['A']
        self.rt.builtins['pl:count-rows']=lambda values:calls.append(values) or [[None,self.p,1]]
        for scope in [self.scope(),self.scope(category='trees'),self.scope(species_key='ID:1')]:
            self.rt.call('pl:output-counts',scope)
        self.assertEqual(len(calls),1)

    def test_new_species_join_their_category_and_renamed_species_keep_stable_filter(self):
        p=self.put('species_id','S1')
        scope=self.scope(category='trees',species_key='ID:S1')
        self.assertTrue(self.rt.call('pl:table-record-matches',self.put('name',gbk('新名称'),p),scope))
        self.assertFalse(self.rt.call('pl:table-record-matches',self.put('kind',3,p),scope))

    def test_manually_named_species_remain_linked_when_renamed(self):
        p=self.put('species_id','')
        groups=self.rt.call('pl:table-split-groups',[[p,1]],'species',self.scope())
        self.assertTrue(self.rt.call('pl:table-record-matches',self.put('name',gbk('设计师改名'),p),groups[0][1]))
        self.assertFalse(self.rt.call('pl:table-record-matches',self.put('id','UNRELATED',self.put('name',gbk('其他品种'),p)),groups[0][1]))

    def test_area_units_validate_without_allowing_area_specs_as_single_plants(self):
        for kind in [1,2,4,5]:
            p=self.put('quantity_unit',gbk('平方米'),self.put('kind',kind))
            self.assertIsNone(self.rt.call('pl:plant-error',p))
            self.assertIsNotNone(self.rt.call('pl:insert-error',p))
        for kind in [0,3]:
            self.assertIsNotNone(self.rt.call('pl:plant-error',self.put('quantity_unit',gbk('平方米'),self.put('kind',kind))))

    def test_unchanged_area_schedule_import_does_not_reject_its_square_metre_unit(self):
        p=self.put('quantity_unit',gbk('平方米'),self.put('kind',1))
        before=self.rt.call('pl:output-table-cells',[p,43.3])
        self.assertEqual(self.rt.call('pl:table-edited-plant',p,before,before[:9]),p)

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in SplitSchedules.__dict__:setattr(SplitSchedules,name,None)
if __name__=='__main__':unittest.main()
