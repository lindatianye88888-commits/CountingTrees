"""Exercise real .NET/LISP return marshalling and the production native insertion method on a DWG copy."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'developer/tests'))
from lisp_harness import parse

HEADER='''using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
[assembly:CommandClass(typeof(PlacementInterop.Probe))]
namespace PlacementInterop {
 public sealed class Probe {
  [LispFunction("pc:interop-point")]
  public ResultBuffer Point(ResultBuffer args) {
   return new ResultBuffer(new TypedValue((int)LispDataType.Point3d,new Point3d(218118.0,231230.0,0.0)));
  }
  [CommandMethod("PC_INTEROP_SEED")]
  public void Seed() {
   Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
   using(Transaction tr=db.TransactionManager.StartTransaction()) {
    var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForWrite);
    var baseLayer=new LayerTableRecord {Name="PC_BASE"};
    layers.Add(baseLayer);tr.AddNewlyCreatedDBObject(baseLayer,true);
    var plants=new LayerTableRecord {Name="PL_树木_圆圈"};
    layers.Add(plants);tr.AddNewlyCreatedDBObject(plants,true);
    db.Clayer=baseLayer.ObjectId;baseLayer.IsLocked=true;
    var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForWrite);
    var definition=new BlockTableRecord {Name="PC_INTEROP_TREE"};
    blocks.Add(definition);tr.AddNewlyCreatedDBObject(definition,true);
    var circle=new Circle(Point3d.Origin,Vector3d.ZAxis,0.5);circle.Layer="0";
    definition.AppendEntity(circle);tr.AddNewlyCreatedDBObject(circle,true);
    foreach(string tag in new[]{"PL_NAME","PL_DIAMETER"}) {
     var attribute=new AttributeDefinition {Tag=tag,TextString="",Height=.1,Position=Point3d.Origin};
     attribute.Layer="0";definition.AppendEntity(attribute);tr.AddNewlyCreatedDBObject(attribute,true);
    }
    tr.Commit();
   }
  }
'''
BODY='''(defun pl:register-command (short full) nil)
(defun pc:check (/ raw point previous rawhandle handle entity ed first)
 (setq raw (pc:interop-point)
       previous (vl-catch-all-apply 'trans (list raw 1 0))
       point (pl:point-value raw)
       rawhandle (pl:native-insert "PC_INTEROP_TREE" (trans point 1 0) 3000.0 "PL_树木_圆圈")
       handle (pl:native-value rawhandle)
       entity (handent handle) ed (entget entity) first (entnext entity))
 (list
  (and (= (type raw) 'LIST) (= (length raw) 1) (listp (car raw)))
  (vl-catch-all-error-p previous)
  (equal point '(218118.0 231230.0 0.0) 1.0e-6)
  (and (= (type rawhandle) 'LIST) (= (type handle) 'STR))
  (= (cdr (assoc 0 ed)) "INSERT")
  (= (cdr (assoc 2 ed)) "PC_INTEROP_TREE")
  (equal (cdr (assoc 10 ed)) point 1.0e-6)
  (= (cdr (assoc 41 ed)) 3000.0)
  (= (cdr (assoc 8 ed)) "PL_树木_圆圈")
  (and (= (getvar "CLAYER") "PC_BASE") (/= 0 (logand 4 (cdr (assoc 70 (tblsearch "LAYER" "PC_BASE"))))))
  (and (= (cdr (assoc 0 (entget first))) "ATTRIB") (= (cdr (assoc 2 (entget first))) "PL_NAME") (= (cdr (assoc 2 (entget (entnext first)))) "PL_DIAMETER"))
  (null (pl:point-value nil))
  (equal (pl:point-value '(12.0 34.0)) '(12.0 34.0 0.0))
 ))
(setq pc:result (vl-catch-all-apply 'pc:check nil))
(setq pc:file (open RESULT_PATH "w"))
(prin1 (if (vl-catch-all-error-p pc:result) (vl-catch-all-error-message pc:result) pc:result) pc:file)
(close pc:file)
(princ)
'''
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--drawing',type=Path,required=True)
    ap.add_argument('--cad-dir',type=Path,default=Path(os.environ.get('PLANTCAD_CAD_DIR',r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')))
    args=ap.parse_args()
    output=ROOT/'bridge/host-output'/('placement-interop-'+uuid.uuid4().hex[:8]);output.mkdir(parents=True)
    original=hashlib.sha256(args.drawing.read_bytes()).hexdigest()
    shutil.copy2(args.drawing,output/'input.dwg')
    source=(ROOT/'bridge/src/PlantCADPanel.cs').read_text(encoding='utf-8')
    start=source.index('  [LispFunction("pl:native-insert")]')
    opening=source.index('{',start);depth=1;end=opening+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    method=source[start:end]
    fixture=output/'InteropFixture.cs';fixture.write_text(HEADER+method+'\n }\n}\n',encoding='utf-8')
    dll=output/'InteropFixture.dll'
    csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(csc),'/nologo','/utf8output','/target:library','/platform:x64','/out:'+str(dll)]+
                   ['/reference:'+str(args.cad_dir/name) for name in ['acmgd.dll','acdbmgd.dll','accoremgd.dll']]+[str(fixture)],check=True)
    def quote(p):return '"'+str(p).replace('\\','/')+'"'
    core=output/'plantcad-core.lsp';ui=output/'plantcad-ui.lsp'
    for name,target in [('plantcad-core.lsp',core),('plantcad-ui.lsp',ui)]:
        target.write_bytes((ROOT/'developer/src'/name).read_text(encoding='utf-8').replace('\n','\r\n').encode('gbk'))
    result_path=output/'result.txt';check=output/'check.lsp'
    check.write_bytes(BODY.replace('RESULT_PATH',quote(result_path)).replace('\n','\r\n').encode('gbk'))
    bootstrap=output/'bootstrap.lsp'
    bootstrap.write_bytes(('(defun pl:register-command (short full) nil)\r\n(load '+quote(core)+')\r\n(load '+quote(ui)+')\r\n(load '+quote(check)+')\r\n(princ)\r\n').encode('gbk'))
    script=output/'check.scr'
    script.write_bytes(('\r\n'.join(['_.NETLOAD',quote(dll),'PC_INTEROP_SEED','(load '+quote(bootstrap)+')','_.QUIT','_No'])+'\r\n').encode('gbk'))
    si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    report={'passed':False,'scope':'AutoCAD 2014 Core Console .NET/LISP interop with the exact production InsertNativeSymbol method; deterministic preview point fixture, no mouse or Tianzheng GUI acceptance',
      'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['developer/src/plantcad-ui.lsp','developer/src/plantcad-core.lsp','bridge/src/PlantCADPanel.cs']},
      'production_insert_method_sha256':hashlib.sha256(method.encode('utf-8')).hexdigest()}
    try:
        run=subprocess.run([str(args.cad_dir/'accoreconsole.exe'),'/i',str(output/'input.dwg'),'/s',str(script)],
            cwd=output,startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (output/'console-output.bin').write_bytes(run.stdout)
        value=parse(result_path.read_text(encoding='gbk'))[0] if result_path.exists() else 'missing result'
        print('Native interop result:',value,flush=True)
        if run.returncode!=0 or value!=[True]*13:raise AssertionError((run.returncode,value))
        assert hashlib.sha256(args.drawing.read_bytes()).hexdigest()==original
        report.update(passed=True,assertions=13,original_drawing_unchanged=True,
            checks=['Screenshot point returned as a real one-point ResultBuffer list',
             'Original unnormalised point reproduces trans argument error',
             'Normalised point retains exact site coordinates',
             'Native handle unwraps into a string',
             'Production insertion creates an actual block reference on plant layer',
             'Block position/scale and two attribute instances are created',
             'Locked current base layer remains locked and current',
             'Cancel remains nil; two-dimensional points are promoted to 3D'])
        print('Native marshalling and actual production insertion passed.',flush=True)
    finally:
        (ROOT/'developer/placement-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
