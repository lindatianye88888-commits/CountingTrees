"""Read saved user drawing only through an isolated DWG copy and record native timings."""
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,uuid,os
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--drawing',type=Path,required=True);args=parser.parse_args()
    out=ROOT/'bridge/host-output'/('performance-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    source=args.drawing.resolve();before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg')
    dll=out/'PerformanceProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/reference:System.Web.Extensions.dll','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/PerformanceProbe.cs')],check=True)
    quote=lambda p:'"'+str(p).replace('\\','/')+'"'
    script=out/'test.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'PC_PERFORMANCE_PROBE','_.QUIT','_No'])+'\r\n').encode('gbk'))
    run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    (out/'console.bin').write_bytes(run.stdout)
    result=out/'performance.json'
    if not result.exists():raise RuntimeError('No native report: '+str(out))
    report=json.loads(result.read_text(encoding='utf-8-sig'));report.update(source=str(source),original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before,receiver_sha256=hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).hexdigest())
    samples=report.get('areas',[])
    report['fills_succeeded']=sum(not item['fill'].startswith('ERROR:') for item in samples)
    report['fills_failed']=len(samples)-report['fills_succeeded']
    report['repeat_signature_total_ms']=sum(item['repeat_signature_ms'] for item in samples)
    report['first_signature_total_ms']=sum(item['signature_ms'] for item in samples)
    result.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    verification={'passed':bool(samples) and report.get('passed') and report['fills_failed']==0 and all(item['signature_ok'] and item['repeat_equal'] for item in samples),
                  'scope':'AutoCAD 2014 Core Console on a saved drawing copy: real REGION fills, reversed-edge compatibility and warm boundary-cache timings; not desktop UI or COM latency measurement',
                  'assertions':len(samples)*3,'drawing_sha256':before,'original_unchanged':report['original_unchanged'],'output':str(out),
                  'fills_succeeded':report['fills_succeeded'],'fills_failed':report['fills_failed'],
                  'repeat_signature_total_ms':report['repeat_signature_total_ms'],'first_signature_total_ms':report['first_signature_total_ms'],
                  'runtime_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp']}}
    (ROOT/'developer/performance-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));print('OUTPUT',out)
if __name__=='__main__':main()
