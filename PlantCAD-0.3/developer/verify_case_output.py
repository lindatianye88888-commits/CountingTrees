"""Case2 coverage and production measurement labels, using native CAD on a copy."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
out=ROOT/'bridge/host-output'/('case-output-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
source=ROOT.parent/'案例2/植物配置20261021.dwg';before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg');dll=out/'CaseOutputProbe.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:System.Web.Extensions.dll','/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests'/n) for n in ['CaseAreaProbe.cs','OutputProbe.cs']],check=True)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
# Visually audited locations in previously missed large, narrow and nested beds.
seeds=[(34537214502.31024,3134342074.9540305),(34537242731.64979,3134377058.830069),(34537088063.93582,3134391735.8287573),(34537270570.065506,3134354610.810843),(34537145396.11023,3134388642.00776),(34537121123.06859,3134391468.083194),(34537187327.66862,3134352585.901206),(34537189442.47403,3134384812.611064)]
body=r'''
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:layer-open (name / row) (and (setq row (tblsearch "LAYER" name)) (= 0 (logand 4 (cdr (assoc 70 row))))))
(defun pl:init-layers () (pc:seed-output-layers (mapcar 'car (pl:layers))) (regapp "PLANTCAD01"))
(pl:init-layers) (setq pl:*native-ui* T) (pl:db-put "UNIT" 0)
(setq pc:checks nil)
(defun pc:check (value) (setq pc:checks (append pc:checks (list (if value T nil)))))
(setq pc:h (pc:case-handles "PL_灌木_原始线"))
(pc:check (= (length pc:h) 241))
(setq pc:count (pl:native-value (pl:native-area-begin pc:h "PL_灌木_原始线")))
(pc:case-stats)
(pc:check (= pc:count 118))
'''
for x,y in seeds:body+=f"(pc:check (>= (pl:native-value (pc:case-index '({x} {y} 0.0))) 0))\n"
body+=r'''
(setq pc:batch (pl:native-area-export-all "PL_面积_计算边界"))
(pc:check (= (length (cdr pc:batch)) 118))
(pl:consume-area-batch pc:batch -1)
(pc:check (= (length (pl:all-areas)) 118))
(pc:check (and (vl-some '(lambda (row) (= (nth 4 row) 1)) (cdr pc:batch)) (not (vl-some '(lambda (row) (and (= (nth 4 row) 1) (not (equal (pl:data-get (handent (car row)) "AREA_FITTED") 1)))) (cdr pc:batch)))))
(pc:check (not (vl-some '(lambda (row) (not (pl:area-output-linked (handent (car row))))) (cdr pc:batch))))
(pc:check (not (vl-some '(lambda (row) (<= (nth 3 row) 0)) (cdr pc:batch))))
(pc:check (equal (apply '+ (mapcar '(lambda (row) (pl:area-value (handent (car row)))) (cdr pc:batch))) (/ (pl:native-value (pl:native-area-total)) 1000000.0) 0.001))
(setq pc:areas (length (pl:all-areas)) pc:labels (length (pl:all-labels)))
(pl:native-area-end)
(pc:check (= (pl:native-value (pl:native-area-begin pc:h "PL_灌木_原始线")) 118))
(pl:consume-area-batch (pl:native-area-export-all "PL_面积_计算边界") -1)
(pc:check (and (= pc:areas (length (pl:all-areas))) (= pc:labels (length (pl:all-labels)))))
(pl:native-area-end)
'''
result=out/'checks.txt';load=out/'test.lsp'
body=body.replace('(pc:check (and (= pc:areas', '(progn (setq pc:cf (open '+q(out/'counts.txt')+' "w")) (prin1 (list pc:areas pc:labels (length (pl:all-areas)) (length (pl:all-labels))) pc:cf) (close pc:cf)) (pc:check (and (= pc:areas')

body=body.replace('(defun pc:check (value) (setq pc:checks (append pc:checks (list (if value T nil)))))','(defun pc:check (value / f) (setq pc:checks (append pc:checks (list (if value T nil)))) (setq f (open '+q(out/'progress.txt')+' "w")) (prin1 pc:checks f) (close f))')
load.write_bytes(("(setq pc:r (vl-catch-all-apply '(lambda ()\n"+body+'\npc:checks) nil))\n(setq pc:f (open '+q(result)+' "w")) (prin1 (if (vl-catch-all-error-p pc:r) (vl-catch-all-error-message pc:r) pc:r) pc:f) (close pc:f)\n').replace('\n','\r\n').encode('gbk'))
def trace(label):return '(progn (setq pc:f (open '+q(out/'trace.txt')+' "a")) (write-line "'+label+'" pc:f) (close pc:f))'
script=out/'run.scr';script.write_bytes(('\r\n'.join([trace('start'),'_.NETLOAD',q(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',q(dll),trace('native loaded'),'(setq pl:*dir* '+q(ROOT)+')','(load '+q(ROOT/'plantcad.lsp')+')',trace('lisp loaded'),'(progn (setq pc:load (vl-catch-all-apply \'load (list '+q(load)+'))) (setq pc:f (open '+q(out/'load.txt')+' "w")) (prin1 (if (vl-catch-all-error-p pc:load) (vl-catch-all-error-message pc:load) pc:load) pc:f) (close pc:f))',trace('completed'),'PC_CASE_DUPLICATES','_.QUIT','_No'])+'\r\n').encode('gbk'))
run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'console.bin').write_bytes(run.stdout);value=result.read_text(encoding='gbk') if result.exists() else 'MISSING';print('OUTPUT',out,'EXIT',run.returncode,'RESULT',value,flush=True)
report=dict(passed=value=='('+' '.join(['T']*18)+')',assertions=18,source=str(source),source_sha256=before,scope='AutoCAD 2014 kernel on case2 copy: 241 raw edges, 118 bounded cells including parking bays and one microscopic extra fragment, 8 previously missed locations, old-region migration without parallel duplicate, all internal labels, native area sum, fitted-boundary provenance and repeat-scan reuse; headless LDATA adapter, no user drawing edits',output=str(out),original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before,runtime_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-workflow.lsp']})
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not report['passed']:raise SystemExit('Case coverage failed')
(ROOT/'developer/case-coverage-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
