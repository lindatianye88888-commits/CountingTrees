using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(CaseDrawingProbe))]
public class CaseDrawingProbe {
 [CommandMethod("PC_CASE_INSPECT")]
 public void Inspect(){
  Database db=Application.DocumentManager.MdiActiveDocument.Database;
  var spaces=new List<object>();var blocks=new List<object>();
  using(Transaction tr=db.TransactionManager.StartTransaction()) {
   var table=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead);
   foreach(ObjectId id in table) {
    var block=(BlockTableRecord)tr.GetObject(id,OpenMode.ForRead);
    if(!block.IsLayout){blocks.Add(new{block.Name,block.IsFromExternalReference,block.PathName});continue;}
    var types=new Dictionary<string,int>();var layers=new Dictionary<string,int>();var texts=new List<object>();
    foreach(ObjectId entityId in block) {
     Entity e=tr.GetObject(entityId,OpenMode.ForRead) as Entity;if(e==null)continue;
     string type=e.GetType().Name;if(!types.ContainsKey(type))types[type]=0;types[type]++;
     if(!layers.ContainsKey(e.Layer))layers[e.Layer]=0;layers[e.Layer]++;
     string text=null;double height=0;Autodesk.AutoCAD.Geometry.Point3d p=Autodesk.AutoCAD.Geometry.Point3d.Origin;
     var single=e as DBText;var multi=e as MText;var leader=e as MLeader;
     if(single!=null){text=single.TextString;height=single.Height;p=single.Position;}
     if(multi!=null){text=multi.Text;height=multi.TextHeight;p=multi.Location;}
     if(leader!=null&&leader.ContentType==ContentType.MTextContent){using(MText mt=leader.MText){text=mt.Text;height=mt.TextHeight;p=mt.Location;}}
     if(text!=null)texts.Add(new{text,height,x=p.X,y=p.Y,layer=e.Layer,type});
    }
    spaces.Add(new{block.Name,types,layers,texts});
   }
  }
  string path=Application.DocumentManager.MdiActiveDocument.Name;
  var result=new{name=Path.GetFileName(path),units=db.Insunits.ToString(),spaces,blocks};
  File.WriteAllText(Path.ChangeExtension(path,".json"),new JavaScriptSerializer{MaxJsonLength=32000000}.Serialize(result));
  db.DxfOut(Path.ChangeExtension(path,".dxf"),16,DwgVersion.AC1027);
 }
}
