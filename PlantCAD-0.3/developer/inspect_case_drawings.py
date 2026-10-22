"""Read case DWGs using AutoCAD copies; export diagnostic DXFs and text inventories."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def quote(p):return '"'+str(p).replace('\\','/')+'"'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',type=Path);args=parser.parse_args()
    source=ROOT.parent/'案例'
    out=args.resume.resolve() if args.resume else ROOT/'bridge/host-output'/('case-review-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True,exist_ok=True)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.dwg')}
    (out/'sources-before.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in hashes:
        if not (out/name).exists():shutil.copy2(source/name,out/name)
    dll=out/'CaseDrawingProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/reference:System.Web.Extensions.dll','/out:'+str(dll)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/CaseDrawingProbe.cs')],check=True)
    script=out/'inspect.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(dll),'PC_CASE_INSPECT','_.QUIT','_No'])+'\r\n').encode('gbk'))
    for name in hashes:
        if (out/name).with_suffix('.json').exists():continue
        if args.resume and name=='XCA2.dwg':print('SKIPPED prior bounded timeout '+name,flush=True);continue
        run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/name),'/s',str(script)],creationflags=subprocess.CREATE_NO_WINDOW,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=75)
        (out/(name+'.console')).write_bytes(run.stdout)
        if run.returncode or not (out/name).with_suffix('.json').exists():raise RuntimeError(name+' inspect failed')
        print('INSPECTED '+name,flush=True)
    assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    (out/'sources.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    print('OUTPUT '+str(out),flush=True)
if __name__=='__main__':main()
