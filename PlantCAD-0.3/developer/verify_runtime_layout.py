"""Exercise the actual flat/versioned package and shared MCP queue resolver in AutoCAD 2014."""
from pathlib import Path
import hashlib,json,shutil,subprocess,uuid
ROOT=Path(__file__).resolve().parents[1];CAD=Path(r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')

def main():
    out=ROOT/'bridge/host-output'/('runtime-layout-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    source=ROOT/'bridge/host-output/area-native-224da63d/input.dwg'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    helper=out/'RuntimeLayoutProbe.dll'
    subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/utf8output','/target:library','/reference:System.Web.Extensions.dll','/out:'+str(helper),'/reference:'+str(ROOT/'bridge/PlantCADBridge.dll')]+['/reference:'+str(CAD/n) for n in ['acmgd.dll','accoremgd.dll','acdbmgd.dll']]+[str(ROOT/'developer/tests/RuntimeLayoutProbe.cs')],check=True)
    records=[]
    quote=lambda p:'"'+str(p).replace('\\','/')+'"'
    for nested in [False,True]:
        folder=out/('nested' if nested else 'flat');package=folder/'Contents';module=package/'bridge'
        if nested:module=module/'test-api-group'
        module.mkdir(parents=True);shutil.copy2(ROOT/'bridge/PlantCADBridge.dll',module/'PlantCADBridge.dll')
        for name in ['plantcad.lsp','plantcad-core.lsp','plantcad-design.lsp','plantcad-ai.lsp','plantcad-ui.lsp','plantcad-workflow.lsp','plantcad.dcl','plantcatalog.tsv']:
            shutil.copy2(ROOT/name,package/name)
        queue=folder/'shared-queue';queue.mkdir()
        (package/'bridge/queue-root.json').write_text(json.dumps({'queue_root':str(queue)}),encoding='utf-8')
        shutil.copy2(source,folder/'input.dwg')
        lines=['_.NETLOAD',quote(module/'PlantCADBridge.dll'),'_.NETLOAD',quote(helper),'CT_LAYOUT_TEST',
            '(setq ct:f (open '+quote(folder/'aliases.txt')+' "w")) (prin1 (list (getcname "COUNTINGTREES") (getcname "数树") (getcname "PLANTCAD")) ct:f) (close ct:f)',
            '_.QUIT','_No']
        (folder/'run.scr').write_bytes(('\r\n'.join(lines)+'\r\n').encode('gbk'))
        proc=subprocess.run([str(CAD/'accoreconsole.exe'),'/i',str(folder/'input.dwg'),'/s',str(folder/'run.scr')],cwd=folder,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (folder/'console.bin').write_bytes(proc.stdout)
        result=json.loads((folder/'layout-result.json').read_text(encoding='utf-8-sig'))
        aliases=(folder/'aliases.txt').read_text(encoding='gbk')
        assert proc.returncode==0 and Path(result['package'])==package and Path(result['queue'])==queue and result['paired']
        assert Path(result['receiver'])==module/'PlantCADBridge.dll'
        assert 'COUNTINGTREES' in aliases and '数树' in aliases and 'PLANTCAD' in aliases and 'nil' not in aliases
        records.append({'nested':nested,'package_and_queue_resolved':True,'aliases':aliases})
        print('Native package layout passed:','nested' if nested else 'flat',flush=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    report={'passed':True,'assertions':12,'cases':records,'original_unchanged':True,'output':str(out),
        'scope':'AutoCAD 2014 Core Console: production DLL loaded flat and in a version-group subfolder, resolves paired LISP/catalogue root and shared queue config; three launch aliases registered. Does not run higher API DLLs on a mismatched host or assert Tianzheng/GUI acceptance.',
        'receiver_sha256':hashlib.sha256((ROOT/'bridge/PlantCADBridge.dll').read_bytes()).hexdigest()}
    (ROOT/'developer/runtime-layout-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
