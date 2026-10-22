"""Convert only copied case files that the 2014 console could not inspect."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'bridge/host-output/case-review-4cf0f270'
converted=out/'oda';converted.mkdir(exist_ok=True)
exe=Path(r'C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe')
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
for pattern in ['ZS*.dwg','XCA2.dwg']:
    run=subprocess.run([str(exe),str(out),str(converted),'ACAD2013','DXF','0','0',pattern],startupinfo=startup,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=100)
    print(pattern,run.returncode,[(p.name,p.stat().st_size) for p in converted.glob('*.dxf')],flush=True)
