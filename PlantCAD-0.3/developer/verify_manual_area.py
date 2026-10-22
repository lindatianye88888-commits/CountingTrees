"""Manual closed-boundary geometry, missing-label recovery, and idempotent numbering."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=ROOT/'bridge/host-output/area-native-224da63d/input.dwg'
out=ROOT/'bridge/host-output'/('manual-area-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True);shutil.copy2(source,out/'input.dwg')
before=hashlib.sha256(source.read_bytes()).hexdigest();dll=out/'ManualAreaProbe.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/ManualAreaProbe.cs')],check=True)
quote=lambda p:'"'+str(p).replace('\\','/')+'"'
body=r'''
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(pl:db-put "UNIT" 1) (setq pl:*native-ui* T)
(setq pc:boundary (pl:native-value (pc:manual-boundary)))
(setq pc:batch (pl:native-area-manual (list pc:boundary) "PL_面积_计算边界"))
(pl:consume-area-batch pc:batch -1)
(setq pc:area (handent (caadr pc:batch)) pc:no (pl:area-number pc:area))
(setq pc:label (car (pl:area-output-linked pc:area)))
(setq pc:checks (list (and pc:area pc:label T) (= (pl:area-value pc:area) 200.0)))
(entdel pc:label)
(pl:consume-area-batch (pl:native-area-manual (list pc:boundary) "PL_面积_计算边界") -1)
(setq pc:label (car (pl:area-output-linked pc:area)))
(setq pc:checks (append pc:checks (list (and pc:label T) (= (pl:area-number pc:area) pc:no) (= (length (pl:area-output-linked pc:area)) 1))))
(setq pc:debug (list (pl:all-labels) pc:label (pl:source pc:label) pc:area (pl:role pc:label) (pl:data-get pc:label "OUTPUT_OPTIONS") (cdr (assoc 0 (entget pc:label)))))
(pl:consume-area-batch (pl:native-area-manual (list pc:boundary) "PL_面积_计算边界") -1)
(setq pc:checks (append pc:checks (list (equal (car (pl:area-output-linked pc:area)) pc:label) (= (length (pl:area-output-linked pc:area)) 1) (= (pl:area-number pc:area) pc:no))))
'''
body=body.replace('(pl:db-put "UNIT"','(defun pl:layer-issue (name) nil)\n(pl:db-put "UNIT"')
body+='\n(setq pc:df (open '+quote(out/'debug.txt')+' "w")) (prin1 pc:debug pc:df) (close pc:df)\n'
body+='\n(setq pc:f (open '+quote(out/'manual-lisp.txt')+' "w")) (prin1 pc:checks pc:f) (close pc:f)\n'
(out/'check.lsp').write_bytes(body.replace('\n','\r\n').encode('gbk'))
script=out/'check.scr';script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'PC_MANUAL_AREA_TEST','(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','(load '+quote(out/'check.lsp')+')','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60);(out/'console.bin').write_bytes(run.stdout)
native=(out/'manual-native.txt').read_text(encoding='utf-8-sig') if (out/'manual-native.txt').exists() else 'MISSING'
lisp=(out/'manual-lisp.txt').read_text(encoding='gbk') if (out/'manual-lisp.txt').exists() else 'MISSING'
passed=native.startswith('PASS ') and lisp=='('+' '.join(['T']*8)+')' and run.returncode==0
report={'passed':passed,'native':native,'lisp':lisp,'assertions':(int(native.split()[1]) if native.startswith('PASS ') else 0)+8,'output':str(out),'original_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,'scope':'AutoCAD 2014 kernel: manual closed curves/regions, explicit cross-layer edges, holes, source geometry retention, open-boundary rejection, locked layer rollback, production LISP missing-label repair and idempotence; headless per-handle LDATA adapter; real desktop LDATA is verified separately','runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-workflow.lsp']}}
(ROOT/'developer/manual-area-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('OUTPUT',out,'NATIVE',native,'LISP',lisp,flush=True)
if not passed:raise SystemExit('Manual area verification failed')

