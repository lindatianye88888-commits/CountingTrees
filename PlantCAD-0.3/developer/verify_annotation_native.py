"""Native output regression in an isolated AutoCAD profile and owned sample copy.

Does not connect to desktop CAD or read user drawings. This executes the actual
production MLeader code through OutputProbe, including font increases on short
left/right, single/two-line landings. Pure Lisp settings checks run separately.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-base',type=Path,default=ROOT/'bridge/host-output');args=ap.parse_args()
 token=uuid.uuid4().hex[:8];out=args.output_base/('annotation-size-'+token);out.mkdir(parents=True)
 source=CAD/'Support/chroma.dwg';original=hashlib.sha256(source.read_bytes()).hexdigest();drawing=out/'test.dwg';shutil.copy2(source,drawing)
 dll=out/'OutputProbe.dll';production=ROOT/'bridge/PlantCADBridge.dll'
 subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),
  '/reference:'+str(production)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/OutputProbe.cs')],check=True)
 quote=lambda p:'"'+str(p).replace('\\','/')+'"'
 profile=out/'cad-profile';report={'passed':False,'scope':__doc__,'output':str(out),'receiver_sha256':hashlib.sha256(production.read_bytes()).hexdigest()}
 # All rule bodies are production code. Omit only the interactive main startup.
 modules=[]
 for name in ['plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad-project-import.lsp']:
  content=(ROOT/'developer/src'/name).read_text(encoding='utf-8')
  if name=='plantcad.lsp':content=content.split('\n(if (pl:locate-core)',1)[0]
  target=out/name;target.write_bytes(content.replace('\n','\r\n').encode('gbk'));modules.append(target)
 sys.path.insert(0,str(ROOT/'developer/tests'));from lisp_harness import parse
 prefix=r'''
(setq pl:*native-ui* T pl:*drawing-changed* nil pl:*failure* nil pc:checks nil)
(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))
(defun pl:data-put (e key value)
 (if (member key '("PLANT" "AREA_PLANT" "UNITS")) (setq pl:*drawing-changed* T))
 (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))
(defun pl:refresh-all-symbols () 0)
(defun pl:dialog (name) 1)
(defun pl:popup (key values) T) (defun set_tile (key value) T)
(defun action_tile (key value) T) (defun unload_dialog (value) T)
(defun get_tile (key) (cdr (assoc key pc:tiles)))
(defun done_dialog (status) status)
(defun start_dialog () (if pc:cancel 0 (progn (pl:accept-settings) 1)))
(defun pc:check (name value) (setq pc:checks (append pc:checks (list (list name (if value T nil))))))
'''
 body=r'''
(pc:seed-output-layers (mapcar 'car (pl:layers)))
(foreach pc:e (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE")))) (entdel pc:e))
(setq pc:area (car (pl:ss-list (ssget "_X" '((0 . "REGION"))))))
(pl:mark pc:area "AREA" nil) (pl:data-put pc:area "UNITS" 1000.0)
(pl:data-put pc:area "AREA_NO" "A1") (pl:data-put pc:area "AREA_LABEL_RADIUS" 0.001)
(setq pc:plant (pl:put 'name "海桐" (pl:put 'kind 1 (pl:put 'quantity_unit "平方米"
 (pl:put 'spec_no "S001" (pl:empty-plant "SHRUB"))))))
(pl:save-def pc:plant) (pl:data-put pc:area "AREA_PLANT" pc:plant)
(pl:db-put "UNIT" 0) (pl:db-put "PLOT_OPTIONS" '((scale . 100.0) (paper_height . 2.5)))
(setq pc:measured (pl:area-value pc:area) pc:inside (pl:create-area-label pc:area '(0.0 0.0 0.0)))
(setq pc:single (pl:write-native-area-label pc:area '(2.0 2.0 0.0) '(-12.0 -4.0 0.0)
 '((layout . 1) (elbow -8.0 -4.0 0.0)) nil nil))
(setq pc:double (pl:write-native-area-label pc:area '(2.0 2.0 0.0) '(12.0 -6.0 0.0)
 '((layout . 0) (elbow 8.0 -6.0 0.0)) nil nil))
(pc:check "initial font follows millimetre drawing setting"
 (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:single))))) 250.0 1e-8))
(setq pc:tiles '(("unit" . "1") ("plot_scale" . "100") ("paper_height" . "0.25") ("show_number" . "0")))
(pl:settings-work) (pl:sync-drawing)
(pc:check "settings UI centimetres stored as millimetres" (equal (pl:get 'paper_height (pl:db-get "PLOT_OPTIONS" nil)) 2.5 1e-8))
(pc:check "settings apply to existing single-line label" (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:single))))) 0.25 1e-8))
(pc:check "settings apply to existing two-line label" (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:double))))) 0.25 1e-8))
(pc:check "settings apply to interior area indicator" (equal (cdr (assoc 40 (entget pc:inside))) 0.25 1e-8))
(setq pc:tiles '(("unit" . "1") ("plot_scale" . "200") ("paper_height" . "0.5") ("show_number" . "0")))
(pl:settings-work) (pl:sync-drawing)
(pc:check "scale and font increase reaches actual MLeader" (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:single))))) 1.0 1e-8))
(pc:check "two-line font increase reaches actual MLeader" (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:double))))) 1.0 1e-8))
(pc:check "arrow follows new font" (equal (cadr (pc:leader-style (cdr (assoc 5 (entget pc:single))))) 0.3 1e-8))
(pc:check "interior font increases with settings" (equal (cdr (assoc 40 (entget pc:inside))) 1.0 1e-8))
(pc:check "area keeps original measurement units" (= (pl:data-get pc:area "UNITS") 1000.0))
(pc:check "measured area does not change" (equal pc:measured (pl:area-value pc:area) 1e-8))
(pc:check "single-line layout retained" (= (pl:get 'layout (pl:data-get pc:single "OUTPUT_OPTIONS")) 1))
(pc:check "two-line layout retained" (= (pl:get 'layout (pl:data-get pc:double "OUTPUT_OPTIONS")) 0))
(pc:check "left elbow retained" (equal (nth 4 (pc:leader-style (cdr (assoc 5 (entget pc:single))))) '(-8.0 -4.0 0.0) 1e-8))
(pc:check "right elbow retained" (equal (nth 4 (pc:leader-style (cdr (assoc 5 (entget pc:double))))) '(8.0 -6.0 0.0) 1e-8))
(setq pc:cancel T pc:tiles '(("unit" . "0") ("plot_scale" . "50") ("paper_height" . "5") ("show_number" . "0")))
(pl:settings-work)
(pc:check "cancel retains unit" (= (pl:unit-index) 1))
(pc:check "cancel retains plot scale" (= (pl:get 'scale (pl:db-get "PLOT_OPTIONS" nil)) 200.0))
(pc:check "cancel retains font" (equal (car (pc:leader-style (cdr (assoc 5 (entget pc:single))))) 1.0 1e-8))
(pl:data-put pc:single "OUTPUT_STYLE_VERSION" 2) (pl:sync-area-labels)
(pc:check "legacy version migrates on refresh" (= (pl:data-get pc:single "OUTPUT_STYLE_VERSION") 3))
(pl:db-put "HEIGHT_LABELS" (mapcar '(lambda (e) (cdr (assoc 5 (entget e)))) (list pc:inside pc:single pc:double)))
(pl:db-put "HEIGHT_AREA" (cdr (assoc 5 (entget pc:area))))
(pl:db-put "HEIGHT_MEASURED" pc:measured)
'''
 reopen=r'''
(setq pc:area (handent (pl:db-get "HEIGHT_AREA" nil))
 pc:labels (mapcar 'handent (pl:db-get "HEIGHT_LABELS" nil)))
(pl:sync-drawing)
(pc:check "saved global settings persist" (= (pl:get 'scale (pl:db-get "PLOT_OPTIONS" nil)) 200.0))
(pc:check "saved single-line font persists" (equal (car (pc:leader-style (cdr (assoc 5 (entget (cadr pc:labels)))))) 1.0 1e-8))
(pc:check "saved two-line font persists" (equal (car (pc:leader-style (cdr (assoc 5 (entget (caddr pc:labels)))))) 1.0 1e-8))
(pc:check "saved interior font persists" (equal (cdr (assoc 40 (entget (car pc:labels)))) 1.0 1e-8))
(pc:check "saved area remains unchanged" (equal (pl:db-get "HEIGHT_MEASURED" nil) (pl:area-value pc:area) 1e-8))
'''
 try:
  report['runs']=[]
  for phase,code in [('initial',body),('reopen',reopen)]:
   result=out/(phase+'.txt');lsp=out/(phase+'.lsp')
   wrapped=prefix+"\n(setq pc:r (vl-catch-all-apply '(lambda ()\n"+code+"\n pc:checks) nil))\n"
   wrapped+='(setq pc:f (open '+quote(result)+' "w")) (prin1 (if (vl-catch-all-error-p pc:r) (list "ERROR" pl:*failure* (vl-catch-all-error-message pc:r) pc:checks) pc:r) pc:f) (close pc:f)\n'
   parse(wrapped);lsp.write_bytes(wrapped.replace('\n','\r\n').encode('gbk'))
   commands=['_.NETLOAD',quote(production),'_.NETLOAD',quote(dll)]
   if phase=='initial':commands+=['PC_OUTPUT_TEST']
   commands+=['(setq pl:*dir* '+quote(ROOT)+')']
   trace=out/(phase+'-loads.txt')
   commands+=['(setq pc:trace (open '+quote(trace)+' "w"))','(write-line "BEGIN" pc:trace)','(close pc:trace)']
   for module in modules:
    commands+=['(load '+quote(module)+')','(setq pc:trace (open '+quote(trace)+' "a"))','(write-line '+quote(module.name)+' pc:trace)','(close pc:trace)']
   commands+=["(setq pc:loaded (vl-catch-all-apply 'load (list "+quote(lsp)+')))',
    '(setq pc:trace (open '+quote(trace)+' "a"))',
    '(prin1 (if (vl-catch-all-error-p pc:loaded) (vl-catch-all-error-message pc:loaded) pc:loaded) pc:trace)','(close pc:trace)']
   if phase=='initial':commands+=['_.QSAVE']
   commands+=['_.QUIT','_No'];script=out/(phase+'.scr');script.write_bytes(('\r\n'.join(commands)+'\r\n').encode('gbk'))
   run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(drawing),'/s',str(script),'/isolate','CountingTreesHeight'+token,str(profile)],cwd=out,
    creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=45)
   (out/(phase+'-console.bin')).write_bytes(run.stdout)
   actual=result.read_text(encoding='gbk') if result.exists() else 'MISSING';parsed=parse(actual)[0] if actual!='MISSING' else None
   passed=run.returncode==0 and isinstance(parsed,list) and len(parsed)>0 and all(isinstance(row,list) and len(row)==2 and row[1] is True for row in parsed)
   report['runs'].append({'phase':phase,'passed':passed,'actual':actual});print(phase,actual,flush=True)
   if not passed:raise AssertionError('Annotation settings integration failed: '+phase)
  native=out/'native-result.txt';actual=native.read_text(encoding='utf-8-sig') if native.exists() else 'MISSING'
  match=re.match(r'^PASS (\d+) ',actual)
  report.update(native=actual,assertions=(int(match[1]) if match else 0)+sum(len(parse(r['actual'])[0]) for r in report['runs']),passed=bool(match))
  report['scope']+=' Settings-dialog callbacks and entity LDATA use deterministic adapters; actual MLeader/MTEXT writes and QSAVE/reopen use the CAD database.'
  report['runtime_sha256']={p.name:hashlib.sha256((ROOT/'developer/src'/p.name).read_bytes()).hexdigest() for p in modules}
  report['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==original
  report['passed']=report['passed'] and report['original_unchanged'];print(json.dumps(report,ensure_ascii=False),flush=True)
 finally:
  (ROOT/'developer/annotation-native-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 if not report['passed']:raise SystemExit('Native annotation regression did not pass; inspect the report.')
if __name__=='__main__':main()
