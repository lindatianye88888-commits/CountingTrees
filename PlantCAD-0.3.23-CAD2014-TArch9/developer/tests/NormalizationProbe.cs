using System;
using System.Collections.Generic;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(NormalizationProbe))]
public sealed class NormalizationProbe {
 static int count;
 static readonly PlantCADBridge.Bridge bridge=new PlantCADBridge.Bridge();
 static Database Db {get{return Application.DocumentManager.MdiActiveDocument.Database;}}
 static Point3d G(Point3d p){return new Point3d(p.X,p.Y,0);}
 static void Check(bool value,string message){if(!value)throw new InvalidOperationException(message);count++;}
 static ResultBuffer Args(List<ObjectId> ids,string layer){var v=new List<TypedValue>{new TypedValue((int)LispDataType.ListBegin)};foreach(var id in ids)v.Add(new TypedValue((int)LispDataType.Text,id.Handle.ToString()));v.Add(new TypedValue((int)LispDataType.ListEnd));v.Add(new TypedValue((int)LispDataType.Text,layer));return new ResultBuffer(v.ToArray());}
 static void Layer(string name,bool locked){using(var tr=Db.TransactionManager.StartTransaction()){var layers=(LayerTable)tr.GetObject(Db.LayerTableId,OpenMode.ForWrite);if(!layers.Has(name)){var l=new LayerTableRecord{Name=name};layers.Add(l);tr.AddNewlyCreatedDBObject(l,true);}var layer=(LayerTableRecord)tr.GetObject(layers[name],OpenMode.ForWrite);layer.IsLocked=locked;layer.Color=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByAci,2);tr.Commit();}}
 static List<ObjectId> Add(List<Curve> curves,string layer){Layer(layer,false);var ids=new List<ObjectId>();using(var tr=Db.TransactionManager.StartTransaction()){var space=(BlockTableRecord)tr.GetObject(Db.CurrentSpaceId,OpenMode.ForWrite);var apps=(RegAppTable)tr.GetObject(Db.RegAppTableId,OpenMode.ForWrite);if(!apps.Has("PC_NORMALIZE")){var app=new RegAppTableRecord{Name="PC_NORMALIZE"};apps.Add(app);tr.AddNewlyCreatedDBObject(app,true);}foreach(var c in curves){c.SetDatabaseDefaults(Db);c.Layer=layer;c.ColorIndex=1;ids.Add(space.AppendEntity(c));tr.AddNewlyCreatedDBObject(c,true);using(var data=new ResultBuffer(new TypedValue(1001,"PC_NORMALIZE"),new TypedValue(1000,"keep-tag")))c.XData=data;c.CreateExtensionDictionary();var dict=(DBDictionary)tr.GetObject(c.ExtensionDictionary,OpenMode.ForWrite);var record=new Xrecord();dict.SetAt("PC_KEEP",record);tr.AddNewlyCreatedDBObject(record,true);record.Data=new ResultBuffer(new TypedValue(1,"keep-record"));}tr.Commit();}return ids;}
 static void Case(List<Curve> curves,int faces,string label){
  string layer="PC_N_"+label;var samples=new List<List<Point3d>>();foreach(var c in curves){var points=new List<Point3d>();for(int i=0;i<=8;i++)points.Add(G(c.GetPointAtParameter(c.StartParam+(c.EndParam-c.StartParam)*i/8)));samples.Add(points);}
  List<ObjectId> ids=Add(curves,layer);
  var untouched=Add(new List<Curve>{new Line(new Point3d(300,0,99),new Point3d(310,0,99))},layer)[0];
  using(var args=Args(ids,layer))using(var result=bridge.BeginAreaSession(args)){var v=result.AsArray();Check(v.Length==1&&v[0].Value is int&&(int)v[0].Value==faces,label+" faces: "+v[0].Value);}
  using(var tr=Db.TransactionManager.StartTransaction()){
   for(int i=0;i<ids.Count;i++){
    var c=(Curve)tr.GetObject(ids[i],OpenMode.ForRead);var box=c.GeometricExtents;
    Check(Math.Abs(box.MinPoint.Z)<1e-6&&Math.Abs(box.MaxPoint.Z)<1e-6,label+" zero elevation");
    Check(c.ColorIndex==256&&c.Layer==layer,label+" uniform ByLayer color/layer retained");
    foreach(var p in samples[i])Check(c.GetClosestPointTo(p,false).DistanceTo(p)<1e-5,label+" plan XY shape retained");
    using(var data=c.GetXDataForApplication("PC_NORMALIZE"))Check(data!=null&&Convert.ToString(data.AsArray()[1].Value)=="keep-tag",label+" source XData retained");
    var dict=(DBDictionary)tr.GetObject(c.ExtensionDictionary,OpenMode.ForRead);var record=(Xrecord)tr.GetObject(dict.GetAt("PC_KEEP"),OpenMode.ForRead);Check(Convert.ToString(record.Data.AsArray()[0].Value)=="keep-record",label+" extension data retained");
   }
   var old=(Line)tr.GetObject(untouched,OpenMode.ForRead);Check(old.StartPoint.Z==99&&old.ColorIndex==1,"unselected same-layer line untouched");
  }
  bridge.CloseAreaSession(null);
 }
 [CommandMethod("PC_NORMALIZE_TEST")]
 public void Run(){
  string path=Environment.GetEnvironmentVariable("PC_NORMALIZE_RESULT");
  try{
   Case(new List<Curve>{new Line(new Point3d(0,0,1),new Point3d(10,0,2)),new Line(new Point3d(10,0,3),new Point3d(10,10,4)),new Line(new Point3d(10,10,-5),new Point3d(0,10,6)),new Line(new Point3d(0,10,7),new Point3d(0,0,-8))},1,"LINE");
   var poly=new Polyline();poly.AddVertexAt(0,new Point2d(0,0),0,0,0);poly.AddVertexAt(1,new Point2d(10,0),0,0,0);poly.AddVertexAt(2,new Point2d(10,10),0,0,0);poly.AddVertexAt(3,new Point2d(0,10),0,0,0);poly.Closed=true;poly.Elevation=13;Case(new List<Curve>{poly},1,"PLINE");
   var oldPoly=new Polyline2d(Poly2dType.SimplePoly,new Point3dCollection(new[]{new Point3d(0,0,7),new Point3d(10,0,7),new Point3d(10,10,7),new Point3d(0,10,7)}),0,true,0,0,null);Case(new List<Curve>{oldPoly},1,"POLY2D");
   var spatial=new Polyline3d(Poly3dType.SimplePoly,new Point3dCollection(new[]{new Point3d(0,0,1),new Point3d(10,0,2),new Point3d(10,10,3),new Point3d(0,10,4)}),true);Case(new List<Curve>{spatial},1,"POLY3D");
   var spline=new Spline(new Point3dCollection(new[]{new Point3d(0,0,1),new Point3d(3,3,2),new Point3d(7,3,-5),new Point3d(10,0,6)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0);Case(new List<Curve>{spline,new Line(new Point3d(10,0,90),new Point3d(0,0,80))},1,"SPLINE");
   Case(new List<Curve>{new Arc(new Point3d(0,0,7),5,0,Math.PI),new Line(new Point3d(-5,0,9),new Point3d(5,0,10))},1,"ARC");
   Case(new List<Curve>{new Circle(new Point3d(0,0,-11),Vector3d.ZAxis,4)},1,"CIRCLE");
   Case(new List<Curve>{new Ellipse(new Point3d(0,0,8),Vector3d.ZAxis,new Vector3d(8,0,0),.5,0,2*Math.PI)},1,"ELLIPSE");
   // A failed batch rolls back already modified objects; locked layers are never unlocked.
   var rollback=Add(new List<Curve>{new Line(new Point3d(0,0,8),new Point3d(10,0,9)),new Arc(new Point3d(0,0,10),new Vector3d(0,1,1),4,0,Math.PI)},"PC_ROLLBACK");
   using(var args=Args(rollback,"PC_ROLLBACK"))using(var result=bridge.BeginAreaSession(args))Check(Convert.ToString(result.AsArray()[0].Value).StartsWith("ERROR:"),"tilted type-changing arc reports failure");
   using(var tr=Db.TransactionManager.StartTransaction()){var line=(Line)tr.GetObject(rollback[0],OpenMode.ForRead);Check(line.StartPoint.Z==8&&line.EndPoint.Z==9&&line.ColorIndex==1,"failed normalization batch rollback");}
   Layer("PC_ROLLBACK",true);using(var args=Args(rollback,"PC_ROLLBACK"))using(var result=bridge.BeginAreaSession(args))Check(Convert.ToString(result.AsArray()[0].Value).Contains("锁定"),"locked layer stops with real reason");
   using(var tr=Db.TransactionManager.StartTransaction()){var line=(Line)tr.GetObject(rollback[0],OpenMode.ForRead);var layer=(LayerTableRecord)tr.GetObject(line.LayerId,OpenMode.ForRead);Check(layer.IsLocked&&line.StartPoint.Z==8,"locked source state retained");}
   File.WriteAllText(path,"PASS "+count);
  }catch(System.Exception ex){File.WriteAllText(path,"FAIL "+count+" "+ex);}
 }
}
