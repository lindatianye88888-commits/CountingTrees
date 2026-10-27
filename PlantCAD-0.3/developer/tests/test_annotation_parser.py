from pathlib import Path
import os,subprocess,tempfile,unittest

class AnnotationParser(unittest.TestCase):
 def test_production_parser_in_dotnet_framework(self):
  csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
  if not csc.is_file():self.skipTest('.NET Framework compiler is required for native parser checks')
  root=Path(__file__).resolve().parents[2]
  with tempfile.TemporaryDirectory(prefix='countingtrees_parser_') as tmp:
   dll=Path(tmp)/'ParserChecks.dll'
   subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/out:'+str(dll),
    str(root/'bridge/src/PlantAnnotationParser.cs'),str(Path(__file__).with_name('AnnotationParserTests.cs'))],check=True,capture_output=True)
   command="[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; [System.Reflection.Assembly]::LoadFrom('"+str(dll).replace("'","''")+"') | Out-Null; [AnnotationParserTests]::Run()"
   result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,encoding='utf-8',errors='replace',timeout=30)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   self.assertTrue(result.stdout.startswith('PASS 19'),result.stdout+result.stderr)
