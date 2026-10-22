"""Owned CAD session helpers for the PlantCAD native panel acceptance test."""
from pathlib import Path
import argparse,json,subprocess,time,uuid,winreg,ctypes
import pythoncom,pywintypes,win32com.client,win32gui,win32con,win32process

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'bridge/host-output/panel-session.json'
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014\acad.exe')
PROFILE=r'Software\Autodesk\AutoCAD\R19.1\ACAD-D001:804\Profiles'

def require_interactive_desktop():
    """Fail before launching GUI tests when Windows input desktop is locked."""
    from ctypes import wintypes
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.OpenInputDesktop.restype=wintypes.HANDLE
    api.CloseDesktop.argtypes=[wintypes.HANDLE]
    desktop=api.OpenInputDesktop(0,False,1)
    if not desktop:
        raise RuntimeError('Windows input desktop is unavailable; unlock Windows/remote desktop before CAD GUI tests (error '+str(ctypes.get_last_error())+')')
    api.CloseDesktop(desktop)

def windows(pid):
    result=[]
    def visit(h,_):
        if win32process.GetWindowThreadProcessId(h)[1]==pid: result.append(h)
    win32gui.EnumWindows(visit,None)
    return result

def children(parent):
    result=[]
    win32gui.EnumChildWindows(parent,lambda h,_:result.append(h),None)
    return result

def describe(h):
    return {'handle':h,'class':win32gui.GetClassName(h),'text':win32gui.GetWindowText(h),
            'visible':bool(win32gui.IsWindowVisible(h)),'rect':win32gui.GetWindowRect(h),'id':win32gui.GetDlgCtrlID(h)}

def dismiss_notice(pid):
    # AutoCAD's separate welcome browser can keep startup COM unavailable.
    # Match the actual browser executable and parent PID before closing only its welcome.
    from ctypes import wintypes
    import sys
    sys.path.insert(0,str(ROOT))
    from install_panel import PROCESSENTRY32
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    api.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32)]
    api.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32)]
    api.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=api.CreateToolhelp32Snapshot(2,0)
    browser_pids=[]
    if snapshot!=ctypes.c_void_p(-1).value:
        try:
            entry=PROCESSENTRY32();entry.dwSize=ctypes.sizeof(entry)
            ok=api.Process32FirstW(snapshot,ctypes.byref(entry))
            while ok:
                if entry.parent==pid and entry.name.lower()=='acbrowserhost.exe':
                    browser_pids.append(entry.pid)
                ok=api.Process32NextW(snapshot,ctypes.byref(entry))
        finally:api.CloseHandle(snapshot)
    for browser in browser_pids:
        for frame in windows(browser):
            if win32gui.GetClassName(frame)=='QWidget' and win32gui.GetWindowText(frame)=='欢迎':
                win32gui.PostMessage(frame,win32con.WM_CLOSE,0,0)
    for h in windows(pid):
        if win32gui.GetWindowText(h)!='纬衡出图管理系统': continue
        controls=children(h)
        if any('客户端服务未启动, 截图功能将关闭!' in win32gui.GetWindowText(c) for c in controls):
            for c in controls:
                if win32gui.GetClassName(c)=='Button' and win32gui.GetWindowText(c)=='确定':
                    win32gui.PostMessage(c,win32con.BM_CLICK,0,0)

def wait_for(fn,pid=None,timeout=45):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        pythoncom.PumpWaitingMessages()
        if pid:
            dismiss_notice(pid)
            # This test verifies an interactive panel, so show only its owned frame.
            for frame in windows(pid):
                if win32gui.GetClassName(frame).startswith('AfxMDIFrame') and not win32gui.IsWindowVisible(frame):
                    win32gui.ShowWindow(frame,win32con.SW_MAXIMIZE)
                    try:win32gui.SetForegroundWindow(frame)
                    except pywintypes.error:pass
        try:
            value=fn()
            if value:return value
        except pywintypes.com_error:pass
        time.sleep(.15)
    raise TimeoutError('CAD did not reach expected state')

def state():
    return json.loads(STATE.read_text(encoding='utf-8'))

def owned():
    s=state()
    app=win32com.client.GetActiveObject('AutoCAD.Application.19.1')
    assert win32process.GetWindowThreadProcessId(app.HWND)[1]==s['pid']
    return s,app

def quote(s):return '"'+str(s).replace('\\','/').replace('"','\\"')+'"'
def point(*xyz):return win32com.client.VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,xyz)

def probe(expr):
    s,app=owned();doc=app.ActiveDocument
    assert doc.FullName==s['drawing'],'Unexpected active document'
    target=Path(s['output'])/(uuid.uuid4().hex+'.txt')
    expression="(progn (setq pct:result (vl-catch-all-apply '(lambda () "+expr+") nil)) (if (vl-catch-all-error-p pct:result) (strcat \"ERROR: \" (vl-catch-all-error-message pct:result)) pct:result))"
    doc.SendCommand('(progn (setq pct:file (open '+quote(target)+' "w")) (prin1 '+expression+' pct:file) (close pct:file) (princ))\n')
    wait_for(lambda:target.exists() and target.stat().st_size>0,s['pid'])
    wait_for(lambda:app.GetAcadState().IsQuiescent,s['pid'])
    return target.read_text(encoding='gbk').strip()

def click(h):
    assert win32process.GetWindowThreadProcessId(h)[1]==state()['pid']
    win32gui.PostMessage(h,win32con.BM_CLICK,0,0)

def dialog(title):
    s=state()
    return next((h for h in windows(s['pid']) if win32gui.IsWindowVisible(h) and title in win32gui.GetWindowText(h)),None)

def button(parent,text):
    return next(h for h in children(parent) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)==text and ('button' in win32gui.GetClassName(h).lower()))

def panel_button(text):
    s,app=owned()
    for parent in windows(s['pid']):
        try:return button(parent,text)
        except StopIteration:pass
    raise LookupError('Panel button not found: '+text)

def set_text(h,text):
    assert win32process.GetWindowThreadProcessId(h)[1]==state()['pid']
    win32gui.SendMessage(h,win32con.WM_SETTEXT,0,text)

def edit_for_label(parent,label):
    controls=[describe(h) for h in children(parent) if win32gui.IsWindowVisible(h)]
    assert parent and win32gui.IsWindow(parent), 'Dialog changed before input'
    caption=next(c for c in controls if label in c['text'] and c['class']=='Static')
    x1,y1,x2,y2=caption['rect']
    edits=[c for c in controls if c['class']=='Edit' and c['rect'][0]>=x2-4 and abs((c['rect'][1]+c['rect'][3]-y1-y2)/2)<14]
    return min(edits,key=lambda c:c['rect'][0])['handle']

def list_select(h,index=0):
    win32gui.SendMessage(h,win32con.LB_SETSEL,1,index)
    parent=win32gui.GetParent(h)
    win32gui.PostMessage(parent,win32con.WM_COMMAND,win32gui.GetDlgCtrlID(h)|(win32con.LBN_SELCHANGE<<16),h)

def capture_owned_window(path,handle,pid):
    from PIL import Image
    assert win32process.GetWindowThreadProcessId(handle)[1]==pid
    left,top,right,bottom=win32gui.GetWindowRect(handle);width=right-left;height=bottom-top
    import win32ui
    dc=win32gui.GetWindowDC(handle);source=win32ui.CreateDCFromHandle(dc);memory=source.CreateCompatibleDC()
    bitmap=win32ui.CreateBitmap();bitmap.CreateCompatibleBitmap(source,width,height);memory.SelectObject(bitmap)
    try:
        if not ctypes.windll.user32.PrintWindow(handle,memory.GetSafeHdc(),2):raise RuntimeError('Owned window PrintWindow failed')
        Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1).save(path)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle());memory.DeleteDC();source.DeleteDC();win32gui.ReleaseDC(handle,dc)
    return str(path)

def capture(path=None,handle=None):
    from PIL import ImageGrab
    s=state()
    h=handle or next(w for w in windows(s['pid']) if win32gui.GetClassName(w).startswith('AfxMDIFrame'))
    assert win32process.GetWindowThreadProcessId(h)[1]==s['pid']
    try:win32gui.SetForegroundWindow(h)
    except pywintypes.error:pass
    time.sleep(.4)
    image=ImageGrab.grab(bbox=win32gui.GetWindowRect(h),all_screens=True)
    out=Path(path or Path(s['output'])/'native-panel.png')
    out.parent.mkdir(parents=True,exist_ok=True)
    image.save(out)
    return str(out)

def start(direct=False):
    try:win32com.client.GetActiveObject('AutoCAD.Application.19.1')
    except pywintypes.com_error:pass
    else:raise RuntimeError('A CAD session is already open; refusing to attach.')
    output=ROOT/'bridge/host-output'/('panel-'+uuid.uuid4().hex[:8]);output.mkdir(parents=True)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,PROFILE) as k:original=winreg.QueryValueEx(k,'')[0]
    si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    if direct:
        process=subprocess.Popen([str(CAD),'/p','TArch9','/nologo'],startupinfo=si)
        cad_pid=process.pid
        startup='AutoCAD 2014 /p TArch9 (installed Tianzheng modules)'
        command_line=str(CAD)+' /p TArch9 /nologo'
    else:
        launcher=Path(r'D:\Program Files (x86)\天正\TGStart64.exe')
        process=subprocess.Popen([str(launcher)],startupinfo=si,cwd=str(launcher.parent))
        service=win32com.client.Dispatch('WbemScripting.SWbemLocator').ConnectServer('.','root/cimv2')
        found=wait_for(lambda:list(service.ExecQuery("SELECT ProcessId,CommandLine FROM Win32_Process WHERE Name='acad.exe'")),timeout=45)
        assert len(found)==1, 'Expected one newly launched CAD process'
        cad_pid=int(found[0].ProcessId);startup='TGStart64.exe (actual Tianzheng launcher)';command_line=found[0].CommandLine
    baseline=ROOT/'bridge/host-output/profile-before-panel-test.json'
    if baseline.exists():original=json.loads(baseline.read_text(encoding='utf-8'))['profile']
    s={'pid':cad_pid,'launcher_pid':process.pid,'startup':startup,
       'command_line':command_line,'output':str(output),'original_profile':original,'checks':[],'drawing':str(output/'panel-base.dwg')}
    STATE.parent.mkdir(parents=True,exist_ok=True);STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Started owned Tianzheng-profile CAD PID '+str(cad_pid),flush=True)
    app=wait_for(lambda:win32com.client.GetActiveObject('AutoCAD.Application.19.1'),cad_pid,100)
    wait_for(lambda:app.GetAcadState().IsQuiescent,cad_pid,75)
    prepare()

def prepare():
    s,app=owned()
    app.Visible=True
    candidates=[d for d in app.Documents if d.Name and not d.FullName]
    assert candidates, "No owned empty startup drawing"
    doc=candidates[0]
    doc.Activate()
    assert doc.ModelSpace.Count==0, "Startup drawing is not empty"
    wait_for(lambda:app.GetAcadState().IsQuiescent,s['pid'])
    layer=doc.Layers.Add('BASE_EXISTING');layer.Color=4;doc.ActiveLayer=layer
    doc.ModelSpace.AddLine(point(1000,1000,0),point(16000,1000,0))
    doc.ModelSpace.AddLine(point(16000,1000,0),point(16000,12000,0))
    doc.ModelSpace.AddCircle(point(4000,4500,0),700)
    doc.ModelSpace.AddText('EXISTING BASE',point(6000,11000,0),300)
    layer.Lock=True
    doc.SetVariable('INSUNITS',4)
    doc.SaveAs(s['drawing'])
    s['base_handles']=[e.Handle for e in doc.ModelSpace]
    s['base_entities']=[{'handle':e.Handle,'type':e.ObjectName,'layer':e.Layer} for e in doc.ModelSpace]
    s['before_variables']={k:doc.GetVariable(k) for k in ['CLAYER','INSUNITS','LTSCALE','TEXTSTYLE','OSMODE','SECURELOAD','TRUSTEDPATHS']}
    s['support_path']=app.Preferences.Files.SupportPath
    s['profile']=app.Preferences.Profiles.ActiveProfile
    STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Owned existing base prepared. The PLANTCAD command opens the panel without manual NETLOAD.',flush=True)

def finish():
    s,app=owned()
    for doc in list(app.Documents):
        if doc.FullName and not Path(doc.FullName).is_relative_to(Path(s['output'])):
            raise RuntimeError('Unexpected user drawing: leave CAD open.')
    for doc in list(app.Documents):doc.Close(False)
    app.Quit()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,PROFILE,0,winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE) as k:
        if winreg.QueryValueEx(k,'')[0]=='TArch9':winreg.SetValueEx(k,'',0,winreg.REG_SZ,s['original_profile'])
    print('Owned test session closed and original profile restored.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','prepare','inspect','probe','capture','finish']);p.add_argument('value',nargs='?')
    p.add_argument('--direct',action='store_true');a=p.parse_args()
    if a.action=='start':start(a.direct)
    elif a.action=='prepare':prepare()
    elif a.action=='finish':finish()
    elif a.action=='probe':print(probe(a.value))
    elif a.action=='capture':print(capture(a.value))
    else:
        s,app=owned()
        rows=[]
        for h in windows(s['pid']):
            if win32gui.IsWindowVisible(h):rows.append({'window':describe(h),'controls':[describe(c) for c in children(h) if win32gui.IsWindowVisible(c) and win32gui.GetWindowText(c)]})
        print(json.dumps({'session':s,'last_prompt':app.ActiveDocument.GetVariable('LASTPROMPT'),'windows':rows},ensure_ascii=False,indent=2))
