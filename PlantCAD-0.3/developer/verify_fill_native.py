"""Verify native filling and saved associations on a copy of a supplied case DWG.

The source drawing and the running desktop CAD session are never modified.
Private drawings and generated reports are excluded from public packages.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drawing',required=True,type=Path)
    args=parser.parse_args()
    source=args.drawing.resolve();before=hashlib.sha256(source.read_bytes()).hexdigest()
    token=uuid.uuid4().hex[:8];out=ROOT/'bridge/host-output'/('fill-native-'+token);out.mkdir(parents=True)
    drawing=out/'input.dwg';shutil.copy2(source,drawing)
    production=ROOT/'bridge/PlantCADBridge.dll';dll=out/'FillCaseProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/reference:System.Web.Extensions.dll',
        '/out:'+str(dll),'/reference:'+str(production)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/FillCaseProbe.cs')],check=True)
    quote=lambda p:'"'+p.as_posix()+'"'
    report={'passed':False,'source_sha256':before,'receiver_sha256':hashlib.sha256(production.read_bytes()).hexdigest(),'output':str(out),'runs':[]}
    try:
        for phase,command in [('initial','PC_FILL_CASE_TEST'),('reopen','PC_FILL_CASE_REOPEN')]:
            commands=['_.NETLOAD',quote(production),'_.NETLOAD',quote(dll),command]
            if phase=='initial':commands+=['_.QSAVE']
            commands+=['_.QUIT','_No'];script=out/(phase+'.scr');script.write_bytes(('\r\n'.join(commands)+'\r\n').encode('gbk'))
            run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(drawing),'/s',str(script),'/isolate','CTFill'+token,str(out/'cad-profile')],cwd=out,
                creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=120)
            (out/(phase+'-console.bin')).write_bytes(run.stdout)
            result=out/('fill-'+phase+'.json')
            data=json.loads(result.read_text(encoding='utf-8-sig')) if result.exists() else {'passed':False,'error':'Native script did not produce a report'}
            report['runs'].append(data);print(phase,json.dumps(data if not data['passed'] else {k:v for k,v in data.items() if k!='rows'},ensure_ascii=False),flush=True)
            if run.returncode or not data['passed']:raise AssertionError('Native fill validation failed: '+phase)
        report['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
        report['checks']=sum(r['checks'] for r in report['runs']);report['passed']=report['original_unchanged']
    finally:
        (ROOT/'developer/fill-native-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='runs'},ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit('Fill verification failed')
if __name__=='__main__':main()
