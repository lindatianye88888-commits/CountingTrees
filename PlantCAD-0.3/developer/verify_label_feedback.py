"""Existing label sizing, direct CAD text edits, fixed precision and full totals."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=Path(json.loads((ROOT/'developer/output-verification.json').read_text(encoding='utf-8'))['output'])/'input.dwg'
out=ROOT/'bridge/host-output'/('label-feedback-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg');dll=out/'OutputProbe.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/OutputProbe.cs')],check=True)
quote=lambda p:'"'+str(p).replace('\\','/')+'"'
sys.path.insert(0,str(ROOT/'developer/tests'));from lisp_harness import parse
prefix=r'''
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:layer-open (name / row) (and (setq row (tblsearch "LAYER" name)) (= 0 (logand 4 (cdr (assoc 70 row))))))
(defun pl:refresh-symbol (e) T) (defun pl:refresh-all-symbols () 0)
(defun pl:init-layers () (pc:seed-output-layers (mapcar 'car (pl:layers))) (regapp "PLANTCAD01"))
(defun getpoint (message) '(-80.0 -80.0 0.0))
(setq pl:*native-ui* T pl:*drawing-changed* nil pl:*failure* nil)
'''
body=r'''
(setq pc:area (car (pl:all-areas)) pc:label (car (pl:area-output-linked pc:area)) pc:value (pl:area-value pc:area))
(pc:edit-area-name (cdr (assoc 5 (entget pc:label))) "{\\fSimHei;CAD直改灌木}  9999.99 平方米")
(pl:sync-drawing)
(setq pc:text (pl:native-value (pl:native-leader-text (cdr (assoc 5 (entget pc:label))))))
(setq pc:checks (list
 (= (pl:get 'name (pl:data-get pc:area "AREA_PLANT")) "CAD直改灌木")
 (equal pc:value (pl:area-value pc:area) 1e-8)
 (not (vl-string-search "9999.99" pc:text))
 (not (null (vl-string-search (pl:area-text pc:value) pc:text)))))
(setq pc:before (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
(pl:db-put "PLOT_OPTIONS" '((scale . 200.0) (paper_height . 4.0) (show_number . 1)))
(pl:sync-drawing)
(setq pc:after (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
(setq pc:checks (append pc:checks (list (equal (car pc:after) 0.8 1e-8)
 (equal (cadr pc:after) 0.24 1e-8) (equal (caddr pc:after) 1.6 1e-8)
 (equal (nth 3 pc:before) (nth 3 pc:after) 1e-8))))
(setq pl:*drawing-changed* nil)
(pc:edit-area-name (cdr (assoc 5 (entget pc:label))) "统计直改灌木  123.45㎡")
(setq pl:*count-scope* "Model") (pl:count-work)
(setq pc:checks (append pc:checks (list (= (pl:get 'name (pl:data-get pc:area "AREA_PLANT")) "统计直改灌木")
 (equal pc:value (pl:area-value pc:area) 1e-8))))
(pl:sync-drawing)
(setq pc:tree (pl:put 'name "统计乔木" (pl:put 'spec_no "T001" (pl:put 'crown 3.0 (pl:put 'height 6.0 (pl:empty-plant "TOTAL_TREE"))))))
(pl:save-def pc:tree)
(setq pc:e (pl:make '((0 . "INSERT") (2 . "PL02_CIRCLE") (8 . "0") (10 52.0 0.0 0.0) (41 . 3.0) (42 . 3.0) (43 . 3.0))))
(pl:mark pc:e "TREE" nil) (pl:data-put pc:e "PLANT" pc:tree) (pl:data-put pc:e "UNITS" 1.0)
(setvar "DIMZIN" 8)
(setq pl:*count-scope* "Selected") (pl:table-work)
(setq pc:records (pl:output-table-records "count" (pl:db-get "LAST_COUNT_SCOPE" nil)))
(setq pc:checks (append pc:checks (list
 (= (pl:get 'scope (pl:db-get "LAST_COUNT_SCOPE" nil)) "model")
 (equal (mapcar '(lambda (row) (pl:get 'kind (car row))) pc:records) '(0 3 1))
 (= (nth 7 (pl:output-table-cells (caddr pc:records))) (pl:area-text pc:value))
 (= (length pc:records) 3)
 (= (pl:area-text 12.5) "12.50"))))
(pl:db-put "PC_FEEDBACK_AREA" (cdr (assoc 5 (entget pc:area))))
(pl:db-put "PC_FEEDBACK_LABEL" (cdr (assoc 5 (entget pc:label))))
(pl:db-put "PC_FEEDBACK_VALUE" pc:value)
'''
def run(name,body,save=False):
 result=out/(name+'.txt');wrapped=prefix+'\n(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+body+'\n pc:checks) nil))\n(setq pc:f (open '+quote(result)+' "w")) (prin1 (if (vl-catch-all-error-p pc:r) (list pl:*failure* (vl-catch-all-error-message pc:r)) pc:r) pc:f) (close pc:f)\n'
 parse(wrapped);lsp=out/(name+'.lsp');lsp.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
 script=out/(name+'.scr');lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','(load '+quote(lsp)+')']
 if save:lines+=['_.QSAVE']
 lines+=['_.QUIT','_No'];script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
 proc=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=75);(out/(name+'-console.bin')).write_bytes(proc.stdout)
 text=result.read_text(encoding='gbk') if result.exists() else 'MISSING';print(name,text,flush=True)
 return proc.returncode==0 and text.startswith('(T ') and 'nil' not in text and '"' not in text,text
passed,seed=run('seed',body,True);reopen='NOT RUN'
if passed:
 passed,reopen=run('reopen',r'''
(setq pc:area (handent (pl:db-get "PC_FEEDBACK_AREA" nil)) pc:label (handent (pl:db-get "PC_FEEDBACK_LABEL" nil)))
(pl:sync-drawing)
(setq pc:checks (list (= (pl:get 'name (pl:data-get pc:area "AREA_PLANT")) "统计直改灌木")
 (equal (pl:area-value pc:area) (pl:db-get "PC_FEEDBACK_VALUE" nil) 1e-8)
 (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:label))))) 0.8 1e-8)
 (= (length (pl:output-table-records "count" '((scope . "model")))) 3)
 (= (pl:area-text 12.5) "12.50")))
''')
report={'passed':passed,'seed':seed,'reopen':reopen,'assertions':seed.count('T')+reopen.count('T'),'output':str(out),'original_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,'scope':'AutoCAD 2014 kernel: direct MLeader plant-name edits import on sync and statistics, geometry remains authoritative, existing leader height/arrow/landing change together with text location retained, full-model total ignores selected scope, type sorting and DIMZIN-independent two-decimal areas, saved/reopened linkage; per-handle LDATA and scripted insertion adapters; glyph centering checked separately on desktop','runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}}
(ROOT/'developer/label-feedback-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTPUT',out,flush=True)
if not passed:raise SystemExit('Label feedback verification failed')
