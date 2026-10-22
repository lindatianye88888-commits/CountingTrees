"""Verify compiled SDK references and bundle routing; not a substitute for CAD host testing."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bridge'))
from cad_targets import TARGETS,COMPATIBILITY_URL
import install_panel

def main():
    csc=Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe')
    exe=ROOT/'developer/bin/AssemblyReferenceProbe.exe';exe.parent.mkdir(exist_ok=True)
    subprocess.run([str(csc),'/nologo','/target:exe','/out:'+str(exe),str(ROOT/'developer/tests/AssemblyReferenceProbe.cs')],check=True)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    rows=[]
    for target in TARGETS:
        binary=ROOT/target['module'];meta=json.loads((binary.parent/'build-info.json').read_text(encoding='utf-8'))
        assert meta['sha256']==digest(binary) and meta['inputs']['target']==target['key']
        for name,sha in meta['inputs'].items():
            if name.endswith('.cs'):assert digest(ROOT/'bridge/src'/name)==sha,name
        for attempt in range(4):
            try:
                run=subprocess.run([str(exe),str(binary)],encoding='utf-8',capture_output=True,check=True,timeout=10);break
            except PermissionError:
                if attempt==3:raise
                time.sleep(.5)
        references=dict(line.strip().split('|',1) for line in run.stdout.splitlines() if '|' in line)
        expected=target['series_min'][1:]
        assert set(references)=={'acmgd','acdbmgd','accoremgd'},references
        assert all(value.startswith(expected+'.') for value in references.values()),(target,references)
        rows.append({**target,'compiled':True,'host_tested':False,'sha256':digest(binary),'autodesk_references':references})
        print('SDK references verified:',target['key'],references,flush=True)
    # XML generation consumes the same supported-version table; SDK references
    # above are checked independently against the actual compiled assemblies.
    xml=install_panel.bundle_xml();(ROOT/'developer/PackageContents-preview.xml').write_text(xml,encoding='utf-8')
    report={'passed':True,'scope':'Six real SDK-specific x64 compiles and assembly reference metadata; generated nonoverlapping AutoCAD 2014—2024 bundle ranges. No 2015—2024 runtime, Tianzheng, mouse, or print acceptance.',
        'compatibility_source':COMPATIBILITY_URL,'groups':rows,'unverified_hosts':list(range(2015,2025)),
        'source_sha256':{'bridge/cad_targets.py':digest(ROOT/'bridge/cad_targets.py'),'install_panel.py':digest(ROOT/'install_panel.py'),'bridge/build_bridge.py':digest(ROOT/'bridge/build_bridge.py')}}
    (ROOT/'developer/multiversion-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
