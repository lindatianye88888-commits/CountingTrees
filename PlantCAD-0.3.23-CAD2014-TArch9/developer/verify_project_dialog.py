from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];exe=ROOT/'developer/bin/ProjectDialogRenderer.exe';exe.parent.mkdir(exist_ok=True)
sources=[ROOT/'bridge/src/PlantProjectDialog.cs',ROOT/'developer/tests/ProjectDialogRenderer.cs']
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:winexe','/reference:System.Drawing.dll','/reference:System.Windows.Forms.dll','/out:'+str(exe)]+list(map(str,sources)),check=True)
out=ROOT/'docs/images';subprocess.run([str(exe),str(out)],check=True,timeout=30)
result=(out/'project-dialog-render.txt').read_text();(out/'project-dialog-render.txt').unlink()
report={'passed':result=='PASS 13','assertions':13,'scope':'Actual WinForms project picker: resize small/large, 8 columns, all-type/category/name/code filters, sorted-row stable identity, empty project add/edit behavior; CAD modal ownership tested separately','source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
(ROOT/'developer/project-dialog-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(result,flush=True);assert report['passed']
