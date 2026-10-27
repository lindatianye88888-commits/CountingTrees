"""Export source geometry and every recognized face on a read-only DWG copy."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
p=argparse.ArgumentParser();p.add_argument('--drawing',type=Path,default=ROOT.parent/'案例2/植物配置20261021.dwg');a=p.parse_args()
out=ROOT/'bridge/host-output'/('coverage-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
before=hashlib.sha256(a.drawing.read_bytes()).hexdigest();shutil.copy2(a.drawing,out/'input.dwg');dll=out/'AreaCoverageAudit.dll'
sources=[ROOT/'bridge/src/PlantAreaGeometry.cs',ROOT/'bridge/src/PlantAreaRepair.cs',ROOT/'developer/tests/AreaCoverageAudit.cs']
instrumented=out/'PlantAreaGeometry.cs'
text=sources[0].read_text(encoding='utf-8').replace('if(regions.Count!=1){','if(regions.Count!=1){AreaCoverageAudit.Reject("regions="+regions.Count,curves,outline);').replace('catch(Autodesk.AutoCAD.Runtime.Exception){InvalidContours++;}', 'catch(Autodesk.AutoCAD.Runtime.Exception ex){AreaCoverageAudit.Reject(ex.ToString(),curves,outline);InvalidContours++;}')
text=text.replace('if(edge.To!=next.From)return null;', 'if(edge.To!=next.From){AreaCoverageAudit.Reject("discontinuous ring",curves,new List<Point3d>());return null;}')
text=text.replace('>tolerance)return null;', '>tolerance){AreaCoverageAudit.Reject("endpoint displacement",curves,new List<Point3d>());return null;}')
text=text.replace('catch(Autodesk.AutoCAD.Runtime.Exception){return null;}', 'catch(Autodesk.AutoCAD.Runtime.Exception ex){AreaCoverageAudit.Reject("fallback: "+ex.ToString(),input,new List<Point3d>());return null;}')
text=text.replace('foreach(DBObject obj in result)obj.Dispose();return null;', 'AreaCoverageAudit.Reject("fallback rejected count="+result.Count+" expected="+expected+" length="+length+" tolerance="+tolerance+(result.Count==1?" actual="+((Region)result[0]).Area:""),curves,new List<Point3d>());foreach(DBObject obj in result)obj.Dispose();return null;')
instrumented.write_text(text,encoding='utf-8');sources[0]=instrumented
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:System.Web.Extensions.dll']+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+list(map(str,sources)),check=True)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
script=out/'run.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',q(dll),'PC_AREA_COVERAGE','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'console.bin').write_bytes(run.stdout);assert hashlib.sha256(a.drawing.read_bytes()).hexdigest()==before
print('OUTPUT',out,flush=True)
data=json.loads((out/'coverage.json').read_text(encoding='utf-8-sig'))
for name,layer in data.items():print(name,len(layer['sources']),[{k:r[k] if k not in ['faces','pieces','nodes','repairs','rejected'] else len(r[k]) for k in r} for r in layer['runs']],flush=True)
