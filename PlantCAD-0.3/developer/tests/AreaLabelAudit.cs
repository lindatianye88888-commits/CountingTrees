using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(AreaLabelAudit))]
public class AreaLabelAudit {
 [CommandMethod("PC_AREA_LABEL_AUDIT")]
 public void Run(){
  var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;
  var objects=new List<Dictionary<string,object>>();
  using(Transaction tr=db.TransactionManager.StartTransaction()) {
   var model=(BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db),OpenMode.ForRead);
   foreach(ObjectId id in model) {
    var e=tr.GetObject(id,OpenMode.ForRead) as Entity;if(e==null)continue;
    string role=null,source=null;
    using(ResultBuffer data=e.GetXDataForApplication("PLANTCAD01"))if(data!=null)foreach(TypedValue v in data){if(v.TypeCode==1000&&role==null)role=Convert.ToString(v.Value);if(v.TypeCode==1005)source=Convert.ToString(v.Value);}
    if(role!="AREA"&&role!="AREA_LABEL")continue;
    var layer=(LayerTableRecord)tr.GetObject(e.LayerId,OpenMode.ForRead);
    var row=new Dictionary<string,object>{{"handle",e.Handle.ToString()},{"role",role},{"source",source},{"type",e.GetType().Name},{"layer",e.Layer},{"visible",e.Visible},{"layer_off",layer.IsOff},{"layer_frozen",layer.IsFrozen},{"layer_locked",layer.IsLocked}};
    var region=e as Region;var poly=e as Polyline;var text=e as MText;var leader=e as MLeader;
    if(region!=null)row["area_drawing_units"]=region.Area;
    if(poly!=null&&poly.Closed)row["area_drawing_units"]=poly.Area;
    if(text!=null){row["text"]=text.Contents;row["height"]=text.TextHeight;row["position"]=new[]{text.Location.X,text.Location.Y,text.Location.Z};}
    if(leader!=null){using(MText mt=leader.MText){row["text"]=mt.Contents;row["height"]=mt.TextHeight;row["position"]=new[]{leader.TextLocation.X,leader.TextLocation.Y,leader.TextLocation.Z};}}
    try{var box=e.GeometricExtents;row["min"]=new[]{box.MinPoint.X,box.MinPoint.Y,box.MinPoint.Z};row["max"]=new[]{box.MaxPoint.X,box.MaxPoint.Y,box.MaxPoint.Z};}catch{}
    objects.Add(row);
   }
  }
  var report=new{drawing=doc.Name,units=db.Insunits.ToString(),objects};
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(doc.Name),"area-label-audit.json"),new JavaScriptSerializer{MaxJsonLength=8000000}.Serialize(report));
 }
}
