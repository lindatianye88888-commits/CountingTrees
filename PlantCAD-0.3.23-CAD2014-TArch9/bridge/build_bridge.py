"""Build against a user-owned AutoCAD 2014 x64 install; do not redistribute SDK DLLs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parent
def build(cad_dir=None,test_reader=False):
    cad=Path(cad_dir or os.environ.get('PLANTCAD_CAD_DIR',r'D:\Program Files (x86)\CAD2014\AutoCAD 2014'))
    csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not csc.is_file(): raise SystemExit('.NET Framework 4 compiler not found.')
    references=[cad/n for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]
    if not all(p.is_file() for p in references): raise SystemExit('AutoCAD 2014 managed SDK DLLs not found; specify --cad-dir.')
    wpf=csc.parent/'WPF'
    base=[str(csc),'/nologo','/utf8output','/optimize+','/reference:System.Web.Extensions.dll','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll']+['/reference:'+str(wpf/name) for name in ['WindowsBase.dll','PresentationCore.dll','PresentationFramework.dll']]
    if test_reader:
        reader_report={'passed':False,'at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                       'reader_source_sha256':hashlib.sha256((ROOT/'src/LispValueReader.cs').read_bytes()).hexdigest(),
                       'test_source_sha256':hashlib.sha256((ROOT/'tests/ReaderTests.cs').read_bytes()).hexdigest()}
        (ROOT/'reader-verification.json').write_text(json.dumps(reader_report,indent=2),encoding='utf-8')
        with tempfile.TemporaryDirectory(prefix='plantcad_reader_') as temp:
            test=Path(temp)/'ReaderTests.exe'
            subprocess.run(base+['/target:exe','/out:'+str(test),str(ROOT/'src/LispValueReader.cs'),str(ROOT/'tests/ReaderTests.cs')],check=True)
            for attempt in range(4):
                try:
                    subprocess.run([str(test)],check=True)
                    break
                except PermissionError:
                    if attempt==3:raise
                    time.sleep(.5)
        reader_report['passed']=True
        (ROOT/'reader-verification.json').write_text(json.dumps(reader_report,indent=2),encoding='utf-8')
    sources=[ROOT/'src/PlantCADBridge.cs',ROOT/'src/LispValueReader.cs',ROOT/'src/PlantCADPanel.cs',ROOT/'src/PlantCADWorkbench.cs',ROOT/'src/PlantAreaGeometry.cs',ROOT/'src/PlantAreaRepair.cs',ROOT/'src/PlantAreaInteraction.cs',ROOT/'src/PlantAreaNormalization.cs',ROOT/'src/PlantInstanceEditing.cs',ROOT/'src/PlantOutput.cs']
    sources.append(ROOT/'src/PlantAreaLeader.cs')
    sources.append(ROOT/'src/PlantAreaManual.cs')
    sources.append(ROOT/'src/PlantAreaLabelEdit.cs')
    sources.extend([ROOT/'src/PlantProjectDialog.cs',ROOT/'src/PlantProjectBridge.cs'])
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs={str(p.name):digest(p) for p in sources+references+[csc]}
    cache_path=ROOT/'build-info.json'
    try:cache=json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):cache={}
    receiver=ROOT/'PlantCADBridge.dll'
    if cache.get('inputs')==inputs and receiver.is_file() and cache.get('sha256')==digest(receiver):
        print('Reused receiver with unchanged source, SDK, compiler and verified hash.')
        return
    subprocess.run(base+['/target:library','/platform:x64','/out:'+str(ROOT/'PlantCADBridge.dll')]+
                   ['/reference:'+str(p) for p in references]+
                   [str(p) for p in sources],check=True)
    cache_path.write_text(json.dumps({'target':'AutoCAD 2014 x64','inputs':inputs,'sha256':digest(receiver)},indent=2),encoding='utf-8')
    print('Built AutoCAD 2014 x64 receiver; actual host behavior requires CAD testing.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cad-dir');parser.add_argument('--test-reader',action='store_true');args=parser.parse_args()
    build(args.cad_dir,args.test_reader)
