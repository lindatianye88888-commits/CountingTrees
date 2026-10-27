"""Verify mixed project collection and existing schedules in an owned drawing copy.

Uses the AutoCAD 2014 Core Console, not the user's desktop CAD. Per-entity LDATA
uses a named-dictionary adapter because Core Console lacks entity COM wrappers.
New-spec confirmation is accepted by a test adapter; real dialog checks are separate.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
sys.path.insert(0,str(ROOT/'developer/tests'))
from lisp_harness import parse
def quote(path):return '"'+str(path).replace('\\','/').replace('"','\\"')+'"'
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-base',type=Path,default=ROOT/'bridge/host-output');args=ap.parse_args()
 if args.output_base.name!='host-output':ap.error('Test output base must be named host-output')
 out=args.output_base/('project-import-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 source=CAD/'Support/chroma.dwg';before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'test.dwg')
 dll=out/'ProjectImportProbe.dll'
 subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),
  '/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+
  [str(ROOT/'developer/tests'/name) for name in ['OutputProbe.cs','ProjectImportProbe.cs']],check=True)
 # Load production definitions without running the interactive startup/migration commands.
 definitions=[]
 for name in ['plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad-project-import.lsp']:
  text=(ROOT/'developer/src'/name).read_text(encoding='utf-8');forms=parse(text)
  # Reader preserves the exact production function text, including comments/escapes.
  import re
  for match in re.finditer(r'(?ms)^\(defun .*?(?=^\(defun |\Z)',text):
   chunk=match.group();parsed=parse(chunk)
   # A final chunk can include top-level command registration. Keep only its defun.
   depth=0;end=None;in_string=False;escape=False;comment=False
   for i,c in enumerate(chunk):
    if comment:
     if c=='\n':comment=False
     continue
    if in_string:
     if escape:escape=False
     elif c=='\\':escape=True
     elif c=='"':in_string=False
     continue
    if c==';':comment=True
    elif c=='"':in_string=True
    elif c=='(':depth+=1
    elif c==')':
     depth-=1
     if depth==0:end=i+1;break
   if end is None:raise RuntimeError('Missing production function boundary')
   definitions.append('(eval (read '+json.dumps(chunk[:end],ensure_ascii=False)+'))')
 adapter=r'''
(vl-load-com)
(setq pl:*app* "PLANTCAD01" pl:*dict* "PLANTCAD01_DATA" pl:*native-ui* T pl:*failure* nil)
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value)
 (if (member key '("PLANT" "AREA_PLANT" "UNITS" "PROJECT_PLANT" "PROJECT_COUNT")) (setq pl:*drawing-changed* T))
 (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:refresh-all-symbols () 0)
(defun pl:refresh-symbol (e) T)
(defun pl:edit-dialog (p) p)
(defun pc:check (label good)
 (setq pc:results (append pc:results (list (list label (if good T nil))))))
'''
 body=r'''
(pc:seed-output-layers (mapcar 'car (pl:layers))) (regapp "PLANTCAD01")
(pl:db-put "UNIT" 1) (pl:db-put "PLOT_OPTIONS" '((scale . 100.0) (paper_height . 2.5)))
(setq pc:handles (pc:import-fixtures) pc:objects (mapcar 'handent pc:handles))
(pl:db-put "PC_IMPORT_HANDLES" pc:handles)
(setq pc:tree (pl:put 'name "银杏" (pl:put 'spec_no "T001" (pl:put 'dbh 12.0 (pl:put 'height 6.0 (pl:put 'crown 3.0 (pl:empty-plant "TREE")))))))
(setq pc:ball (pl:put 'name "海桐球" (pl:put 'spec_no "B001" (pl:put 'kind 3 (pl:put 'height 1.0 (pl:put 'crown 1.0 (pl:empty-plant "BALL")))))))
(setq pc:shrub (pl:put 'name "海桐" (pl:put 'spec_no "S001" (pl:put 'kind 1 (pl:put 'quantity_unit "平方米" (pl:empty-plant "SHRUB"))))))
(foreach pc:p (list pc:tree pc:ball pc:shrub) (pl:save-def pc:p))
(foreach pc:row (list (list (nth 0 pc:objects) pc:tree) (list (nth 1 pc:objects) pc:ball))
 (pl:mark (car pc:row) "TREE" nil) (pl:data-put (car pc:row) "PLANT" (cadr pc:row)) (pl:data-put (car pc:row) "UNITS" 1.0))
(setq pc:area (nth 2 pc:objects)) (pl:mark pc:area "AREA" nil)
(pl:data-put pc:area "AREA_PLANT" pc:shrub) (pl:data-put pc:area "UNITS" 1.0) (pl:data-put pc:area "AREA_NO" "A1")
(pl:mark (nth 3 pc:objects) "LABEL" (nth 0 pc:handles))
(pl:mark (nth 4 pc:objects) "AREA_LABEL" (nth 2 pc:handles))
(pl:built-blocks)
(setq pc:table (pl:output-table-write nil '(0.0 -5.0 0.0) "PL_表格_苗木" "count" "苗木数量总表" 0.25 '((scope . "model"))))
(setq pc:selected (pl:output-table-write nil '(0.0 -15.0 0.0) "PL_表格_苗木" "count" "选中名称" 0.25
 (list '(scope . "selected") (cons 'handles (list (nth 5 pc:handles))))))
(setq pc:cover (pl:output-table-write nil '(20.0 -5.0 0.0) "PL_表格_苗木" "count" "灌木地被" 0.25 '((scope . "model") (category . "cover"))))
(setq pc:list (pl:output-table-write nil '(20.0 -15.0 0.0) "PL_表格_植物名录" "list" "植物名录" 0.25 '((scope . "model"))))
(pl:db-put "PC_IMPORT_TABLES" (mapcar '(lambda (e) (cdr (assoc 5 (entget e)))) (list pc:table pc:selected pc:cover pc:list)))
(pl:db-put "PLANTS" nil) (setq pl:*drawing-changed* nil)
(setq pc:result (pl:collect-project-objects pc:objects))
(pc:check "mixed source count" (equal pc:result '(7 5 0)))
(pc:check "five project specifications" (= (length (pl:defs)) 5))
(pc:check "four plain sources linked" (= (length (pl:all-project-sources)) 4))
(setq pc:rows (pl:output-table-records "count" '((scope . "model"))))
(pc:check "total includes all five plants" (= (length pc:rows) 5))
(pc:check "two tree symbols, not diameter twelve" (equal (cadr (assoc pc:tree pc:rows)) 2))
(pc:check "area uses geometry rather than text 9999" (equal (cadr (assoc pc:shrub pc:rows)) 3.13 1e-8))
(pc:check "pending name rows" (= (length (vl-remove-if-not '(lambda (row) (equal (nth 2 row) "pending")) pc:rows)) 2))
(pc:check "table updated immediately" (= (length (pl:data-get pc:table "TABLE_ROWS")) 5))
(pc:check "existing table retains entity handle" (equal (cdr (assoc 5 (entget pc:table))) (car (pl:db-get "PC_IMPORT_TABLES" nil))))
(pc:check "selected table retains original scope" (= (length (pl:data-get pc:selected "TABLE_ROWS")) 1))
(pc:check "cover table retains type filter" (= (length (pl:data-get pc:cover "TABLE_ROWS")) 3))
(pc:check "project list schedule updated" (= (length (pl:data-get pc:list "TABLE_ROWS")) 5))
(setq pc:actual (pl:native-table-read (cdr (assoc 5 (entget pc:table)))))
(pc:check "native total table has five visible rows" (= (length pc:actual) 6))
(pc:check "native text pending cell" (= (length (vl-remove-if-not '(lambda (row) (member "待关联" row)) (cdr pc:actual))) 2))
(pc:check "native table legends" (= (pl:native-value (pc:check-legends (cdr (assoc 5 (entget pc:table))))) 5))
(pc:check "repeat import idempotent" (equal (pl:collect-project-objects pc:objects) '(7 0 0)))
(pc:check "repeat total remains two trees" (equal (cadr (assoc pc:tree (pl:output-table-records "count" '((scope . "model"))))) 2))
(setq pc:shrub (pl:put 'name "海桐新版" (pl:by-id "SHRUB")))
(pl:save-project-spec pc:shrub) (pl:sync-drawing)
(pc:check "project edit propagates to imported source statistics" (= (pl:get 'name (pl:annotation-plant (nth 7 pc:objects))) "海桐新版"))
(pc:check "project edit propagates to existing native table" (member "海桐新版" (cadr (pl:native-table-read (cdr (assoc 5 (entget pc:cover)))))))
(pl:db-put "PC_IMPORT_CHECKS" pc:results)
'''
 reopen=r'''
(setq pc:handles (pl:db-get "PC_IMPORT_HANDLES" nil) pc:objects (mapcar 'handent pc:handles)
 pc:tables (mapcar 'handent (pl:db-get "PC_IMPORT_TABLES" nil)))
(pl:sync-drawing)
(pc:check "saved definitions persist" (= (length (pl:defs)) 5))
(pc:check "saved source associations persist" (= (length (pl:all-project-sources)) 4))
(pc:check "saved total still has five plant rows" (= (length (pl:data-get (car pc:tables) "TABLE_ROWS")) 5))
(pc:check "saved native selected table has one row" (= (length (pl:native-table-read (cdr (assoc 5 (entget (cadr pc:tables)))))) 2))
(pc:check "saved pending sources have no quantities" (null (pl:quantity-data (nth 5 pc:objects))))
(pc:check "saved imported tree quantity is one" (= (cadr (pl:quantity-data (nth 8 pc:objects))) 1))
'''
 report={'passed':False,'output':str(out),'scope':__doc__,'runs':[]}
 try:
  for label,code in [('initial',body),('reopen',reopen)]:
   result=out/(label+'.txt')
   wrapped=adapter+'\n(setq pc:results nil)\n(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+code+'\n pc:results) nil))\n'
   wrapped+='(setq pc:f (open '+quote(result)+' "w"))\n(prin1 (if (vl-catch-all-error-p pc:r) (list "ERROR" pl:*failure* (vl-catch-all-error-message pc:r)) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
   parse(wrapped);check=out/(label+'.lsp');check.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
   commands=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll)]
   if label=='initial':commands+=['PC_IMPORT_SEED']
   commands+=['(setq pl:*dir* '+quote(ROOT)+')']+definitions+['(load '+quote(check)+')']
   if label=='initial':commands+=['_.QSAVE']
   commands+=['_.QUIT','_No'];script=out/(label+'.scr');script.write_bytes(('\r\n'.join(commands)+'\r\n').encode('gbk'))
   run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'test.dwg'),'/s',str(script)],cwd=out,
    creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
   (out/(label+'-console.bin')).write_bytes(run.stdout)
   actual=result.read_text(encoding='gbk') if result.exists() else 'MISSING'
   print(label,actual,flush=True);parsed=parse(actual)[0] if actual!='MISSING' else None
   passed=run.returncode==0 and isinstance(parsed,list) and len(parsed)>0 and all(isinstance(row,list) and len(row)==2 and row[1] is True for row in parsed)
   report['runs'].append({'phase':label,'passed':passed,'actual':actual,'exit_code':run.returncode})
   if not passed:raise AssertionError('Native project collection failed: '+label)
  report['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
  report['runtime_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'developer/src').glob('*.lsp'))+[ROOT/'bridge/PlantCADBridge.dll']}
  report['passed']=report['original_unchanged'];report['assertions']=sum(len(parse(r['actual'])[0]) for r in report['runs'])
 finally:
  (ROOT/'developer/project-import-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
