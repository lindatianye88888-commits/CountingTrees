"""Exercise planting output against AutoCAD 2014, only in a copied test DWG."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid

ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
PY=Path(r'C:\Users\abc\AppData\Local\Programs\Python\Python312\python.exe')
def quote(path):return '"'+str(path).replace('\\','/')+'"'
def main():
    out=ROOT/'bridge/host-output'/('planting-output-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    source=ROOT/'bridge/host-output/area-native-224da63d/input.dwg'
    if not source.is_file():source=next((ROOT/'bridge/host-output').rglob('input.dwg'))
    before=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,out/'input.dwg')
    for path in (ROOT/'developer/src').iterdir():
        if path.suffix in ('.lsp','.dcl','.tsv'):(ROOT/path.name).write_bytes(path.read_text(encoding='utf-8').replace('\r\n','\n').replace('\n','\r\n').encode('gbk'))
    dll=out/'OutputProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),
                    '/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/OutputProbe.cs')],check=True)
    body=r'''
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:layer-open (name / row) (and (setq row (tblsearch "LAYER" name)) (= 0 (logand 4 (cdr (assoc 70 row))))))
(defun pl:refresh-symbol (e) T)
(defun pl:refresh-all-symbols () 0)
(defun pl:init-layers () (pc:seed-output-layers (mapcar 'car (pl:layers))) (regapp "PLANTCAD01"))
(pl:init-layers) (setq pl:*native-ui* T pl:*failure* nil)
(foreach pc:e (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE")))) (entdel pc:e))
(pl:db-put "PLANTS" nil) (pl:db-put "SPEC_HISTORY" nil) (pl:db-put "UNIT" 1)
(pl:db-put "PLOT_OPTIONS" '((scale . 100.0) (paper_height . 2.5)))
(pl:built-blocks)
(setq pc:area nil)
(foreach pc:e (pl:ss-list (ssget "_X" '((0 . "REGION")))) (if (not pc:area) (setq pc:area pc:e)))
(pl:mark pc:area "AREA" nil) (pl:data-put pc:area "UNITS" 1.0) (pl:data-put pc:area "AREA_NO" "A1")
(setq pc:ball (pl:put 'name "红叶石楠球" (pl:put 'kind 3 (pl:put 'crown 1.0 (pl:put 'height 1.0 (pl:put 'spec_no "B001" (pl:empty-plant "BALL")))))))
(setq pc:flower (pl:put 'name "花境组合" (pl:put 'kind 4 (pl:put 'spec_no "F001" (pl:empty-plant "FLOWER")))))
(pl:save-def pc:ball) (pl:save-def pc:flower)
(pl:bind-area-plant pc:area pc:flower)
(setq pc:trees nil)
(foreach pc:point '((24.0 0.0 0.0) (26.0 0.0 0.0))
 (setq pc:e (pl:make (list '(0 . "INSERT") '(2 . "PL02_CIRCLE") (cons 8 (pl:tree-layer pc:ball)) (cons 10 pc:point) '(41 . 1.0) '(42 . 1.0) '(43 . 1.0))))
 (pl:mark pc:e "TREE" nil) (pl:data-put pc:e "PLANT" pc:ball) (pl:data-put pc:e "UNITS" 1.0) (setq pc:trees (cons pc:e pc:trees)))
(setq pc:label (pl:output-area-label pc:area '(2.0 2.0 0.0) '(-8.0 -4.0 0.0) '((layout . 0))))
(setq pc:checks (list
 (= (pl:tree-layer pc:ball) "PL_灌木球_圆圈")
 (= (cdr (assoc 8 (entget pc:label))) "PL_花境_标注")
 (= (length (pl:area-output-linked pc:area)) 1)
 (and (vl-string-search "\\P" (pl:native-value (pl:native-leader-text (cdr (assoc 5 (entget pc:label)))))) T)))
(setq pc:label (pl:output-area-label pc:area '(2.0 2.0 0.0) '(-8.0 -4.0 0.0) '((layout . 1))))
(setq pc:checks (append pc:checks (list
 (= (length (pl:area-output-linked pc:area)) 1)
 (null (vl-string-search "\\P" (pl:native-value (pl:native-leader-text (cdr (assoc 5 (entget pc:label))))))))))
(setq pc:tables nil)
(foreach pc:entry '(("count" "PL_表格_苗木") ("list" "PL_表格_植物名录") ("specs" "PL_表格_植物规格"))
 (setq pc:table (pl:output-table-write nil '(0.0 -16.0 0.0) (cadr pc:entry) (car pc:entry) "关联表" 0.25 '((scope . "model"))))
 (setq pc:tables (append pc:tables (list pc:table))))
(setq pc:checks (append pc:checks (list
 (= (length pc:tables) 3)
 (= (pl:native-value (pc:check-legends (cdr (assoc 5 (entget (car pc:tables)))))) 2))))
(setq pc:ball (pl:put 'crown 1.2 (pl:put 'height 1.5 pc:ball)))
(pl:save-project-spec pc:ball) (pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (= (length (pl:defs)) 2)
 (equal (cdr (assoc 41 (entget (car pc:trees)))) 1.2 1e-8)
 (equal (pl:get 'height (pl:plant (cadr pc:trees))) 1.5 1e-8)
 (= (pl:get 'spec_no (pl:plant (car pc:trees))) "B001"))))
(setq pc:table (car pc:tables) pc:rows (pl:data-get pc:table "TABLE_ROWS") pc:ballrow (if (= (caar pc:rows) "BALL") 2 3))
(pc:edit-table (cdr (assoc 5 (entget pc:table))) pc:ballrow 7 "160")
(pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (equal (pl:get 'crown (pl:by-id "BALL")) 1.6 1e-8)
 (equal (cdr (assoc 41 (entget (car pc:trees)))) 1.6 1e-8))))
(pc:edit-table (cdr (assoc 5 (entget pc:table))) pc:ballrow 8 "999")
(pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (= (nth 7 (nth (- pc:ballrow 1) (pl:native-table-read (cdr (assoc 5 (entget pc:table)))))) "2")
 (= (nth 6 (cadr (assoc "BALL" (pl:data-get (cadr pc:tables) "TABLE_ROWS")))) "160")
 (= (length (pl:defs)) 2))))
(setq pc:flower (pl:put 'name "宿根花境" pc:flower))
(pl:save-project-spec pc:flower) (pl:sync-drawing)
(setq pc:checks (append pc:checks (list
 (and (vl-string-search "宿根花境" (pl:native-value (pl:native-leader-text (cdr (assoc 5 (entget pc:label)))))) T)
 (= (pl:get 'layout (pl:data-get pc:label "OUTPUT_OPTIONS")) 1)
 (= (length (pl:area-output-linked pc:area)) 1))))
(pl:db-put "PC_OUTPUT_CHECKS" pc:checks)
'''
    # Place tables separately so the resulting DWG can also be inspected visually.
    body=body.replace("(foreach pc:entry", "(setq pc:table-y -16.0)\n(foreach pc:entry").replace("nil '(0.0 -16.0 0.0)","nil (list 0.0 pc:table-y 0.0)").replace('(setq pc:tables (append pc:tables (list pc:table))))','(setq pc:tables (append pc:tables (list pc:table)) pc:table-y (- pc:table-y 12.0)))')
    check=out/'check.lsp'
    wrapped='(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+body+'\n pc:checks) nil))\n(setq pc:f (open '+quote(out/'lisp-result.txt')+' "w"))\n(prin1 (if (vl-catch-all-error-p pc:r) (list pl:*failure* (vl-catch-all-error-message pc:r)) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
    import sys
    sys.path.insert(0,str(ROOT/'developer/tests'))
    from lisp_harness import parse
    parse(wrapped)
    check.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
    script=out/'check.scr'
    lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'PC_OUTPUT_TEST',
           '(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','(load '+quote(check)+')','_.QSAVE','_.QUIT','_No']
    script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
    run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    (out/'console.bin').write_bytes(run.stdout)
    native=(out/'native-result.txt').read_text(encoding='utf-8-sig') if (out/'native-result.txt').exists() else 'MISSING'
    lisp=(out/'lisp-result.txt').read_text(encoding='gbk') if (out/'lisp-result.txt').exists() else 'MISSING'
    print('OUTPUT',out,flush=True);print('NATIVE',native,flush=True);print('LISP',lisp,flush=True)
    passed=run.returncode==0 and native.startswith('PASS ') and lisp.startswith('(T ') and 'nil' not in lisp and '"' not in lisp
    reopened='NOT RUN'
    if passed:
        reopen_body=body.split('(pl:init-layers) (setq')[0]+r'''
(setq pl:*native-ui* T pl:*failure* nil pc:tables nil)
(foreach pc:e (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE")))) (if (pl:data-get pc:e "TABLE_KIND") (setq pc:tables (cons pc:e pc:tables))))
(pl:sync-drawing)
(setq pc:checks (list
 (= (length (pl:defs)) 2)
 (= (length (pl:all-trees)) 2)
 (= (length (pl:all-areas)) 1)
 (= (length pc:tables) 3)
 (equal (pl:get 'crown (pl:by-id "BALL")) 1.6 1e-8)
 (= (pl:get 'name (pl:by-id "FLOWER")) "宿根花境")
 (= (length (pl:area-output-linked (car (pl:all-areas)))) 1)
 (and (handent (pl:data-get (car (pl:all-areas)) "FILL_HANDLE")) T)
 (= (pl:native-value (pc:check-legends (cdr (assoc 5 (entget (car pc:tables)))))) 2)))
'''
        reopened_lsp=out/'reopen.lsp'
        wrapped='(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+reopen_body+'\n pc:checks) nil))\n(setq pc:f (open '+quote(out/'reopen-result.txt')+' "w"))\n(prin1 (if (vl-catch-all-error-p pc:r) (list pl:*failure* (vl-catch-all-error-message pc:r)) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
        parse(wrapped);reopened_lsp.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
        reopen_script=out/'reopen.scr'
        lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','(load '+quote(reopened_lsp)+')','_.QUIT','_No']
        reopen_script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
        again=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(reopen_script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (out/'reopen-console.bin').write_bytes(again.stdout)
        reopened=(out/'reopen-result.txt').read_text(encoding='gbk') if (out/'reopen-result.txt').exists() else 'MISSING'
        print('REOPEN',reopened,flush=True)
        passed=again.returncode==0 and reopened=='('+' '.join(['T']*9)+')'
    report={'passed':passed,'scope':'AutoCAD 2014 Core Console: production native hatches/tables and production LISP graph, QSAVE/reopen persistence; per-entity LDATA uses a named-dictionary adapter; attribute text rendering and real GUI mouse interactions require desktop acceptance',
            'output':str(out),'native':native,'lisp':lisp,'reopen':reopened,'assertions':(int(native.split()[1]) if native.startswith('PASS ') else 0)+20+9,'original_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,
            'runtime_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}}
    (ROOT/'developer/output-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not passed:raise SystemExit('Native output verification failed; inspect saved reports.')
if __name__=='__main__':main()
