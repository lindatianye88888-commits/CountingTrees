using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(FillCaseProbe))]
public class FillCaseProbe {
 static int checks;
 static bool inspectPatternLines;
 static int controlPatternLines=-1;
 // The case probe uses a pattern scale of 100 drawing units. Its rendering
 // error budget is 0.02 units, independently of the exact measurement region.
 const double RenderingTolerance=.02;
 static Database DB {get{return Application.DocumentManager.MdiActiveDocument.Database;}}
 static void Check(bool value,string message){if(!value)throw new InvalidOperationException(message);checks++;}
 static ObjectId Id(string handle){return DB.GetObjectId(false,new Handle(Int64.Parse(handle,System.Globalization.NumberStyles.HexNumber)),0);}
 static bool Linked(Entity entity,string role,string source){
  bool hasRole=false,hasSource=source==null;
  using(var data=entity.GetXDataForApplication("PLANTCAD01"))if(data!=null)foreach(TypedValue value in data){
   if(value.TypeCode==1000&&Convert.ToString(value.Value)==role)hasRole=true;
   if(value.TypeCode==1005&&Convert.ToString(value.Value)==source)hasSource=true;
  }
  return hasRole&&hasSource;
 }
 static List<ObjectId> Areas(){
  var result=new List<ObjectId>();using(var tr=DB.TransactionManager.StartTransaction())foreach(ObjectId id in (BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForRead)){
   var region=tr.GetObject(id,OpenMode.ForRead) as Region;if(region!=null&&Linked(region,"AREA",null))result.Add(id);
  }return result;
 }
 static string Fill(ObjectId area,string pattern){
  using(var args=new ResultBuffer(new TypedValue(5005,area.Handle.ToString()),new TypedValue(5005,pattern),new TypedValue(5001,100.0),new TypedValue(5001,0.0),new TypedValue(5005,"PL_灌木_填充")))
  using(var result=new Bridge().WriteAreaFill(args))return Convert.ToString(result.AsArray()[0].Value);
 }
 static void LineInspectionControl(){
  ObjectId area;
  using(var tr=DB.TransactionManager.StartTransaction())using(var poly=new Polyline()){
   poly.AddVertexAt(0,new Point2d(0,0),0,0,0);poly.AddVertexAt(1,new Point2d(10000,0),0,0,0);
   poly.AddVertexAt(2,new Point2d(10000,10000),0,0,0);poly.AddVertexAt(3,new Point2d(0,10000),0,0,0);poly.Closed=true;
   var input=new DBObjectCollection();input.Add(poly);var region=(Region)Region.CreateFromCurves(input)[0];
   var space=(BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForWrite);area=space.AppendEntity(region);tr.AddNewlyCreatedDBObject(region,true);tr.Commit();
  }
  string filled=Fill(area,"ANSI31");Check(!filled.StartsWith("ERROR:"),"Simple origin control fill failed: "+filled);
  using(var tr=DB.TransactionManager.StartTransaction()){
   var hatch=(Hatch)tr.GetObject(Id(filled),OpenMode.ForWrite);hatch.EvaluateHatch(true);
   var lines=hatch.GetHatchLinesData();try{controlPatternLines=lines.Count;inspectPatternLines=lines.Count>0;}finally{foreach(Line2d line in lines)line.Dispose();}
   foreach(ObjectId edge in hatch.GetAssociatedObjectIds())tr.GetObject(edge,OpenMode.ForWrite).Erase();
   hatch.Erase();tr.GetObject(area,OpenMode.ForWrite).Erase();tr.Commit();
  }
 }
 static double ClosedArea(Curve source){
  using(var curve=(Curve)source.Clone()){
   var p=curve.GeometricExtents.MinPoint;curve.TransformBy(Matrix3d.Displacement(new Vector3d(-p.X,-p.Y,-p.Z)));
   var poly=curve as Polyline;if(poly!=null)return poly.Area;
   var input=new DBObjectCollection();input.Add(curve);var regions=Region.CreateFromCurves(input);double result=0;
   try{foreach(Region region in regions)result+=region.Area;}finally{foreach(DBObject obj in regions)obj.Dispose();}return result;
  }
 }
 static List<Point2d> Outline(Curve curve,Point3d origin){
  var points=new List<Point2d>();var poly=curve as Polyline;
  if(poly!=null){
   for(int i=0;i<poly.NumberOfVertices;i++){
    int count=Math.Max(1,(int)Math.Ceiling(Math.Abs(4*Math.Atan(poly.GetBulgeAt(i)))*128));
    for(int k=0;k<count;k++){var p=poly.GetPointAtParameter(i+(double)k/count);points.Add(new Point2d(p.X-origin.X,p.Y-origin.Y));}
   }
  }else for(int i=0;i<1024;i++){var p=curve.GetPointAtParameter(curve.StartParam+(curve.EndParam-curve.StartParam)*i/1024.0);points.Add(new Point2d(p.X-origin.X,p.Y-origin.Y));}
  return points;
 }
 static bool Contains(List<Point2d> polygon,Point2d point){
  bool inside=false;Point2d previous=polygon[polygon.Count-1];
  foreach(var p in polygon){if((p.Y>point.Y)!=(previous.Y>point.Y)&&point.X<(previous.X-p.X)*(point.Y-p.Y)/(previous.Y-p.Y)+p.X)inside=!inside;previous=p;}return inside;
 }
 static void Validate(ObjectId area,string handle){
  using(var tr=DB.TransactionManager.StartTransaction()){
   var source=(Region)tr.GetObject(area,OpenMode.ForRead);var hatch=(Hatch)tr.GetObject(Id(handle),OpenMode.ForWrite);
   Check(hatch.Associative,"Lost hatch association: "+area.Handle);
   Check(Linked(hatch,"AREA_FILL",area.Handle.ToString()),"Lost managed source link");
   hatch.EvaluateHatch(true);Check(hatch.NumberOfLoops>0,"Missing hatch loops");
   var ids=hatch.GetAssociatedObjectIds();Check(ids.Count==hatch.NumberOfLoops,"Expected one closed curve per case loop");
   double sum=0,perimeter=0;Extents3d? box=null;
   // DWG stores external-entity linkage separately from the transient
   // Outermost append hint. Classify geometry independently after reopening.
   var outlines=new List<List<Point2d>>();var areas=new List<double>();var frame=source.GeometricExtents.MinPoint;
   for(int i=0;i<ids.Count;i++){
    var curve=(Curve)tr.GetObject(ids[i],OpenMode.ForRead);Check(curve.Closed,"Associated case loop is open");
    Check(Linked(curve,"FILL_EDGE",area.Handle.ToString()),"Lost owned boundary link");
    var bounds=curve.GeometricExtents;if(box.HasValue){var combined=box.Value;combined.AddExtents(bounds);box=combined;}else box=bounds;
    Check((hatch.LoopTypeAt(i)&HatchLoopTypes.NotClosed)==0,"Native hatch reports an open loop after regeneration");
    areas.Add(ClosedArea(curve));outlines.Add(Outline(curve,frame));
    perimeter+=curve.GetDistanceAtParameter(curve.EndParam)-curve.GetDistanceAtParameter(curve.StartParam);
   }
   for(int i=0;i<outlines.Count;i++){int depth=0;for(int j=0;j<outlines.Count;j++)if(i!=j&&areas[j]>areas[i]&&Contains(outlines[j],outlines[i][0]))depth++;sum+=(depth%2==0?1:-1)*areas[i];}
   var expected=source.GeometricExtents;double coordinate=Math.Max(Math.Abs(expected.MinPoint.X),Math.Abs(expected.MinPoint.Y));
   double tolerance=Math.Max(1e-6,Math.Max((expected.MaxPoint-expected.MinPoint).Length*1e-8,coordinate*2.2204460492503131e-16*16));
   double positionTolerance=Math.Max(tolerance*8,RenderingTolerance);
   Check(box.Value.MinPoint.DistanceTo(expected.MinPoint)<=positionTolerance&&box.Value.MaxPoint.DistanceTo(expected.MaxPoint)<=positionTolerance,"Associated edges moved away from original region");
   var flags=new List<string>();for(int i=0;i<hatch.NumberOfLoops;i++)flags.Add(hatch.LoopTypeAt(i).ToString());
   Check(Math.Abs(sum-source.Area)<=Math.Max(source.Area*1e-8,Math.Max(tolerance*perimeter*16,perimeter*RenderingTolerance)),"Filled boundary area differs from source, including holes: actual="+sum.ToString("R")+" source="+source.Area.ToString("R")+" flags="+String.Join(";",flags.ToArray()));
   var visible=hatch.GeometricExtents;
   Check(visible.MinPoint.DistanceTo(expected.MinPoint)<=positionTolerance&&visible.MaxPoint.DistanceTo(expected.MaxPoint)<=positionTolerance,"Hatch was not restored to original world position");
   if(inspectPatternLines&&source.Area>100000){var lines=hatch.GetHatchLinesData();try{Check(lines.Count>0,"Hatch contains no rendered pattern lines");}finally{foreach(Line2d line in lines)line.Dispose();}}
   tr.Commit();
  }
 }
 static string ReportPath(string phase){return Path.Combine(Path.GetDirectoryName(DB.Filename),"fill-"+phase+".json");}
 static void Report(string phase,List<object> rows,System.Exception error){
  File.WriteAllText(ReportPath(phase),new JavaScriptSerializer{MaxJsonLength=8000000}.Serialize(new{passed=error==null,checks=checks,regions=rows.Count,pattern_line_inspection=inspectPatternLines,origin_control_pattern_lines=controlPatternLines,rows=rows,error=error==null?null:error.ToString()}));
 }
 [CommandMethod("PC_FILL_CASE_TEST")]
 public void Run(){
  var rows=new List<object>();System.Exception failure=null;
  try{
   var areas=Areas();Check(areas.Count>0,"No managed case regions");LineInspectionControl();
   foreach(ObjectId id in areas){
    double originalArea;Extents3d originalBox;
    using(var tr=DB.TransactionManager.StartTransaction()){var source=(Region)tr.GetObject(id,OpenMode.ForRead);originalArea=source.Area;originalBox=source.GeometricExtents;}
    string first=Fill(id,"ANSI31");Check(!first.StartsWith("ERROR:"),id.Handle+": "+first);Validate(id,first);
    string replacement=Fill(id,"ANSI32");Check(!replacement.StartsWith("ERROR:"),id.Handle+" replacement: "+replacement);
    Check(Id(first).IsErased,"Replacement duplicated old hatch");Validate(id,replacement);
    using(var tr=DB.TransactionManager.StartTransaction()){
     var source=(Region)tr.GetObject(id,OpenMode.ForRead);Check(source.Area==originalArea&&source.GeometricExtents.MinPoint==originalBox.MinPoint&&source.GeometricExtents.MaxPoint==originalBox.MaxPoint,"Filling modified source region");
    }
    rows.Add(new{source=id.Handle.ToString(),hatch=replacement});
   }
   for(int i=31;i<=38;i++){string result=Fill(areas[0],"ANSI"+i);Check(!result.StartsWith("ERROR:"),"Predefined pattern failed: "+result);Validate(areas[0],result);}
   string invalid=Fill(areas[0],"COUNTINGTREES_INVALID_PATTERN");Check(invalid.StartsWith("ERROR:"),"Invalid pattern accepted");
   using(var tr=DB.TransactionManager.StartTransaction()){
    var layer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))["PL_灌木_填充"],OpenMode.ForRead);
    Check(layer.Color.ColorIndex==8,"Default shrub fill is not gray");
   }
  }catch(System.Exception ex){failure=ex;}Report("initial",rows,failure);
 }
 [CommandMethod("PC_FILL_CASE_REOPEN")]
 public void Reopen(){
  var rows=new List<object>();System.Exception failure=null;
  try{
   LineInspectionControl();
   foreach(ObjectId area in Areas()){
    var fills=new List<string>();using(var tr=DB.TransactionManager.StartTransaction())foreach(ObjectId id in (BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForRead)){
     var entity=tr.GetObject(id,OpenMode.ForRead) as Hatch;if(entity!=null&&Linked(entity,"AREA_FILL",area.Handle.ToString()))fills.Add(id.Handle.ToString());
    }
    Check(fills.Count==1,"Expected one managed hatch after reopening "+area.Handle);Validate(area,fills[0]);rows.Add(new{source=area.Handle.ToString(),hatch=fills[0]});
   }
   Check(rows.Count>0,"No saved managed fills");
  }catch(System.Exception ex){failure=ex;}Report("reopen",rows,failure);
 }
}
