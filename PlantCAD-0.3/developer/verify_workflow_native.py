from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--drawing",type=Path,required=True);args=ap.parse_args()
 out=ROOT/'bridge/host-output'/('workflow-native-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 original=args.drawing;before=hashlib.sha256(original.read_bytes()).hexdigest();shutil.copy2(original,out/'input.dwg')
 csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';dll=out/'WorkflowProbe.dll'
 subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/WorkflowProbe.cs')],check=True)
 quote=lambda p:'"'+str(p).replace('\\','/')+'"'
 seed=r'''
(pl:db-put "UNIT" 0)
(setq pc:progress "geometry without plants")
(setq pl:*range-kind* -1)
(pl:range-session-loop)
(setq pc:a nil pc:b nil)
(foreach pc:e (pl:all-areas) (cond ((= (pl:area-number pc:e) "A1") (setq pc:a pc:e)) ((= (pl:area-number pc:e) "A2") (setq pc:b pc:e))))
(setq pc:duplicate (cdr (pl:native-area-export-all "PL_面积_计算边界")))
(setq pc:no-plants (null (pl:defs)) pc:plain-label (pl:area-label-text pc:a)
      pc:raw-total (pl:native-value (pl:native-area-total))
      pc:label-count (pl:native-value (pc:area-labels-inside)))
(pl:native-area-end)
(setq pc:p (pl:new-spec nil) pc:p (pl:put 'name "红叶石楠" pc:p) pc:p (pl:put 'kind 1 pc:p) pc:p (pl:put 'dbh 0.0 pc:p) pc:p (pl:put 'crown 0.6 pc:p))
(pl:save-def pc:p) (pl:db-put "CURRENT" (pl:get 'id pc:p))
(setq pc:bound (pl:bind-area-plant pc:a pc:p))
(pl:sync-area-labels)
(pl:db-put "CATALOG_PICKED" (list (car (pl:catalog)) (cadr (pl:catalog))))
(pl:db-put "UNITS_PER_M" 10.0) (pl:db-put "UNIT" 3)
(setq pc:checks (list
 (and pc:a pc:b (equal 6.0 (pl:area-value pc:a) 1e-8) (equal 6.0 (pl:area-value pc:b) 1e-8))
 (null pc:duplicate)
 (= (length (pl:all-areas)) 2)
 (= (length (pl:all-labels)) 2)
 (equal (apply '+ (mapcar 'caddr (pl:count-rows (pl:statistics-model)))) 12.0 1e-8)
 pc:no-plants
 (= pc:plain-label "区域 A1\\P6.00 平方米")
 (null (pl:data-get pc:b "AREA_PLANT"))
 pc:bound
 (= (pl:area-title pc:a) "红叶石楠")
 (= (cdr (assoc 62 (tblsearch "LAYER" "PL_面积_计算边界"))) 2)
 (= (pl:native-value (pc:undo-flags)) 1)
 (null (getcname "PLSET"))
 (equal pc:raw-total 12000000.0 1e-8)
 (> (pl:data-get pc:a "AREA_LABEL_RADIUS") 0)
 (= (pl:data-get pc:a "AREA_REPAIRED") 0)
 (= pc:label-count 2)

))
'''
 reopened=r'''
(setq pc:p (pl:current) pc:areas (pl:all-areas))
(setq pc:checks (list
 (= (pl:get 'name pc:p) "红叶石楠")
 (= (length (pl:db-get "CATALOG_PICKED" nil)) 2)
 (equal (pl:get 'crown (pl:seed-size pc:p (pl:project-size-defaults))) 0.6 1e-8)
 (= (length pc:areas) 2)
 (= (length (pl:all-labels)) 2)
 (equal (pl:area-value (car pc:areas)) 6.0 1e-8)
 (equal (apply '+ (mapcar 'caddr (pl:count-rows (pl:statistics-model)))) 12.0 1e-8)
 (equal (pl:units) 10.0 1e-8)
 (= (length (vl-remove-if-not '(lambda (e) (null (pl:data-get e "AREA_PLANT"))) pc:areas)) 1)
 (= (length (vl-remove-if-not '(lambda (e) (= (pl:area-title e) "红叶石楠")) pc:areas)) 1)
 (and (member "A1" (mapcar 'pl:area-number pc:areas)) (member "A2" (mapcar 'pl:area-number pc:areas)) T)
))
'''
 repair=r'''
(pl:db-put "UNIT" 1) (setq pl:*range-kind* -1 pc:progress "automatic repair batch")
(pc:reset-broken-session)
(pl:range-session-loop)
(setq pc:areas (pl:all-areas))
(pc:reset-broken-session)
(pl:range-session-loop)
(setq pc:checks (list
 (= (length pc:areas) 2)
 (= (length (pl:all-labels)) 2)
 (= (length (pl:all-areas)) 2)
 (null (pl:defs))
 (< (abs (- (apply '+ (mapcar 'caddr (pl:count-rows pc:areas))) 100.0)) 0.001)
 (= (length (vl-remove-if-not '(lambda (e) (= (pl:data-get e "AREA_REPAIRED") 1)) pc:areas)) 2)
 (and (vl-string-search "约 " (pl:area-label-text (car pc:areas))) T)
 (= (pl:native-value (pc:area-labels-inside)) 2)
 (> (sslength (ssget "_X" '((0 . "LINE") (-3 ("PLANTCAD01"))))) 0)
 (null (cdr (pl:native-area-export-all "PL_面积_计算边界")))
))
(pl:native-area-end)
'''
 report={'passed':False,'scope':'Actual AutoCAD 2014 Core Console with production DLL/LISP: seeded automatic all-area export and gap-recovery session with no plant definitions, real REGION/labels/statistics, optional later plant association, native QSAVE/reopen DWG; headless adapters: native layer seed and per-handle named LDATA dictionaries replace unavailable COM; production per-entity COM data backend is not tested here; no GUI picking or Tianzheng double-click acceptance','checks':[],'runtime_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ui.lsp','plantcad-workflow.lsp']}}
 try:
  for stage,body in [('seed',seed),('reopen',reopened),('repair',repair)]:
   result=out/(stage+'.txt');check=out/(stage+'.lsp')
   code="(setq pc:r (vl-catch-all-apply '(lambda ()\n"+body+"\n pc:checks) nil))\n"+'(setq pc:f (open '+quote(result)+' "w"))\n(prin1 (if (vl-catch-all-error-p pc:r) (strcat pc:progress ": " (vl-catch-all-error-message pc:r)) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
   check.write_bytes(code.replace('\n','\r\n').encode('gbk'))
   script=out/(stage+'.scr')
   lines=['_.NETLOAD',quote(ROOT/'bridge/PlantCADBridge.dll'),'_.NETLOAD',quote(dll),'(setq pl:*dir* '+quote(ROOT)+')','(load '+quote(ROOT/'plantcad.lsp')+')']
   if stage=='seed':lines+=['PC_AREA_SESSION']
   if stage=='repair':lines+=['PC_AREA_SESSION']
   lines+=[
    '(setq pl:*native-ui* T)',
    '(defun pl:data-get (e key) (vlax-ldata-get (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key nil))',
    '(defun pl:data-put (e key value) (vlax-ldata-put (strcat "PC_ENTITY_" (cdr (assoc 5 (entget e)))) key value))',
    '(progn (setq pc:loaded (vl-catch-all-apply \'load (list '+quote(check)+'))) (setq pc:lf (open '+quote(out/(stage+'-load.txt'))+' "w")) (prin1 (if (vl-catch-all-error-p pc:loaded) (vl-catch-all-error-message pc:loaded) pc:loaded) pc:lf) (close pc:lf))']
   if stage=='seed':lines+=['_.QSAVE']
   lines+=['_.QUIT','_No']
   trace=out/(stage+'-script-trace.txt')
   def step(message):return '(progn (setq pc:tf (open '+quote(trace)+' "a")) (write-line "'+message+'" pc:tf) (close pc:tf))'
   lines.insert(0,step('script-start'))
   lines.insert(6,step('assemblies-loaded'))
   lines.insert(len(lines)-2,step('body-finished'))
   script.write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
   drawing=out/'input.dwg'
   if stage=='repair':drawing=out/'repair.dwg';shutil.copy2(original,drawing)
   run=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(drawing),'/s',str(script)],cwd=out,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
   (out/(stage+'-console.bin')).write_bytes(run.stdout)
   value=result.read_text(encoding='gbk') if result.exists() else 'MISSING';print(stage,value,flush=True)
   assert run.returncode==0 and value=='('+' '.join(['T']*({'seed':17,'reopen':11,'repair':10}[stage]))+')',(run.returncode,value)
   report['checks'].append(stage)
  report.update(passed=True,assertions=38,original_drawing_unchanged=hashlib.sha256(original.read_bytes()).hexdigest()==before)
 finally:(ROOT/'developer/workflow-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
