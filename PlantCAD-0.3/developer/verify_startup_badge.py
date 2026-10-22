"""Bounded startup/badge/DCL checks in an owned AutoCAD 2014 TArch9 session; no user drawing is opened."""
from pathlib import Path
import ctypes,json,subprocess,sys,time,uuid,winreg,hashlib
from ctypes import wintypes
import win32gui,win32con,win32process,pywintypes
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'developer'))
from install_panel import cad_running
import panel_host_tools as h
PROFILE=r'Software\Autodesk\AutoCAD\R19.1\ACAD-D001:804\Profiles'
def main():
 if cad_running():raise RuntimeError('Existing CAD session: leave it untouched.')
 output=ROOT/'bridge/host-output'/('startup-badge-'+uuid.uuid4().hex[:8]);output.mkdir(parents=True)
 source=ROOT/'bridge/host-output/preserved-startup-d88f64fd.dwg'
 import shutil
 shutil.copy2(source,output/'input.dwg')
 source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
 installed=json.loads((ROOT/'install-state.json').read_text(encoding='utf-8'))
 package=Path(installed['bundle'])/'Contents'
 quote=lambda p:'"'+str(p).replace('\\','/')+'"'
 seed=output/'seed.lsp'
 seed.write_bytes(('''(setq pl:*dir* PACKAGE pl:*native-ui* T)
(load MAIN)
(setq pc:p (pl:put 'spec_no "P001" (pl:put 'name "银杏" (pl:empty-plant "GUI_TEST_GINKGO"))))
(setq pc:p (pl:put 'crown 3.0 (pl:put 'height 4.0 (pl:put 'dbh 12.0 pc:p))))
(pl:save-def pc:p)
(pl:db-put "CURRENT" (pl:get 'id pc:p))
(setq pc:f (open MARKER "w"))
(prin1 (arx) pc:f)
(close pc:f)
(princ)
'''.replace('PACKAGE',quote(package)).replace('MAIN',quote(package/'plantcad.lsp')).replace('MARKER',quote(output/'ready.txt'))).replace('\n','\r\n').encode('gbk'))
 script=output/'start.scr';script.write_bytes(('(load '+quote(seed)+')\r\n').encode('gbk'))
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,PROFILE) as k:original=winreg.QueryValueEx(k,'')[0]
 si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
 process=subprocess.Popen([r'D:\Program Files (x86)\CAD2014\AutoCAD 2014\acad.exe',str(output/'input.dwg'),'/p','TArch9','/nologo','/b',str(script)],startupinfo=si)
 pid=process.pid
 report={'passed':False,'pid':pid,'output':str(output),'original_profile':original,
 'scope':'Owned AutoCAD 2014 /p TArch9 session; actual TGStart64 shortcut launcher is not exercised',
 'checks':[],'receiver_sha256':hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).hexdigest(),
 'runtime_sha256':{row['name']:row['sha256'] for row in installed['files']}}
 state=ROOT/'developer/startup-verification.json'
 def flush():state.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 def check(label):report['checks'].append(label);flush();print('PASS GUI '+label,flush=True)
 def windows():return [w for w in h.windows(pid) if win32gui.IsWindowVisible(w)]
 def title(fragment):
  return next((w for w in windows() if fragment in win32gui.GetWindowText(w)),None)
 def wait(fn,seconds=20):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if process.poll() is not None:raise RuntimeError('Owned CAD exited before the check completed.')
   try:
    h.dismiss_notice(pid)
    for w in h.windows(pid):
     if win32gui.IsWindow(w) and win32gui.GetClassName(w).startswith('AfxMDIFrame') and not win32gui.IsWindowVisible(w):win32gui.ShowWindow(w,win32con.SW_MAXIMIZE)
    value=fn()
    if value:return value
   except pywintypes.error as exc:
    if exc.winerror!=1400:raise
   time.sleep(.15)
  raise TimeoutError('Native GUI did not reach expected state.')
 def click(control):
  assert win32process.GetWindowThreadProcessId(control)[1]==pid
  win32gui.PostMessage(control,win32con.BM_CLICK,0,0)
 def button(parent,text):return h.button(parent,text)
 def panel_button(text):
  return button(title('PlantCAD 植物工作台'),text)
 def dbl(control):
  assert win32process.GetWindowThreadProcessId(control)[1]==pid
  pos=(24<<16)|24
  for msg in [win32con.WM_LBUTTONDOWN,win32con.WM_LBUTTONUP,win32con.WM_LBUTTONDBLCLK,win32con.WM_LBUTTONUP]:
   win32gui.PostMessage(control,msg,win32con.MK_LBUTTON if msg in [win32con.WM_LBUTTONDOWN,win32con.WM_LBUTTONDBLCLK] else 0,pos)
 def text(control):
  assert win32process.GetWindowThreadProcessId(control)[1]==pid
  api=ctypes.WinDLL('user32',use_last_error=True)
  api.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
  buf=ctypes.create_unicode_buffer(2048);result=ctypes.c_size_t()
  ok=api.SendMessageTimeoutW(control,win32con.WM_GETTEXT,2048,ctypes.cast(buf,ctypes.c_void_p).value,2,1000,ctypes.byref(result))
  if not ok:raise RuntimeError('Owned control text read timed out')
  return buf.value
 def field(parent,label,kind='Edit'):
  controls=[h.describe(c) for c in h.children(parent) if win32gui.IsWindowVisible(c)]
  caption=next(c for c in controls if c['class']=='Static' and label in c['text'])
  left,top,right,bottom=caption['rect']
  candidates=[c for c in controls if c['class']==kind and c['rect'][0]>=right-4 and abs((c['rect'][1]+c['rect'][3]-top-bottom)/2)<16]
  return min(candidates,key=lambda c:c['rect'][0])['handle']
 def list_text(control,index):
  length=win32gui.SendMessage(control,win32con.LB_GETTEXTLEN,index,0)
  buf=ctypes.create_unicode_buffer(length+1)
  win32gui.SendMessage(control,win32con.LB_GETTEXT,index,buf)
  return buf.value
 print('Owned startup GUI PID '+str(pid),flush=True);flush()
 try:
  badge=wait(lambda:title('PlantCAD 植物小圆标'),75)
  assert not title('PlantCAD 植物工作台')
  check('Startup automatically shows only the plant badge; PLANTCAD was not invoked')
  wait(lambda:(output/'ready.txt').exists(),20)
  report['loaded_modules']=(output/'ready.txt').read_text(encoding='gbk')
  frame=next(w for w in h.windows(pid) if win32gui.GetClassName(w).startswith('AfxMDIFrame'))
  report['native_title']=win32gui.GetWindowText(frame)
  dbl(h.children(badge)[0])
  panel=wait(lambda:title('PlantCAD 植物工作台'))
  wait(lambda:any('冠幅：300 cm' in win32gui.GetWindowText(c) for c in h.children(panel)),20)
  check('Badge double-click expands the real workbench with current species and 300 cm crown')
  time.sleep(.4);click(panel_button('选植物'))
  catalogue=wait(lambda:title('可编辑植物品种表'))
  lists=[c for c in h.children(catalogue) if win32gui.GetClassName(c)=='ListBox']
  left=max(lists,key=lambda c:win32gui.GetWindowRect(c)[2]-win32gui.GetWindowRect(c)[0])
  right=min(lists,key=lambda c:win32gui.GetWindowRect(c)[2]-win32gui.GetWindowRect(c)[0])
  win32gui.SendMessage(left,win32con.LB_SETSEL,1,0)
  win32gui.PostMessage(catalogue,win32con.WM_COMMAND,win32gui.GetDlgCtrlID(left)|(win32con.LBN_SELCHANGE<<16),left)
  wait(lambda:win32gui.SendMessage(right,win32con.LB_GETCOUNT,0,0)==1)
  assert '[常绿]' in list_text(right,0),list_text(right,0)
  check('Selecting a catalogue plant immediately shows its classification in the right selected list')
  try:
   from PIL import ImageGrab
   win32gui.SetForegroundWindow(catalogue);time.sleep(.2)
   ImageGrab.grab(bbox=win32gui.GetWindowRect(catalogue),all_screens=True).save(ROOT/'docs/images/已选植物实机.png')
  except Exception as exc:report['capture_note']=repr(exc)
  click(button(catalogue,'关闭'));wait(lambda:not title('可编辑植物品种表'))
  time.sleep(.3);click(panel_button('项目规格'))
  project=wait(lambda:title('项目植物与规格'))
  box=max((c for c in h.children(project) if win32gui.GetClassName(c)=='ListBox'),key=lambda c:win32gui.GetWindowRect(c)[3]-win32gui.GetWindowRect(c)[1])
  win32gui.SendMessage(box,win32con.LB_SETCURSEL,0,0)
  win32gui.PostMessage(project,win32con.WM_COMMAND,win32gui.GetDlgCtrlID(box)|(win32con.LBN_DBLCLK<<16),box)
  spec=wait(lambda:title('植物规格与图例'))
  assert text(field(spec,'冠幅 / cm'))=='300'
  assert text(field(spec,'高度 / cm'))=='400'
  check('Double-clicking project row opens its editor with centimetre values')
  click(button(spec,'取消'));project=wait(lambda:title('项目植物与规格'));click(button(project,'关闭'))
  wait(lambda:not title('项目植物与规格'))
  # Test the actual window-caption double click rather than a direct helper call.
  win32gui.PostMessage(panel,0x00A3,2,0)
  wait(lambda:title('PlantCAD 植物小圆标') and not title('PlantCAD 植物工作台'))
  check('Double-clicking the workbench caption collapses it back to the badge')
  assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
  report.update(passed=True,original_test_drawing_unchanged=True)
 except BaseException as exc:
  report['error']=repr(exc);print('GUI stopped: '+repr(exc),flush=True)
 finally:
  flush()
  # Close only the owned input drawing; any unexpected document is left for the user.
  frames=[w for w in h.windows(pid) if win32gui.GetClassName(w).startswith('AfxMDIFrame')]
  if process.poll() is None and frames and 'input.dwg' in win32gui.GetWindowText(frames[0]).lower():
   win32gui.PostMessage(frames[0],win32con.WM_CLOSE,0,0)
   until=time.monotonic()+12
   while process.poll() is None and time.monotonic()<until:
    for dialog in windows():
     if win32gui.GetClassName(dialog)!='#32770':continue
     controls=h.children(dialog)
     captions=' '.join(win32gui.GetWindowText(c) for c in controls)
     if 'input.dwg' in captions.lower() and ('保存' in captions or 'save' in captions.lower()):
      no=next((c for c in controls if win32gui.GetClassName(c)=='Button' and ('否' in win32gui.GetWindowText(c) or win32gui.GetWindowText(c).lower().startswith('no'))),None)
      if no:click(no)
    time.sleep(.15)
  if process.poll() is not None:
   with winreg.OpenKey(winreg.HKEY_CURRENT_USER,PROFILE,0,winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE) as k:
    if winreg.QueryValueEx(k,'')[0]=='TArch9':winreg.SetValueEx(k,'',0,winreg.REG_SZ,original)
   report['cleanup']='Owned CAD closed; original default profile restored.'
  else:report['cleanup']='Owned test CAD left open; no forced process termination.'
  flush()
  print('GUI report: '+str(state),flush=True)
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
