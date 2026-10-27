using System;
using System.IO;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(ManualAreaProbe))]
public class ManualAreaProbe {
 static Database DB {get{return Application.DocumentManager.MdiActiveDocument.Database;}}
 static int count;static void Check(bool ok,string why){if(!ok)throw new InvalidOperationException(why);count++;}
 static ObjectId Id(string handle){return DB.GetObjectId(false,new Handle(Int64.Parse(handle,System.Globalization.NumberStyles.HexNumber)),0);}
 static Polyline Box(double x,double y,double w,double h){var p=new Polyline();p.AddVertexAt(0,new Point2d(x,y),0,0,0);p.AddVertexAt(1,new Point2d(x+w,y),0,0,0);p.AddVertexAt(2,new Point2d(x+w,y+h),0,0,0);p.AddVertexAt(3,new Point2d(x,y+h),0,0,0);p.Closed=true;return p;}
 static string Add(Entity entity,string layer="0"){using(Transaction tr=DB.TransactionManager.StartTransaction()){
  var space=(BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForWrite);int color=entity.ColorIndex;if(color<0||color>256)color=256;entity.SetDatabaseDefaults(DB);space.AppendEntity(entity);tr.AddNewlyCreatedDBObject(entity,true);entity.LayerId=((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))[layer];entity.ColorIndex=color;string handle=entity.Handle.ToString();tr.Commit();return handle;
 }}
 static TypedValue[] Batch(params string[] handles){var v=new List<TypedValue>{new TypedValue(5016)};foreach(string h in handles)v.Add(new TypedValue(5005,h));v.Add(new TypedValue(5017));v.Add(new TypedValue(5005,"PL_面积_计算边界"));using(var input=new ResultBuffer(v.ToArray()))using(var output=new Bridge().ManualArea(input))return output.AsArray();}
 static List<string> Handles(TypedValue[] values){if(Convert.ToString(values[0].Value)!="AREA_BATCH")throw new InvalidOperationException(Convert.ToString(values[0].Value));var result=new List<string>();bool first=false;foreach(TypedValue v in values){if(v.TypeCode==5016)first=true;else if(first&&v.TypeCode==5005){result.Add(Convert.ToString(v.Value));first=false;}}return result;}
 static void Mark(string handle){using(Transaction tr=DB.TransactionManager.StartTransaction()){
  var apps=(RegAppTable)tr.GetObject(DB.RegAppTableId,OpenMode.ForRead);if(!apps.Has("PLANTCAD01")){apps.UpgradeOpen();var app=new RegAppTableRecord{Name="PLANTCAD01"};apps.Add(app);tr.AddNewlyCreatedDBObject(app,true);}
  using(var data=new ResultBuffer(new TypedValue(1001,"PLANTCAD01"),new TypedValue(1000,"AREA")))((Entity)tr.GetObject(Id(handle),OpenMode.ForWrite)).XData=data;tr.Commit();
 }}
 static void Area(string handle,double value){using(Transaction tr=DB.TransactionManager.StartTransaction())Check(Math.Abs(((Region)tr.GetObject(Id(handle),OpenMode.ForRead)).Area-value)<1e-6,"Manual area differs from original geometry");}
 [CommandMethod("PC_MANUAL_AREA_TEST")]
 public void Test(){string dir=Path.GetDirectoryName(Application.DocumentManager.MdiActiveDocument.Name);
  try {
   using(Transaction tr=DB.TransactionManager.StartTransaction()){
    var layers=(LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForWrite);foreach(string n in new[]{"PL_面积_计算边界","MANUAL_A","MANUAL_B"})if(!layers.Has(n)){var layer=new LayerTableRecord{Name=n};layers.Add(layer);tr.AddNewlyCreatedDBObject(layer,true);}tr.Commit();
   }
   var box=Box(100,100,20,10);box.Elevation=7;string source=Add(box),area=Handles(Batch(source))[0];Check(area!=source,"Original boundary was reused as editable region");Area(area,200);Mark(area);
   Check(Handles(Batch(source))[0]==area,"Repeated manual measure duplicated a region");Check(Handles(Batch(area))[0]==area,"Picking an existing area did not reuse its handle");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){var original=(Polyline)tr.GetObject(Id(source),OpenMode.ForRead);Check(original.Elevation==7&&original.Closed,"Manual measurement changed source geometry");Check(((Region)tr.GetObject(Id(area),OpenMode.ForRead)).GeometricExtents.MinPoint.Z==0,"Plan area was not flattened on a detached copy");}
   foreach(bool ellipse in new[]{false,true}){
    string h=ellipse?Add(new Ellipse(new Point3d(200,200,3),Vector3d.ZAxis,new Vector3d(5,0,0),.6,0,Math.PI*2)):Add(new Circle(new Point3d(300,300,4),Vector3d.ZAxis,5));
    var found=Handles(Batch(h));Check(found.Count==1,"Closed curve not measured");Area(found[0],ellipse?Math.PI*15:Math.PI*25);Mark(found[0]);
   }
   var edges=new List<string>();var pts=new[]{new Point3d(400,400,9),new Point3d(420,400,9),new Point3d(420,410,9),new Point3d(400,410,9)};
   for(int i=0;i<4;i++){var line=new Line(pts[i],pts[(i+1)%4]);line.ColorIndex=(short)(i+1);edges.Add(Add(line,i%2==0?"MANUAL_A":"MANUAL_B"));}
   var mixed=Handles(Batch(edges.ToArray()));Check(mixed.Count==1,"Explicit multi-layer edges were filtered out");Area(mixed[0],200);Mark(mixed[0]);
   using(Transaction tr=DB.TransactionManager.StartTransaction()){for(int i=0;i<4;i++){var line=(Line)tr.GetObject(Id(edges[i]),OpenMode.ForRead);Check(line.StartPoint.Z==9&&line.ColorIndex==i+1,"Manual edge source was modified");}}
   TypedValue[] open=Batch(edges[0],edges[1],edges[2]);Check(Convert.ToString(open[0].Value).StartsWith("ERROR:"),"Open boundary was silently inferred");
   using(var outer=Box(500,500,20,10))using(var inner=Box(508,503,4,4)){
    var objects=new DBObjectCollection();objects.Add(outer);var region=(Region)Region.CreateFromCurves(objects)[0];objects.Clear();objects.Add(inner);
    using(var hole=(Region)Region.CreateFromCurves(objects)[0])region.BooleanOperation(BooleanOperationType.BoolSubtract,hole);
    string h=Add(region);var found=Handles(Batch(h));Check(found.Count==1,"Hole became a separate measured region");Area(found[0],184);Mark(found[0]);
   }
   using(Transaction tr=DB.TransactionManager.StartTransaction()){var layer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))["PL_面积_计算边界"],OpenMode.ForWrite);layer.IsLocked=true;tr.Commit();}
   Check(Convert.ToString(Batch(source)[0].Value).StartsWith("ERROR:"),"Locked destination accepted manual write");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){var layer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))["PL_面积_计算边界"],OpenMode.ForWrite);layer.IsLocked=false;tr.Commit();}
   File.WriteAllText(Path.Combine(dir,"manual-native.txt"),"PASS "+count);
  }catch(System.Exception ex){File.WriteAllText(Path.Combine(dir,"manual-native.txt"),"checks="+count+" "+ex.ToString());}
 }
 [LispFunction("pc:manual-boundary")]
 public ResultBuffer Boundary(ResultBuffer args){string handle=Add(Box(700,700,20,10));return new ResultBuffer(new TypedValue(5005,handle));}
}


