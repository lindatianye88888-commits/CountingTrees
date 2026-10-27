"""Compare the same case geometry under drawing, reverse, handle and shuffled input."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=ROOT.parent/'案例2/植物配置20261021.dwg'
before=hashlib.sha256(source.read_bytes()).hexdigest()
out=ROOT/'bridge/host-output'/('case-orders-'+uuid.uuid4().hex[:8]);out.mkdir()
shutil.copy2(source,out/'input.dwg');dll=out/'CaseOrders.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/target:library','/platform:x64','/out:'+str(dll),'/reference:System.Web.Extensions.dll','/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/CaseAreaProbe.cs')],check=True)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
script=out/'run.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',q(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',q(dll),'PC_CASE_ORDER_TEST','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'console.bin').write_bytes(run.stdout)
rows=json.loads((out/'case-orders.json').read_text(encoding='utf-8-sig'))
geometries={r['mode']:json.loads((out/('order-'+r['mode']+'.json')).read_text(encoding='utf-8-sig')) for r in rows}
def signature(g):
    result=[]
    for f in g['faces']:
        points=f['outline']
        result.append(tuple(round(v,2) for v in [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points),f['area']]))
    return sorted(result)
same=all(signature(g)==signature(geometries['drawing']) for g in geometries.values())
baseline=json.loads((ROOT/'developer/fixtures/case2-baseline.json').read_text(encoding='utf-8'))
assert baseline['source_sha256']==before,'Case source changed; review and update independent baseline before accepting counts'
retained=[]
for original in baseline['faces']:
    found=False
    for face in geometries['drawing']['faces']:
        points=face['outline'];bounds=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        if max(abs(a-b) for a,b in zip(bounds,original['bounds']))<.05 and abs(face['area']-original['area'])<=max(1.0,original['area']*1e-7):found=True;break
    retained.append(found)
unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before
report={'passed':run.returncode==0 and same and unchanged and all(retained) and all(r['result']=='118' for r in rows),'assertions':4+len(retained),'baseline_regions_retained':sum(retained),'orders':rows,'source':str(source),'original_unchanged':unchanged,'scope':'AutoCAD 2014 case2: 118 computed cells including one microscopic extra fragment; all 117 previously audited cells retain their bounds/areas; original/reverse/handle/shuffled selections identical','runtime_sha256':{'bridge/PlantCADBridge.dll':hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).hexdigest()},'output':str(out)}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTPUT',out,'ORDERS',rows,'EQUAL GEOMETRY',same,'BASELINE RETAINED',sum(retained),'/',len(retained),flush=True)
if not report['passed']:raise SystemExit('Case order invariance failed')
(ROOT/'developer/case-order-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
