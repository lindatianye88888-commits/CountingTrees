"""Actual area-output LISP and native MLeader; deterministic mouse/DCL adapters."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
    source=Path(json.loads((ROOT/'developer/output-verification.json').read_text(encoding='utf-8'))['output'])/'input.dwg'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    out=ROOT/'bridge/host-output'/('area-leader-flow-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True);shutil.copy2(source,out/'input.dwg')
    dll=out/'OutputProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/OutputProbe.cs')],check=True)
    sys.path.insert(0,str(ROOT/'developer/tests'));from lisp_harness import parse
    quote=lambda p:'"'+str(p).replace('\\','/')+'"'
    prefix=r'''
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:layer-open (name / row) (and (setq row (tblsearch "LAYER" name)) (= 0 (logand 4 (cdr (assoc 70 row))))))
(defun pl:refresh-symbol (e) T) (defun pl:refresh-all-symbols () 0)
(defun pl:init-layers () (pc:seed-output-layers (mapcar 'car (pl:layers))) (regapp "PLANTCAD01"))
(setq pl:*native-ui* T pl:*drawing-changed* nil pl:*failure* nil)
'''
    body=r'''
(setq pc:area (car (pl:all-areas)) pc:old-label (car (pl:area-output-linked pc:area))
 pc:old-plant (pl:data-get pc:area "AREA_PLANT") pc:value (pl:area-value pc:area)
 pc:options '((layout . 0) (fill . 0) (bind . 0)) pc:events nil pc:tiles nil pc:cancel nil)
(pl:data-put pc:area "AREA_ANCHOR" '(2.0 2.0 0.0))
(defun pl:selected-areas () (list pc:area))
(defun pl:area-output-options () pc:options)
(defun getpoint (base message / point)
 (setq pc:events (append pc:events '("point")) point (car pc:points) pc:points (cdr pc:points)) point)
(defun pl:dialog (name) (setq pc:events (append pc:events (list name))) 1)
(defun set_tile (key value / old) (setq old (assoc key pc:tiles) pc:tiles (if old (subst (cons key value) old pc:tiles) (cons (cons key value) pc:tiles))) value)
(defun get_tile (key) (cdr (assoc key pc:tiles)))
(defun start_list (key) T) (defun add_list (value) T) (defun end_list () T)
(defun action_tile (key value) T) (defun unload_dialog (id) T)
(defun done_dialog (status) (setq pc:status status))
(defun start_dialog ()
 (if pc:cancel (done_dialog 0)
  (progn (pl:area-species-row "1") (pl:area-species-accept))) pc:status)
(setq pc:points '(nil)) (pl:output-area-work)
(setq pc:checks (list
 (equal pc:events '("point"))
 (entget pc:old-label)
 (equal pc:old-plant (pl:data-get pc:area "AREA_PLANT"))))
(setq pc:checks (mapcar '(lambda (x) (if x T nil)) pc:checks))
(setq pc:events nil pc:points '((-8.0 -4.0 0.0) (-58.0 9.0 0.0)) pc:cancel T)
(pl:output-area-work)
(setq pc:checks (append pc:checks (list
 (equal pc:events '("point" "point" "pl_area_species"))
 (and (entget pc:old-label) T)
 (equal pc:old-plant (pl:data-get pc:area "AREA_PLANT")))))
(setq pc:events nil pc:points '((-8.0 -4.0 0.0) (-58.0 9.0 0.0)) pc:cancel nil)
(pl:output-area-work)
(setq pc:label (car (pl:area-output-linked pc:area)) pc:style (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
(setq pc:checks (append pc:checks (list
 (equal pc:events '("point" "point" "pl_area_species"))
 (not (entget pc:old-label))
 (= (cdr (assoc 0 (entget pc:label))) "MULTILEADER")
 (= (length (pl:area-output-linked pc:area)) 1)
 (= (pl:get 'layout (pl:data-get pc:label "OUTPUT_OPTIONS")) 0)
 (equal (pl:get 'elbow (pl:data-get pc:label "OUTPUT_OPTIONS")) '(-8.0 -4.0 0.0) 1e-8)
 (equal (nth 4 pc:style) '(-8.0 -4.0 0.0) 1e-8)
 (equal (nth 5 pc:style) '(-58.0 -4.0 0.0) 1e-8)
 (not (null (vl-string-search "\\P" (pl:area-annotation-raw pc:label))))
 (equal pc:value (pl:area-value pc:area) 1e-8))))
(pl:db-put "AREA_OUTPUT_OPTIONS" '((layout . 1) (fill . 1) (bind . 1)))
(setq pc:p (pl:put 'name "换品种后保持双行" (pl:data-get pc:area "AREA_PLANT")))
(pl:save-project-spec pc:p) (pl:sync-drawing)
(pl:data-put pc:label "OUTPUT_STYLE_VERSION" nil) (pl:sync-area-labels)
(setq pc:after (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
(setq pc:checks (append pc:checks (list
 (= (pl:get 'layout (pl:data-get pc:label "OUTPUT_OPTIONS")) 0)
 (not (null (vl-string-search "\\P" (pl:area-annotation-raw pc:label))))
 (equal (nth 4 pc:style) (nth 4 pc:after) 1e-8)
 (equal (nth 5 pc:style) (nth 5 pc:after) 1e-8)
 (equal (pl:data-get pc:label "OUTPUT_STYLE_VERSION") 2))))
(pl:db-put "PC_PICKED_LABEL" (cdr (assoc 5 (entget pc:label))))
(pl:db-put "PC_PICKED_AREA" (cdr (assoc 5 (entget pc:area))))
'''
    def run(name,body,save=False):
        result=out/(name+'.txt')
        wrapped=prefix+'\n(setq pc:r (vl-catch-all-apply \'(lambda ()\n'+body+'\n pc:checks) nil))\n(setq pc:f (open '+quote(result)+' "w")) (prin1 (if (vl-catch-all-error-p pc:r) (list pl:*failure* (vl-catch-all-error-message pc:r)) pc:r) pc:f) (close pc:f)\n'
        parse(wrapped);lsp=out/(name+'.lsp');lsp.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
        script=out/(name+'.scr');lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','(load '+quote(lsp)+')']
        if save:lines+=['_.QSAVE']
        lines+=['_.QUIT','_No'];script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
        proc=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (out/(name+'-console.bin')).write_bytes(proc.stdout)
        text=result.read_text(encoding='gbk') if result.exists() else 'MISSING';print(name,text,flush=True)
        return proc.returncode==0 and text.startswith('(T ') and 'nil' not in text and '"' not in text,text
    passed,seed=run('seed',body,True);reopen='NOT RUN'
    if passed:
        passed,reopen=run('reopen',r'''
(setq pc:label (handent (pl:db-get "PC_PICKED_LABEL" nil)) pc:area (handent (pl:db-get "PC_PICKED_AREA" nil)))
(pl:sync-drawing)
(setq pc:style (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
(setq pc:checks (list
 (= (pl:get 'layout (pl:data-get pc:label "OUTPUT_OPTIONS")) 0)
 (not (null (vl-string-search "\\P" (pl:area-annotation-raw pc:label))))
 (equal (nth 4 pc:style) '(-8.0 -4.0 0.0) 1e-8)
 (equal (nth 5 pc:style) '(-58.0 -4.0 0.0) 1e-8)
 (= (length (pl:area-output-linked pc:area)) 1)))
''')
    report={'passed':passed,'seed':seed,'reopen':reopen,'assertions':seed.count('T')+reopen.count('T'),'output':str(out),
        'original_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,
        'scope':'AutoCAD 2014 Core Console: actual two-point area-output LISP then species selection, skip/cancel preservation, exact native elbow/tail, per-label layout independent of subsequent global defaults, rename/sync and DWG reopen; deterministic mouse/DCL tile and named-dictionary LDATA adapters, not GUI interaction/render acceptance',
        'runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}}
    (ROOT/'developer/area-leader-flow-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('OUTPUT',out,flush=True)
    if not passed:raise SystemExit('Area leader flow verification failed')
if __name__=='__main__':main()
