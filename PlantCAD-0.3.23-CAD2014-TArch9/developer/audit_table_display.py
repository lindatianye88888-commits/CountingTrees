"""Inspect text contents and effective display heights in a saved drawing copy."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=ROOT.parent/'20261016压力测试01/Drawing2.dwg'
out=ROOT/'bridge/host-output'/('table-display-audit-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg');dll=out/'TableDisplayAudit.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/reference:System.Web.Extensions.dll','/out:'+str(dll)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/TableDisplayAudit.cs')],check=True)
quote=lambda p:'"'+str(p).replace('\\','/')+'"'
script=out/'audit.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(dll),'PC_TABLE_DISPLAY_AUDIT','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
(out/'console.bin').write_bytes(run.stdout)
assert run.returncode==0 and hashlib.sha256(source.read_bytes()).hexdigest()==before
data=json.loads((out/'table-display-audit.json').read_text(encoding='utf-8-sig'))
print('OUTPUT',out,flush=True)
for table in data:
 print('TABLE',table['handle'],'size',table['rows'],table['columns'])
 for row in table['sample']:
  print('ROW',row['row'],'row_height',row['height'],[(c['text'],c['height'],c['font'],c['fixed_height'],c['contents']) for c in row['cells']])
