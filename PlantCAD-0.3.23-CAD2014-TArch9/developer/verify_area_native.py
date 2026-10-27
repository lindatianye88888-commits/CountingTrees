from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
cad=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--drawing",type=Path,required=True);args=ap.parse_args()
 out=ROOT/'bridge/host-output'/('area-native-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 fixture=args.drawing
 before=hashlib.sha256(fixture.read_bytes()).hexdigest();shutil.copy2(fixture,out/'input.dwg')
 csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
 dll=out/'AreaProbe.dll';sources=[ROOT/'bridge/src/PlantAreaGeometry.cs',ROOT/'bridge/src/PlantAreaRepair.cs',ROOT/'developer/tests/AreaProbe.cs']
 subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll)]+['/reference:'+str(cad/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+list(map(str,sources)),check=True)
 script=out/'test.scr';script.write_bytes(('_.NETLOAD\n"'+str(dll).replace('\\','/')+'"\nPC_AREA_TEST\n_.QUIT\n').replace('\n','\r\n').encode('gbk'))
 env=os.environ.copy();env['PC_AREA_RESULT']=str(out/'result.txt')
 report={'passed':False,'scope':'AutoCAD 2014 kernel: unchanged curve areas, adaptive inferred gap recovery, mixed 13-cell diagram and automatic interior label anchors; no Tianzheng GUI or mouse acceptance','source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
 try:
  run=subprocess.run([str(cad/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,env=env,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=55)
  (out/'console.bin').write_bytes(run.stdout);value=(out/'result.txt').read_text(encoding='utf-8') if (out/'result.txt').exists() else 'MISSING'
  print(value,flush=True)
  assert run.returncode==0 and value.startswith('PASS '),(run.returncode,value)
  report.update(passed=True,assertions=int(value.split()[1]),original_drawing_unchanged=hashlib.sha256(fixture.read_bytes()).hexdigest()==before)
 finally:(ROOT/'developer/area-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
