"""Capture only the owned DCL window and a native CAD PNG, never other apps."""
from pathlib import Path
import ctypes,hashlib,json,shutil,subprocess,sys,time,uuid
import win32gui,win32con,win32ui,win32process
from PIL import Image
import panel_host_tools as h
ROOT=Path(__file__).resolve().parents[1]
ctypes.windll.user32.SetProcessDPIAware()
sys.path.insert(0,str(ROOT));from install_panel import cad_running
if cad_running():raise RuntimeError('Existing CAD is open; refusing to attach')
out=ROOT/'bridge/host-output'/('output-preview-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
source=ROOT.parent/'20261016压力测试01/Drawing2.dwg';before=hashlib.sha256(source.read_bytes()).hexdigest()
drawing=out/'preview-copy.dwg';shutil.copy2(source,drawing)
q=lambda p:'"'+str(p).replace('\\','/')+'"'
probe_dll=Path(json.loads((ROOT/'developer/desktop-legend-ui-verification.json').read_text(encoding='utf-8'))['output'])/'DesktopHangProbe.dll'
script=out/'startup.scr';script.write_bytes(('\r\n'.join(['FILEDIA','0','CMDDIA','0','_.NETLOAD',q(probe_dll),'PC_HANG_OBSERVE','PLANTCAD'])+'\r\n').encode('gbk'))
si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
process=subprocess.Popen([str(h.CAD),str(drawing),'/p','TArch9','/nologo','/b',str(script)],cwd=out,startupinfo=si)
state={'pid':process.pid,'drawing':str(drawing),'output':str(out)};statefile=out/'session.json';statefile.write_text(json.dumps(state),encoding='utf-8')
driver=ROOT/'developer/verify_desktop_erase.py';report={'passed':False,'output':str(out),'scope':'Installed AutoCAD 2014/TArch9 on copied user DWG; DCL captured with PrintWindow, table exported by native PNGOUT; no desktop or other application screenshots','assertions':0}
def wait(fn,timeout=60):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if process.poll() is not None:raise RuntimeError('Owned preview CAD exited')
  h.dismiss_notice(process.pid)
  for w in h.windows(process.pid):
   if win32gui.GetClassName(w).startswith('AfxMDIFrame') and not win32gui.IsWindowVisible(w):win32gui.ShowWindow(w,win32con.SW_MAXIMIZE)
   if win32gui.GetWindowText(w)=='缺少 SHX 文件':
    for c in h.children(w):
     if win32gui.GetWindowText(c)=='忽略缺少的 SHX 文件并继续':win32gui.PostMessage(c,win32con.BM_CLICK,0,0)
  if fn():return
  time.sleep(.2)
 raise TimeoutError('Owned output preview did not complete')
def send(command,blocking=True):
 child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(driver),'--remote',str(statefile),command],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if blocking:
  output,_=child.communicate(timeout=45)
  if child.returncode:raise RuntimeError(output.decode('utf-8',errors='replace'))
 return child
def capture_window(hwnd,path):
 assert win32process.GetWindowThreadProcessId(hwnd)[1]==process.pid
 left,top,right,bottom=win32gui.GetWindowRect(hwnd);width=right-left;height=bottom-top
 dc=win32gui.GetWindowDC(hwnd);source_dc=win32ui.CreateDCFromHandle(dc);memory=source_dc.CreateCompatibleDC()
 bitmap=win32ui.CreateBitmap();bitmap.CreateCompatibleBitmap(source_dc,width,height);memory.SelectObject(bitmap)
 try:
  if not ctypes.windll.user32.PrintWindow(hwnd,memory.GetSafeHdc(),2):raise RuntimeError('Owned DCL PrintWindow failed')
  Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1).save(path)
 finally:
  win32gui.DeleteObject(bitmap.GetHandle());memory.DeleteDC();source_dc.DeleteDC();win32gui.ReleaseDC(hwnd,dc)
try:
 log=out/'events.log';wait(lambda:log.exists() and 'END PLANTCADLOADED' in log.read_text(encoding='utf-8-sig'),110)
 send('(progn (setvar "TILEMODE" 1) (defun getpoint (message) \'(160000000.0 100000000.0 0.0)) (pl:table-work) (setq pc:preview-table (entlast)) (princ))')
 # Find the managed table rather than relying on AutoCAD's internal table subentities.
 send('(progn (setq pc:preview-table nil) (foreach e (pl:ss-list (ssget "_X" \'((0 . "ACAD_TABLE")))) (if (and (equal (pl:data-get e "TABLE_TITLE") "苗木数量总表") (> (car (cdr (assoc 10 (entget e)))) 150000000.0)) (setq pc:preview-table e))) (command "_.ZOOM" "_Object" pc:preview-table "") (princ))')
 png=out/'total.png'
 send('(progn (setvar "SELECTIONPREVIEW" 0) (setvar "HIGHLIGHT" 0) (vl-catch-all-apply \'setvar \'("TABLEINDICATOR" 0)) (sssetfirst nil nil) (command "_.REGEN") (command "_.PNGOUT" '+q(png)+' pc:preview-table ""))');wait(lambda:png.exists() and png.stat().st_size>1000)
 target=ROOT/'docs/images/苗木数量总表图例实机.png';shutil.copy2(png,target);report['table_image']=str(target);report['assertions']+=1
 child=send('(pl:library-work)',False);dialog=[None]
 def project_ready():
  dialog[0]=next((w for w in h.windows(process.pid) if '项目植物与规格' in win32gui.GetWindowText(w) and win32gui.IsWindowVisible(w)),None);return dialog[0]
 wait(project_ready);time.sleep(.5)
 target=ROOT/'docs/images/项目参数对齐实机.png';capture_window(dialog[0],target);report['project_image']=str(target);report['project_window']=h.describe(dialog[0]);report['assertions']+=1
 close=next(c for c in h.children(dialog[0]) if win32gui.GetWindowText(c)=='关闭' and 'button' in win32gui.GetClassName(c).lower())
 win32gui.PostMessage(close,win32con.BM_CLICK,0,0);child.communicate(timeout=20)
 if child.returncode:raise RuntimeError('Project dialog did not close')
 report['assertions']+=1;report['passed']=True
finally:
 report['original_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
 if process.poll() is None:
  try:send('--close');process.wait(timeout=15)
  except Exception:
   if process.poll() is None:process.terminate();process.wait(timeout=15)
 report['runtime_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['bridge/PlantCADBridge.dll','plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl']}
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 if report['passed']:(ROOT/'developer/output-preview-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
