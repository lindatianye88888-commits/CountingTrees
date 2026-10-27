using System;
using System.Collections.Generic;
using System.Reflection;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(WorkflowProbe))]
public class WorkflowProbe {
 [CommandMethod("PC_AREA_SESSION")]
 public void Session(){
  var doc=Application.DocumentManager.MdiActiveDocument;
  using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
   var layers=(LayerTable)tr.GetObject(doc.Database.LayerTableId,OpenMode.ForWrite);
   foreach(string name in new[]{"PL_灌木_计算边界","PL_面积_计算边界","PL_标注_区域","PL_面积_推定补线"})if(!layers.Has(name)){
    var layer=new LayerTableRecord{Name=name,Color=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByAci,2)};
    layers.Add(layer);tr.AddNewlyCreatedDBObject(layer,true);
   }
   tr.Commit();
  }
  var p=new Polyline();p.AddVertexAt(0,new Point2d(0,0),0,0,0);p.AddVertexAt(1,new Point2d(6000,0),0,0,0);p.AddVertexAt(2,new Point2d(6000,2000),0,0,0);p.AddVertexAt(3,new Point2d(0,2000),0,0,0);p.Closed=true;
  var line=new Line(new Point3d(3000,0,0),new Point3d(3000,2000,0));
  var type=typeof(PlantCADBridge.Bridge);Type geometry=type.Assembly.GetType("PlantCADBridge.PlantAreaGeometry");
  object area=Activator.CreateInstance(geometry,new object[]{new List<Curve>{p,line},1e-7});p.Dispose();line.Dispose();
  type.GetField("areaGeometry",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,area);
  type.GetField("areaDocument",BindingFlags.Static|BindingFlags.NonPublic).SetValue(null,doc);
 }
 [CommandMethod("PC_AREA_BROKEN_SESSION")]
 public void BrokenSession(){
  try {PrepareBrokenSession();}catch(System.Exception ex){System.IO.File.WriteAllText(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(Application.DocumentManager.MdiActiveDocument.Name),"broken-error.txt"),ex.ToString());}
 }
 void PrepareBrokenSession(){
  Session();var type=typeof(PlantCADBridge.Bridge);Type geometry=type.Assembly.GetType("PlantCADBridge.PlantAreaGeometry");
  var field=type.GetField("areaGeometry",BindingFlags.Static|BindingFlags.NonPublic);((IDisposable)field.GetValue(null)).Dispose();
  var box=new Polyline();box.AddVertexAt(0,new Point2d(0,0),0,0,0);box.AddVertexAt(1,new Point2d(10,0),0,0,0);box.AddVertexAt(2,new Point2d(10,10),0,0,0);box.AddVertexAt(3,new Point2d(0,10),0,0,0);
  var spline=new Spline(new Point3dCollection(new[]{new Point3d(0,5,0),new Point3d(3,6,0),new Point3d(6,4,0),new Point3d(9.9,5,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0);
  object area=Activator.CreateInstance(geometry,new object[]{new List<Curve>{box,spline},1e-7});
  box.Dispose();spline.Dispose();field.SetValue(null,area);
  ((HashSet<int>)type.GetField("chosenFaces",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null)).Clear();
 }
 [LispFunction("pc:reset-broken-session")]
 public ResultBuffer ResetBroken(ResultBuffer args){BrokenSession();return null;}
 [LispFunction("pc:area-labels-inside")]
 public ResultBuffer LabelsInside(ResultBuffer args){
  var type=typeof(PlantCADBridge.Bridge);object geometry=type.GetField("areaGeometry",BindingFlags.Static|BindingFlags.NonPublic).GetValue(null);
  int count=0;var doc=Application.DocumentManager.MdiActiveDocument;
  using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
   var space=(BlockTableRecord)tr.GetObject(doc.Database.CurrentSpaceId,OpenMode.ForRead);
   foreach(ObjectId id in space){var text=tr.GetObject(id,OpenMode.ForRead) as MText;if(text==null)continue;
    using(ResultBuffer data=text.GetXDataForApplication("PLANTCAD01")){
     if(data==null)continue;bool areaLabel=false;foreach(TypedValue v in data)if(v.TypeCode==1000&&Convert.ToString(v.Value)=="AREA_LABEL")areaLabel=true;
     if(!areaLabel)continue;count++;int face=(int)geometry.GetType().GetMethod("Find").Invoke(geometry,new object[]{text.Location});if(face<0||text.TextHeight<=0)return null;
    }
   }
  }
  return new ResultBuffer(new TypedValue((int)LispDataType.Int32,count));
 }
 [LispFunction("pc:undo-flags")]
 public ResultBuffer Flags(ResultBuffer args){
  foreach(string method in new[]{"OpenWorkbench","DispatchWorkbench","RefreshWorkbench","WorkbenchLoaded"}){
   var info=typeof(PlantCADBridge.Bridge).GetMethod(method);
   var a=(CommandMethodAttribute)Attribute.GetCustomAttribute(info,typeof(CommandMethodAttribute));
   if((a.Flags&CommandFlags.NoUndoMarker)==0)return null;
  }
  return new ResultBuffer(new TypedValue((int)LispDataType.Int32,1));
 }
}
