"""Reproduce case2's former area failure and verify installed project resizing on copies."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,subprocess,sys,time,uuid
import panel_host_tools as h
import pywintypes
ROOT=Path(__file__).resolve().parents[1];CAD=h.CAD.parent
ctypes.windll.user32.SetProcessDPIAware()
sys.path.insert(0,str(ROOT));from install_panel import cad_running
if cad_running():raise RuntimeError('User CAD is open; refusing to attach')
h.require_interactive_desktop()
out=ROOT/'bridge/host-output'/('case-desktop-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
source=ROOT.parent/'案例2/植物配置20261021.dwg';before=hashlib.sha256(source.read_bytes()).hexdigest();drawing=out/'case-copy.dwg';shutil.copy2(source,drawing)
dll=out/'CaseDesktopProbe.dll'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll),'/reference:System.Drawing.dll','/reference:System.Windows.Forms.dll','/reference:System.Web.Extensions.dll','/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests'/n) for n in ['DesktopHangProbe.cs','CaseAreaProbe.cs']],check=True)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
installed=json.loads((ROOT/'install-state.json').read_text(encoding='utf-8'))
installed_dll=Path(installed['bundle'])/'Contents/bridge/PlantCADBridge.dll'
script=out/'startup.scr'
prefix=['(progn (setq pc:startup-f (open '+q(out/'startup-vars.txt')+' "w")) (prin1 (list (getvar "FILEDIA") (getvar "CMDDIA") (getvar "NOMUTT")) pc:startup-f) (close pc:startup-f))','FILEDIA','0','CMDDIA','0','NOMUTT','1','_.OPEN',q(drawing)]
script.write_bytes(('\r\n'.join(prefix+['_.NETLOAD',q(installed_dll),'_.NETLOAD',q(dll),'PC_HANG_OBSERVE','PLANTCAD'])+'\r\n').encode('gbk'))
si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=3
template=Path(os.environ['LOCALAPPDATA'])/'Autodesk/AutoCAD 2014/R19.1/chs/Template/acadiso.dwt'
if not template.is_file():raise RuntimeError('Missing isolated startup template: '+str(template))
process=subprocess.Popen([str(h.CAD),'/t',str(template),'/p','TArch9','/nologo','/b',str(script)],cwd=out,startupinfo=si)
state={'pid':process.pid,'drawing':str(drawing),'output':str(out)};statefile=out/'session.json';statefile.write_text(json.dumps(state),encoding='utf-8')
report={'passed':False,'source':str(source),'output':str(out),'checks':[],'scope':'AutoCAD 2014/TArch9 installed bundle on isolated copy of case2 DWG: 241 real shrub edges, production region registration/internal labels, repeat scan reuse, source XY and foreign geometry/color retention, actual resizable project modal dialog and filtered choice returned to LISP'}
driver=ROOT/'developer/verify_desktop_erase.py'
from verify_desktop_erase import owned_app
startup_dispatched=False
startup_at=time.monotonic()
def wait(fn,timeout=45):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if process.poll() is not None:raise RuntimeError('Owned case CAD exited')
  try:h.dismiss_notice(process.pid)
  except pywintypes.error as ex:
   if ex.winerror!=1400:raise
  for frame in h.windows(process.pid):
   try:kind=h.win32gui.GetClassName(frame);title=h.win32gui.GetWindowText(frame)
   except pywintypes.error as ex:
    if ex.winerror==1400:continue
    raise
   if kind.startswith('AfxMDIFrame') and not h.win32gui.IsWindowVisible(frame):h.win32gui.ShowWindow(frame,h.win32con.SW_MAXIMIZE)
   if title=='缺少 SHX 文件':
    for c in h.children(frame):
     if h.win32gui.GetWindowText(c)=='忽略缺少的 SHX 文件并继续':h.win32gui.PostMessage(c,h.win32con.BM_CLICK,0,0)
  global startup_dispatched
  if not startup_dispatched and not (out/'events.log').exists() and time.monotonic()-startup_at>10:
   try:
    app=owned_app(state);doc=app.ActiveDocument
    if app.GetAcadState().IsQuiescent and doc.GetVariable('CMDACTIVE')==0:
     print('Owned drawing ROT ready, dispatching explicit startup',flush=True)
     startup_dispatched=True
     doc.SendCommand('_.NETLOAD\n'+q(installed_dll)+'\n_.NETLOAD\n'+q(dll)+'\nPC_HANG_OBSERVE\nPLANTCAD\n')
   except Exception:pass
  if fn():return
  time.sleep(.2)
 raise TimeoutError('Case verification did not complete')
def send(command,block=True):
 child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(driver),'--remote',str(statefile),command],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if block:
  output,_=child.communicate(timeout=45)
  if child.returncode:raise RuntimeError(output.decode('utf-8',errors='replace'))
 return child
def probe(expr):
 p=out/(uuid.uuid4().hex+'.txt')
 send('(progn (setq pct:r (vl-catch-all-apply \'(lambda () '+expr+') nil)) (setq pct:f (open '+q(p)+' "w")) (prin1 (if (vl-catch-all-error-p pct:r) (list pl:*failure* (vl-catch-all-error-message pct:r)) pct:r) pct:f) (close pct:f) (princ))')
 wait(lambda:p.exists() and p.stat().st_size>0);return p.read_text(encoding='gbk').strip()
def check(expr,name):
 result=probe(expr);report['checks'].append({'name':name,'result':result});print(name,result,flush=True)
 if result!='T':raise AssertionError(name+': '+result)
try:
 log=out/'events.log';wait(lambda:log.exists() and 'END PLANTCADLOADED' in log.read_text(encoding='utf-8-sig'),300)
 check('(progn (setvar "TILEMODE" 1) (pl:db-put "UNIT" 0) (pl:init-layers) (setq pc:case-handles (pc:case-handles "PL_灌木_原始线") pc:xy (pl:native-value (pc:case-signature "PL_灌木_原始线" 0)) pc:foreign (pl:native-value (pc:case-signature "PL_灌木_原始线" 1))) (= (length pc:case-handles) 241))','Real case2 boundary selection')
 report['begin_debug']=probe('(progn (setq pc:case-count (pl:native-value (pl:native-area-begin pc:case-handles "PL_灌木_原始线"))) (list pc:case-count (pc:case-stats)))');print(report['begin_debug'],flush=True)
 check('(progn (setq pc:case-total (pl:native-value (pl:native-area-total))) (= pc:case-count 118))','Microscopic joints produce all 118 case faces')
 check("(>= (pl:native-value (pc:case-index '(34537214502.31024 3134342074.9540305 0.0))) 0)","Previously missed location 1")
 check("(>= (pl:native-value (pc:case-index '(34537242731.64979 3134377058.830069 0.0))) 0)","Previously missed location 2")
 check("(>= (pl:native-value (pc:case-index '(34537088063.93582 3134391735.8287573 0.0))) 0)","Previously missed location 3")
 check("(>= (pl:native-value (pc:case-index '(34537270570.065506 3134354610.810843 0.0))) 0)","Previously missed location 4")
 check("(>= (pl:native-value (pc:case-index '(34537145396.11023 3134388642.00776 0.0))) 0)","Previously missed location 5")
 check("(>= (pl:native-value (pc:case-index '(34537121123.06859 3134391468.083194 0.0))) 0)","Previously missed location 6")
 check("(>= (pl:native-value (pc:case-index '(34537187327.66862 3134352585.901206 0.0))) 0)","Previously missed location 7")
 check("(>= (pl:native-value (pc:case-index '(34537189442.47403 3134384812.611064 0.0))) 0)","Previously missed location 8")
 check('(progn (setq pc:case-batch (pl:native-area-export-all "PL_面积_计算边界")) (pl:consume-area-batch pc:case-batch -1) (= (length (cdr pc:case-batch)) 118))','All case2 faces generate region and measurement output')
 check('(not (vl-some \'(lambda (row) (not (pl:area-output-linked (handent (car row))))) (cdr pc:case-batch)))','Every face has internal area text')
 check('(not (vl-some \'(lambda (row) (<= (nth 3 row) 0)) (cdr pc:case-batch)))','All label anchors have positive interior clearance in world coordinates')
 check('(equal (apply \'+ (mapcar \'(lambda (row) (pl:area-value (handent (car row)))) (cdr pc:case-batch))) (/ pc:case-total 1000000.0) 0.001)','Exported area sum matches native geometric total')
 check('(equal pc:xy (pl:native-value (pc:case-signature "PL_灌木_原始线" 0)))','Selected original boundary XY retained')
 check('(equal pc:foreign (pl:native-value (pc:case-signature "PL_灌木_原始线" 1)))','Foreign curves colors and XYZ retained')
 check('(progn (setq pc:case-areas (length (pl:all-areas)) pc:case-labels (length (pl:all-labels))) (pl:native-area-end) (= (pl:native-value (pl:native-area-begin pc:case-handles "PL_灌木_原始线")) 118))','Repeated case scan remains valid')
 check('(progn (pl:consume-area-batch (pl:native-area-export-all "PL_面积_计算边界") -1) (and (= pc:case-areas (length (pl:all-areas))) (= pc:case-labels (length (pl:all-labels)))))','Repeated scan reuses regions and text')
 send('(progn (pl:native-area-end) (foreach pc:k \'(0 1 2 3 4 5) (setq pc:p (pl:put \'kind pc:k (pl:put \'name (strcat "界面对齐" (itoa pc:k)) (pl:put \'spec_no (strcat "UI" (itoa pc:k)) (pl:empty-plant (strcat "UI_TYPE_" (itoa pc:k))))))) (pl:save-def pc:p)))')
 send('PC_PROJECT_OBSERVE');child=send('(pl:library-work)',False);result=out/'project-probe.txt'
 wait(lambda:result.exists() and result.stat().st_size>0,30);report['project_result']=result.read_text(encoding='utf-8-sig')
 if not report['project_result'].startswith('PASS '):raise AssertionError(report['project_result'])
 child.communicate(timeout=15)
 check('(equal (pl:get \'id (pl:current)) "UI_TYPE_5")','Resizable project choice returns correct plant specification')
 shutil.copy2(out/'project-dialog.png',ROOT/'docs/images/项目窗口可缩放实机.png')
 report['passed']=True
except Exception as ex:report['error']=repr(ex);print('FAIL',repr(ex),flush=True)
finally:
 report['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before;report['assertions']=len(report['checks'])
 if process.poll() is None:
  try:send('--close');process.wait(timeout=15)
  except Exception:
   if process.poll() is None:process.terminate();process.wait(timeout=15)
 report['runtime_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 if report['passed']:(ROOT/'developer/case-desktop-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('REPORT',out,flush=True)
if not report['passed']:raise SystemExit(1)
