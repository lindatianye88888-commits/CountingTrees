from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--drawing',type=Path,required=True);args=ap.parse_args()
 out=ROOT/'bridge/host-output'/('normalize-native-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 before=hashlib.sha256(args.drawing.read_bytes()).hexdigest();shutil.copy2(args.drawing,out/'input.dwg')
 csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';dll=out/'NormalizationProbe.dll'
 subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/NormalizationProbe.cs')],check=True)
 q=lambda p:'"'+str(p).replace('\\','/')+'"'
 script=out/'test.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',q(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',q(dll),'PC_NORMALIZE_TEST','_.QUIT','_No'])+'\r\n').encode('gbk'))
 env=os.environ.copy();env['PC_NORMALIZE_RESULT']=str(out/'result.txt')
 names=['bridge/PlantCADBridge.dll','bridge/src/PlantAreaNormalization.cs','bridge/src/PlantAreaInteraction.cs','developer/tests/NormalizationProbe.cs']
 report={'passed':False,'scope':'AutoCAD 2014 Core Console production selection/normalization: LINE, PLINE, old 2D/3D POLYLINE, nonplanar SPLINE, ARC/CIRCLE/ELLIPSE, plan XY geometry retained, ByLayer color, source metadata/handles retained, unselected entities/locked layers preserved and failure rollback; no Tianzheng desktop undo acceptance','source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
 try:
  run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,env=env,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=55)
  (out/'console.bin').write_bytes(run.stdout);value=(out/'result.txt').read_text(encoding='utf-8-sig') if (out/'result.txt').exists() else 'MISSING';print(value,flush=True)
  assert run.returncode==0 and value.startswith('PASS '),(run.returncode,value,str(out))
  report.update(passed=True,assertions=int(value.split()[1]),original_drawing_unchanged=hashlib.sha256(args.drawing.read_bytes()).hexdigest()==before)
 finally:(ROOT/'developer/normalization-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
