from pathlib import Path
import os,subprocess,tempfile,unittest

class NativeLandingSize(unittest.TestCase):
 def test_production_landing_method_keeps_the_requested_font(self):
  csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
  if not csc.is_file():self.skipTest('.NET Framework compiler required')
  root=Path(__file__).resolve().parents[2]
  source=(root/'bridge/src/PlantAreaLeader.cs').read_text(encoding='utf-8')
  start=source.index('  static void SetAreaLanding(');end=source.index('  static Point3d OutputPoint(',start)
  method=source[start:end]
  template=Path(__file__).with_name('AreaLandingSizingTests.cs').read_text(encoding='utf-8')
  with tempfile.TemporaryDirectory(prefix='countingtrees_landing_') as tmp:
   cs=Path(tmp)/'SizingTests.cs';dll=Path(tmp)/'SizingTests.dll'
   cs.write_text(template.replace('/* PRODUCTION_METHOD */',method),encoding='utf-8')
   subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/out:'+str(dll),str(cs)],check=True,capture_output=True)
   command="[System.Reflection.Assembly]::LoadFrom('"+str(dll).replace("'","''")+"') | Out-Null; [AreaLandingSizingTests]::Run()"
   result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,errors='replace',timeout=30)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   self.assertIn('PASS 12',result.stdout,result.stdout+result.stderr)
