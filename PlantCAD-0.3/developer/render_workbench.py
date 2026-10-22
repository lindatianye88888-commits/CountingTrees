"""Compile and exercise the actual floating workbench without loading AutoCAD."""
from pathlib import Path
import os,subprocess,json,hashlib
root=Path(__file__).resolve().parents[1]
csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
binary=root/'developer/bin/WorkbenchRenderer.exe'
binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run([str(csc),'/nologo','/utf8output','/target:exe','/reference:System.Drawing.dll','/reference:System.Windows.Forms.dll',
                '/out:'+str(binary),str(root/'bridge/src/PlantCADWorkbench.cs'),str(root/'developer/tests/WorkbenchRenderer.cs')],check=True)
si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
subprocess.run([str(binary),str(root/'docs/images')],startupinfo=si,check=True)

record=root/"developer/ui-verification.json"
state=json.loads(record.read_text(encoding="utf-8-sig"))
state["control_sha256"]=hashlib.sha256((root/"bridge/src/PlantCADWorkbench.cs").read_bytes()).hexdigest()
record.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
