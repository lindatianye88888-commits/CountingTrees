"""Exercise specification deletion on an owned DWG in an isolated CoreConsole.

Production Lisp planning, project metadata, native transaction erase, native
tables, HATCH and save/reopen are exercised. Confirmation is deterministic;
per-entity LDATA uses named-dictionary adapters because CoreConsole lacks COM.
No desktop CAD or user drawing is changed. No GUI/print acceptance is implied.
"""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')

PREFIX=r'''
(setq pl:*native-ui* T pl:*drawing-changed* nil pl:*failure* nil pc:checks nil)
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:refresh-all-symbols () 0)
(defun pc:check (name value) (setq pc:checks (append pc:checks (list (list name (if value T nil))))))
(defun pc:handle (e) (cdr (assoc 5 (entget e))))
(defun pc:alive (h / e) (and (setq e (handent h)) (entget e)))
(defun pc:lock (name locked / e ed flags)
 (setq e (tblobjname "LAYER" name) ed (entget e) flags (cdr (assoc 70 ed)))
 (entmod (subst (cons 70 (if locked (logior flags 4) (- flags (logand flags 4)))) (assoc 70 ed) ed)))
(defun pc:text (content role source)
 (pl:mark (pl:make (list '(0 . "TEXT") '(8 . "0") '(10 0.0 0.0 0.0) '(40 . 1.0) (cons 1 content))) role source))
(defun pc:rect (x role / e)
 (setq e (pl:make (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") '(8 . "0") '(100 . "AcDbPolyline")
  '(90 . 4) '(70 . 1) (cons 10 (list x 0.0)) (cons 10 (list (+ x 10.0) 0.0))
  (cons 10 (list (+ x 10.0) 10.0)) (cons 10 (list x 10.0)))))
 (if role (pl:mark e role nil)) e)
'''
BODY=r'''
;; All entities live in an owned sample copy.
(foreach pc:e (pl:ss-list (ssget "_X")) (entdel pc:e))
(foreach pc:row (pl:layers)
 (if (not (tblsearch "LAYER" (car pc:row)))
  (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
    (cons 2 (car pc:row)) '(70 . 0) (cons 62 (cadr pc:row)) '(6 . "Continuous")))))
(pc:check "new paper font default displays one centimetre" (= (/ (pl:get 'paper_height (pl:plot-options)) 10.0) 1.0))
(pl:db-put "UNIT" 1) (pl:db-put "PLOT_OPTIONS" '((scale . 100.0) (paper_height . 2.5)))
(setq pc:p (pl:put 'name "紫竹" (pl:put 'kind 6 (pl:put 'crown 1.0 (pl:put 'spec_no "P001" (pl:empty-plant "DELETE"))))))
(setq pc:q (pl:put 'id "KEEP" (pl:put 'spec_no "P002" pc:p)))
(pl:save-def pc:p) (pl:save-def pc:q) (pl:db-put "CURRENT" "DELETE")
(pc:check "bamboo classification is independent" (equal (pl:kind-name 6) "竹类"))
(pc:check "existing font setting retained" (= (pl:get 'paper_height (pl:plot-options)) 2.5))
(pc:check "fill scale retained" (= (pl:get 'fill_scale pc:p) 0.1))
(pl:built-blocks)
(setq pc:tree (pl:make '((0 . "INSERT") (8 . "PL_竹类_圆圈") (2 . "PL02_CIRCLE") (10 0.0 20.0 0.0))))
(pl:mark pc:tree "TREE" nil) (pl:data-put pc:tree "PLANT" pc:p)
(setq pc:keep (pl:make '((0 . "INSERT") (8 . "0") (2 . "PL02_CIRCLE") (10 20.0 20.0 0.0))))
(pl:mark pc:keep "TREE" nil) (pl:data-put pc:keep "PLANT" pc:q)
(setq pc:label (pc:text "紫竹" "LABEL" (pc:handle pc:tree)))
(setq pc:area (pc:rect 0.0 "AREA")) (pl:data-put pc:area "AREA_PLANT" pc:p) (pl:data-put pc:area "UNITS" 1.0)
(pl:data-put pc:area "AREA_NO" "A1")
(setq pc:fill (pl:native-value (pl:native-fill (pc:handle pc:area) "ANSI31" 0.1 0.0 "PL_灌木_填充")))
(pc:check "native hatch seeded" (and (= (type pc:fill) 'STR) (handent pc:fill)))
(setq pc:source (pc:text "紫竹" "PROJECT_SOURCE" nil)) (pl:data-put pc:source "PROJECT_PLANT" pc:p)
(setq pc:raw (pc:rect 50.0 nil))
(setq pc:mixed (pl:output-table-write nil '(0.0 40.0 0.0) "PL_表格_苗木" "count" "苗木数量总表" 0.25 '((scope . "model"))))
(setq pc:only (pl:output-table-write nil '(0.0 60.0 0.0) "PL_表格_苗木" "count" "紫竹P001" 0.25
 (list '(scope . "selected") (cons 'handles (list (pc:handle pc:tree))))))
(setq pc:plan (pl:project-delete-plan "DELETE" (pl:ss-list (ssget "_X" '((-3 ("PLANTCAD01")))))))
(setq pc:removed (mapcar 'pc:handle (append (car pc:plan) (cadr pc:plan) (caddr pc:plan))))
(pc:check "plan includes tree area source" (= (length (car pc:plan)) 3))
(pc:check "plan includes hatch boundaries and label" (>= (length (cadr pc:plan)) 3))
(pc:check "dedicated table selected" (member pc:only (caddr pc:plan)))
(pc:check "mixed table retained" (not (member pc:mixed (caddr pc:plan))))
(setq pc:invalid (pl:native-value (pl:native-project-erase (list (pc:handle pc:tree) (pc:handle pc:raw)))))
(pc:check "unmanaged target rejected" (and (= (type pc:invalid) 'STR) (= (substr pc:invalid 1 6) "ERROR:")))
(pc:check "transaction rejection leaves first target intact" (entget pc:tree))
(pc:lock "PL_竹类_圆圈" T)
(setq pc:invalid (pl:native-value (pl:native-project-erase (list (pc:handle pc:label) (pc:handle pc:tree)))))
(pc:check "locked target rejects entire transaction" (and (= (type pc:invalid) 'STR) (entget pc:label) (entget pc:tree)))
(pc:lock "PL_竹类_圆圈" nil)
(defun pl:native-project-delete-confirm (label objects tables) 0)
(pc:check "cancel returns without deleting" (not (pl:delete-project-spec pc:p)))
(pc:check "cancel keeps entities and project" (and (entget pc:tree) (pl:by-id "DELETE")))
(pc:lock "PL_表格_苗木" T)
(setq pc:invalid (vl-catch-all-apply 'pl:project-delete-plan (list "DELETE" (pl:ss-list (ssget "_X" '((-3 ("PLANTCAD01"))))))))
(pc:check "locked mixed table blocks deletion plan" (vl-catch-all-error-p pc:invalid))
(setq pl:*failure* nil) (pc:lock "PL_表格_苗木" nil)
(defun pl:native-project-delete-confirm (label objects tables) 1)
;; BEGIN_DELETE
(pc:check "confirmed specification deleted" (pl:delete-project-spec pc:p))
(foreach pc:h pc:removed (pc:check (strcat "deleted managed handle " pc:h) (not (pc:alive pc:h))))
(pc:check "same name different specification retained" (and (entget pc:keep) (pl:by-id "KEEP")))
(pc:check "source raw line retained" (entget pc:raw))
(pc:check "mixed native table retained" (entget pc:mixed))
(pc:check "mixed table snapshot excludes deleted id" (not (assoc "DELETE" (pl:data-get pc:mixed "TABLE_ROWS"))))
(pc:check "mixed table native cells exclude P001" (not (vl-string-search "P001" (vl-princ-to-string (pl:native-table-read (pc:handle pc:mixed))))))
(pc:check "dedicated table removed" (not (entget pc:only)))
(pc:check "project definition and history removed" (and (not (pl:by-id "DELETE")) (= (length (pl:db-get "SPEC_HISTORY" nil)) 1)))
(pc:check "current now points to remaining specification" (= (pl:db-get "CURRENT" nil) "KEEP"))
(pc:check "shared symbol definition retained" (tblsearch "BLOCK" "PL02_CIRCLE"))
;; AFTER_UNDO
(foreach pc:h pc:removed (pc:check (strcat "undo restores managed handle " pc:h) (pc:alive pc:h)))
(pc:check "undo restores project history and current" (and (pl:by-id "DELETE") (= (length (pl:db-get "SPEC_HISTORY" nil)) 2) (= (pl:db-get "CURRENT" nil) "DELETE")))
(pc:check "undo restores mixed table cells" (vl-string-search "P001" (vl-princ-to-string (pl:native-table-read (pc:handle pc:mixed)))))
(pl:delete-project-spec pc:p)
(pl:db-put "DELETE_TEST_REMOVED" pc:removed)
(pl:db-put "DELETE_TEST_KEEP" (mapcar 'pc:handle (list pc:keep pc:raw pc:mixed)))
'''
REOPEN=r'''
(foreach pc:h (pl:db-get "DELETE_TEST_REMOVED" nil) (pc:check (strcat "saved deleted handle " pc:h) (not (pc:alive pc:h))))
(foreach pc:h (pl:db-get "DELETE_TEST_KEEP" nil) (pc:check (strcat "saved retained handle " pc:h) (pc:alive pc:h)))
(pc:check "saved project contains only remaining specification" (and (= (length (pl:defs)) 1) (pl:by-id "KEEP") (not (pl:by-id "DELETE"))))
(pl:sync-drawing)
(setq pc:mixed (handent (caddr (pl:db-get "DELETE_TEST_KEEP" nil))))
(pc:check "refresh after reopen does not resurrect deleted specification" (and (not (pl:by-id "DELETE")) (not (assoc "DELETE" (pl:data-get pc:mixed "TABLE_ROWS")))) )
'''

def main():
 import sys
 sys.path.insert(0,str(ROOT/'developer/tests'));from lisp_harness import parse
 token=uuid.uuid4().hex[:8];out=ROOT/'bridge/host-output'/('project-delete-'+token);out.mkdir(parents=True)
 source=CAD/'Support/chroma.dwg';original=hashlib.sha256(source.read_bytes()).hexdigest();drawing=out/'test.dwg';shutil.copy2(source,drawing)
 production=ROOT/'bridge/PlantCADBridge.dll';quote=lambda p:'"'+str(p).replace('\\','/')+'"'
 report={'passed':False,'output':str(out),'scope':__doc__,'runs':[],'receiver_sha256':hashlib.sha256(production.read_bytes()).hexdigest()}
 modules=[]
 for name in ['plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad-project-import.lsp']:
  content=(ROOT/'developer/src'/name).read_text(encoding='utf-8')
  if name=='plantcad.lsp':content=content.split('\n(if (pl:locate-core)',1)[0]
  target=out/name;target.write_bytes(content.replace('\n','\r\n').encode('gbk'));modules.append(target)
 report['runtime_sha256']={p.name:hashlib.sha256((ROOT/'developer/src'/p.name).read_bytes()).hexdigest() for p in modules}
 try:
  seed,remaining=BODY.split(';; BEGIN_DELETE',1);delete,undo=remaining.split(';; AFTER_UNDO',1)
  for phase,steps in [('initial',[('seed',seed),('delete',delete),('undo',undo)]),('reopen',[('reopen',REOPEN)])]:
   commands=['_.NETLOAD',quote(production),'(setq pl:*dir* '+quote(ROOT)+')']
   commands+=['(load '+quote(p)+')' for p in modules]
   if phase=='initial':commands+=['_.UNDO','_Auto','_Off','_.UNDO','_End']
   for name,code in steps:
    result=out/(name+'.txt');lsp=out/(name+'.lsp')
    wrapped=PREFIX+'\n(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+code+'\n pc:checks) nil))\n'
    wrapped+='(setq pc:f (open '+quote(result)+' "w")) (prin1 (if (vl-catch-all-error-p pc:r) (list "ERROR" pl:*failure* (vl-catch-all-error-message pc:r) pc:checks) pc:r) pc:f) (close pc:f)\n'
    parse(wrapped);lsp.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
    # UNDO commands must run after the Lisp invocation has returned. Calling U
    # inside LOAD remains in its implicit undo group on AutoCAD 2014.
    if name=='delete':commands+=['_.UNDO','_Begin']
    if name=='undo':commands+=['_.UNDO','_End','_.UNDO','_End','(getvar "UNDOCTL")','_.U']
    commands+=['(load '+quote(lsp)+')']
   if phase=='initial':commands+=['_.QSAVE']
   commands+=['_.QUIT','_No'];script=out/(phase+'.scr');script.write_bytes(('\r\n'.join(commands)+'\r\n').encode('gbk'))
   run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(drawing),'/s',str(script),'/isolate','CountingTreesDelete'+token,str(out/'cad-profile')],cwd=out,
    creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=55)
   (out/(phase+'-console.bin')).write_bytes(run.stdout)
   for name,code in steps:
    result=out/(name+'.txt');actual=result.read_text(encoding='gbk') if result.exists() else 'MISSING'
    parsed=parse(actual)[0] if actual!='MISSING' else None
    passed=run.returncode==0 and isinstance(parsed,list) and len(parsed)>0 and all(isinstance(row,list) and len(row)==2 and row[1] is True for row in parsed)
    report['runs'].append({'phase':name,'passed':passed,'actual':actual});print(name,actual,flush=True)
    if not passed:raise AssertionError('Project deletion native check failed: '+name)
  report.update(passed=True,assertions=sum(len(parse(r['actual'])[0]) for r in report['runs']),original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==original)
  report['passed']=report['original_unchanged'];print('PASS',report['assertions'],flush=True)
 finally:
  (ROOT/'developer/project-delete-native-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
