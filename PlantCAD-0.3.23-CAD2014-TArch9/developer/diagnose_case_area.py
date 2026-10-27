from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=ROOT.parent/'案例2/植物配置20261021.dwg';out=ROOT/'bridge/host-output'/('case-area-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg');dll=out/'CaseAreaProbe.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:System.Web.Extensions.dll','/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/CaseAreaProbe.cs')],check=True)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
script=out/'run.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',q(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',q(dll),'PC_CASE_AREA','_.QUIT','_No'])+'\r\n').encode('gbk'))
p=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'console.bin').write_bytes(p.stdout)
print('OUTPUT',out,flush=True)
for row in json.loads((out/'case-area.json').read_text(encoding='utf-8-sig')):print(json.dumps(row,ensure_ascii=False),flush=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
