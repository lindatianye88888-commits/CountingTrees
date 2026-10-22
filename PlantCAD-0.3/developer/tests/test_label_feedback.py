"""Regression checks for existing-area label sizing and edited-name recognition."""
import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk,chinese

class LabelFeedback(fixtures.Rules):
    def test_shrub_ball_name_is_centered_and_lower_fields_hidden(self):
        p=self.put('kind',3,self.put('spec_no','B001'))
        opts=[Pair(Sym('show_number'),1)]
        name=self.rt.call('pl:symbol-attribute','PL_NAME',p,[12.,24.,0.],2.,opts)
        self.assertEqual(name[1],[12.,24.,0.]);self.assertFalse(name[2])
        self.assertTrue(self.rt.call('pl:symbol-attribute','PL_DIAMETER',p,[12.,24.,0.],2.,opts)[2])
        self.assertTrue(self.rt.call('pl:symbol-attribute','PL_SPEC',p,[12.,24.,0.],2.,opts)[2])

    def test_tree_number_is_hidden_without_removing_schedule_number(self):
        p=self.put('spec_no','P018')
        value=self.rt.call('pl:symbol-attribute','PL_SPEC',p,[0.,0.,0.],2.,[Pair(Sym('show_number'),1)])
        self.assertEqual(value[0],'P018');self.assertTrue(value[2])
        self.assertEqual(self.get('spec_no',p),'P018')
        self.assertEqual(self.rt.call('pl:symbol-attribute','PL_DIAMETER',p,[0.,0.,0.],2.,None)[0],'12')

    def test_area_precision_survives_cad_zero_suppression(self):
        for raw,expected in [('12','12.00'),('12.5','12.50'),('.5','0.50'),('0','0.00')]:
            self.rt.builtins['rtos']=lambda *args,value=raw:value
            self.assertEqual(self.rt.call('pl:area-text',12.5),expected)

    def test_area_cells_are_two_decimals_and_counts_remain_integers(self):
        p=self.put('quantity_unit',gbk('平方米'),self.put('kind',1))
        self.assertEqual(self.rt.call('pl:output-table-cells',[p,705.681824])[7],'705.68')
        self.assertEqual(self.rt.call('pl:output-table-cells',[p,12.5])[7],'12.50')
        self.assertEqual(self.rt.call('pl:output-table-cells',[self.p,3])[7],'3')

    def test_total_table_forces_model_scope_even_after_selected_statistics(self):
        seen=[]
        self.rt.env[Sym('pl:*count-scope*')]='Selected'
        self.rt.builtins['pl:count-work']=lambda:seen.append(self.rt.env[Sym('pl:*count-scope*')]) or True
        self.rt.builtins['pl:output-table-create']=lambda *args:seen.append(args)
        self.rt.call('pl:table-work')
        self.assertEqual(seen[0],'Model');self.assertIn('总表',chinese(seen[1][2]))

    def test_type_sort_is_stable_and_keeps_every_distinct_specification(self):
        records=[[self.put('kind',kind,self.put('id',str(i))),1] for i,kind in enumerate([2,3,0,1,3,0,5,4])]
        result=self.rt.call('pl:sort-plant-records',records)
        self.assertEqual([self.get('id',row[0]) for row in result],['2','5','1','4','0','3','6','7'])
        self.assertEqual(len(result),len(records))

    def test_existing_native_label_resizes_even_when_its_text_has_not_changed(self):
        writes=[];text=gbk('海桐 12.00 平方米');opts=[Pair(Sym('layout'),1)]
        self.rt.builtins.update({'pl:all-labels':lambda:['L'],'pl:role':lambda e:'AREA_LABEL',
            'pl:writable':lambda e:True,'pl:source':lambda e:'A','pl:area-label-text':lambda e:text,
            'pl:output-area-text':lambda *args:text,'pl:area-annotation-raw':lambda e:text,
            'pl:area-annotation-height':lambda *args:25.,'pl:area-label-layer':lambda e:'LABEL_LAYER',
            'entget':lambda e:[Pair(0,'MULTILEADER'),Pair(8,'LABEL_LAYER')],
            'pl:data-get':lambda e,k:{'OUTPUT_OPTIONS':opts,'OUTPUT_HEIGHT':10.,'AREA_LABEL_TEXT':text,'ANCHOR':[0.,0.,0.]}.get(k),
            'pl:write-native-area-label':lambda *args:writes.append(args) or 'L'})
        self.rt.call('pl:sync-area-labels')
        self.assertEqual(len(writes),1);self.assertEqual(writes[0][-1],25.)

    def edited_labels(self,labels=('L',),names=None,baseline=True,defs=None):
        self.writes=[];self.rt.env[Sym('pl:*native-ui*')]=True;self.rt.env[Sym('pl:*drawing-changed*')]=None
        names=names or {'L':gbk('海桐')};old=gbk('茶梅 12.00 平方米')
        target=self.put('name',gbk('海桐'),self.put('id','TARGET'))
        self.rt.builtins.update({'pl:all-labels':lambda:list(labels),'pl:role':lambda e:'AREA_LABEL',
            'pl:source':lambda e:'A','pl:writable':lambda e:True,'entget':lambda e:[Pair(0,'MULTILEADER'),Pair(5,e)],
            'pl:data-get':lambda e,k:old if k=='AREA_LABEL_TEXT' and baseline else None,
            'pl:area-annotation-raw':lambda e:names[e]+gbk(' 12.00 平方米'),
            'pl:native-area-label-name':lambda e:names[e], 'pl:area-title':lambda e:gbk('茶梅'),
            'pl:area-label-text':lambda e:old,'pl:output-area-text':lambda *args:old,
            'pl:defs':lambda:defs if defs is not None else [target],
            'pl:area-label-name':lambda *args:self.writes.append(args) or target,
            'pl:fail':lambda message:(_ for _ in []).throw(ValueError(chinese(message)))})

    def test_directly_edited_names_are_imported_for_new_and_legacy_labels(self):
        for baseline in [True,False]:
            self.edited_labels(baseline=baseline)
            self.assertEqual(self.rt.call('pl:import-area-label-edits'),1)
            self.assertEqual(self.writes,[('A',gbk('海桐'))])

    def test_project_specification_change_takes_precedence_over_old_label(self):
        self.edited_labels();self.rt.env[Sym('pl:*drawing-changed*')]=True
        self.rt.call('pl:import-area-label-edits');self.assertEqual(self.writes,[])

    def test_conflicting_labels_on_one_area_are_rejected_before_writing(self):
        defs=[self.put('name',gbk(name),self.put('id',str(i))) for i,name in enumerate(['海桐','桂花'])]
        self.edited_labels(('L1','L2'),{'L1':gbk('海桐'),'L2':gbk('桂花')},defs=defs)
        with self.assertRaises(ValueError):self.rt.call('pl:import-area-label-edits')
        self.assertEqual(self.writes,[])

    def test_ambiguous_species_name_requires_a_unique_specification(self):
        defs=[self.put('name',gbk('海桐'),self.put('id',str(i))) for i in range(2)]
        self.edited_labels(defs=defs)
        with self.assertRaises(ValueError):self.rt.call('pl:import-area-label-edits')
        self.assertEqual(self.writes,[])

    def test_manually_edited_area_number_does_not_change_plant_binding(self):
        self.edited_labels(names={'L':gbk('茶梅')})
        self.rt.call('pl:import-area-label-edits');self.assertEqual(self.writes,[])

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in LabelFeedback.__dict__:setattr(LabelFeedback,name,None)
if __name__=='__main__':unittest.main()
