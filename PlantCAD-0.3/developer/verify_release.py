"""Verify runtime conversion and distribution without claiming a real CAD host pass."""
from pathlib import Path
import csv,hashlib,json,sys,zipfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'developer'))
from build import ARCHIVE,pack,package_files
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
if manifest.get('compatibility_groups'):
    matrix=json.loads((root/'developer/multiversion-verification.json').read_text(encoding='utf-8'))
    assert matrix.get('passed') and all(
        hashlib.sha256((root/row['module']).read_bytes()).hexdigest()==row['sha256'] for row in matrix['groups'])
    assert all(row.get('host_tested') for row in matrix['groups']), 'Full multi-version release pending actual CAD/Tianzheng host acceptance; compile success alone is insufficient'
for row in manifest['files']:
    data=(root/row['name']).read_bytes()
    assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
    if row['encoding']=='GBK':
        assert not data.startswith(b'\xef\xbb\xbf')
        assert b'\n' not in data.replace(b'\r\n',b'')
        source=(root/'developer/src'/row['name']).read_text(encoding='utf-8').replace('\r\n','\n')
        assert data.decode('gbk').replace('\r\n','\n')==source
with (root/'plantcatalog.tsv').open(encoding='gbk',newline='') as f:
    rows=list(csv.DictReader(f,delimiter='\t'))
assert len(rows)==manifest['catalogue_entries'] and len({r['id'] for r in rows})==len(rows)
sys.path.insert(0,str(root/'developer/tests'))
from lisp_harness import Runtime,parse,Sym
rt=Runtime()
for path in (root/'developer/src').glob('*.lsp'):rt.load(parse(path.read_text(encoding='utf-8')))
rt.builtins['equal']=lambda a,b,fuzz=0:abs(a-b)<=fuzz if isinstance(a,(float,int)) and isinstance(b,(float,int)) else a==b
rt.builtins['prin1']=lambda *args:None
rt.call('c:plcheck')
assert rt.env[Sym('pl:*check-pass*')]==17 and rt.env[Sym('pl:*check-fail*')]==0
reader=json.loads((root/'bridge/reader-verification.json').read_text(encoding='utf-8'))
reader_valid=reader.get('passed') is True and reader.get('reader_source_sha256')==hashlib.sha256((root/'bridge/src/LispValueReader.cs').read_bytes()).hexdigest() and reader.get('test_source_sha256')==hashlib.sha256((root/'bridge/tests/ReaderTests.cs').read_bytes()).hexdigest()
report=dict(release='0.3',automated_rule_tests=manifest['automated_rule_tests'],test_groups=manifest['test_groups'],
            cad_pure_check_simulation=dict(passed=17,failed=0),
            native_value_reader='passed (independent .NET run, current sources)' if reader_valid else 'not verified for current sources',catalogue_entries=len(rows),
            gbk_roundtrip='passed',manifest_hashes='passed',real_cad_host_tested=manifest['host_tested'],host_test_scope=manifest['host_test_scope'])
native=json.loads((root/'developer/native-rule-verification.json').read_text(encoding='utf-8'))
native_valid=native.get('passed') is True and len(native.get('checks',[]))==12 and all(
    hashlib.sha256((root/'developer/src'/name).read_bytes()).hexdigest()==digest
    for name,digest in native.get('source_sha256',{}).items())
ui=json.loads((root/'developer/ui-verification.json').read_text(encoding='utf-8-sig'))
ui_valid=ui.get('passed') is True and ui.get('control_sha256')==hashlib.sha256((root/'bridge/src/PlantCADWorkbench.cs').read_bytes()).hexdigest()
assert native_valid and ui_valid
report['native_engine_rule_checks']=12
report['native_engine_scope']=native['scope']
report['actual_winforms_menu_click_checks']=ui['clickable_menu_actions']
placement=json.loads((root/'developer/placement-verification.json').read_text(encoding='utf-8'))
placement_valid=placement.get('passed') is True and placement.get('assertions')==13 and all(
    hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
    for name,digest in placement.get('source_sha256',{}).items())
assert placement_valid
report['native_placement_interop_assertions']=13
report['native_placement_scope']=placement['scope']
for filename,label in [('area-verification.json','native_curve_geometry'),('workflow-verification.json','native_area_registration_and_dwg_roundtrip'),('area-selection-verification.json','native_area_selection_interop'),('normalization-verification.json','native_boundary_normalization'),('output-verification.json','native_linked_planting_output'),('performance-verification.json','real_drawing_fill_and_cache')]:
    record=json.loads((root/'developer'/filename).read_text(encoding='utf-8'))
    hashes=record.get('source_sha256',record.get('runtime_sha256',{}))
    valid=record.get('passed') is True and bool(hashes) and all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
    assert valid,filename+' stale or failed'
    report[label]=dict(assertions=record['assertions'],scope=record['scope'])
reportpath=root/'developer/verification.json'
project=json.loads((root/'developer/project-dialog-verification.json').read_text(encoding='utf-8'))
assert project['passed'] and all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in project['source_sha256'].items())
report['resizable_project_dialog']=dict(assertions=project['assertions'],scope=project['scope'])
case=json.loads((root/'developer/case-desktop-verification.json').read_text(encoding='utf-8'))
assert case['passed'] and case['original_unchanged'] and all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in case['runtime_sha256'].items())
report['case2_area_and_project_desktop']=dict(assertions=case['assertions'],scope=case['scope'])
coverage=json.loads((root/'developer/case-coverage-verification.json').read_text(encoding='utf-8'))
assert coverage['passed'] and coverage['original_unchanged'] and coverage['assertions']==18
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in coverage['runtime_sha256'].items())
report['case2_missed_area_coverage']=dict(assertions=coverage['assertions'],scope=coverage['scope'])
orders=json.loads((root/'developer/case-order-verification.json').read_text(encoding='utf-8'))
assert orders['passed'] and orders['original_unchanged'] and all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in orders['runtime_sha256'].items())
report['case2_selection_order']=dict(assertions=orders['assertions'],scope=orders['scope'])

desktop=json.loads((root/'developer/desktop-erase-verification.json').read_text(encoding='utf-8'))
assert desktop['passed'] and desktop['original_unchanged'] and desktop['assertions']>=24
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in desktop['runtime_sha256'].items())
report['desktop_erase_undo']=dict(assertions=desktop['assertions'],scope=desktop['scope'])
manual=json.loads((root/'developer/manual-area-verification.json').read_text(encoding='utf-8'))
assert manual['passed'] and manual['original_unchanged']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in manual['runtime_sha256'].items())
report['manual_area_geometry']=dict(assertions=manual['assertions'],scope=manual['scope'])
manual_desktop=json.loads((root/'developer/desktop-manual-area-verification.json').read_text(encoding='utf-8'))
assert manual_desktop['passed'] and manual_desktop['manual_edges_result']=='T' and manual_desktop['original_unchanged']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in manual_desktop['runtime_sha256'].items())
report['desktop_manual_area']=dict(assertions=manual_desktop['assertions'],scope=manual_desktop['scope'])
for filename,label in [('schedule-split-verification.json','linked_split_schedules'),('desktop-schedule-verification.json','desktop_schedule_display'),('label-feedback-verification.json','native_label_feedback'),('area-leader-flow-verification.json','native_two_point_area_leader_flow'),('desktop-label-feedback-verification.json','desktop_label_feedback'),('desktop-legend-ui-verification.json','desktop_named_legends_and_project_columns'),('output-preview-verification.json','native_export_and_owned_window_preview')]:
    record=json.loads((root/'developer'/filename).read_text(encoding='utf-8'))
    assert record['passed'] and record['original_unchanged']
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in record['runtime_sha256'].items())
    report[label]=dict(assertions=record['assertions'],scope=record['scope'])
reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
report['archive_files']=len(package_files())
reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
pack()
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(set(z.namelist()))==report['archive_files']
    assert not any('/bridge/runtime/' in n or '/host-output/' in n or '/developer/bin/' in n or n.endswith('/install-state.json') or n.endswith('/queue-root.json') for n in z.namelist())
    assert 'PlantCAD-0.3/install_panel.py' in z.namelist()
    assert 'PlantCAD-0.3/docs/images/操作浮窗.png' in z.namelist()
    for row in manifest['files']:assert z.read(root.name+'/'+row['name'])==(root/row['name']).read_bytes()
digest=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
ARCHIVE.with_suffix('.zip.sha256').write_text(digest+'  '+ARCHIVE.name+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
print('Final archive SHA256: '+digest)
