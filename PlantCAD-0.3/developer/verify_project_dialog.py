"""Render and exercise the real project form without connecting to AutoCAD."""
from pathlib import Path
import hashlib,json,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
def main():
 out=ROOT/'bridge/host-output'/('project-form-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 sources=[ROOT/'bridge/src/PlantProjectDialog.cs',ROOT/'developer/tests/ProjectDialogRenderer.cs'];dll=out/'ProjectFormChecks.dll'
 subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/out:'+str(dll)]+[str(p) for p in sources],check=True)
 quote=lambda p:"'"+str(p).replace("'","''")+"'"
 command=("$ErrorActionPreference='Stop'\n[System.Reflection.Assembly]::LoadFrom("+quote(dll)+") | Out-Null\n"+
  "$t=[System.AppDomain]::CurrentDomain.GetAssemblies() | ForEach-Object { $_.GetType('ProjectDialogRenderer',$false) } | Where-Object { $_ } | Select-Object -First 1\n"+
  "$t.GetMethod('Main',[System.Reflection.BindingFlags]'Static,NonPublic').Invoke($null, @(,[string[]]@("+quote(out)+"))) | Out-Null\n")
 run=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-STA','-Command',command],capture_output=True,timeout=45)
 result=(out/'project-dialog-render.txt').read_text(encoding='utf-8-sig') if (out/'project-dialog-render.txt').exists() else 'MISSING'
 report={'passed':run.returncode==0 and result=='PASS 16','assertions':16,'result':result,'output':str(out),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'scope':'Real WinForms: resizing, filters, sorted-row identity, empty-project collection and ambiguous-specification picking; no CAD modal-ownership acceptance.'}
 (ROOT/'developer/project-form-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 compatible=dict(report,source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 (ROOT/'developer/project-dialog-verification.json').write_text(json.dumps(compatible,ensure_ascii=False,indent=2),encoding='utf-8')
 print(result,flush=True)
 if not report['passed']:
  print(run.stderr.decode('utf-8',errors='replace'));raise SystemExit('Project form verification failed')
if __name__=='__main__':main()
