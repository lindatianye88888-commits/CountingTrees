"""Install only PlantCAD's per-user AutoCAD bundle, without changing CAD security or profiles."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,shutil,sys,xml.etree.ElementTree as ET
from ctypes import wintypes
from bridge.cad_targets import TARGETS,COMPATIBILITY_URL

ROOT=Path(__file__).resolve().parent
FILES=['plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp',
       'plantcad-workflow.lsp','plantcad.dcl','plantcatalog.tsv','bridge/PlantCADBridge.dll']
FILES.extend(t['module'] for t in TARGETS if t['key']!='2014')

def bundle_xml():
    package=ET.Element('ApplicationPackage',{'SchemaVersion':'1.0','AppVersion':'0.3.24','Name':'CountingTrees',
        'Description':'CountingTrees（数树）植物工作台 · AutoCAD 2014—2024 64位',
        'ProductCode':'{D75A82EC-CE0F-4E2D-AFC4-28FCD8D02618}','UpgradeCode':'{C2916E13-F217-47DD-981D-52C14ED13391}'})
    ET.SubElement(package,'CompanyDetails',Name='CountingTrees')
    for target in TARGETS:
        component=ET.SubElement(package,'Components')
        ET.SubElement(component,'RuntimeRequirements',OS='Win64',Platform='AutoCAD*',SeriesMin=target['series_min'],SeriesMax=target['series_max'])
        entry=ET.SubElement(component,'ComponentEntry',{'AppName':'CountingTrees','AppType':'.Net',
            'ModuleName':'./Contents/'+target['module'],'LoadOnStartup':'True','LoadOnAutoCADStartup':'True',
            'LoadOnCommandInvocation':'True','LoadOnAppearance':'False','LoadOnProxy':'False'})
        commands=ET.SubElement(entry,'Commands',GroupName='PLANTCAD')
        for name in ['COUNTINGTREES','数树','PLANTCAD','PLANTCADPLACE']:
            ET.SubElement(commands,'Command',{'Global':name,'Local':name})
    return '<?xml version="1.0" encoding="utf-8"?>\n'+ET.tostring(package,encoding='unicode')+'\n'

class PROCESSENTRY32(ctypes.Structure):
    _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('pid',wintypes.DWORD),
              ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
              ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
              ('name',wintypes.WCHAR*260)]

def cad_running():
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    api.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32)]
    api.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32)]
    api.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=api.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry=PROCESSENTRY32();entry.dwSize=ctypes.sizeof(entry)
        ok=api.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            if entry.name.lower()=='acad.exe':return True
            ok=api.Process32NextW(snapshot,ctypes.byref(entry))
        return False
    finally:api.CloseHandle(snapshot)

def assert_unloaded(path):
    if not path.exists():return
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    api.CreateFileW.restype=wintypes.HANDLE;api.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=api.CreateFileW(str(path),0x80000000|0x40000000,0,None,3,0,None)
    if handle==ctypes.c_void_p(-1).value:raise RuntimeError('CountingTrees（数树）正在使用中。请关闭CAD后更新：'+str(path))
    api.CloseHandle(handle)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--update-unloaded',action='store_true',help='Update only if all existing runtime files are unused.')
    args=parser.parse_args()
    for name in FILES:
        if not (ROOT/name).is_file():raise RuntimeError('Missing paired runtime file: '+name)
    bundle=Path(os.environ['APPDATA'])/'Autodesk/ApplicationPlugins/PlantCAD.bundle'
    contents=bundle/'Contents';manifest=bundle/'PackageContents.xml'
    if bundle.is_symlink():raise RuntimeError('Refusing redirected bundle folder')
    if bundle.exists():
        if not manifest.is_file() or ET.parse(manifest).getroot().get('Name') not in ('PlantCAD','CountingTrees'):
            raise RuntimeError('Existing folder does not belong to CountingTrees（数树）')
    if args.check:
        print(json.dumps({'source':str(ROOT),'bundle':str(bundle),'files':FILES,'targets':TARGETS,'compatibility_source':COMPATIBILITY_URL},ensure_ascii=False,indent=2));return
    if cad_running():
        if not args.update_unloaded:raise RuntimeError('Please close Tianzheng/AutoCAD before installing or updating.')
        for name in FILES:assert_unloaded(contents/name)
    (contents/'bridge').mkdir(parents=True,exist_ok=True)
    queue=ROOT/'bridge/runtime';queue.mkdir(parents=True,exist_ok=True)
    for name in FILES:
        target=contents/name
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(target.name+'.installing')
        shutil.copy2(ROOT/name,temporary)
        os.replace(temporary,target)
    (contents/'bridge/queue-root.json').write_text(json.dumps({'queue_root':str(queue)},ensure_ascii=False,indent=2),encoding='utf-8')
    manifest.write_text(bundle_xml(),encoding='utf-8')
    state={'bundle':str(bundle),'source':str(ROOT),'queue':str(queue),'version':'0.3.24','targets':TARGETS,
           'files':[{'name':name,'sha256':hashlib.sha256((contents/name).read_bytes()).hexdigest()} for name in FILES]}
    (ROOT/'install-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CountingTrees（数树）0.3.24已安装。按AutoCAD 2014—2024版本分组加载；高版本待对应实机验收。输入 COUNTINGTREES 或 数树打开。')
    print(bundle)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Installation stopped: '+str(error),file=sys.stderr);sys.exit(1)
