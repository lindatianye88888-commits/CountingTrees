"""Read-only region/annotation audit against a saved DWG copy."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=ROOT.parent/'20261016压力测试01/Drawing2.dwg'
out=ROOT/'bridge/host-output'/('area-label-audit-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg')
dll=out/'AreaLabelAudit.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/reference:System.Web.Extensions.dll','/out:'+str(dll)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/AreaLabelAudit.cs')],check=True)
quote=lambda p:'"'+str(p).replace('\\','/')+'"'
script=out/'audit.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(dll),'PC_AREA_LABEL_AUDIT','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
(out/'console.bin').write_bytes(run.stdout)
r=json.loads((out/'area-label-audit.json').read_text(encoding='utf-8-sig'))
areas=[x for x in r['objects'] if x['role']=='AREA'];labels=[x for x in r['objects'] if x['role']=='AREA_LABEL']
linked={x['source'] for x in labels};r['missing_labels']=[x for x in areas if x['handle'] not in linked]
r['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
(out/'area-label-audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTPUT',out,'AREAS',len(areas),'LABELS',len(labels),'MISSING',len(r['missing_labels']),'ORIGINAL_UNCHANGED',r['original_unchanged'],flush=True)
for row in r['missing_labels']:print('MISSING',json.dumps(row,ensure_ascii=False))
print('HEIGHTS',sorted([(x.get('height'),x['handle'],x.get('text')) for x in labels],key=lambda x:x[0]))
