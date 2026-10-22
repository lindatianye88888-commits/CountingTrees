"""Full, bounded native UI acceptance on an owned AutoCAD 2014/TArch9 test drawing."""
from pathlib import Path
import hashlib,json,time,uuid,winreg,sys
import pythoncom,pywintypes,win32com.client,win32api,win32gui,win32con,win32process
import panel_host_tools as h
from msvcrt import get_osfhandle

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from mcp_server import QueueBridge
output=ROOT/'bridge/host-output'/('panel-acceptance-'+uuid.uuid4().hex[:8])
output.mkdir(parents=True)
report={'passed':False,'user_project_opened_or_saved':False,'checks':[],
        'startup':'COM-created AutoCAD 2014 with installed TArch9 profile; admin TGStart64 launcher not exercised'}
app=doc=None
original='<<未命名配置>>'
session=None

def check(name):
    report['checks'].append(name)
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS '+name,flush=True)

def labels(parent):
    return [win32gui.GetWindowText(c) for c in h.children(parent) if win32gui.GetClassName(c)=='Static']

def ui_button(text):
    for w in h.windows(session['pid']):
        try:return h.button(w,text)
        except StopIteration:pass
    raise LookupError(text)

def wait_dialog(title):
    return h.wait_for(lambda:h.dialog(title),session['pid'],30)

def wait_idle():
    h.wait_for(lambda:doc.GetVariable('CMDACTIVE')==0 and app.GetAcadState().IsQuiescent,session['pid'],35)

try:
    if '--owned' in sys.argv:
        session,app=h.owned()
        output=Path(session['output'])
        report['startup']=session.get('startup','Owned native test session')
        pid=session['pid'];doc=app.ActiveDocument;path=Path(session['drawing'])
        assert doc.FullName==str(path), 'Unexpected active drawing'
    else:
        try:win32com.client.GetActiveObject('AutoCAD.Application.19.1')
        except pywintypes.com_error:pass
        else:raise RuntimeError('An existing CAD session is open; refusing to touch it.')
        print('Starting isolated COM-owned CAD; no user project will be opened.',flush=True)
        app=win32com.client.DispatchEx('AutoCAD.Application.19.1')
        app.Visible=True
        pid=win32process.GetWindowThreadProcessId(app.HWND)[1]
        if app.Preferences.Profiles.ActiveProfile!='TArch9': app.Preferences.Profiles.ActiveProfile='TArch9'
        h.wait_for(lambda:app.GetAcadState().IsQuiescent,pid,80)
        doc=app.Documents.Item(0) if app.Documents.Count else app.Documents.Add(r'D:\Program Files (x86)\天正\sys19x64\ACAD.DWT')
        assert not doc.FullName and doc.ModelSpace.Count==0,'Expected a new empty owned document'
        layer=doc.Layers.Add('BASE_EXISTING');layer.Color=4;doc.ActiveLayer=layer
        doc.ModelSpace.AddLine(h.point(1000,1000,0),h.point(16000,1000,0))
        doc.ModelSpace.AddLine(h.point(16000,1000,0),h.point(16000,12000,0))
        doc.ModelSpace.AddCircle(h.point(4000,4500,0),700)
        doc.ModelSpace.AddText('PANEL ACCEPTANCE BASE',h.point(6000,11000,0),300)
        layer.Lock=True
        doc.SetVariable('INSUNITS',4)
        path=output/'panel-base.dwg';doc.SaveAs(str(path))
    installed=json.loads((ROOT/'install-state.json').read_text(encoding='utf-8'))
    installed_dll=Path(installed['bundle'])/'Contents/bridge/PlantCADBridge.dll'
    assert hashlib.sha256(installed_dll.read_bytes()).digest()==hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).digest(), 'Installed DLL differs from current final build'
    base_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    before={k:doc.GetVariable(k) for k in ['CLAYER','INSUNITS','LTSCALE','TEXTSTYLE','OSMODE','SECURELOAD','TRUSTEDPATHS']}
    support=app.Preferences.Files.SupportPath
    session={'pid':pid,'drawing':str(path),'output':str(output),'original_profile':original,'checks':[]}
    h.STATE.write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding='utf-8')
    # Keep the verified COM references alive throughout all modal DCL windows.
    h.owned=lambda:(session,app)
    doc.SendCommand('PLANTCAD\n')
    h.wait_for(lambda:any('PlantCAD 植物工作台'==win32gui.GetWindowText(w) for w in h.windows(pid)),pid,35)
    wait_idle()
    h.wait_for(lambda:any('已加载' in win32gui.GetWindowText(c)
        for w in h.windows(pid) if win32gui.GetWindowText(w)=='PlantCAD 植物工作台'
        for c in h.children(w)),pid,35)
    state=h.probe('(pl:ui-state)')
    assert '0.3-float-1' in state,state
    modules=h.probe('(arx)')
    assert 'tch_' in modules.lower(),modules
    report['loaded_modules']=modules
    report['cad_version']=app.Version
    check('Installed bundle loads native strip and paired LISP in existing nonempty DWG')
    check('Tianzheng ARX modules coexist with native strip')

    app.ZoomExtents()
    h.click(ui_button('选植物'))
    catalogue=wait_dialog('可编辑植物品种表')
    h.set_text(h.edit_for_label(catalogue,'名称搜索'),'银杏')
    h.click(h.button(catalogue,'筛选'))
    lst=next(c for c in h.children(catalogue) if win32gui.GetClassName(c)=='ListBox')
    h.wait_for(lambda:win32gui.SendMessage(lst,win32con.LB_GETCOUNT,0,0)==1,pid)
    h.list_select(lst,0);time.sleep(.15)
    h.click(h.button(catalogue,'为选中品种建立规格'))
    spec=wait_dialog('植物规格与图例')
    text=labels(spec)
    assert any('当前树种：银杏' in t for t in text),text
    assert any('冠幅 / 米' in t and '必填' in t for t in text),text
    h.capture(str(ROOT/'docs/images/植物规格与图例.png'),spec)
    check('Panel button searches real catalogue and opens species-labelled spec dialog with symbol preview')

    h.click(h.button(spec,'保存规格'))
    project=wait_dialog('项目植物与规格')
    h.click(h.button(project,'设为当前规格'))
    wait_idle()
    draft=h.probe('(pl:ui-state)')
    assert '银杏' in draft and '("crown_m" 0.0)' in draft,draft
    check('Unknown crown remains a visible draft rather than an invented default')
    h.click(ui_button('补冠幅布置'))
    spec=wait_dialog('植物规格与图例')
    assert any('请先补填' in t for t in labels(spec)),labels(spec)
    h.click(h.button(spec,'保存规格'));time.sleep(.2)
    assert h.dialog('植物规格与图例')==spec
    h.set_text(h.edit_for_label(spec,'冠幅 / 米'),'3')
    h.set_text(h.edit_for_label(spec,'胸径 / cm'),'12')
    h.set_text(h.edit_for_label(spec,'高度 / m'),'4')
    h.click(h.button(spec,'保存规格'))
    settings=wait_dialog('绘图单位与出图文字')
    h.click(h.button(settings,'确定'))
    h.wait_for(lambda:'植物中心' in str(doc.GetVariable('LASTPROMPT')),pid,35)
    check('Place button opens exact current spec for missing crown and rejects empty placement')

    # A real click in the owned CAD drawing viewport, with the preview active.
    graphic=None;position=None
    for x,y in [(450,350),(500,400),(350,300),(600,350)]:
        candidate=win32gui.WindowFromPoint((x,y))
        if win32process.GetWindowThreadProcessId(candidate)[1]==pid and win32gui.GetClassName(candidate).startswith('Afx'):
            graphic=candidate;position=(x,y);break
    assert graphic is not None,'Owned drawing viewport not found'
    old_cursor=win32gui.GetCursorPos()
    win32api.SetCursorPos(position);time.sleep(.3)
    local=win32gui.ScreenToClient(graphic,position);param=(local[1]<<16)|(local[0]&0xffff)
    win32gui.PostMessage(graphic,win32con.WM_MOUSEMOVE,0,param)
    win32gui.PostMessage(graphic,win32con.WM_LBUTTONDOWN,win32con.MK_LBUTTON,param)
    win32gui.PostMessage(graphic,win32con.WM_LBUTTONUP,0,param)
    time.sleep(.4)
    doc.SendCommand('\n')
    wait_idle()
    win32api.SetCursorPos(old_cursor)
    plants=h.probe('(length (pl:all-trees))')
    assert plants=='1',plants
    check('Native mouse-following preview accepts a real viewport click and creates one tree')

    reference=next(e for e in doc.ModelSpace if e.ObjectName=='AcDbBlockReference' and e.Name=='PL02_CIRCLE')
    assert abs(reference.XScaleFactor-3000.)<.001
    attributes={a.TagString:a.TextString for a in reference.GetAttributes()}
    assert attributes['PL_NAME']=='银杏' and attributes['PL_DIAMETER']=='12',attributes
    assert doc.ModelSpace.Count==5
    assert {k:doc.GetVariable(k) for k in before}==before
    assert app.Preferences.Files.SupportPath==support
    assert doc.Layers.Item('BASE_EXISTING').Lock
    report['native_tree']={'handle':reference.Handle,'block':reference.Name,'scale':reference.XScaleFactor,'attributes':attributes}
    check('Real circle is 3000mm wide, named Ginkgo with chest diameter 12; locked current base layer preserved')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==base_hash
    check('Drawing is not auto-saved')

    doc.SendCommand('PLANTCADCONNECT\n')
    queue=QueueBridge(ROOT/'bridge/runtime',timeout=25)
    h.wait_for(lambda:queue.status().get('connected') and queue.status().get('process_id')==pid,pid,35)
    native=queue.call('get_plants',{'target':{'scope':'model'},'limit':10})
    assert native['ok'] and native['count']==1 and native['plants'][0]['name']=='银杏',native
    report['mcp_read']=native
    check('Installed bundle shares configured MCP queue and reads the newly placed tree')

    # Verify document switching is never disabled by panel refresh and each drawing gets commands.
    wait_idle()
    original_doc=doc
    other=app.Documents.Add(r'D:\Program Files (x86)\天正\sys19x64\ACAD.DWT')
    h.wait_for(lambda:app.GetAcadState().IsQuiescent and other.GetVariable('CMDACTIVE')==0,pid,30)
    doc=other
    # State reader here is not tied to the original file; query a marker through a temporary report.
    marker=output/'second-ready.txt'
    doc.SendCommand('(progn (setq pct:f (open '+h.quote(marker)+' "w")) (prin1 (car (atoms-family 1 (list "C:PLANTCADINSERT"))) pct:f) (close pct:f) (princ))\n')
    h.wait_for(lambda:marker.exists() and marker.stat().st_size>0,pid,30)
    assert 'PLANTCADINSERT' in marker.read_text(encoding='gbk')
    check('New document receives placement command automatically')
    original_doc.Activate();doc=original_doc
    wait_idle()
    assert '银杏' in h.probe('(pl:ui-state)')
    other.Close(False)
    check('Switching back restores document-specific species and spec without unknown commands')

    app.ZoomExtents()
    main=next(w for w in h.windows(pid) if win32gui.GetClassName(w).startswith('AfxMDIFrame'))
    h.capture(str(ROOT/'docs/images/天正操作面板.png'),main)
    panel=next(w for w in h.windows(pid) if win32gui.GetWindowText(w)=='PlantCAD 植物工作台')
    h.capture(str(ROOT/'docs/images/操作浮窗实机.png'),panel)
    report['passed']=True
    print('NATIVE PANEL ACCEPTANCE PASSED.',flush=True)
except BaseException as exc:
    report['error']=repr(exc)
    print('Native acceptance stopped: '+repr(exc),flush=True)
    raise
finally:
    report['receiver_sha256']=hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).hexdigest()
    report['runtime_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.suffix in ('.lsp','.dcl','.tsv')}
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['passed'] and app is not None:
        for item in list(app.Documents):
            if item.FullName and not Path(item.FullName).is_relative_to(output):
                raise RuntimeError('Unexpected user drawing; leave CAD open')
        for item in list(app.Documents):item.Close(False)
        app.Quit()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,h.PROFILE,0,winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE) as k:
            if winreg.QueryValueEx(k,'')[0]=='TArch9':winreg.SetValueEx(k,'',0,winreg.REG_SZ,original)
        report['cleanup']='Owned test documents closed without saving; original default profile restored.'
        (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Report: '+str(output/'verification.json'),flush=True)
