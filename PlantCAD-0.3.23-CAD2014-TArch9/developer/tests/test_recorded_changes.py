import ast
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class RecordedChanges(fixtures.Rules):
    def setUp(self):
        super().setUp()
        self.rt.builtins['vl-symbol-name']=lambda value:str(value).upper()

    def test_cm_roundtrip_keeps_existing_tree_size(self):
        self.assertEqual(self.rt.call('pl:dimension-cm',Sym('height'),self.p),400.)
        self.assertEqual(self.rt.call('pl:dimension-cm',Sym('crown'),self.p),300.)
        value=self.rt.call('pl:dimension-input',Sym('crown'),'300',0)
        updated=self.put('crown',value)
        self.assertEqual(value,3.)
        self.assertEqual(self.rt.call('pl:block-scale',updated,1000.),3000.)
        self.assertEqual(self.get('crown',self.p),3.)

    def test_shrub_and_groundcover_diameter_placeholders_are_optional(self):
        for kind in [1,2]:
            p=self.put('kind',kind,self.put('dbh',0.))
            self.assertEqual(chinese(self.rt.call('pl:dimension-text',Sym('dbh'),p)),'——')
            self.assertEqual(chinese(self.rt.call('pl:dbh-text',p,0,None)),'')
            for text in ['',gbk('——'),'-','--']:
                self.assertEqual(self.rt.call('pl:dimension-input',Sym('dbh'),text,kind),0.)

    def test_explicit_designer_diameter_is_preserved(self):
        p=self.put('kind',1,self.put('dbh',9.5))
        self.assertEqual(self.rt.call('pl:dimension-text',Sym('dbh'),p),'9.5')
        self.assertEqual(self.rt.call('pl:dimension-input',Sym('caliper'),'8.5',1),8.5)

    def test_dash_does_not_become_a_negative_or_valid_tree_diameter(self):
        self.assertEqual(self.rt.call('pl:dimension-input',Sym('dbh'),gbk('——'),0),0.)
        self.assertIsNone(self.rt.call('pl:dimension-input',Sym('crown'),'-100',1))

    def test_editor_fill_converts_metres_and_shows_optional_caliper(self):
        fields={}
        self.rt.builtins.update({
            'set_tile':lambda key,value:fields.__setitem__(key,value),
            'get_tile':lambda key:fields.get(key,''),
            'pl:popup':lambda *args:None,'pl:dialog-preview':lambda *args:None,
            'pl:units':lambda:1000.,
            'pl:catalog':lambda:None,
        })
        self.rt.call('pl:fill-edit',self.put('kind',1))
        self.assertEqual(fields['height'],'400')
        self.assertEqual(fields['crown'],'300')
        self.assertEqual(fields['dbh'],'12')
        self.assertEqual(chinese(fields['caliper']),'——')

    def test_editor_save_converts_cm_to_existing_persistence_units(self):
        fields={'name':gbk('桂花'),'spec_no':'P001','kind':'1','diameter_mode':'0','quantity_unit':'0','style':'0',
                'block':'','dbh':gbk('——'),'caliper':gbk('——'),'height':'40','crown':'150','factor':'1','base':'',
                'fill_pattern':'0','fill_scale':'10','fill_angle':'0'}
        saved=[]
        self.rt.env[Sym('pl:*edit*')]=self.p;self.rt.env[Sym('pl:*require-crown*')]=True
        self.rt.builtins.update({
            'get_tile':lambda key:fields[key],'set_tile':lambda *args:None,
            'mode_tile':lambda *args:None,'pl:used-specs':lambda:[self.p],
            'pl:prepare-edited-spec':lambda p,old,defs:p,'pl:history-error':lambda p:None,
            'done_dialog':lambda value:saved.append(value),
        })
        self.rt.call('pl:accept-edit')
        result=self.rt.env[Sym('pl:*edit-result*')]
        self.assertEqual(saved,[1])
        self.assertEqual([self.get(k,result) for k in ['dbh','caliper','height','crown']],[0.,0.,.4,1.5])
        self.assertEqual(self.rt.call('pl:diameter',result,1000.),1500.)

    def test_project_double_click_opens_the_exact_row_editor(self):
        result=[];self.rt.builtins['done_dialog']=lambda status:result.append(status)
        self.rt.call('pl:project-row-action','2',1)
        self.assertEqual(result,[])
        self.rt.call('pl:project-row-action','2',4)
        self.assertEqual(result,[3])
        self.assertEqual(self.rt.env[Sym('pl:*index*')],2)

    def species(self,id,category,tags=''):
        return [Pair(Sym('id'),id),Pair(Sym('name'),gbk(id)),Pair(Sym('category'),category),Pair(Sym('tags'),gbk(tags))]
    def test_filter_change_keeps_selected_plants_from_other_categories(self):
        a=self.species('A',0);b=self.species('B',1)
        picked=self.rt.call('pl:species-merge-selection',None,[a],[0])
        picked=self.rt.call('pl:species-merge-selection',picked,[b],[0])
        self.assertEqual([self.get('id',s) for s in picked],['A','B'])
        picked=self.rt.call('pl:species-merge-selection',picked,[b],None)
        self.assertEqual([self.get('id',s) for s in picked],['A'])

    def test_filter_restores_indices_and_does_not_duplicate_selected_species(self):
        a=self.species('A',0);b=self.species('B',1)
        self.assertEqual(self.rt.call('pl:indices-text',[b],[a,b]),'1')
        self.assertEqual(self.rt.call('pl:species-merge-selection',[b],[a,b],[1]),[b])

    def test_category_tags_and_explicit_color_flower_tags(self):
        self.assertEqual([chinese(t) for t in self.rt.call('pl:species-tags',self.species('A',0,'彩叶|开花'))],['常绿','彩叶','开花'])
        self.assertEqual([chinese(t) for t in self.rt.call('pl:species-tags',self.species('B',1))],['落叶'])
        self.assertFalse(self.rt.call('pl:species-tags',self.species('C',4)))

    def test_old_and_tagged_catalogues_roundtrip(self):
        line=gbk('S1\t银杏\t1\t北京\t来源\t备注\t待询价')
        old=self.rt.call('pl:species-from-line',line)
        self.assertEqual(self.rt.call('pl:species-line',old),line+'\t')
        tagged=self.rt.call('pl:species-from-line',line+'\t'+gbk('彩叶|开花'))
        self.assertEqual(self.rt.call('pl:species-line',tagged),line+'\t'+gbk('彩叶|开花'))

    def test_schedule_uses_cm_and_placeholder_without_changing_saved_data(self):
        p=self.put('kind',2,self.put('dbh',0.))
        row=self.rt.call('pl:schedule-row',p,12)
        self.assertEqual([chinese(x) for x in row[2:6]],['——','——','400','300'])
        self.assertEqual([self.get(k,p) for k in ['height','crown']],[4.,3.])

    def table_refresh(self,layer,rows):
        cells={}
        self.rt.builtins.update({
            'vla-get-layer':lambda obj:gbk(layer),
            'vla-get-rows':lambda obj:len(rows)+2,
            'vla-gettext':lambda obj,r,c:'',
            'vla-get-regeneratetablesuppressed':lambda obj:False,
            'vla-put-regeneratetablesuppressed':lambda obj,value:None,
            'vl-catch-all-apply':lambda fn,args:self.rt.call(str(fn),*(args or [])),
            'vl-catch-all-error-p':lambda result:False,
            'vla-settext':lambda obj,r,c,value:cells.__setitem__((r,c),chinese(value)),
            'vla-update':lambda obj:None,
        })
        self.rt.call('pl:ai-update-table','TABLE',rows)
        return cells

    def test_refresh_existing_quantity_table_changes_headers_with_converted_values(self):
        rows=self.rt.call('pl:ai-quantity-rows',self.rt.call('pl:add-count',self.p,None))
        cells=self.table_refresh('PL_表格_苗木',rows)
        self.assertEqual([cells[(1,4)],cells[(1,5)]],['高度 cm','冠幅 cm'])
        self.assertEqual([cells[(2,4)],cells[(2,5)]],['400','300'])

    def test_refresh_existing_spec_table_changes_its_different_column_headers(self):
        rows=self.rt.call('pl:spec-list-rows',[self.p])
        cells=self.table_refresh('PL_表格_植物规格',rows)
        self.assertEqual([cells[(1,5)],cells[(1,6)]],['高度 cm','冠幅 cm'])
        self.assertEqual([cells[(2,5)],cells[(2,6)]],['400','300'])

    def test_unchanged_legacy_schedule_does_not_write_or_regenerate_cells(self):
        rows=self.rt.call('pl:spec-list-rows',[self.p])
        cells=self.table_refresh('PL_表格_植物规格',rows)
        writes=[]
        self.rt.builtins['vla-gettext']=lambda obj,r,c:gbk(cells.get((r,c),''))
        self.rt.builtins['vla-settext']=lambda *args:writes.append(args)
        self.rt.builtins['vla-update']=lambda *args:writes.append('update')
        self.rt.call('pl:ai-update-table','TABLE',rows)
        self.assertEqual(writes,[])

    def test_legacy_schedule_restores_regeneration_setting_after_failure(self):
        self.table_refresh('PL_表格_植物规格',[])
        settings=[]
        def fail(*args):raise ValueError('locked table')
        def caught(fn,args):
            try:return self.rt.call(str(fn),*(args or []))
            except Exception as error:return error
        self.rt.builtins.update({'vla-gettext':fail,'vla-put-regeneratetablesuppressed':lambda obj,value:settings.append(value),
            'vl-catch-all-apply':caught,'vl-catch-all-error-p':lambda r:isinstance(r,Exception),'pl:rethrow':lambda e:(_ for _ in []).throw(e)})
        with self.assertRaisesRegex(ValueError,'locked table'):self.rt.call('pl:ai-update-table','TABLE',[])
        self.assertEqual(settings[-1],False)

    def test_startup_manifest_enables_auto_load_at_component_level(self):
        root=Path(__file__).resolve().parents[2]
        tree=ast.parse((root/'install_panel.py').read_text(encoding='utf-8'))
        xml=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='xml' for t in n.targets))
        entry=ET.fromstring(xml).find('./Components/ComponentEntry')
        self.assertEqual(entry.get('LoadOnAutoCADStartup'),'True')
        self.assertEqual(entry.get('LoadOnStartup'),'True')
        self.assertIsNone(entry.find('LoadReasons'))

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in RecordedChanges.__dict__:
        setattr(RecordedChanges,name,None)
if __name__=='__main__':unittest.main()
