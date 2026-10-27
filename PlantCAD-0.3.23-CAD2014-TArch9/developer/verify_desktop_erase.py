"""Bounded ERASE/UNDO regression in an owned desktop CAD and a copied DWG.

Uses real installed bundle, native event subscriptions, COM LDATA and attributes.
Never attaches to an already open user CAD. A watchdog can end only the process
created by this test; input DWG is hashed and never opened directly.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[1]
CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')

def quote(path):return '"'+str(path).replace('\\','/').replace('"','\\"')+'"'

def owned_app(state):
    import win32com.client,win32process,pythoncom
    try:
        app=win32com.client.GetActiveObject('AutoCAD.Application.19.1')
        if win32process.GetWindowThreadProcessId(app.HWND)[1]==state['pid']:return app
    except pythoncom.com_error:pass
    # Some CAD sessions register the drawing moniker without the global app
    # moniker. Bind only an existing, exact copied-DWG moniker; never create COM.
    rot=pythoncom.GetRunningObjectTable();ctx=pythoncom.CreateBindCtx(0)
    for moniker in rot.EnumRunning():
        if moniker.GetDisplayName(ctx,None).casefold()==state['drawing'].casefold():
            app=win32com.client.Dispatch(rot.GetObject(moniker)).Application
            assert win32process.GetWindowThreadProcessId(app.HWND)[1]==state['pid'],'Unexpected CAD process'
            return app
    raise RuntimeError('Owned copied drawing has no automation registration yet')

def remote(state,command=None):
    import win32process
    app=owned_app(state)
    assert win32process.GetWindowThreadProcessId(app.HWND)[1]==state['pid'],'Unexpected CAD process'
    if command is None:
        for doc in list(app.Documents):
            if doc.FullName and not Path(doc.FullName).is_relative_to(Path(state['output'])):
                raise RuntimeError('Unexpected user drawing; leave CAD open')
        variables=Path(state['output'])/'startup-vars.txt'
        if variables.is_file():
            import re
            values=re.findall(r'\d+',variables.read_text(encoding='ascii'))
            if len(values)!=3:raise RuntimeError('Invalid owned startup variable snapshot')
            for name,value in zip(['FILEDIA','CMDDIA','NOMUTT'],values):app.ActiveDocument.SetVariable(name,int(value))
        for doc in list(app.Documents):doc.Close(False)
        app.Quit()
    else:
        assert app.ActiveDocument.FullName==state['drawing'],'Unexpected active drawing'
        app.ActiveDocument.SendCommand(command+'\n')

def main():
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--drawing',type=Path,required=True)
    p.add_argument('--label',default='fixed')
    p.add_argument('--annotations',action='store_true')
    p.add_argument('--manual-areas',action='store_true')
    p.add_argument('--schedules',action='store_true')
    p.add_argument('--label-feedback',action='store_true')
    p.add_argument('--legend-ui',action='store_true')
    p.add_argument('--trace-sync',action='store_true')
    args=p.parse_args()
    sys.path.insert(0,str(ROOT))
    from install_panel import cad_running
    if cad_running():raise RuntimeError('Existing CAD is open: refusing to start or attach')
    import panel_host_tools as h
    h.require_interactive_desktop()
    out=ROOT/'bridge/host-output'/('desktop-erase-'+args.label+'-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    original=hashlib.sha256(args.drawing.read_bytes()).hexdigest()
    drawing=out/'test-copy.dwg';shutil.copy2(args.drawing,drawing)
    dll=out/'DesktopHangProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/platform:x64','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/out:'+str(dll)]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(ROOT/'developer/tests/DesktopHangProbe.cs')],check=True)
    script=out/'startup.scr'
    script.write_bytes(('\r\n'.join(['FILEDIA','0','CMDDIA','0','_.NETLOAD',quote(dll),'PC_HANG_OBSERVE','PLANTCAD'])+'\r\n').encode('gbk'))
    si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    process=subprocess.Popen([str(CAD/'acad.exe'),str(drawing),'/p','TArch9','/nologo','/b',str(script)],startupinfo=si,cwd=out)
    state={'pid':process.pid,'drawing':str(drawing),'output':str(out)}
    statefile=out/'session.json';statefile.write_text(json.dumps(state),encoding='utf-8')
    installed=json.loads((ROOT/'install-state.json').read_text(encoding='utf-8'))
    report={'passed':False,'label':args.label,'installed_version':installed['version'],'pid':process.pid,'original':str(args.drawing.resolve()),'output':str(out),'checks':[],'operations':[],'scope':'AutoCAD 2014 desktop with TArch9 profile, installed bundle, native events, real COM attributes and LDATA; copied user drawing only','runtime_sha256':{row['name']:hashlib.sha256((Path(installed['bundle'])/'Contents'/row['name']).read_bytes()).hexdigest() for row in installed['files']}}
    eventfile=out/'events.log'
    startup_ready=[False]
    def events():return eventfile.read_text(encoding='utf-8-sig') if eventfile.exists() else ''
    def wait_for(fn,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if process.poll() is not None:raise RuntimeError('Owned test CAD exited '+str(process.returncode))
            # Only dismiss known startup notices in the owned PID. No interaction with other CAD.
            import panel_host_tools as h
            h.dismiss_notice(process.pid)
            for frame in h.windows(process.pid):
                if args.legend_ui and not startup_ready[0] and h.win32gui.GetClassName(frame).startswith('AfxMDIFrame') and not h.win32gui.IsWindowVisible(frame):
                    h.win32gui.ShowWindow(frame,h.win32con.SW_MAXIMIZE)
                if h.win32gui.GetWindowText(frame)=='缺少 SHX 文件':
                    for control in h.children(frame):
                        if h.win32gui.GetWindowText(control)=='忽略缺少的 SHX 文件并继续':
                            h.win32gui.PostMessage(control,h.win32con.BM_CLICK,0,0)
            if fn():return
            time.sleep(.2)
        raise TimeoutError('Desktop CAD did not complete expected operation')
    def send(command,timeout=30):
        started=time.monotonic()
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__)), '--remote',str(statefile),command],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace')
        while True:
            try:
                output,_=child.communicate(timeout=.3);break
            except subprocess.TimeoutExpired:
                import panel_host_tools as h
                for frame in h.windows(process.pid):
                    if h.win32gui.GetWindowText(frame)=='AutoCAD 消息':
                        controls=h.children(frame);message=' | '.join(h.win32gui.GetWindowText(c) for c in controls if h.win32gui.GetWindowText(c))
                        for control in controls:
                            if h.win32gui.GetClassName(control)=='Button':h.win32gui.PostMessage(control,h.win32con.BM_CLICK,0,0);break
                        try:child.communicate(timeout=5)
                        except subprocess.TimeoutExpired:child.kill();child.communicate()
                        raise RuntimeError('Owned CAD reported a modal error: '+message)
                if time.monotonic()-started>timeout:
                    child.kill();child.communicate();raise TimeoutError('Desktop command did not complete: '+command)
        if child.returncode:raise RuntimeError('Desktop command dispatch failed: '+output)
        report['operations'].append({'command':command,'send_seconds':round(time.monotonic()-started,4)})
    def probe(expr):
        target=out/(uuid.uuid4().hex+'.txt')
        send('(progn (setq pc:probe (open '+quote(target)+' "w")) (prin1 '+expr+' pc:probe) (close pc:probe) (princ))')
        wait_for(lambda:target.exists() and target.stat().st_size>0)
        return target.read_text(encoding='gbk').strip()
    def check(value,name):
        if not value:raise AssertionError(name)
        report['checks'].append(name);print('PASS '+name,flush=True)
    def settle():
        # Ensure queued command/event work runs after the operation has returned.
        start=len(events());send('PC_HANG_SNAPSHOT')
        wait_for(lambda:'END PC_HANG_SNAPSHOT' in events()[start:])
        time.sleep(2)
        start=len(events());send('PC_HANG_SNAPSHOT')
        wait_for(lambda:'END PC_HANG_SNAPSHOT' in events()[start:])
    try:
        wait_for(lambda:'END PLANTCADLOADED' in events(),110)
        startup_ready[0]=True
        if args.legend_ui:
            import panel_host_tools as h
            for frame in h.windows(process.pid):
                if h.win32gui.GetClassName(frame).startswith('AfxMDIFrame'):h.win32gui.ShowWindow(frame,h.win32con.SW_HIDE)
        settle();check(True,'Installed panel and real LISP loaded in copied user DWG')
        check('tch_' in probe('(arx)').lower(),'Tianzheng modules coexist in desktop CAD')
        if args.trace_sync:
            workflow=(ROOT/'developer/src/plantcad-workflow.lsp').read_text(encoding='utf-8')
            traced=workflow[workflow.index('(defun pl:sync-drawing-work '):workflow.index('(defun pl:sync-native ')]
            for name in ['upgrade-area-leaders','import-table-edits','cache-entities','sync-labels','ai-refresh-tables']:
                traced=traced.replace('(pl:'+name+')','(progn (pc:trace-sync "'+name+' begin") (pl:'+name+') (pc:trace-sync "'+name+' end"))')
            traced=traced.replace('(pl:try-fill-area e)','(progn (pc:trace-sync (strcat "fill " (cdr (assoc 5 (entget e))))) (pl:try-fill-area e))')
            imported=workflow[workflow.index('(defun pl:import-table-edits '):workflow.index('(defun pl:sync-drawing ')]
            imported=imported.replace('(setq actual (pl:native-table-read','(pc:trace-sync (strcat "table read " (cdr (assoc 5 (entget table))))) (setq actual (pl:native-table-read')
            imported=imported.replace('(if (and (listp actual)', '(pc:trace-sync (strcat "table actual " (vl-princ-to-string actual))) (pc:trace-sync (strcat "table saved " (vl-princ-to-string saved))) (if (and (listp actual)')
            imported=imported.replace('(setq changed (pl:table-edited-plant','(pc:trace-sync (strcat "edit row " (vl-princ-to-string row))) (setq changed (pl:table-edited-plant')
            imported=imported.replace('(pl:save-project-spec (cadr pair))','(progn (pc:trace-sync (strcat "save project " (vl-princ-to-string pair))) (pl:save-project-spec (cadr pair)))')
            tracefile=out/'trace-sync.lsp'
            logger='(defun pc:trace-sync (message / file) (setq file (open '+quote(out/'sync-phases.log')+' "a")) (write-line message file) (close file))\n'
            tracefile.write_bytes((logger+imported+traced).replace('\n','\r\n').encode('gbk'))
            send('(load '+quote(tracefile)+')')
        if args.schedules:
            report['schedule_heights_before']=probe('(progn (setq pc:schedule-source nil) (foreach e (pl:ss-list (ssget "_X" \'((0 . "ACAD_TABLE")))) (if (equal (pl:data-get e "TABLE_KIND") "count") (setq pc:schedule-source e))) (if pc:schedule-source (pc:table-heights (cdr (assoc 5 (entget pc:schedule-source))))))')
        # Use real existing managed tree and create one managed fill on an existing scanned region.
        seed=r'''(progn (setvar "TILEMODE" 1) (setq pc:tree (car (pl:all-trees)) pc:area (car (pl:all-areas)))
          (pl:bind-area-plant pc:area (pl:put 'fill_scale 0.1 (pl:plant pc:tree)))
          (setq pc:fill (handent (pl:data-get pc:area "FILL_HANDLE")))
          (list (and pc:tree T) (and pc:area T) (and pc:fill T)))'''.replace('\n',' ')
        check(probe(seed)=='(T T T)','Real tree, region, and associative hatch ready')
        settle()
        if args.manual_areas:
            prepare=r'''(progn
              (setq pc:manual-source (pl:make '((0 . "LWPOLYLINE") (100 . "AcDbEntity") (8 . "0") (62 . 6)
                (100 . "AcDbPolyline") (90 . 4) (70 . 1) (10 100000000.0 100000000.0) (10 100020000.0 100000000.0)
                (10 100020000.0 100010000.0) (10 100000000.0 100010000.0))))
              (setq pc:manual-count (length (pl:all-areas)))
              (setq pc:manual-batch (pl:native-area-manual (list (cdr (assoc 5 (entget pc:manual-source)))) "PL_面积_计算边界"))
              (pl:consume-area-batch pc:manual-batch -1)
              (setq pc:manual-area (handent (caadr pc:manual-batch)) pc:manual-no (pl:area-number pc:manual-area)
                pc:manual-label (car (pl:area-output-linked pc:manual-area)))
              (and pc:manual-label (= (length (pl:all-areas)) (1+ pc:manual-count))))'''.replace('\n',' ')
            check(probe(prepare)=='T','Manual closed boundary creates one area and an internal measurement label using real LDATA')
            send('(command "_.ERASE" pc:manual-label "")')
            recover=r'''(progn
              (pl:consume-area-batch (pl:native-area-manual (list (cdr (assoc 5 (entget pc:manual-source)))) "PL_面积_计算边界") -1)
              (and (= (pl:area-number pc:manual-area) pc:manual-no)
                (= (length (pl:area-output-linked pc:manual-area)) 1)
                (= (length (pl:all-areas)) (1+ pc:manual-count))))'''.replace('\n',' ')
            check(probe(recover)=='T','Deleted area text is repaired without duplicate region or changed numbering')
            check(probe('(= (cdr (assoc 62 (entget pc:manual-source))) 6)')=='T','Manual measurement preserves original boundary color')
            inside=r'''(progn (setq pc:manual-position (cdr (assoc 10 (entget (car (pl:area-output-linked pc:manual-area))))))
              (and (> (car pc:manual-position) 100000000.0) (< (car pc:manual-position) 100020000.0)
                (> (cadr pc:manual-position) 100000000.0) (< (cadr pc:manual-position) 100010000.0)))'''.replace('\n',' ')
            check(probe(inside)=='T','Manual area indicator is located strictly inside the closed boundary')
            edges=r'''(progn (setq pc:manual-edges nil pc:edge-index 0)
              (foreach pc:segment '(((100040000.0 100000000.0 9.0) (100060000.0 100000000.0 9.0))
                ((100060000.0 100000000.0 9.0) (100060000.0 100010000.0 9.0))
                ((100060000.0 100010000.0 9.0) (100040000.0 100010000.0 9.0))
                ((100040000.0 100010000.0 9.0) (100040000.0 100000000.0 9.0)))
                (setq pc:edge (pl:make (list '(0 . "LINE")
                  (cons 8 (if (= (rem pc:edge-index 2) 0) "0" "PL_面积_计算边界")) '(62 . 6)
                  (cons 10 (car pc:segment)) (cons 11 (cadr pc:segment))))
                  pc:manual-edges (cons (cdr (assoc 5 (entget pc:edge))) pc:manual-edges)
                  pc:edge-index (1+ pc:edge-index)))
              (setq pc:edge-batch (pl:native-area-manual pc:manual-edges "PL_面积_计算边界"))
              (and (= (pl:consume-area-batch pc:edge-batch -1) 1)
                (equal (vla-get-Area (vlax-ename->vla-object (handent (caadr pc:edge-batch)))) 200000000.0 1.0)))'''.replace('\n',' ')
            edges_result=probe(edges);report['manual_edges_result']=edges_result
            if edges_result!='T':report['manual_edges_error']=probe('pc:edge-batch')
            check(edges_result=='T','Explicit multi-layer edges measure the complete closed area in real desktop CAD')
            repeat=r'''(progn
              (pl:consume-area-batch (pl:native-area-manual pc:manual-edges "PL_面积_计算边界") -1)
              (and (= (length (pl:all-areas)) (+ 2 pc:manual-count))
                (equal (mapcar '(lambda (handle) (list (cdr (assoc 62 (entget (handent handle))))
                  (caddr (cdr (assoc 10 (entget (handent handle))))))) pc:manual-edges)
                  '((6 9.0) (6 9.0) (6 9.0) (6 9.0)))))'''.replace('\n',' ')
            check(probe(repeat)=='T','Multi-layer measurement reuses the area and preserves all source colors and elevations')
            saved_missing=r'''(progn (setq pc:saved-missing 0 pc:saved-areas (pl:all-areas) pc:saved-sequence (pl:db-get "AREA_SEQUENCE" 0))
              (foreach pc:saved-area pc:saved-areas
                (if (not (pl:area-output-linked pc:saved-area))
                  (progn (setq pc:saved-missing (1+ pc:saved-missing))
                    (pl:consume-area-batch (pl:native-area-manual
                      (list (cdr (assoc 5 (entget pc:saved-area)))) "PL_面积_计算边界") -1))))
              (and (= (length (pl:all-areas)) (length pc:saved-areas))
                (= (pl:db-get "AREA_SEQUENCE" 0) pc:saved-sequence)
                (not (vl-some '(lambda (area) (not (pl:area-output-linked area))) pc:saved-areas))))'''.replace('\n',' ')
            check(probe(saved_missing)=='T','Existing unlabeled regions in the saved user drawing are supplemented without new numbers or duplicate areas')
            report['saved_missing_labels_supplemented']=probe('pc:saved-missing')
        if args.annotations:
            # Exercise the production annotation completion, new typed name and legacy table refresh.
            expression=r'''(progn (setq pc:started (getvar "MILLISECS"))
              (pl:run '(lambda () (pl:area-label-name pc:area "手输灌木测试")
                (setq pc:label (pl:output-area-label pc:area '(2.0 2.0 0.0) '(-20000.0 -20000.0 0.0) '((layout . 0))))))
              (setq pc:finish-ms (- (getvar "MILLISECS") pc:started))
              (list (cdr (assoc 0 (entget pc:label))) pc:finish-ms))'''.replace('\n',' ')
            result=probe(expression);report['annotation_finish_result']=result
            check(result.startswith('("MULTILEADER" '),'Annotation completion creates a single native MLeader after typing new shrub name')
            milliseconds=int(result.rsplit(' ',1)[1].rstrip(')'))
            check(milliseconds<3000,'Annotation completion including legacy schedule refresh is under 3 seconds')
            check(probe('(= (cdr (assoc 62 (tblsearch "LAYER" "PL_灌木_填充"))) 8)')=='T','Shrub fill defaults to gray in real desktop CAD')
            check(probe('(= (length (pl:area-output-linked pc:area)) 1)')=='T','Text and arrow have no separate loose entities')
            check(probe('(progn (setq pc:before (pc:leader-points (cdr (assoc 5 (entget pc:label))))))').startswith('(('),'Native leader positions readable')
            send('(command "_.MOVE" pc:label "" "_non" "0,0,0" "_non" "1000,2000,0")')
            check(probe('(equal (car (pc:leader-points (cdr (assoc 5 (entget pc:label))))) (mapcar \'+ (car pc:before) \'(1000.0 2000.0 0.0)) 1e-6)')=='T','Real CAD MOVE moves the text with the annotation')
            send('_.U');settle()
            check(probe('(equal (pc:leader-points (cdr (assoc 5 (entget pc:label)))) pc:before 1e-6)')=='T','UNDO restores text and arrow positions together')
            check(probe('(progn (pl:legacy-output-area-label pc:area \'(2.0 2.0 0.0) \'(-20000.0 -20000.0 0.0) \'((layout . 1))) (= (length (pl:area-output-linked pc:area)) 3))')=='T','Legacy separate text and line fixture ready')
            check(probe('(progn (pl:sync-native) (setq pc:label (car (pl:area-output-linked pc:area))) (and (= (length (pl:area-output-linked pc:area)) 1) (= (cdr (assoc 0 (entget pc:label))) "MULTILEADER")))')=='T','Explicit sync upgrades old loose annotations to native MLeader')
            warm=probe('(progn (setq pc:started (getvar "MILLISECS")) (pl:sync-native) (- (getvar "MILLISECS") pc:started))')
            check(warm.isdigit() and int(warm)<3000,'Warm explicit sync completes within 3 seconds')
            report['annotation_warm_sync_ms']=int(warm)
            # The former hatch can be replaced by the new shrub's pattern during completion.
            check(probe('(and (setq pc:fill (handent (pl:data-get pc:area "FILL_HANDLE"))))')!='nil','Managed gray hatch remains linked after completion')
        for variable in ['pc:tree','pc:fill']:
            for repeat in range(3):
                start=len(events());send('(command "_.ERASE" '+variable+' "")');settle()
                check(probe('(null (entget '+variable+'))')=='T',f'{variable} deletion stays deleted, cycle {repeat+1}')
                if args.label=='fixed':check('START PLANTCADASSOCIATIONSYNC' not in events()[start:],'ERASE queues no full drawing write')
                send('_.U');settle()
                restored=probe('(and (entget '+variable+') T)')
                if restored!='T':report['undo_failure_prompt']=probe('(getvar "LASTPROMPT")')
                check(restored=='T',f'{variable} undo restores same entity, cycle {repeat+1}')
        # Real COM attribute writes and project metadata must still synchronize explicitly.
        edited=r'''(progn (setq pc:p (pl:plant pc:tree) pc:new-height (+ 0.1 (pl:get 'height pc:p)))
          (pl:run '(lambda () (pl:save-project-spec (pl:put 'height pc:new-height pc:p))))
          (equal (pl:get 'height (pl:plant pc:tree)) pc:new-height 1e-8))'''.replace('\n',' ')
        check(probe(edited)=='T','Project specification edit still updates the real tree')
        check(probe('(progn (pl:sync-native) T)')=='T','Explicit association sync completes with real attributes and LDATA')
        settle();send('_.REGEN');settle();check(True,'Desktop remains responsive after regeneration')
        if args.schedules:
            check(probe('(and pc:schedule-source (= (pl:data-get pc:schedule-source "TABLE_FORMAT") 4) (= 1 (pl:native-value (pc:table-display-check (cdr (assoc 5 (entget pc:schedule-source)))))))')=='T','Existing user schedule migrates to named legends, number/legend first and readable data heights')
            report['schedule_heights_after']=probe('(pc:table-heights (cdr (assoc 5 (entget pc:schedule-source))))')
            split=r'''(progn
              (defun getpoint (message) '(100000000.0 100000000.0 0.0))
              (setq pc:schedule-groups (pl:output-tables-split pc:schedule-source "PL_表格_苗木" "count" (pl:data-get pc:schedule-source "TABLE_SCOPE") "category")
                pc:schedule-species (pl:output-tables-split pc:schedule-source "PL_表格_苗木" "count" (pl:data-get pc:schedule-source "TABLE_SCOPE") "species"))
              (and pc:schedule-groups pc:schedule-species (entget pc:schedule-source)
                (not (vl-some '(lambda (e) (/= 1 (pl:native-value (pc:table-display-check (cdr (assoc 5 (entget e)))))))
                  (append pc:schedule-groups pc:schedule-species)))))'''.replace('\n',' ')
            check(probe(split)=='T','Category and species split workflows create readable linked tables and preserve the source schedule')
            records=r'''(progn (setq pc:schedule-rows nil)
              (foreach e pc:schedule-groups (setq pc:schedule-rows (append pc:schedule-rows (pl:data-get e "TABLE_ROWS"))))
              (and (= (length pc:schedule-rows) (length (pl:data-get pc:schedule-source "TABLE_ROWS")))
                (not (vl-some '(lambda (row) (not (member row pc:schedule-rows))) (pl:data-get pc:schedule-source "TABLE_ROWS")))))'''.replace('\n',' ')
            check(probe(records)=='T','Split category schedules retain all original quantities, specifications and selected scope')
            no_dash=r'''(progn
              (setq pc:no-dash-plant (pl:put 'id "DESKTOP_NO_DASH" (pl:put 'spec_no "ZZ_NO_DASH" (pl:put 'dbh 0.0 (pl:put 'caliper 0.0 (pl:put 'crown 1.0 (pl:put 'height 1.0 (pl:plant pc:tree)))))))
                pc:no-dash-tree (pl:demo-insert pc:no-dash-plant '(120000000.0 100000000.0 0.0)) pc:diameter-ok nil)
              (pl:save-def pc:no-dash-plant)
              (foreach pc:attribute (vlax-invoke (vlax-ename->vla-object pc:no-dash-tree) 'GetAttributes)
                (if (= (strcase (vla-get-TagString pc:attribute)) "PL_DIAMETER")
                  (setq pc:diameter-ok (and (= (vla-get-TextString pc:attribute) "") (= (vla-get-Invisible pc:attribute) :vlax-true)))))
              pc:diameter-ok)'''.replace('\n',' ')
            check(probe(no_dash)=='T','Missing diameter attributes are empty and hidden rather than displaying a dash')
            check(probe('(progn (pl:sync-native) (not (vl-some \'(lambda (e) (/= 1 (pl:native-value (pc:table-display-check (cdr (assoc 5 (entget e))))))) (append pc:schedule-groups pc:schedule-species))))')=='T','Split tables remain readable after real project synchronization')
            report['schedule_split_result']='T'
        if args.label_feedback:
            assert args.annotations and args.schedules,'Label feedback requires annotation and schedule fixtures'
            ball=r'''(progn
              (setq pc:ball-plant (pl:put 'id "DESKTOP_CENTER_BALL" (pl:put 'spec_no "BALL_CENTER"
                (pl:put 'name "测试灌木球" (pl:put 'kind 3 (pl:put 'quantity_unit "株"
                (pl:put 'crown 1.0 (pl:put 'height 1.0 (pl:plant pc:tree))))))))
                pc:ball (pl:demo-insert pc:ball-plant '(120000000.0 100000000.0 0.0))
                pc:ball-center-ok nil pc:ball-lower-ok T)
              (pl:save-def pc:ball-plant)
              (foreach pc:a (vlax-invoke (vlax-ename->vla-object pc:ball) 'GetAttributes)
                (cond ((= (vla-get-TagString pc:a) "PL_NAME")
                  (setq pc:ball-center-ok (and (= (vla-get-TextString pc:a) "测试灌木球")
                    (= (vla-get-Invisible pc:a) :vlax-false)
                    (equal (vlax-safearray->list (vlax-variant-value (vla-get-TextAlignmentPoint pc:a)))
                      '(120000000.0 100000000.0 0.0) 1e-6))))
                ((member (vla-get-TagString pc:a) '("PL_SPEC" "PL_DIAMETER"))
                  (setq pc:ball-lower-ok (and pc:ball-lower-ok (= (vla-get-Invisible pc:a) :vlax-true))))))
              (and pc:ball-center-ok pc:ball-lower-ok))'''.replace('\n',' ')
            check(probe(ball)=='T','Real shrub ball name is centered in its circle with no visible lower specification or diameter')
            tree=r'''(progn
              (setq pc:tree-plant (pl:put 'id "DESKTOP_TREE_NO_NUMBER" (pl:put 'spec_no "TREE_KEEP_NUMBER"
                (pl:put 'name "测试乔木" (pl:put 'kind 0 (pl:put 'dbh 12.0
                (pl:put 'caliper 0.0 (pl:put 'quantity_unit "株" (pl:plant pc:tree))))))))
                pc:tree-number (pl:demo-insert pc:tree-plant '(122000000.0 100000000.0 0.0))
                pc:hidden-number nil pc:visible-diameter nil)
              (pl:save-def pc:tree-plant)
              (pl:db-put "PLOT_OPTIONS" (pl:put 'show_number 1 (pl:db-get "PLOT_OPTIONS" nil)))
              (pl:refresh-symbol pc:tree-number)
              (foreach pc:a (vlax-invoke (vlax-ename->vla-object pc:tree-number) 'GetAttributes)
                (cond ((= (vla-get-TagString pc:a) "PL_SPEC")
                  (setq pc:hidden-number (and (= (vla-get-Invisible pc:a) :vlax-true)
                    (= (vla-get-TextString pc:a) "TREE_KEEP_NUMBER"))))
                ((= (vla-get-TagString pc:a) "PL_DIAMETER")
                  (setq pc:visible-diameter (and (= (vla-get-Invisible pc:a) :vlax-false)
                    (not (null (vl-string-search "12" (vla-get-TextString pc:a)))))))))
              (and pc:hidden-number pc:visible-diameter))'''.replace('\n',' ')
            check(probe(tree)=='T','Tree number stays hidden even when show_number is enabled, while actual diameter and stored number remain')
            resize=r'''(progn
              (setq pc:feedback-points (pc:leader-points (cdr (assoc 5 (entget pc:label)))))
              (pl:db-put "PLOT_OPTIONS" '((scale . 200.0) (paper_height . 3.5) (show_number . 1)))
              (pl:sync-native)
              (setq pc:feedback-style (pc:leader-style (cdr (assoc 5 (entget pc:label)))))
              (setq pc:feedback-height (* 0.7 (pl:data-get pc:area "UNITS")))
              (and (equal (car pc:feedback-style) pc:feedback-height 1e-6)
                (equal (cadr pc:feedback-style) (* 0.3 pc:feedback-height) 1e-6)
                (equal (caddr pc:feedback-style) (* 2.0 pc:feedback-height) 1e-6)
                (equal (pc:leader-points (cdr (assoc 5 (entget pc:label)))) pc:feedback-points 1e-6)))'''.replace('\n',' ')
            check(probe(resize)=='T','Existing shrub annotation, arrow and landing follow new plot settings without relocating text or anchor')
            edited_name=r'''(progn
              (setq pc:feedback-value (pl:area-value pc:area) pl:*drawing-changed* nil)
              (pc:edit-area-name (cdr (assoc 5 (entget pc:label))) "{\\fSimHei;桌面直改灌木} 9999.99 平方米")
              (setq pl:*count-scope* "Model") (pl:count-work)
              (and (= (pl:get 'name (pl:data-get pc:area "AREA_PLANT")) "桌面直改灌木")
                (equal (pl:area-value pc:area) pc:feedback-value 1e-8)))'''.replace('\n',' ')
            check(probe(edited_name)=='T','Actual CAD text-name edit is recognized before counting and does not replace geometric area with typed numbers')
            corrected=r'''(progn (pl:sync-native)
              (setq pc:feedback-text (pl:native-value (pl:native-leader-text (cdr (assoc 5 (entget pc:label))))))
              (and (vl-string-search "桌面直改灌木" pc:feedback-text)
                (vl-string-search (pl:area-text pc:feedback-value) pc:feedback-text)
                (not (vl-string-search "9999.99" pc:feedback-text))))'''.replace('\n',' ')
            check(probe(corrected)=='T','Synchronization retains the edited name and restores the geometric area with two decimal places')
            total=r'''(progn
              (setq pc:tables-before (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE")))))
              (defun getpoint (message) '(160000000.0 100000000.0 0.0))
              (setvar "DIMZIN" 8) (setq pl:*count-scope* "Selected") (pl:table-work)
              (setq pc:total nil)
              (foreach pc:t (pl:ss-list (ssget "_X" '((0 . "ACAD_TABLE"))))
                (if (not (member pc:t pc:tables-before)) (setq pc:total pc:t)))
              (and pc:total (= (pl:get 'scope (pl:data-get pc:total "TABLE_SCOPE")) "model")
                (= (pl:data-get pc:total "TABLE_TITLE") "苗木数量总表")
                (= (length (pl:data-get pc:total "TABLE_ROWS")) (length (pl:count-rows (pl:statistics-model))))))'''.replace('\n',' ')
            check(probe(total)=='T','Main menu creates a full-model all-type total despite stale selected scope')
            order=r'''(progn
              (setq pc:total-records (pl:output-table-records "count" (pl:data-get pc:total "TABLE_SCOPE")))
              (setq pc:rank -1 pc:ordered T pc:seen nil pc:area-format T)
              (foreach pc:record pc:total-records
                (setq pc:current-rank (pl:plant-rank (car pc:record)) pc:seen (cons pc:current-rank pc:seen))
                (if (< pc:current-rank pc:rank) (setq pc:ordered nil))
                (setq pc:rank pc:current-rank)
                (if (= (pl:get 'quantity_unit (car pc:record)) "平方米")
                  (progn (setq pc:q (nth 7 (pl:output-table-cells pc:record)) pc:dot (vl-string-search "." pc:q))
                    (if (or (not pc:dot) (/= (- (strlen pc:q) pc:dot 1) 2)) (setq pc:area-format nil)))))
              (and pc:ordered pc:area-format (member 0 pc:seen) (member 1 pc:seen) (member 2 pc:seen)
                (= 1 (pl:native-value (pc:table-display-check (cdr (assoc 5 (entget pc:total)))))) T))'''.replace('\n',' ')
            check(probe(order)=='T','Total contains trees, balls and groundcover in that order with two-decimal areas and readable numbered legends')
            report['label_feedback_result']='T'
        if args.legend_ui:
            assert args.label_feedback,'Legend UI requires the all-type total fixture'
            check(probe('(= 1 (pl:native-value (pc:table-named-legends-check (cdr (assoc 5 (entget pc:total))))))')=='T','Every total-table legend contains its own plant name together with the scaled drawing symbol')
            seed_ui=r'''(progn (foreach pc:kind '(0 1 2 3 4 5)
              (pl:save-def (pl:put 'id (strcat "UI_TYPE_" (itoa pc:kind))
                (pl:put 'spec_no (strcat "UI" (itoa pc:kind))
                (pl:put 'kind pc:kind (pl:put 'name (strcat "界面对齐" (itoa pc:kind)) (pl:plant pc:tree))))))) T)'''.replace('\n',' ')
            check(probe(seed_ui)=='T','All six plant categories available in project list fixture')
            import panel_host_tools as h,ctypes
            mainframe=next(w for w in h.windows(process.pid) if h.win32gui.GetClassName(w).startswith('AfxMDIFrame'))
            h.win32gui.ShowWindow(mainframe,h.win32con.SW_MAXIMIZE)
            try:h.win32gui.SetForegroundWindow(mainframe)
            except Exception:pass
            send('PC_PROJECT_OBSERVE')
            dialog_child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__)),'--remote',str(statefile),'(pl:library-work)'],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            result=out/'project-probe.txt'
            wait_for(lambda:result.exists() and result.stat().st_size>0,30)
            report['project_dialog_result']=result.read_text(encoding='utf-8-sig')
            check(report['project_dialog_result'].startswith('PASS '),'Actual resizable project window keeps eight columns, grows its list and filters all six categories')
            dialog_child.communicate(timeout=15)
            check(dialog_child.returncode==0,'Project dialog closes normally after resizing and choosing a specification')
            check(probe('(equal (pl:get \'id (pl:current)) "UI_TYPE_5")')=='T','Filtered project choice returns the correct specification to the real LISP workflow')
            image=ROOT/'docs/images/项目参数对齐实机.png';shutil.copy2(out/'project-dialog.png',image)
            report['project_ui_image']=str(image)
            send('(command "_.ZOOM" "_Object" pc:total "")')
            send('_.REGEN');time.sleep(.5)
            preview=out/'total-preview.png'
            send('(progn (setvar "SELECTIONPREVIEW" 0) (setvar "HIGHLIGHT" 0) (vl-catch-all-apply \'setvar \'("TABLEINDICATOR" 0)) (sssetfirst nil nil) (command "_.PNGOUT" '+quote(preview)+' pc:total ""))')
            wait_for(lambda:preview.exists() and preview.stat().st_size>1000)
            image=ROOT/'docs/images/苗木数量总表图例实机.png';shutil.copy2(preview,image)
            report['legend_ui_image']=str(image);report['legend_ui_result']='T'
        report['passed']=True
    except Exception as error:
        report['error']=repr(error)
        try:
            import panel_host_tools as h
            report['owned_window_titles']=[h.win32gui.GetWindowText(w) for w in h.windows(process.pid)]
        except Exception:pass
        print('FAIL '+repr(error),flush=True)
    finally:
        report['original_unchanged']=hashlib.sha256(args.drawing.read_bytes()).hexdigest()==original
        report['assertions']=len(report['checks'])
        try:
            if process.poll() is None:
                subprocess.run([sys.executable,'-X','utf8','-B',str(Path(__file__)),'--remote',str(statefile),'--close'],timeout=15,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
                process.wait(timeout=15)
        except Exception as error:
            report['cleanup_error']=repr(error)
            # This Popen handle belongs exclusively to this copied-DWG test session.
            if process.poll() is None:process.terminate();process.wait(timeout=15)
            report['owned_test_process_terminated']=True
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if args.label=='fixed' and report['passed']:
            (ROOT/'developer/desktop-erase-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.annotations:(ROOT/'developer/desktop-annotation-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.manual_areas:(ROOT/'developer/desktop-manual-area-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.schedules:(ROOT/'developer/desktop-schedule-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.label_feedback:(ROOT/'developer/desktop-label-feedback-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.legend_ui:(ROOT/'developer/desktop-legend-ui-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if args.legend_ui:
                preview_report=dict(passed=True,original_unchanged=report['original_unchanged'],assertions=3,output=str(out),runtime_sha256=report['runtime_sha256'],scope='Installed AutoCAD 2014/TArch9 on copied DWG: native PNGOUT total table and owned WinForms DrawToBitmap project dialog, no other application capture',table_image=report['legend_ui_image'],project_image=report['project_ui_image'])
                (ROOT/'developer/output-preview-verification.json').write_text(json.dumps(preview_report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('REPORT '+str(out/'verification.json'),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':
    if '--remote' in sys.argv:
        state=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        remote(state,None if sys.argv[3]=='--close' else sys.argv[3])
    else:main()
