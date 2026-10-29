"""Render the real About and project forms; verify attribution without opening CAD."""
from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 sources=[ROOT/'bridge/src/PlantCADWorkbench.cs',ROOT/'bridge/src/PlantProjectDialog.cs',ROOT/'developer/tests/BrandRenderer.cs']
 dll=ROOT/'developer/bin/BrandRenderer.dll';dll.parent.mkdir(exist_ok=True)
 subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/reference:System.Drawing.dll','/reference:System.Windows.Forms.dll','/out:'+str(dll)]+[str(p) for p in sources],check=True)
 quote=lambda p:"'"+str(p).replace("'","''")+"'"
 command="$ErrorActionPreference='Stop';[Reflection.Assembly]::LoadFrom("+quote(dll)+") | Out-Null;$t=[AppDomain]::CurrentDomain.GetAssemblies() | ForEach-Object { $_.GetType('BrandRenderer',$false) } | Where-Object { $_ } | Select-Object -First 1;$t.GetMethod('Main',[Reflection.BindingFlags]'Static,NonPublic').Invoke($null,@(,[string[]]@("+quote(ROOT/'docs/images')+"))) | Out-Null"
 subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-STA','-Command',command],check=True,timeout=45)
 report=ROOT/'developer/brand-verification.json';data=json.loads(report.read_text(encoding='utf-8-sig'));assert data['passed']
 data['source_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS: About attribution, contacts, logo and actual form screenshots')
if __name__=='__main__':main()
