"""Build a reproducible source package and AutoCAD 2014 x64 AI receiver."""
from pathlib import Path
import csv
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
import zipfile
DEV=Path(__file__).resolve().parent
ROOT=DEV.parent
ARCHIVE=ROOT.parent/'CountingTrees_数树_0.3_浮窗开发版.zip'
def package_files():
    return [p for p in sorted(ROOT.rglob('*')) if p.is_file()
            and p.name not in ('install-state.json','queue-root.json') and '__pycache__' not in p.parts and p.suffix!='.pyc'
            and 'bin' not in p.relative_to(ROOT).parts and 'backups' not in p.relative_to(ROOT).parts and 'runtime' not in p.relative_to(ROOT).parts and 'host-output' not in p.relative_to(ROOT).parts]
def pack():
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED) as z:
        for path in package_files():z.write(path,Path(ROOT.name)/path.relative_to(ROOT))
def build():
    counts={}
    for name,directory in [('plant_rules',DEV/'tests'),('mcp_protocol',ROOT/'bridge/tests')]:
        suite=unittest.defaultTestLoader.discover(str(directory),pattern='test_*.py')
        counts[name]=suite.countTestCases()
        result=unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():raise SystemExit('Build stopped: tests failed.')
    subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'bridge/build_bridge.py'),'--all'],check=True)
    subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'bridge/configure_clients.py')],check=True)
    files=[]
    for src in sorted((DEV/'src').iterdir()):
        if src.suffix not in ('.lsp','.dcl','.tsv'):continue
        text=src.read_text(encoding='utf-8').replace('\r\n','\n')
        data=text.replace('\n','\r\n').encode('gbk',errors='strict')
        (ROOT/src.name).write_bytes(data)
        files.append(dict(name=src.name,size=len(data),sha256=hashlib.sha256(data).hexdigest(),encoding='GBK'))
    binary=ROOT/'bridge/PlantCADBridge.dll'
    files.append(dict(name='bridge/PlantCADBridge.dll',size=binary.stat().st_size,
                      sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),encoding='binary'))
    sys.path.insert(0,str(ROOT/'bridge'))
    from cad_targets import TARGETS,COMPATIBILITY_URL
    for target in TARGETS:
        if target['key']=='2014':continue
        module=ROOT/target['module']
        files.append(dict(name=target['module'],size=module.stat().st_size,sha256=hashlib.sha256(module.read_bytes()).hexdigest(),encoding='binary'))
    with (DEV/'src/plantcatalog.tsv').open(encoding='utf-8') as f:
        catalogue_count=sum(1 for _ in csv.DictReader(f,delimiter='\t'))
    readme=(ROOT/'docs/使用说明.md').read_text(encoding='utf-8')
    for title in ['开发说明.md','验证说明.md','CAD实测清单.md','本轮操作反馈.md','整体复查报告.md','两点引线与样式稳定性.md','兼容性与测试矩阵.md']:
        readme=readme.replace(']('+title+')','](docs/'+title+')')
    readme=readme.replace('](images/','](docs/images/')
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    host_scopes=[]
    for record,scope in [
        ('panel-verification.json','AutoCAD 2014 x64 + TArch9: native workbench, per-document autoload, species/spec UI, crown completion and dynamic placement'),
        ('host-verification.json','AutoCAD 2014 x64 structured MCP plant adjustment'),
        ('compatibility-verification.json','AutoCAD 2014 x64 + installed TArch9: saved base loading, command coexistence, MCP read and test plant insertion')]:
        try:host=json.loads((DEV/record).read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        same_receiver=host.get('receiver_sha256')==hashlib.sha256(binary.read_bytes()).hexdigest()
        same_runtime=bool(host.get('runtime_sha256')) and all(
            (ROOT/name).is_file() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
            for name,digest in host.get('runtime_sha256',{}).items())
        if host.get('passed') is True and same_receiver and same_runtime:host_scopes.append(scope)
    tested=bool(host_scopes)
    try:
        desktop=json.loads((DEV/'desktop-legend-ui-verification.json').read_text(encoding='utf-8'))
        current=desktop.get('runtime_sha256',{})
        if desktop.get('passed') and desktop.get('original_unchanged') and current and all(
            hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in current.items()):
            host_scopes.append('AutoCAD 2014 x64 + TArch9 desktop: installed bundle on copied DWG, real COM attributes/LDATA, area labels, erase/undo, full and split schedules, named legends and resizable project window')
            tested=True
    except (OSError,ValueError):pass
    manifest=dict(name='CountingTrees',name_zh='数树',display_name='CountingTrees（数树）',author='梅梅的AI景观实验室',contacts={'gmail':'lindatianye88888@gmail.com','qq':'375803231@qq.com'},release='0.3',date=datetime.date.today().isoformat(),revision='0.3.25',target='Windows AutoCAD 2014—2024 x64; matching Tianzheng versions require host acceptance',
                  compatibility_groups=TARGETS,compatibility_source=COMPATIBILITY_URL,unverified_hosts=list(range(2015,2025)),
                  host_tested=False,host_tested_years=[2014] if tested else [],host_test_scope='; '.join(host_scopes+['2015—2024 native host/Tianzheng acceptance pending; not full GUI/print or third-party object editing acceptance']),automated_rule_tests=sum(counts.values()),test_groups=counts,
                  catalogue_entries=catalogue_count,runtime_encoding='CP936/GBK',files=files)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    pack()
    print(f'Built {ROOT.name}: {sum(counts.values())} tests, {catalogue_count} plants, {len(files)} runtime files.')
    return ROOT
if __name__=='__main__':
    sys.dont_write_bytecode=True
    build()
