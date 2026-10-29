from pathlib import Path
import csv
import unittest
import test_rules as fixtures
from lisp_harness import Runtime, Sym, Pair, parse, gbk, chinese

ROOT = Path(__file__).resolve().parents[1]

class DesignRules(fixtures.Rules):
    # Reuse the real-source fixture, not inherited test cases.
    def test_ground_diameter_is_separate_from_chest_and_crown(self):
        p=self.put('caliper', 8.0)
        p=self.put('diameter_mode', 1, p)
        self.assertEqual(self.label(1,p=p),r'香樟\P8')
        self.assertEqual(self.label(1,2,1,p),r'香樟\Pd=8cm')
        self.assertIn('D=12cm  d=8cm',self.label(2,p=p))
        self.assertEqual(self.get('crown',p),3.0)

    def test_missing_ground_diameter_does_not_use_dbh(self):
        p=self.put('diameter_mode',1)
        self.assertEqual(self.label(1,p=p),'香樟')

    def test_five_metre_crown_has_exact_drawing_diameter(self):
        p=self.put('crown',5.0)
        for units,result in [(1000,5000),(1,5),(100,500)]:
            self.assertEqual(self.rt.call('pl:diameter',p,units),result)

    def test_paper_height_tracks_scale_and_drawing_units(self):
        for units in [1000.0,1.0,100.0]:
            for scale in [50.0,100.0,200.0]:
                with self.subTest(units=units,scale=scale):
                    h=self.rt.call('pl:paper-height',2.5,scale,units)
                    self.assertAlmostEqual(h/units/scale*1000,2.5)

    def test_numbered_specs_do_not_merge_in_schedule(self):
        a=self.put('spec_no','P001')
        b=self.put('spec_no','P002')
        rows=self.rt.call('pl:add-count',a,None)
        rows=self.rt.call('pl:add-count',b,rows)
        self.assertEqual(len(rows),2)
        self.assertEqual([r[2] for r in rows],[1,1])

    def test_ground_diameter_and_quantity_unit_split_schedule(self):
        rows=self.rt.call('pl:add-count',self.p,None)
        rows=self.rt.call('pl:add-count',self.put('caliper',8.0),rows)
        rows=self.rt.call('pl:add-count',self.put('quantity_unit',gbk('丛')),rows)
        self.assertEqual(len(rows),3)

    def test_duplicate_number_rejected_case_insensitive_but_self_edit_allowed(self):
        existing=self.put('spec_no','P001')
        edited=self.put('spec_no','p001')
        self.assertIsNone(self.rt.call('pl:spec-error',edited,[existing]))
        other=self.put('id','P2',edited)
        self.assertIsNotNone(self.rt.call('pl:spec-error',other,[existing]))
        self.assertIsNotNone(self.rt.call('pl:spec-error',self.p,None))

    def test_generated_numbers_skip_used_and_reuse_holes(self):
        defs=[]
        for no in ['p001','P003','SPEC-X']:
            defs.append(self.put('spec_no',no))
        self.assertEqual(self.rt.call('pl:next-spec-number',defs),'P002')
        defs=[self.put('spec_no',f'P{i:03}') for i in range(1,101)]
        self.assertEqual(self.rt.call('pl:next-spec-number',defs),'P101')

    def memory_database(self,plants):
        database={'PLANTS':plants}
        self.rt.builtins['pl:all-trees']=lambda:None
        self.rt.builtins['pl:db-get']=lambda key,default:database.get(key,default)
        self.rt.builtins['pl:db-put']=lambda key,value:database.__setitem__(key,value) or value
        self.rt.builtins['getvar']=lambda key:{'DATE':46000.1,'HANDSEED':'AB'}[key]
        return database

    def test_legacy_migration_keeps_real_specs_and_adds_unique_numbers(self):
        old=[pair for pair in self.p if pair.car not in
             [Sym('caliper'),Sym('diameter_mode'),Sym('spec_no'),Sym('species_id'),Sym('quantity_unit')]]
        second=self.put('id','P2',old)
        database=self.memory_database([old,second])
        self.rt.call('pl:migrate-defs')
        self.assertEqual([self.get('spec_no',p) for p in database['PLANTS']],['P001','P002'])
        for p in database['PLANTS']:
            self.assertEqual([self.get(k,p) for k in ['dbh','height','crown']],[12.,4.,3.])
        previous=list(database['PLANTS'])
        self.rt.call('pl:migrate-defs')
        self.assertEqual(database['PLANTS'],previous)

    def test_changed_real_crown_allocates_variant_once(self):
        original=self.put('spec_no','P001')
        database=self.memory_database([original])
        changed=self.put('crown',5.,original)
        a=self.rt.call('pl:instance-variant',changed)
        b=self.rt.call('pl:instance-variant',changed)
        self.assertEqual(self.get('spec_no',a),'P002')
        self.assertEqual(self.get('id',a),self.get('id',b))
        self.assertEqual(len(database['PLANTS']),2)
        self.assertEqual(self.get('crown',database['PLANTS'][0]),3.)

    def test_species_filter_combines_name_category_and_region(self):
        rows=[]
        for identity,name,cat,region in [('a','银杏',1,'北京、上海'),('b','香樟',0,'上海、广州'),('c','麦冬',4,'北京')]:
            rows.append([Pair(Sym('id'),identity),Pair(Sym('name'),gbk(name)),
                         Pair(Sym('category'),cat),Pair(Sym('region'),gbk(region))])
        self.assertEqual(len(self.rt.call('pl:species-filter',rows,-1,'',gbk('北京'))),2)
        result=self.rt.call('pl:species-filter',rows,0,gbk('樟'),gbk('上海'))
        self.assertEqual(chinese(self.get('name',result[0])),'香樟')
        self.assertEqual(self.rt.call('pl:species-filter',rows,4,gbk('樟'),''),None)

    def test_catalogue_tsv_roundtrip_and_invalid_columns(self):
        line=gbk('S1\t银杏\t1\t北京\t设计师\t规格待核实\t已询价')
        species=self.rt.call('pl:species-from-line',line)
        self.assertEqual(self.rt.call('pl:species-line',species),line+'\t')
        for bad in ['id\tname','S1\t银杏\t1.5\t北京\t来源\t备注\t待询价',
                    'S1\t银杏\t13\t北京\t来源\t备注\t待询价',
                    'S1\t\t1\t北京\t来源\t备注\t待询价']:
            self.assertIsNone(self.rt.call('pl:species-from-line',gbk(bad)))

    def test_catalogue_import_rejects_whole_file_on_duplicate_id(self):
        header='id\tname\tcategory\tregion\tsource\tnote\tsupply'
        good=gbk('S1\t银杏\t1\t北京\t来源\t备注\t待询价')
        def read(lines):
            iterator=iter(lines)
            self.rt.builtins['open']=lambda *args:'test-file'
            self.rt.builtins['read-line']=lambda *args:next(iterator,None)
            self.rt.builtins['close']=lambda *args:None
            return self.rt.call('pl:read-catalog','test.tsv')
        self.assertEqual(len(read([header,good])),1)
        self.assertIsNone(read([header,good,good]))
        self.assertIsNone(read(['wrong-header',good]))
        self.assertIsNone(read([header,good,'bad-line']))

    def test_embedded_text_uses_paper_height_and_separate_diameter(self):
        p=self.put('caliper',8.)
        p=self.put('diameter_mode',1,p)
        p=self.put('spec_no','P001',p)
        attributes=[{'tag':tag} for tag in ['PL_NAME','PL_DIAMETER','PL_SPEC']]
        updates=[]
        rt=self.rt
        rt.builtins.update({
            'pl:plant':lambda e:p, 'pl:writable':lambda e:True,
            'pl:data-get':lambda e,key:1000.,'vlax-ename->vla-object':lambda e:e,
            'vlax-invoke':lambda obj,method:attributes,
            'pl:db-get':lambda key,default:[Pair(Sym('scale'),100.),Pair(Sym('paper_height'),2.5)] if key=='PLOT_OPTIONS' else default,
            'entget':lambda e:[Pair(67,0),[10,200.,300.,0.]],
            'trans':lambda point,*args:point, 'vlax-3d-point':lambda p:p,
            'vla-get-TagString':lambda a:a['tag'], 'vla-Update':lambda *args:updates.append(args),
        })
        rt.builtins={k.lower():v for k,v in rt.builtins.items()}
        for method,key in [('TextString','text'),('Height','height'),('Color','color'),
                           ('Rotation','rotation'),('Alignment','alignment'),
                           ('TextAlignmentPoint','point'),('Invisible','invisible')]:
            rt.builtins['vla-put-'+method.lower()]=lambda a,v,key=key:a.__setitem__(key,v)
        rt.env[Sym(':vlax-true')]=True
        rt.env[Sym(':vlax-false')]=False
        self.assertTrue(rt.call('pl:refresh-symbol','tree'))
        self.assertEqual([chinese(a['text']) for a in attributes],['香樟','8','P001'])
        self.assertEqual([a['height'] for a in attributes],[250.,250.,250.])
        self.assertEqual(attributes[0]['point'],[200.,487.5,0.])
        self.assertEqual(attributes[1]['point'],[200.,112.5,0.])
        self.assertTrue(attributes[2]['invisible'])
        self.assertEqual(len(updates),4)
        self.assertTrue(rt.call('pl:refresh-symbol','tree'))
        self.assertEqual(len(updates),4,'Unchanged symbols must not write attributes again')
        # Paper-space glyph text is computed at 1:1 despite the model plot scale.
        rt.builtins['entget']=lambda e:[Pair(67,1),[10,200.,300.,0.]]
        rt.call('pl:refresh-symbol','tree')
        self.assertEqual(attributes[0]['height'],2.5)
        self.assertEqual(len(updates),8)

    def test_export_schedule_contains_number_and_both_diameters(self):
        p=self.put('spec_no','P001')
        p=self.put('caliper',8.,p)
        lines=[]
        self.rt.builtins['write-line']=lambda line,*args:lines.append(chinese(line))
        self.rt.call('pl:write-csv','file',[[None,p,2]])
        self.assertEqual(next(csv.reader([lines[0]])),
                         ['规格编号','植物名称','胸径cm','地径cm','高度cm','冠幅cm','数量','单位'])
        self.assertEqual(next(csv.reader([lines[1]])),['P001','香樟','12','8','400','300','2','株'])

    def test_seed_catalogue_complete_editable_and_sourced(self):
        with (ROOT/'src/plantcatalog.tsv').open(encoding='utf-8') as f:
            rows=list(csv.DictReader(f,delimiter='\t'))
        self.assertGreaterEqual(len(rows),300)
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        self.assertEqual(len({r['name'] for r in rows}),len(rows))
        self.assertEqual({int(r['category']) for r in rows},set(range(10)))
        for row in rows:
            self.assertIn('gov.cn',row['source'])
            self.assertEqual(row['supply'],'待询价')
            record=self.rt.call('pl:species-from-line',gbk('\t'.join(row.values())))
            self.assertIsNotNone(record,row['name'])


    def test_reserved_numbers_survive_definition_number_change(self):
        original=self.put('spec_no','P001')
        database=self.memory_database([original])
        self.rt.call('pl:remember-spec',original)
        changed=self.put('spec_no','P005',original)
        self.rt.call('pl:save-def',changed)
        self.assertEqual(self.rt.call('pl:next-spec-number',self.rt.call('pl:used-specs')),'P002')
        wrong=self.put('crown',5.,original)
        self.assertIsNotNone(self.rt.call('pl:history-error',wrong))
        self.assertIsNone(self.rt.call('pl:history-error',original))

    def test_edit_real_specs_gets_new_number_but_style_edit_keeps_number(self):
        original=self.put('spec_no','P001')
        self.memory_database([original])
        changed=self.put('crown',5.,original)
        changed=self.rt.call('pl:prepare-edited-spec',changed,original,[original])
        self.assertEqual(self.get('spec_no',changed),'P002')
        styled=self.rt.call('pl:prepare-edited-spec',self.put('style',1,original),original,[original])
        self.assertEqual(self.get('spec_no',styled),'P001')


    def test_project_plant_list_deduplicates_specs_and_preserves_cultivars(self):
        a=self.put('species_id','S1')
        b=self.put('spec_no','P002',a)
        b=self.put('crown',5.,b)
        b=self.put('name',gbk(' 香樟 '),b)
        cultivar=self.put('name',gbk('香樟1号'),a)
        catalogue=[[Pair(Sym('id'),'S1'),Pair(Sym('category'),0),Pair(Sym('region'),gbk('上海'))]]
        rows=self.rt.call('pl:plant-list-rows',[a,b,cultivar],catalogue)
        self.assertEqual([[chinese(v) for v in row] for row in rows],
                         [['1','香樟','常绿乔木','上海'],['2','香樟1号','常绿乔木','上海']])

    def test_project_spec_table_keeps_unplaced_specs_and_both_diameters(self):
        a=self.put('spec_no','P001')
        b=self.put('spec_no','P002',a)
        b=self.put('dbh',0.,b)
        b=self.put('caliper',8.,b)
        b=self.put('crown',5.,b)
        rows=self.rt.call('pl:spec-list-rows',[a,b])
        self.assertEqual(len(rows),2)
        self.assertEqual([chinese(v) for v in rows[1]],
                         ['P002','香樟','乔木','——','8','400','500','株'])
        self.assertEqual(self.rt.call('pl:spec-list-rows',None),None)

    def test_new_tables_use_separate_layers_and_do_not_require_placed_plants(self):
        calls=[]
        self.rt.builtins['pl:ai-model-trees']=lambda:None
        self.rt.builtins['pl:all-areas']=lambda:None
        self.rt.builtins['pl:all-project-sources']=lambda:None
        self.rt.builtins['pl:db-get']=lambda k,d:d
        self.rt.builtins['pl:defs']=lambda:[self.p]
        self.rt.builtins['pl:catalog']=lambda:None
        self.rt.builtins['pl:design-table-work']=lambda *args:calls.append(args)
        self.rt.call('pl:list-table-work')
        self.rt.call('pl:spec-table-work')
        self.assertEqual([chinese(args[0]) for args in calls],
                         ['PL_表格_植物名录','PL_表格_植物规格'])
        self.assertEqual([len(args[2]) for args in calls],[4,8])
        self.assertEqual([len(args[3]) for args in calls],[1,1])

# Avoid repeating Rules' 27 inherited tests in discovery.
for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in DesignRules.__dict__:
        setattr(DesignRules,name,None)

if __name__=='__main__': unittest.main()
