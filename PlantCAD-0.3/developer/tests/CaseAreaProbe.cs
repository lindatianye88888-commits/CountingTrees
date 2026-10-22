using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(CaseAreaProbe))]
public class CaseAreaProbe {
 static object Ring(System.Collections.IEnumerable points){var output=new List<double[]>();foreach(Point3d p in points)output.Add(new[]{p.X,p.Y});return output;}
 static void Snapshot(object geometry,string name){
  var type=geometry.GetType();var rows=new List<object>();
  foreach(object face in (System.Collections.IEnumerable)type.GetField("Faces").GetValue(geometry)){
   var ft=face.GetType();var region=(Region)ft.GetField("Shape").GetValue(face);var holes=new List<object>();
   foreach(object hole in (System.Collections.IEnumerable)ft.GetField("Holes").GetValue(face))holes.Add(Ring((System.Collections.IEnumerable)hole));
   var fitted=ft.GetField("Fitted");rows.Add(new{area=region.Area,outline=Ring((System.Collections.IEnumerable)ft.GetField("Outline").GetValue(face)),holes=holes,fitted=fitted!=null&&(bool)fitted.GetValue(face)});
  }
  var pieces=new List<object>();foreach(Curve c in (System.Collections.IEnumerable)type.GetField("pieces",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(geometry)){
   pieces.Add(new{type=c.GetType().Name,start=new[]{c.StartPoint.X,c.StartPoint.Y},end=new[]{c.EndPoint.X,c.EndPoint.Y}});
  }
  var graph=new List<object>();foreach(object edge in (System.Collections.IEnumerable)type.GetField("edges",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(geometry)){
   var et=edge.GetType();graph.Add(new{from=et.GetField("From").GetValue(edge),to=et.GetField("To").GetValue(edge),angle=et.GetField("Angle").GetValue(edge)});
  }
  var stats=new Dictionary<string,object>();foreach(string property in new[]{"OpenEnds","InvalidContours","JoinedContours","UncertainContours","FittedContours"})stats[property]=type.GetProperty(property).GetValue(geometry,null);
  var result=new{faces=rows,pieces=pieces,nodes=Ring((System.Collections.IEnumerable)type.GetField("nodes",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(geometry)),edges=graph,stats=stats};var db=Application.DocumentManager.MdiActiveDocument.Database;
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(db.Filename),name+".json"),new JavaScriptSerializer{MaxJsonLength=100000000}.Serialize(result));
 }
 [LispFunction("pc:case-stats")]
 public ResultBuffer Stats(ResultBuffer args){
  var type=typeof(Bridge);var g=type.GetField("areaGeometry",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
  var row=new Dictionary<string,object>{{"assembly",type.Assembly.Location},{"geometry",g==null?"none":g.GetType().FullName}};
  if(g!=null){var gt=g.GetType();row["faces"]=((System.Collections.IList)gt.GetField("Faces").GetValue(g)).Count;foreach(string name in new[]{"InvalidContours","JoinedContours","UncertainContours","FittedContours","OpenEnds"}){var p=gt.GetProperty(name);if(p!=null)row[name]=p.GetValue(g,null);}Snapshot(g,"case-geometry");}
  return new ResultBuffer(new TypedValue(5005,new JavaScriptSerializer().Serialize(row)));
 }
 [CommandMethod("PC_CASE_ORDER_TEST")]
 public void OrderTest(){
  var db=Application.DocumentManager.MdiActiveDocument.Database;var handles=new List<string>();var rows=new List<object>();
  using(var input=new ResultBuffer(new TypedValue(5005,"PL_灌木_原始线")))using(var output=Handles(input))foreach(TypedValue value in output)handles.Add(Convert.ToString(value.Value));
  foreach(string mode in new[]{"drawing","reverse","handle","shuffle"}){
   var current=new List<string>(handles);
   if(mode=="reverse")current.Reverse();
   if(mode=="handle")current.Sort((a,b)=>Convert.ToInt64(a,16).CompareTo(Convert.ToInt64(b,16)));
   if(mode=="shuffle"){var random=new Random(20261021);for(int i=current.Count-1;i>0;i--){int j=random.Next(i+1);string value=current[i];current[i]=current[j];current[j]=value;}}
   var args=new List<TypedValue>{new TypedValue(5016)};foreach(string h in current)args.Add(new TypedValue(5005,h));args.Add(new TypedValue(5017));args.Add(new TypedValue(5005,"PL_灌木_原始线"));
   using(var input=new ResultBuffer(args.ToArray()))using(var output=new Bridge().BeginAreaSession(input)){
    var g=typeof(Bridge).GetField("areaGeometry",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
    if(g!=null)Snapshot(g,"order-"+mode);rows.Add(new{mode=mode,result=Convert.ToString(output.AsArray()[0].Value)});
   }
  }
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(db.Filename),"case-orders.json"),new JavaScriptSerializer().Serialize(rows));
 }
 [CommandMethod("PC_CASE_DUPLICATES")]
 public void Duplicates(){
  var db=Application.DocumentManager.MdiActiveDocument.Database;var rows=new List<object>();var regions=new List<Region>();
  using(var tr=db.TransactionManager.StartTransaction()){
   foreach(ObjectId id in (BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForRead)){var r=tr.GetObject(id,OpenMode.ForRead) as Region;if(r!=null)regions.Add(r);}
   for(int i=0;i<regions.Count;i++)for(int j=i+1;j<regions.Count;j++){
    var a=regions[i];var b=regions[j];if(a.GeometricExtents.MinPoint.DistanceTo(b.GeometricExtents.MinPoint)>.01||a.GeometricExtents.MaxPoint.DistanceTo(b.GeometricExtents.MaxPoint)>.01)continue;
    var row=new Dictionary<string,object>{{"a",a.Handle.ToString()},{"b",b.Handle.ToString()},{"areaA",a.Area},{"areaB",b.Area},{"difference",Math.Abs(a.Area-b.Area)},{"boundsDifference",a.GeometricExtents.MinPoint.DistanceTo(b.GeometricExtents.MinPoint)+a.GeometricExtents.MaxPoint.DistanceTo(b.GeometricExtents.MaxPoint)}};rows.Add(row);
    foreach(var pair in new[]{new KeyValuePair<string,Region>("typesA",a),new KeyValuePair<string,Region>("typesB",b)}){var parts=new DBObjectCollection();try{pair.Value.Explode(parts);var types=new Dictionary<string,int>();foreach(DBObject part in parts){string name=part.GetType().Name;if(!types.ContainsKey(name))types[name]=0;types[name]++;}row[pair.Key]=types;}catch(System.Exception ex){row[pair.Key]=ex.Message;}finally{foreach(DBObject part in parts)part.Dispose();}}
    using(var c=(Region)a.Clone())using(var d=(Region)b.Clone())try{
     var p=a.GeometricExtents.MinPoint;var shift=Autodesk.AutoCAD.Geometry.Matrix3d.Displacement(new Autodesk.AutoCAD.Geometry.Vector3d(-p.X,-p.Y,-p.Z));c.TransformBy(shift);d.TransformBy(shift);row["localA"]=c.Area;row["localB"]=d.Area;
     c.BooleanOperation(BooleanOperationType.BoolIntersect,d);row["overlap"]=c.IsNull?0:c.Area;
    }catch(System.Exception e){row["error"]=e.ToString();}
   }
  }
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(db.Filename),"duplicates.json"),new JavaScriptSerializer().Serialize(rows));
 }
 [LispFunction("pc:case-index")]
 public ResultBuffer Index(ResultBuffer args){
  var geometry=typeof(Bridge).GetField("areaGeometry",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
  int index=(int)geometry.GetType().GetMethod("Find").Invoke(geometry,new object[]{args.AsArray()[0].Value});
  return new ResultBuffer(new TypedValue(5010,index));
 }
 [LispFunction("pc:case-handles")]
 public ResultBuffer Handles(ResultBuffer args){
  string layer=Convert.ToString(args.AsArray()[0].Value);var db=Application.DocumentManager.MdiActiveDocument.Database;var values=new List<TypedValue>();
  using(var tr=db.TransactionManager.StartTransaction())foreach(ObjectId id in (BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForRead)){
   var e=tr.GetObject(id,OpenMode.ForRead) as Curve;if(e==null||e.Layer!=layer)continue;
   using(var data=e.GetXDataForApplication("PLANTCAD01")){if(data!=null)continue;}
   values.Add(new TypedValue(5005,e.Handle.ToString()));
  }
  return new ResultBuffer(values.ToArray());
 }
 [LispFunction("pc:case-signature")]
 public ResultBuffer Signature(ResultBuffer args){
  var v=args.AsArray();string layer=Convert.ToString(v[0].Value);bool outside=Convert.ToInt32(v[1].Value)==1;
  var db=Application.DocumentManager.MdiActiveDocument.Database;var text=new System.Text.StringBuilder();
  using(var tr=db.TransactionManager.StartTransaction())foreach(ObjectId id in (BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForRead)){
   var e=tr.GetObject(id,OpenMode.ForRead) as Curve;if(e==null||(outside?e.Layer==layer:e.Layer!=layer))continue;
   using(var data=e.GetXDataForApplication("PLANTCAD01")){if(data!=null)continue;}
   text.Append(e.Handle.ToString()).Append(e.GetType().Name).Append(e.Layer);
   for(int i=0;i<=4;i++){var p=e.GetPointAtParameter(e.StartParam+(e.EndParam-e.StartParam)*i/4.0);text.Append(p.X.ToString("R",System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(p.Y.ToString("R",System.Globalization.CultureInfo.InvariantCulture));if(outside)text.Append(',').Append(p.Z.ToString("R",System.Globalization.CultureInfo.InvariantCulture));}
   if(outside)text.Append(e.ColorIndex);
  }
  using(var hash=System.Security.Cryptography.SHA256.Create())return new ResultBuffer(new TypedValue(5005,BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(text.ToString())))));
 }
 [CommandMethod("PC_CASE_AREA")]
 public void Run(){
  var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;var result=new List<object>();
  var layers=new Dictionary<string,List<string>>();
  using(var tr=db.TransactionManager.StartTransaction()){
   foreach(ObjectId id in (BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForRead)){
    var e=tr.GetObject(id,OpenMode.ForRead) as Curve;if(e==null)continue;
    using(var data=e.GetXDataForApplication("PLANTCAD01")){if(data!=null)continue;}
    if(!layers.ContainsKey(e.Layer))layers[e.Layer]=new List<string>();layers[e.Layer].Add(e.Handle.ToString());
   }
  }
  foreach(var pair in layers){
   var row=new Dictionary<string,object>{{"layer",pair.Key},{"count",pair.Value.Count}};result.Add(row);
   var values=new List<TypedValue>{new TypedValue(5016)};foreach(string h in pair.Value)values.Add(new TypedValue(5005,h));values.Add(new TypedValue(5017));values.Add(new TypedValue(5005,pair.Key));
   try{using(var input=new ResultBuffer(values.ToArray()))using(var output=(ResultBuffer)typeof(Bridge).GetMethod("PrepareAreaSession",BindingFlags.NonPublic|BindingFlags.Instance).Invoke(new Bridge(),new object[]{input})){
    row["result"]=Convert.ToString(output.AsArray()[0].Value);
   }}catch(System.Exception ex){row["error"]=(ex.InnerException??ex).ToString();}
   finally{typeof(Bridge).GetMethod("EndAreaSession",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);}
  }
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(doc.Name),"case-area.json"),new JavaScriptSerializer().Serialize(result));
 }
}
