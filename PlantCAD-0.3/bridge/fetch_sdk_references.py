"""Cache Autodesk-owned NuGet reference assemblies for compilation only.

No third-party SDK binaries are copied into the runtime or distribution package.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,io,json,urllib.request,zipfile
from cad_targets import TARGETS
ROOT=Path(__file__).resolve().parent
CACHE=ROOT.parent/'developer/bin/sdk-cache'
BASE='https://api.nuget.org/v3-flatcontainer'

def fetch(package,version):
    package=package.lower();folder=CACHE/version;folder.mkdir(parents=True,exist_ok=True)
    archive=folder/(package+'.'+version+'.nupkg')
    url=f'{BASE}/{package}/{version}/{package}.{version}.nupkg'
    if not archive.exists():
        request=urllib.request.Request(url,headers={'User-Agent':'CountingTrees-reference-build/0.3'})
        with urllib.request.urlopen(request,timeout=45) as response:data=response.read(32*1024*1024+1)
        if len(data)>32*1024*1024:raise RuntimeError('SDK package unexpectedly large')
        with zipfile.ZipFile(io.BytesIO(data)) as z:assert z.testzip() is None
        archive.write_bytes(data)
    dlls=[]
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if not info.filename.startswith(('lib/','ref/')) or not info.filename.lower().endswith('.dll'):continue
            # Only a basename is used; archive paths cannot escape the cache.
            name=Path(info.filename).name.lower();target=folder/name
            payload=z.read(info)
            if target.exists() and target.read_bytes()!=payload:raise RuntimeError('Conflicting SDK assembly: '+name)
            target.write_bytes(payload);dlls.append(name)
    return dict(package=package,version=version,url=url,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),references=dlls)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--version',action='append');args=ap.parse_args()
    versions=args.version or [t['sdk'] for t in TARGETS if t['sdk']]
    tasks=[(package,v) for v in versions for package in ('AutoCAD.NET','AutoCAD.NET.Core','AutoCAD.NET.Model')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(lambda task:fetch(*task),tasks))
    for version in versions:
        folder=CACHE/version
        for name in ('acmgd.dll','accoremgd.dll','acdbmgd.dll'):
            if not (folder/name).is_file():raise RuntimeError('Missing SDK assembly: '+str(folder/name))
        (folder/'references.json').write_text(json.dumps([r for r in records if r['version']==version],indent=2),encoding='utf-8')
        print('Cached Autodesk SDK reference assemblies:',version,flush=True)
if __name__=='__main__':main()
