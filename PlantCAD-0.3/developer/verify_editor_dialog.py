"""Exercise production DCL in a new, owned, unsaved CAD drawing.

Never attaches to an existing CAD process or opens a user drawing.
Only keyboard/button cancellation is sent to the owned test dialog.
"""
from pathlib import Path
import argparse, ctypes, json, re, subprocess, time, uuid
import win32con, win32gui, win32process

ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014\acad.exe')

def literal(path):
    return '"'+str(path).replace('\\','/').replace('"','\\"')+'"'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='baseline');parser.add_argument('--timeout',type=int,default=70)
    parser.add_argument('--mode',choices=['esc','cancel','close','init'],default='esc')
    parser.add_argument('--isolated',action='store_true',help='Embed production lifecycle functions; adapt field population to avoid source-load startup prompts.')
    args=parser.parse_args()
    out=ROOT/'bridge/host-output'/('editor-'+args.label+'-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    log=out/'trace.txt';probe=out/'probe.lsp';script=out/'startup.scr';drawing=out/('editor-test-'+out.name+'.dxf')
    drawing.write_text('0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n',encoding='ascii')
    # Instrument the real popup implementation without altering its list calls.
    probe.write_bytes(('''(defun pc:trace (s / f) (setq f (open LOGFILE "a")) (write-line s f) (close f))
(defun pl:popup (key values / value)
 (pc:trace (strcat "POPUP " key))
 (start_list key) (foreach value values (add_list value)) (end_list)
 (pc:trace (strcat "POPUP_OK " key)))
(defun c:PC_EDITOR_PROBE (/ p result)
 (pc:trace "BEGIN")
 (setq p (pl:empty-plant "EDITOR_TEST")
  p (pl:put 'name "Test plant" (pl:put 'spec_no "PTEST" p))
  p (pl:put 'dbh 12.0 (pl:put 'height 5.0 (pl:put 'crown 3.0 p))))
 (setq result (vl-catch-all-apply 'pl:edit-dialog (list p)))
 (if (vl-catch-all-error-p result) (pc:trace (strcat "ERROR " (vl-catch-all-error-message result)))
  (pc:trace (if result "RETURN_SAVED" "RETURN_CANCEL")))
 (pc:trace "FINISHED") (princ))
'''.replace('LOGFILE',literal(log))).replace('\n','\r\n').encode('gbk'))
    commands=['(setq pl:*dir* '+literal(ROOT)+' pl:*native-ui* T)',
        '(load '+literal(ROOT/'plantcad.lsp')+')','(load '+literal(probe)+')']
    if args.isolated:
        sources='\n'.join((ROOT/'developer/src'/name).read_text(encoding='utf-8') for name in ['plantcad-core.lsp','plantcad.lsp'])
        names=['pl:get','pl:put','pl:empty-plant','pl:upgrade-plant','pl:cancelled-error-p','pl:rethrow','pl:dialog','pl:edit-dialog-start','pl:edit-dialog']
        commands=['(setq pl:*dir* '+literal(ROOT)+' pl:*native-ui* T pl:*require-crown* nil pl:*failure* nil)']
        for name in names:
            match=re.search(r'(?ms)^\(defun '+re.escape(name)+r'\s.*?(?=^\(defun |\Z)',sources)
            if not match:raise RuntimeError('Production function not found: '+name)
            commands.append('(eval (read '+json.dumps(match.group(),ensure_ascii=False)+'))')
        # The lifecycle and DCL are production code. Population is an adapter:
        # no catalogue, units, layers or private DWG data are required here.
        commands.append('(defun pl:fill-edit (p) (set_tile "name" "Test plant") (set_tile "crown" "300") (pl:popup "quantity_unit" (list "Test")))')
        source=probe.read_text(encoding='gbk')
        commands.append('(eval (read '+json.dumps('(progn '+source+')',ensure_ascii=False)+'))')
    if args.mode=='init':commands.append('(defun pl:fill-edit (p) (car 7))')
    commands.extend(['PC_EDITOR_PROBE','_.QUIT','_N'])
    script.write_bytes(('\r\n'.join(commands)+'\r\n').encode('gbk'))
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    process=subprocess.Popen([str(CAD),str(drawing),'/nologo','/b',str(script)],cwd=out,startupinfo=startup)
    state={'pid':process.pid,'output':str(out),'drawing':str(drawing),'scope':'New generated empty DXF only; existing CAD untouched. Production lifecycle and DCL; field initialization adapted.' if args.isolated else 'New generated empty DXF only; existing CAD untouched.'}
    (out/'session.json').write_text(json.dumps(state),encoding='utf-8');print(json.dumps(state),flush=True)
    end=time.monotonic()+args.timeout;sent=False;last_trace=''
    while time.monotonic()<end and process.poll() is None:
        trace=log.read_text(encoding='gbk',errors='replace') if log.exists() else ''
        if trace!=last_trace:print(trace[len(last_trace):].rstrip(),flush=True);last_trace=trace
        frames=[]
        win32gui.EnumWindows(lambda h,_:frames.append(h) if win32process.GetWindowThreadProcessId(h)[1]==process.pid and win32gui.IsWindowVisible(h) else None,None)
        for hwnd in frames:
            if win32gui.GetClassName(hwnd)=='adesk_dlg0000' and win32gui.GetWindowText(hwnd)=='植物规格与图例' and not sent:
                # Allow initialization to complete; inspect after a short settle.
                if args.mode=='init' or 'POPUP_OK quantity_unit' not in trace:continue
                target=win32gui.GetDlgItem(hwnd,105)
                if args.mode=='esc':
                    win32gui.PostMessage(target,win32con.WM_KEYDOWN,win32con.VK_ESCAPE,0)
                    win32gui.PostMessage(target,win32con.WM_KEYUP,win32con.VK_ESCAPE,0)
                elif args.mode=='cancel':win32gui.PostMessage(hwnd,win32con.WM_COMMAND,2,win32gui.GetDlgItem(hwnd,2))
                elif args.mode=='close':win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
                sent=True;print('INPUT_POSTED '+args.mode,flush=True)
        if 'FINISHED' in trace:
            break
        time.sleep(.2)
    frames=[]
    win32gui.EnumWindows(lambda h,_:frames.append(h) if win32process.GetWindowThreadProcessId(h)[1]==process.pid and win32gui.IsWindowVisible(h) else None,None)
    orphan=any(win32gui.GetClassName(h)=='adesk_dlg0000' and win32gui.GetWindowText(h)=='植物规格与图例' for h in frames)
    passed='FINISHED' in trace and not orphan and ('ERROR ' in trace if args.mode=='init' else 'RETURN_CANCEL' in trace)
    report={**state,'passed':passed,'mode':args.mode,'orphan_editor':orphan,'trace':trace}
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESULT '+json.dumps(report,ensure_ascii=False),flush=True)
    time.sleep(.5)
    if process.poll() is None:
        mains=[win32gui.GetWindowText(h) for h in frames if win32gui.GetClassName(h).startswith('AfxMDIFrame')]
        if all(drawing.name.casefold() in title.casefold() for title in mains):
            process.terminate();process.wait(timeout=10)
        else:print('Unexpected drawing in test process; left open for review.',flush=True)
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
