"""Production split-table workflow, persistent filters, edit-back and reopen."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
source=Path(json.loads((ROOT/'developer/output-verification.json').read_text(encoding='utf-8'))['output'])/'input.dwg'
out=ROOT/'bridge/host-output'/('schedule-split-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
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
(defun pc:display-ok (e) (= 1 (pl:native-value (pc:check-table-display (cdr (assoc 5 (entget e)))))))
(setq pl:*native-ui* T pl:*failure* nil)
'''
body=r'''
(setq pc:ball (pl:put 'species_id "SP_BALL" (pl:by-id "BALL")))
(pl:save-project-spec pc:ball)
(setq pc:tree (pl:put 'species_id "SP_TREE" (pl:put 'spec_no "T001" (pl:put 'kind 0 (pl:put 'name "香樟" (pl:empty-plant "SPLIT_TREE"))))))
(setq pc:tree (pl:put 'dbh 12.0 (pl:put 'height 8.0 (pl:put 'crown 3.0 pc:tree))))
(setq pc:variant (pl:put 'id "BALL_2" (pl:put 'spec_no "B002" (pl:put 'height 2.0 pc:ball))))
(pl:save-def pc:tree) (pl:save-def pc:variant)
(foreach pc:p (list pc:tree pc:variant)
 (setq pc:e (pl:make (list '(0 . "INSERT") '(2 . "PL02_CIRCLE") (cons 8 (pl:tree-layer pc:p)) '(10 52.0 0.0 0.0) '(41 . 1.0) '(42 . 1.0) '(43 . 1.0))))
 (pl:mark pc:e "TREE" nil) (pl:data-put pc:e "PLANT" pc:p) (pl:data-put pc:e "UNITS" 1.0))
(setq pc:all-records (pl:output-table-records "count" '((scope . "model"))))
(setq pc:groups (pl:output-tables-split nil "PL_表格_苗木" "count" '((scope . "model")) "category"))
(setq pc:species (pl:output-tables-split nil "PL_表格_苗木" "count" '((scope . "model")) "species"))
(setq pc:checks (list (= (length pc:groups) 3) (= (length pc:species) 3)
 (equal (mapcar '(lambda (e) (length (pl:data-get e "TABLE_ROWS"))) pc:groups) '(1 2 1))
 (= (length pc:all-records) 4)))
(foreach pc:e (append pc:groups pc:species)
 (setq pc:checks (append pc:checks (list (pc:display-ok pc:e)))))
(setq pc:balltable (cadr pc:groups) pc:rows (pl:data-get pc:balltable "TABLE_ROWS") pc:row (if (= (caar pc:rows) "BALL") 2 3))
(pc:edit-table (cdr (assoc 5 (entget pc:balltable))) pc:row 7 "180")
(pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (equal (pl:get 'crown (pl:by-id "BALL")) 1.8 1e-8)
 (= (nth 6 (cadr (assoc "BALL" (pl:data-get pc:balltable "TABLE_ROWS")))) "180")
 (= (length (pl:data-get pc:balltable "TABLE_ROWS")) 2))))
(setq pc:tree (pl:put 'name "香樟更名" pc:tree)) (pl:save-project-spec pc:tree) (pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (not (null (vl-some '(lambda (e) (equal (pl:get 'species_key (pl:data-get e "TABLE_SCOPE")) "ID:SP_BALL")) pc:species)))
 (not (null (vl-some '(lambda (table) (vl-string-search "香樟更名" (pl:data-get table "TABLE_TITLE"))) pc:species))))))
(pl:db-put "PC_SPLIT_HANDLES" (mapcar '(lambda (e) (cdr (assoc 5 (entget e)))) (append pc:groups pc:species)))
(setq pc:flower-table nil)
(foreach pc:e pc:species (if (assoc "FLOWER" (pl:data-get pc:e "TABLE_ROWS")) (setq pc:flower-table pc:e)))
(pl:save-project-spec (pl:put 'name "手动花境更名" (pl:by-id "FLOWER"))) (pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (= (length (pl:data-get pc:flower-table "TABLE_ROWS")) 1)
 (not (null (vl-string-search "手动花境更名" (pl:data-get pc:flower-table "TABLE_TITLE")))))))
(pl:db-put "PC_SPLIT_CHECKS" pc:checks)
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
passed,seed=run('seed',body,True)
reopen='NOT RUN'
if passed:
 passed,reopen=run('reopen',r'''
(setq pc:tables (mapcar 'handent (pl:db-get "PC_SPLIT_HANDLES" nil)))
(pl:sync-drawing)
(setq pc:checks (list (= (length pc:tables) 6) (equal (pl:get 'crown (pl:by-id "BALL")) 1.8 1e-8)))
(foreach pc:e pc:tables (setq pc:checks (append pc:checks (list
 (= (pl:data-get pc:e "TABLE_FORMAT") 4)
 (pc:display-ok pc:e)))))
''')
report={'passed':passed,'seed':seed,'reopen':reopen,'assertions':seed.count('T')+reopen.count('T'),'output':str(out),'original_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,'scope':'AutoCAD 2014 kernel: production category/species split workflows, source scope, multiple specifications per species, second-column legends, effective text heights, linked table edit-back and DWG reopen; per-handle LDATA and deterministic insertion-point adapters; desktop rendering verified separately','runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}}
(ROOT/'developer/schedule-split-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('OUTPUT',out,flush=True)
if not passed:raise SystemExit('Schedule split verification failed')
