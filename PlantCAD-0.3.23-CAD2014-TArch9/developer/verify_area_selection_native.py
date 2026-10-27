"""Exercise the production selection/area bridge with actual AutoLISP and saved CAD entities.
Core Console supplies a real implied selection; this is not a desktop mouse/Tianzheng test.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--drawing',type=Path,required=True);args=ap.parse_args()
 out=ROOT/'bridge/host-output'/('area-selection-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 before=hashlib.sha256(args.drawing.read_bytes()).hexdigest();shutil.copy2(args.drawing,out/'input.dwg')
 csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';dll=out/'SelectionProbe.dll'
 subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/AreaSelectionProbe.cs')],check=True)
 quote=lambda p:'"'+str(p).replace('\\','/')+'"'
 body=r"""
(pl:db-put "UNIT" 0)
(setq pc:handles (pc:input-handles) pc:extra (pl:native-value (pc:extra-handle)) pc:checks nil)
(defun pc:check (value) (setq pc:checks (append pc:checks (list (if value T nil)))))
;; Actual handles cross AutoLISP/.NET; mixed displayed layers, hidden tree layer.
(pc:check (= (length pc:handles) 28))
(setq pc:begin (pl:area-prepare pc:handles))
(prin1 (list "begin" pc:begin "total" (pl:native-area-total)) pc:debug) (write-line "" pc:debug)
(pc:check (= pc:begin 13))
(pc:check (equal (pl:native-value (pl:native-area-total)) 13000000.0 0.001))
(pc:check (< (cdr (assoc 62 (tblsearch "LAYER" "PL_树木_圆圈"))) 0))
(pl:native-area-end)
;; Multiple yellow layers explicitly request a sample; supplied layer then resolves deterministically.
(pc:check (= (pl:native-value (pl:native-area-begin (append pc:handles (list pc:extra)) "")) "AREA_PICK_LAYER"))
(pc:check (= (pl:native-value (pl:native-area-begin (append pc:handles (list pc:extra)) "PC_SOURCE_YELLOW")) 13))
(pl:native-area-end)
;; One non-yellow layer is accepted, and invalid handles return their real reason.
(pc:check (= (pl:native-value (pl:native-area-begin (list pc:extra) "")) 1))
(pl:native-area-end)
(pc:check (vl-string-search "ERROR:" (pl:native-value (pl:native-area-begin '("NOT_A_HANDLE") ""))))
;; Genuine CAD preselection and ssget (no selection or geometry stubs).
(setq pc:original-selection (ssadd))
(foreach pc:h pc:handles (ssadd (handent pc:h) pc:original-selection))
(sssetfirst nil pc:original-selection)
(setq pc:selected (pl:area-selection))
(pc:check (= (length pc:selected) 28))
(pc:check (null (ssget "_I")))
(sssetfirst nil pc:original-selection)
(pl:geometry-session-work)
(setq pc:areas (pl:all-areas) pc:labels (pl:all-labels))
(pc:check (= (length pc:areas) 13))
(pc:check (= (length pc:labels) 13))
(pc:check (equal (apply '+ (mapcar 'pl:area-value pc:areas)) 13.0 0.001))
(pc:check (null (pl:defs)))
(pc:check (< (cdr (assoc 62 (tblsearch "LAYER" "PL_树木_圆圈"))) 0))
(pc:check (> (cdr (assoc 62 (tblsearch "LAYER" "PC_FOREIGN_BLUE"))) 0))
(pl:native-area-end)
;; Plain CAD TEXT, formatted MTEXT and MLeader are resolved against project definitions.
(setq pc:p (pl:new-spec nil) pc:p (pl:put 'name "红叶石楠" pc:p) pc:p (pl:put 'spec_no "P001" pc:p) pc:p (pl:put 'kind 1 pc:p))
(pl:save-def pc:p)
(setq pc:input-labels (pc:label-input))
(pc:check (= (length pc:input-labels) 4))
(foreach pc:handle pc:input-labels
 (pc:check (= (pl:get 'id (pl:plant-from-picked-annotation (handent pc:handle))) (pl:get 'id pc:p))))
(setq pc:bound-selection (ssadd))
(foreach pc:e (append pc:areas pc:labels) (ssadd pc:e pc:bound-selection))
(sssetfirst nil pc:bound-selection)
(pl:bind-selected-areas pc:p)
(pc:check (= (length (vl-remove-if-not '(lambda (e) (= (pl:get 'id (pl:data-get e "AREA_PLANT")) (pl:get 'id pc:p))) pc:areas)) 13))
(pc:check (equal (apply '+ (mapcar 'pl:area-value pc:areas)) 13.0 0.001))
(pc:check (= (length (pl:all-labels)) 13))
(pc:check (= (pl:get 'id (pl:annotation-plant (car pc:labels))) (pl:get 'id pc:p)))
(pc:check (vl-string-search "红叶石楠" (cdr (assoc 1 (entget (car pc:labels))))))
(pc:check (= (length (pl:count-rows pc:areas)) 1))
(pc:check (equal (caddr (car (pl:count-rows pc:areas))) 13.0 0.001))
(pc:check (= (car (pl:native-label-lines (car pc:input-labels))) "红叶石楠"))
;; Error cleanup preserves root failures; a normal cancellation has no alert.
(setq pc:alerts nil pl:*failure* "TEST_ROOT_CAUSE" pl:*stage* "TEST_STAGE")
(defun alert (message) (setq pc:alerts (cons message pc:alerts)))
(setq pc:failure (vl-catch-all-apply '(lambda () (pl:fail "TEST_ROOT_CAUSE")) nil))
(setq pc:rethrow (vl-catch-all-apply 'pl:rethrow (list pc:failure)))
(pl:report-error pc:rethrow)
(pc:check (= (length pc:alerts) 1))
(pc:check (vl-string-search "TEST_ROOT_CAUSE" (car pc:alerts)))
(setq pc:alerts nil pl:*failure* nil)
(pl:report-error (vl-catch-all-apply 'exit nil))
(pc:check (null pc:alerts))
(pc:check (null pl:*failure*))
"""
 result=out/'result.txt';check=out/'check.lsp'
 body="(setq pc:debug (open "+quote(out/'debug.txt')+' "w"))\n'+body+"\n(close pc:debug)\n"
 code="(setq pc:r (vl-catch-all-apply '(lambda ()\n"+body+"\n pc:checks) nil))\n"+'(setq pc:f (open '+quote(result)+' "w"))\n(prin1 (if (vl-catch-all-error-p pc:r) (strcat (if pl:*stage* pl:*stage* "unknown") ": " (vl-catch-all-error-message pc:r)) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
 check.write_bytes(code.replace('\n','\r\n').encode('gbk'))
 script=out/'test.scr'
 lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')','PC_SELECTION_INPUT',
 '(setq pl:*native-ui* T pl:*range-kind* -1)',
 '(defun pl:init-layers () T)',
 '(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))',
 '(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))',
 '(load '+quote(check)+')','_.QUIT','_No']
 script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
 names=['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-workflow.lsp','plantcad-ui.lsp']
 report={'passed':False,'scope':'AutoCAD 2014 Core Console: actual ssget preselection, 28 mixed-layer entities through production handle bridge, 13 regions and labels, hidden tree layer unaffected, layer disambiguation, plain TEXT/MTEXT/MLeader and exploded block text matching, managed annotation linkage, combined name/area labels and grouped statistics, original error/cancel handling; headless metadata/layer adapters; no desktop mouse or Tianzheng launcher acceptance','runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
 try:
  run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(out/'input.dwg'),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=55)
  (out/'console.bin').write_bytes(run.stdout)
  value=result.read_text(encoding='gbk') if result.exists() else 'MISSING';print(value,flush=True)
  assert run.returncode==0 and value=='('+' '.join(['T']*33)+')',(run.returncode,value,str(out))
  report.update(passed=True,assertions=33,original_drawing_unchanged=hashlib.sha256(args.drawing.read_bytes()).hexdigest()==before)
 finally:(ROOT/'developer/area-selection-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()

