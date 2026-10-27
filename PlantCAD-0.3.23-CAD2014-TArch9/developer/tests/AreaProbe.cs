using System;
using System.Collections.Generic;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(AreaProbe))]
public class AreaProbe {
 static int count;
 static void Check(bool value,string label){if(!value)throw new InvalidOperationException(label);count++;}
 static Polyline Box(double x,double y,double w,double h){var p=new Polyline();p.AddVertexAt(0,new Point2d(x,y),0,0,0);p.AddVertexAt(1,new Point2d(x+w,y),0,0,0);p.AddVertexAt(2,new Point2d(x+w,y+h),0,0,0);p.AddVertexAt(3,new Point2d(x,y+h),0,0,0);p.Closed=true;return p;}
 static void With(List<Curve> curves,Action<PlantAreaGeometry> test){try{using(var g=new PlantAreaGeometry(curves,1e-7,false))test(g);}finally{foreach(var c in curves)c.Dispose();}}
 static void Auto(List<Curve> curves,Action<PlantAreaGeometry> test){try{using(var g=new PlantAreaGeometry(curves,1e-7)){
  test(g);for(int i=0;i<g.Faces.Count;i++)Check(g.Find(g.InteriorPoint(i))==i,"automatic label inside its own cell");
 }}finally{foreach(var c in curves)c.Dispose();}}
 [CommandMethod("PC_AREA_TEST")]
 public void Run(){
  string result=Environment.GetEnvironmentVariable("PC_AREA_RESULT");
  try{
   With(new List<Curve>{Box(0,0,10,10),new Line(new Point3d(5,0,0),new Point3d(5,10,0))},g=>{Check(g.Faces.Count==2,"shared T junction");Check(Math.Abs(g.Faces[0].Area-50)<1e-8,"exact 50");Check(g.Find(new Point3d(2,3,0))!=g.Find(new Point3d(8,3,0)),"point chooses different cells");Check(g.Find(new Point3d(5,3,0))==-1,"on edge rejected");});
   With(new List<Curve>{Box(0,0,10,10),new Arc(new Point3d(5,0,0),5,0,Math.PI)},g=>{Check(g.Faces.Count==2,"shared arc");double a=g.Faces[g.Find(new Point3d(5,2,0))].Area;Check(Math.Abs(a-Math.PI*25/2)<1e-7,"exact arc area");Check(Math.Abs(g.Faces[0].Area+g.Faces[1].Area-100)<1e-7,"curve cells cover original");});
   var bulge=new Polyline();bulge.AddVertexAt(0,new Point2d(-5,0),1,0,0);bulge.AddVertexAt(1,new Point2d(5,0),1,0,0);bulge.Closed=true;
   With(new List<Curve>{bulge},g=>{Check(g.Faces.Count==1,"bulge loop");Check(Math.Abs(g.Faces[0].Area-25*Math.PI)<1e-7,"bulge exact area");});
   With(new List<Curve>{new Circle(Point3d.Origin,Vector3d.ZAxis,3)},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-9*Math.PI)<1e-7,"circle exact"));
   With(new List<Curve>{Box(0,0,10,10),Box(2,2,4,4)},g=>{Check(g.Faces.Count==2,"nested loops");Check(Math.Abs(g.Faces[g.Find(new Point3d(1,1,0))].Area-84)<1e-7,"subtract hole");Check(Math.Abs(g.Faces[g.Find(new Point3d(3,3,0))].Area-16)<1e-7,"inner cell");});
   With(new List<Curve>{Box(0,0,10,10),new Line(new Point3d(5,0,0),new Point3d(5,10,0)),new Line(new Point3d(0,5,0),new Point3d(10,5,0))},g=>{Check(g.Faces.Count==4,"crossing splits four");double total=0;foreach(var f in g.Faces)total+=f.Area;Check(Math.Abs(total-100)<1e-7,"crossing no double count");});
   With(new List<Curve>{Box(0,0,10,10),new Line(Point3d.Origin,new Point3d(10,0,0)),new Line(new Point3d(5,0,0),new Point3d(5,2,0))},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-100)<1e-7,"duplicate and dangling branch"));
   With(new List<Curve>{new Line(Point3d.Origin,new Point3d(10,0,0)),new Line(new Point3d(10,0,0),new Point3d(10,10,0)),new Line(new Point3d(10,10,0),new Point3d(0,10,0)),new Line(new Point3d(0,10,0),new Point3d(0,.01,0))},g=>Check(g.Faces.Count==0&&g.OpenEnds==2,"gap not bridged"));
   With(new List<Curve>{Box(218118,231230,10,10)},g=>Check(g.Find(new Point3d(218120,231232,0))>=0&&Math.Abs(g.Faces[0].Area-100)<1e-7,"site coordinates"));
   var spline=new Spline(new Point3dCollection(new[]{new Point3d(0,0,0),new Point3d(3,3,0),new Point3d(7,3,0),new Point3d(10,0,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0);
   var originals=new DBObjectCollection();originals.Add((Curve)spline.Clone());originals.Add(new Line(new Point3d(10,0,0),Point3d.Origin));double expected=0;foreach(Region r in Region.CreateFromCurves(originals)){expected+=r.Area;r.Dispose();}foreach(DBObject o in originals)o.Dispose();
   With(new List<Curve>{spline,new Line(new Point3d(10,0,0),Point3d.Origin)},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-expected)<1e-7,"exact spline area"));
   Auto(new List<Curve>{new Line(Point3d.Origin,new Point3d(10,0,0)),new Line(new Point3d(10,0,0),new Point3d(10,10,0)),new Line(new Point3d(10,10,0),new Point3d(0,10,0)),new Line(new Point3d(0,10,0),new Point3d(0,.01,0))},g=>Check(g.Faces.Count==1&&g.Repairs.Count>0&&g.Faces[0].Repaired&&Math.Abs(g.Faces[0].Area-100)<1e-7,"repair disconnected line endpoint"));
   var openBox=Box(0,0,10,10);openBox.Closed=false;
   Auto(new List<Curve>{openBox},g=>{Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-100)<1e-7,"open PLINE missing closing edge");Check(!openBox.Closed,"original open flag preserved");});
   Auto(new List<Curve>{new Line(Point3d.Origin,new Point3d(10,0,0)),new Line(new Point3d(10,0,0),new Point3d(10,10,0)),new Line(new Point3d(10,10,0),new Point3d(0,10,0))},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-100)<1e-7,"three LINE sides inferred close"));
   Auto(new List<Curve>{new Line(new Point3d(.1,0,0),new Point3d(10,0,0)),new Line(new Point3d(10,0,0),new Point3d(10,10,0)),new Line(new Point3d(10,10,0),new Point3d(0,10,0)),new Line(new Point3d(0,10,0),new Point3d(0,.1,0))},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-100)<1e-7,"tangent corner restored without chamfer"));
   Auto(new List<Curve>{Box(0,0,10,10),new Line(new Point3d(5,0,0),new Point3d(5,4.9,0)),new Line(new Point3d(5,5.1,0),new Point3d(5,10,0))},g=>Check(g.Faces.Count==2&&Math.Abs(g.Faces[0].Area+g.Faces[1].Area-100)<1e-7&&g.Faces[0].Repaired&&g.Faces[1].Repaired,"broken shared divider recovers both cells"));
   var brokenSpline=new Spline(new Point3dCollection(new[]{new Point3d(0,5,0),new Point3d(3,6,0),new Point3d(6,4,0),new Point3d(9.9,5,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0);
   Auto(new List<Curve>{Box(0,0,10,10),brokenSpline},g=>Check(g.Faces.Count==2&&Math.Abs(g.Faces[0].Area+g.Faces[1].Area-100)<.001,"SPLINE to boundary gap faces="+g.Faces.Count+" repairs="+g.Repairs.Count+" open="+g.OpenEnds+" invalid="+g.InvalidContours+" areas="+(g.Faces.Count>1?(g.Faces[0].Area+g.Faces[1].Area).ToString("R"):"none")));
   Auto(new List<Curve>{new Line(Point3d.Origin,new Point3d(40,20,0)),new Line(new Point3d(-1,2,0),new Point3d(39,22,0))},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area-100)<1e-6,"two open parallel sides inferred end caps"));
   Auto(new List<Curve>{Box(0,0,10,10),new Line(new Point3d(5,-.5,0),new Point3d(5,10.5,0))},g=>Check(g.Faces.Count==2&&g.Repairs.Count==0,"overshoot tails do not become extra cells"));
   Auto(new List<Curve>{Box(0,0,10,10),Box(2,2,4,4)},g=>Check(g.Faces.Count==2&&g.Repairs.Count==0,"closed nested cells keep exact status"));
   var concave=new Polyline();int vi=0;foreach(Point2d p in new[]{new Point2d(0,0),new Point2d(8,0),new Point2d(8,3),new Point2d(3,3),new Point2d(3,8),new Point2d(0,8)})concave.AddVertexAt(vi++,p,0,0,0);concave.Closed=true;
   Auto(new List<Curve>{concave},g=>Check(g.Faces.Count==1,"concave cell for automatic label"));
   foreach(double scale in new[]{.001,1000.0}){
    var scaled=Box(218118*scale,231230*scale,10*scale,10*scale);scaled.Closed=false;
    Auto(new List<Curve>{scaled},g=>Check(g.Faces.Count==1&&Math.Abs(g.Faces[0].Area/(scale*scale)-100)<1e-5,"unit independent gap recovery"));
   }
   var mixedOuter=Box(0,0,10,10);mixedOuter.Closed=false;
   var mixedSpline=new Spline(new Point3dCollection(new[]{new Point3d(0,5,0),new Point3d(3,6,0),new Point3d(6,4,0),new Point3d(9.9,5,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0);
   Auto(new List<Curve>{mixedOuter,mixedSpline},g=>Check(g.Faces.Count==2&&Math.Abs(g.Faces[0].Area+g.Faces[1].Area-100)<.001,"mixed open PLINE and SPLINE"));
   var board=new List<Curve>{new Line(new Point3d(.1,0,0),new Point3d(100,0,0)),new Line(new Point3d(100,0,0),new Point3d(100,60,0)),new Line(new Point3d(100,60,0),new Point3d(0,60,0)),new Line(new Point3d(0,60,0),new Point3d(0,.1,0))};
   foreach(double x in new[]{20.0,40.0,60.0,80.0})board.Add(new Spline(new Point3dCollection(new[]{new Point3d(x,.05,0),new Point3d(x+2,20,0),new Point3d(x-2,40,0),new Point3d(x,59.95,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0));
   board.Add(new Spline(new Point3dCollection(new[]{new Point3d(.05,30,0),new Point3d(35,32,0),new Point3d(65,28,0),new Point3d(99.95,30,0)}),new Vector3d(0,0,0),new Vector3d(0,0,0),4,0));
   board.Add(new Line(new Point3d(130,0,0),new Point3d(180,0,0)));board.Add(new Line(new Point3d(130,5,0),new Point3d(180,5,0)));
   var secondStrip=Box(130,20,40,8);secondStrip.Closed=false;board.Add(secondStrip);
   board.Add(new Line(new Point3d(130,40,0),new Point3d(180,40,0)));board.Add(new Line(new Point3d(180,40,0),new Point3d(180,50,0)));board.Add(new Line(new Point3d(180,50,0),new Point3d(130,50,0)));
   Auto(board,g=>{Check(g.Faces.Count==13,"mixed diagram recovers all 13 cells, found "+g.Faces.Count);double total=0;foreach(var f in g.Faces)total+=f.Area;Check(Math.Abs(total-7070)<.1,"mixed diagram total geometry area");});
   // Many cuts on one straight boundary, including reverse direction and scrambled selection order.
   for(int order=0;order<2;order++){
    var grid=new List<Curve>{new Line(new Point3d(0,0,0),new Point3d(13000,0,0)),new Line(new Point3d(13000,0,0),new Point3d(13000,1000,0)),new Line(new Point3d(13000,1000,0),new Point3d(0,1000,0)),new Line(new Point3d(0,1000,0),new Point3d(0,0,0))};
    for(int i=1;i<13;i++)grid.Add(new Line(new Point3d(i*1000,0,0),new Point3d(i*1000,1000,0)));
    if(order==1)grid.Reverse();
    Auto(grid,g=>{Check(g.Faces.Count==13,"many T junctions recover 13 cells, found "+g.Faces.Count);double total=0;foreach(var f in g.Faces){total+=f.Area;Check(Math.Abs(f.Area-1000000)<.001,"each straight cell area exact");}Check(Math.Abs(total-13000000)<.001,"many T junctions no overlap");Check(g.Repairs.Count==0&&g.OpenEnds==0,"closed straight grid requires no repair");});
   }
   // Node tolerance must also be honoured by the actual region builder. These
   // gaps are numerical joins, not adaptive design repairs; the sources stay put.
   for(int order=0;order<2;order++){
    var near=new List<Curve>{new Line(new Point3d(0,0,0),new Point3d(10,0,0)),new Line(new Point3d(10,.00002,0),new Point3d(10,10,0)),new Line(new Point3d(10,10,0),new Point3d(0,10,0)),new Line(new Point3d(0,10,0),new Point3d(0,.00002,0))};
    if(order==1){near.Reverse();foreach(Curve c in near)c.ReverseCurve();}
    try{using(var g=new PlantAreaGeometry(near,.0001,false)){
     Check(g.Faces.Count==1,"microscopic line joints still generate a region");Check(Math.Abs(g.Faces[0].Area-100)<.001,"joined rectangle preserves its geometric area");
     Check(g.Repairs.Count==0&&!g.Faces[0].Repaired,"numerical joints are not guessed closing edges");Check(g.Find(g.InteriorPoint(0))==0,"joined region has an internal label anchor");
     Check(near[order==0?1:2].StartPoint.DistanceTo(order==0?new Point3d(10,.00002,0):new Point3d(10,10,0))<1e-12,"source line endpoints are unchanged");
    }}finally{foreach(Curve c in near)c.Dispose();}
   }
   foreach(double x in new[]{0.0,160000000.0}){
    var arcJoin=new List<Curve>{new Arc(new Point3d(x,100000000,0),5,0,Math.PI),new Line(new Point3d(x-5,100000000.00002,0),new Point3d(x+5,100000000,0))};
    try{using(var g=new PlantAreaGeometry(arcJoin,.0001,false)){
     Check(g.Faces.Count==1,"microscopic arc-line joint forms its closed region");Check(Math.Abs(g.Faces[0].Area-Math.PI*25/2)<.001,"arc bulge keeps semicircle area at survey coordinates");
     Check(g.Repairs.Count==0,"arc numerical join does not invoke gap guessing");Check(g.Find(g.InteriorPoint(0))==0,"arc joined label lies inside region");
    }}finally{foreach(Curve c in arcJoin)c.Dispose();}
   }
   foreach(double width in new[]{.0005,.005}){
    using(var thin=Box(0,0,10,width))using(var g=new PlantAreaGeometry(new[]{(Curve)thin},.0001,false)){
     if(width<.001){Check(g.Faces.Count==0,"precision sliver is not presented as a valid area");Check(g.UncertainContours==1,"precision sliver is explicitly reported");}
     else{Check(g.Faces.Count==1,"narrow region above uncertainty is retained");Check(Math.Abs(g.Faces[0].Area-.05)<1e-8,"valid narrow area remains accurate");}
    }
   }
   foreach(double center in new[]{0.0,34537214502.0}){
    using(var circle=new Circle(new Point3d(center,0,0),Vector3d.ZAxis,5))using(var line=new Line(new Point3d(center-1e9,0,0),new Point3d(center+1e9,0,0)))using(var g=new PlantAreaGeometry(new Curve[]{line,circle},.00001,false)){
     Check(g.Faces.Count==2,"a long crossing tail does not suppress small circular cells");double total=0;foreach(var face in g.Faces)total+=face.Area;Check(Math.Abs(total-25*Math.PI)<.001,"long-line/small-arc intersections preserve area at local and survey coordinates");
    }
   }
   File.WriteAllText(result,"PASS "+count);
  }catch(System.Exception ex){File.WriteAllText(result,"FAIL "+count+" "+ex);}
 }
}

