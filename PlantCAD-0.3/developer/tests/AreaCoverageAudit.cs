using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(AreaCoverageAudit))]
public class AreaCoverageAudit {
 public static List<object> Rejected=new List<object>();
 public static void Reject(string reason,DBObjectCollection curves,List<Point3d> outline){var parts=new List<object>();foreach(Curve c in curves)parts.Add(new{type=c.GetType().Name,points=Points(c)});Rejected.Add(new{reason=reason,parts=parts,outline=Ring(outline)});}
 static object Points(Curve c){var pts=new List<double[]>();double length=c.GetDistanceAtParameter(c.EndParam)-c.GetDistanceAtParameter(c.StartParam);int n=c is Line?1:Math.Min(2048,Math.Max(64,(int)(length/50)));for(int i=0;i<=n;i++){var p=c.GetPointAtDist(length*i/n);pts.Add(new[]{p.X,p.Y});}return pts;}
 static object Ring(List<Point3d> ring){return ring.ConvertAll(p=>new[]{p.X,p.Y});}
 [CommandMethod("PC_AREA_COVERAGE")]
 public void Run(){
  var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;
  var layers=new Dictionary<string,List<Curve>>();var sources=new Dictionary<string,List<object>>();var result=new Dictionary<string,object>();
  using(var tr=db.TransactionManager.StartTransaction())foreach(ObjectId id in (BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForRead)){
   var c=tr.GetObject(id,OpenMode.ForRead) as Curve;if(c==null)continue;
   using(var data=c.GetXDataForApplication("PLANTCAD01")){if(data!=null)continue;}
   if(!layers.ContainsKey(c.Layer)){layers[c.Layer]=new List<Curve>();sources[c.Layer]=new List<object>();}
   Curve copy;using(var plane=new Plane(Point3d.Origin,Vector3d.ZAxis))copy=c.GetOrthoProjectedCurve(plane);
   if(copy==null)continue;layers[c.Layer].Add(copy);
   sources[c.Layer].Add(new{handle=c.Handle.ToString(),type=c.GetType().Name,closed=c.Closed,points=Points(copy)});
  }
  foreach(var pair in layers){var runs=new List<object>();result[pair.Key]=new{sources=sources[pair.Key],runs=runs};
   foreach(bool repair in new[]{false,true})try{
    double extent=1;foreach(Curve c in pair.Value)extent=Math.Max(extent,(c.GeometricExtents.MaxPoint-c.GeometricExtents.MinPoint).Length);
    Rejected=new List<object>();using(var g=new PlantAreaGeometry(pair.Value,Math.Max(1e-7,extent*1e-9),repair)){
     var faces=new List<object>();for(int i=0;i<g.Faces.Count;i++){var f=g.Faces[i];faces.Add(new{area=f.Area,outline=Ring(f.Outline),holes=f.Holes.ConvertAll(h=>Ring(h)),repaired=f.Repaired,fitted=f.Fitted});}
     var pieces=(List<Curve>)typeof(PlantAreaGeometry).GetField("pieces",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(g);
     var nodes=(List<Point3d>)typeof(PlantAreaGeometry).GetField("nodes",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(g);
     runs.Add(new{repair=repair,faces=faces,pieces=pieces.ConvertAll(c=>Points(c)),nodes=Ring(nodes),open=g.OpenEnds,invalid=g.InvalidContours,joined=g.JoinedContours,uncertain=g.UncertainContours,fitted=g.FittedContours,rejected=Rejected,repairs=g.Repairs.ConvertAll(c=>Points(c))});
    }
   }catch(System.Exception ex){runs.Add(new{repair=repair,error=ex.ToString()});}
   finally{}
  }
  foreach(var pair in layers)foreach(var c in pair.Value)c.Dispose();
  var serializer=new JavaScriptSerializer{MaxJsonLength=100000000};File.WriteAllText(Path.Combine(Path.GetDirectoryName(doc.Name),"coverage.json"),serializer.Serialize(result));
 }
}
