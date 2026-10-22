using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace PlantCADBridge {
 // Detached curves only; source entities and layer visibility are never modified.
 internal sealed partial class PlantAreaGeometry : IDisposable {
  internal sealed class Face { public Region Shape; public List<Point3d> Outline; public readonly List<List<Point3d>> Holes=new List<List<Point3d>>(); public bool Repaired,Fitted; public double Area {get{return Shape.Area;}} }
  sealed class Edge { public Curve Curve; public int From,To,Twin; public double Angle; public bool Used; }
  readonly List<Curve> pieces=new List<Curve>();
  readonly List<Point3d> nodes=new List<Point3d>();
  readonly List<Edge> edges=new List<Edge>();
  public readonly List<Face> Faces=new List<Face>();
  readonly double tolerance;
  readonly Vector3d coordinateOrigin;
  int cutCount;
  public int OpenEnds {get;private set;}
  readonly bool repairEnabled;
  public int InvalidContours {get;private set;}
  public int JoinedContours {get;private set;}
  public int UncertainContours {get;private set;}
  public int FittedContours {get;private set;}
  public PlantAreaGeometry(IEnumerable<Curve> sources,double joinTolerance):this(sources,joinTolerance,true){}
  public PlantAreaGeometry(IEnumerable<Curve> sources,double joinTolerance,bool automaticRepair) {
   tolerance=joinTolerance;repairEnabled=automaticRepair;
   var local=new List<Curve>();Vector3d offset=new Vector3d(0,0,0);
   try{
    var ordered=new List<Curve>(sources);ordered.Sort(CompareSources);
    // Input selections and ObjectId enumeration differ between hosts. Use the
    // same curve order and local origin before tolerance-based node matching.
    if(ordered.Count>0){var first=ordered[0].StartPoint;offset=new Vector3d(first.X,first.Y,0);}
    foreach(Curve source in ordered){
     var copy=(Curve)source.Clone();local.Add(copy);copy.TransformBy(Matrix3d.Displacement(-offset));
    }
    coordinateOrigin=offset;
    Build(local);
    var move=Matrix3d.Displacement(offset);
    foreach(Curve c in pieces)c.TransformBy(move);
    for(int i=0;i<nodes.Count;i++)nodes[i]=nodes[i]+offset;
    // Hole rings refer to a child face's Outline; transform each outline once.
    foreach(Face face in Faces){face.Shape.TransformBy(move);for(int i=0;i<face.Outline.Count;i++)face.Outline[i]=face.Outline[i]+offset;}
    foreach(Line repair in Repairs)repair.TransformBy(move);
   }catch{Dispose();throw;}finally{foreach(Curve c in local)c.Dispose();}
  }
  double CoordinateAreaUncertainty(Region shape,DBObjectCollection curves){
   var box=shape.GeometricExtents;double span=(box.MaxPoint-box.MinPoint).Length;
   foreach(Curve curve in curves){var arc=curve as Arc;var ellipse=curve as Ellipse;if(arc!=null)span=Math.Max(span,arc.Radius);if(ellipse!=null)span=Math.Max(span,ellipse.MajorAxis.Length);}
   double magnitude=Math.Max(Math.Max(Math.Abs(box.MinPoint.X+coordinateOrigin.X),Math.Abs(box.MaxPoint.X+coordinateOrigin.X)),Math.Max(Math.Abs(box.MinPoint.Y+coordinateOrigin.Y),Math.Abs(box.MaxPoint.Y+coordinateOrigin.Y)));
   // Tiny arc fragments can involve large radii in native mass properties.
   // Include that scale, but never a remote tail outside this face.
   return magnitude*2.2204460492503131e-16*span*8;
  }
  static double Length(Curve c){return c.GetDistanceAtParameter(c.EndParam)-c.GetDistanceAtParameter(c.StartParam);}
  static List<Point3d> Sample(Curve c,bool forward) {
   var pts=new List<Point3d>();
   // Used for orientation/containment only. CAD regions supply exact areas.
   int count=c is Line?1:c is Arc?Math.Max(8,(int)Math.Ceiling(Math.Abs(((Arc)c).TotalAngle)*64)):256;
   double length=Length(c);
   for(int k=0;k<=count;k++)pts.Add(c.GetPointAtDist(length*(forward?k:count-k)/count));
   return pts;
  }
  static double SignedArea(List<Point3d> pts) {
   double area=0;Point3d o=pts[0],prev=pts[pts.Count-1];
   foreach(Point3d p in pts){area+=(prev.X-o.X)*(p.Y-o.Y)-(p.X-o.X)*(prev.Y-o.Y);prev=p;}return area/2;
  }
  public static bool Contains(List<Point3d> poly,Point3d point) {
   bool inside=false;Point3d prev=poly[poly.Count-1];
   foreach(Point3d p in poly){if((p.Y>point.Y)!=(prev.Y>point.Y)&&point.X<(prev.X-p.X)*(point.Y-p.Y)/(prev.Y-p.Y)+p.X)inside=!inside;prev=p;}return inside;
  }
  static bool SameCurve(Curve a,Curve b,double tol) {
   if(Math.Abs(Length(a)-Length(b))>tol)return false;
   Point3d mid=a.GetPointAtDist(Length(a)/2);
   return mid.DistanceTo(b.GetClosestPointTo(mid,false))<=tol&&a.StartPoint.DistanceTo(b.GetClosestPointTo(a.StartPoint,false))<=tol&&a.EndPoint.DistanceTo(b.GetClosestPointTo(a.EndPoint,false))<=tol;
  }
  int Node(Point3d p){for(int i=0;i<nodes.Count;i++)if(nodes[i].DistanceTo(p)<=tolerance)return i;nodes.Add(p);return nodes.Count-1;}
  void AddPieces(Curve source,List<Curve> dest) {
   if(source is Polyline||source is Polyline2d||source is Polyline3d){var exploded=new DBObjectCollection();source.Explode(exploded);foreach(DBObject obj in exploded){var c=obj as Curve;if(c!=null)AddPieces(c,dest);obj.Dispose();}}
   else{
    Curve c=(Curve)source.Clone();
    if(c.Closed){double len=Length(c);var pts=new Point3dCollection(new[]{c.GetPointAtDist(len/3),c.GetPointAtDist(2*len/3)});try{foreach(DBObject obj in c.GetSplitCurves(pts))dest.Add((Curve)obj);}finally{c.Dispose();}}
    else dest.Add(c);
   }
  }
  void Build(IEnumerable<Curve> sources) {
   var original=new List<Curve>();
   try{
    foreach(Curve c in sources)AddPieces(c,original);
    if(original.Count>1200)throw new InvalidOperationException("一次最多处理1200段边界，请分区框选。");
    if(original.Count==0)throw new InvalidOperationException("没有可计算的边界曲线。");
    double elevation=original[0].StartPoint.Z;
    foreach(Curve c in original){Extents3d box=c.GeometricExtents;if(Math.Abs(box.MaxPoint.Z-elevation)>tolerance||Math.Abs(box.MinPoint.Z-elevation)>tolerance)throw new InvalidOperationException("边界须位于同一水平面；请先检查标高。");}
    SplitCurves(original);
    if(repairEnabled) {
     for(int pass=0;pass<4;pass++) {
      List<Line> links=PlanRepairs();if(links.Count==0)break;
      foreach(Line link in links){Repairs.Add((Line)link.Clone());original.Add(link);}
      foreach(Curve c in pieces)c.Dispose();pieces.Clear();nodes.Clear();cutCount=0;
      SplitCurves(original);
     }
    }
   }finally{foreach(Curve c in original)c.Dispose();}
   nodes.Clear();
   var outgoing=new Dictionary<int,List<int>>();
   foreach(Curve c in pieces){
    int a=Node(c.StartPoint),b=Node(c.EndPoint);if(a==b)continue;int f=edges.Count;
    double delta=Length(c)*1e-5;
    Vector3d da=c.GetPointAtDist(delta)-c.StartPoint,db=c.GetPointAtDist(Length(c)-delta)-c.EndPoint;
    edges.Add(new Edge{Curve=c,From=a,To=b,Twin=f+1,Angle=Math.Atan2(da.Y,da.X)});edges.Add(new Edge{Curve=c,From=b,To=a,Twin=f,Angle=Math.Atan2(db.Y,db.X)});
    if(!outgoing.ContainsKey(a))outgoing[a]=new List<int>();if(!outgoing.ContainsKey(b))outgoing[b]=new List<int>();outgoing[a].Add(f);outgoing[b].Add(f+1);
   }
   foreach(List<int> list in outgoing.Values){list.Sort((a,b)=>edges[a].Angle.CompareTo(edges[b].Angle));if(list.Count==1)OpenEnds++;}
   for(int start=0;start<edges.Count;start++){
    if(edges[start].Used)continue;var ring=new List<int>();int current=start;
    while(!edges[current].Used){edges[current].Used=true;ring.Add(current);Edge edge=edges[current];List<int> list=outgoing[edge.To];int rev=list.IndexOf(edge.Twin);current=list[(rev+list.Count-1)%list.Count];}
    if(current!=start)continue;
    var perimeter=new List<int>();foreach(int id in ring)if(!ring.Contains(edges[id].Twin))perimeter.Add(id);if(perimeter.Count<2)continue;
    var outline=new List<Point3d>();var curves=new DBObjectCollection();
    try{
     foreach(int id in perimeter){Edge edge=edges[id];List<Point3d> sample=Sample(edge.Curve,id%2==0);sample.RemoveAt(sample.Count-1);outline.AddRange(sample);curves.Add((Curve)edge.Curve.Clone());}
     if(outline.Count<3||SignedArea(outline)<=tolerance*tolerance)continue;
     bool fitted;Region shape=RingRegion(perimeter,curves,out fitted);
     if(shape==null){InvalidContours++;continue;}
     double length=0;foreach(int id in perimeter)length+=Length(edges[id].Curve);
     // A cell thinner than the endpoint uncertainty is a numerical sliver,
     // not a reliably measured region. Report it instead of emitting 0.00 labels.
     if(shape.Area>Math.Max(CoordinateAreaUncertainty(shape,curves),Math.Max(tolerance*tolerance,tolerance*length*4))){Faces.Add(new Face{Shape=shape,Outline=outline,Repaired=UsesRepair(perimeter),Fitted=fitted});if(fitted)FittedContours++;}
     else{UncertainContours++;shape.Dispose();}
    }catch(Autodesk.AutoCAD.Runtime.Exception){InvalidContours++;}finally{foreach(DBObject obj in curves)obj.Dispose();}
   }
   // Subtract disconnected nested loops from their immediate containing cell.
   var shells=new List<Region>();foreach(Face face in Faces)shells.Add((Region)face.Shape.Clone());
   try{
    for(int child=0;child<Faces.Count;child++){
     int parent=-1;
     for(int i=0;i<Faces.Count;i++)if(i!=child&&shells[i].Area>shells[child].Area+tolerance*tolerance&&EnclosesLoop(Faces[i].Outline,Faces[child].Outline))if(parent<0||shells[i].Area<shells[parent].Area)parent=i;
     if(parent>=0){using(var hole=(Region)shells[child].Clone())Faces[parent].Shape.BooleanOperation(BooleanOperationType.BoolSubtract,hole);Faces[parent].Holes.Add(Faces[child].Outline);if(Faces[child].Repaired)Faces[parent].Repaired=true;}
    }
   }finally{foreach(Region shell in shells)shell.Dispose();}
  }
  static int CompareSources(Curve left,Curve right){
   var a=left.GeometricExtents;var b=right.GeometricExtents;
   double[] ak={a.MinPoint.X,a.MinPoint.Y,a.MaxPoint.X,a.MaxPoint.Y,left.StartPoint.X,left.StartPoint.Y,left.EndPoint.X,left.EndPoint.Y,Length(left)};
   double[] bk={b.MinPoint.X,b.MinPoint.Y,b.MaxPoint.X,b.MaxPoint.Y,right.StartPoint.X,right.StartPoint.Y,right.EndPoint.X,right.EndPoint.Y,Length(right)};
   for(int i=0;i<ak.Length;i++){int result=ak[i].CompareTo(bk[i]);if(result!=0)return result;}
   return String.CompareOrdinal(left.GetType().FullName,right.GetType().FullName);
  }
  Region RingRegion(List<int> ring,DBObjectCollection curves,out bool fitted){
   fitted=false;
   try{
    DBObjectCollection regions=Region.CreateFromCurves(curves);
    if(regions.Count==1)return (Region)regions[0];
    foreach(DBObject obj in regions)obj.Dispose();
   }catch(Autodesk.AutoCAD.Runtime.Exception){}
   // Node matching and the ACIS region builder use different tolerances. A
   // topologically closed ring can therefore contain microscopic endpoint gaps.
   // Rebuild only line/arc rings on their already matched nodes; keep arc bulges
   // and reject any displacement larger than the numerical joining tolerance.
   using(var poly=new Polyline()){
    double expected=0,length=0;Point3d origin=nodes[edges[ring[0]].From];
    for(int i=0;i<ring.Count;i++){
     int id=ring[i];Edge edge=edges[id],next=edges[ring[(i+1)%ring.Count]];
     Curve c=edge.Curve;var arc=c as Arc;if(!(c is Line)&&arc==null)return null;
     if(edge.To!=next.From)return null;
     bool forward=id%2==0;Point3d a=nodes[edge.From],b=nodes[edge.To];
     if(a.DistanceTo(forward?c.StartPoint:c.EndPoint)>tolerance||b.DistanceTo(forward?c.EndPoint:c.StartPoint)>tolerance)return null;
     double sweep=arc==null?0:arc.TotalAngle*(forward?1:-1)*(arc.Normal.Z<0?-1:1);
     poly.AddVertexAt(i,new Point2d(a.X-origin.X,a.Y-origin.Y),Math.Tan(sweep/4),0,0);
     expected+=((a.X-origin.X)*(b.Y-origin.Y)-(b.X-origin.X)*(a.Y-origin.Y))/2;
     if(arc!=null)expected+=arc.Radius*arc.Radius*(sweep-Math.Sin(sweep))/2;
     length+=Length(c);
    }
    poly.Closed=true;poly.Elevation=0;
    var input=new DBObjectCollection();input.Add(poly);DBObjectCollection result;
    try{result=Region.CreateFromCurves(input);}catch(Autodesk.AutoCAD.Runtime.Exception){
     Region fallback=FitRingJoints(poly,expected,Math.Max(tolerance*length*4,tolerance*tolerance));
     if(fallback!=null){fallback.TransformBy(Matrix3d.Displacement(origin-Point3d.Origin));fitted=true;JoinedContours++;}return fallback;
    }
    if(result.Count==1){var shape=(Region)result[0];
     if(expected>0&&Math.Abs(shape.Area-expected)<=Math.Max(tolerance*length*4,tolerance*tolerance)) {shape.TransformBy(Matrix3d.Displacement(origin-Point3d.Origin));JoinedContours++;return shape;}
    }
    foreach(DBObject obj in result)obj.Dispose();return null;
   }
  }
  static Region FitRingJoints(Polyline source,double expected,double areaTolerance){
   // Regularize only the immediate neighbourhood of ACIS-rejected joins.
   // The long arc spans keep their bulges; no dense whole-loop tessellation.
   if(expected<=0)return null;
   int vertices=source.NumberOfVertices;if(vertices>2048)return null;var lengths=new double[vertices];
   for(int i=0;i<vertices;i++)lengths[i]=source.GetDistanceAtParameter(i+1)-source.GetDistanceAtParameter(i);
   double limit=Math.Sqrt(areaTolerance/(vertices*8.0));
   foreach(double factor in new[]{.000001,.00001,.0001,.001,.01,.1,1.0}){
    double trim=limit*factor;
    using(var poly=new Polyline()){
     int count=0;
     for(int i=0;i<vertices;i++){
      if(lengths[i]<=trim*2)continue;
      double fraction=Math.Min(.25,trim/lengths[i]);
      Point3d a=source.GetPointAtParameter(i+fraction),b=source.GetPointAtParameter(i+1-fraction);
      double bulge=Math.Tan(Math.Atan(source.GetBulgeAt(i))*(1-2*fraction));
      poly.AddVertexAt(count++,new Point2d(a.X,a.Y),bulge,0,0);
      poly.AddVertexAt(count++,new Point2d(b.X,b.Y),0,0,0);
     }
     if(count<3)continue;
     poly.Closed=true;var input=new DBObjectCollection();input.Add(poly);DBObjectCollection result;
     try{result=Region.CreateFromCurves(input);}catch(Autodesk.AutoCAD.Runtime.Exception){continue;}
     if(result.Count==1){var shape=(Region)result[0];if(Math.Abs(shape.Area-expected)<=areaTolerance)return shape;}
     foreach(DBObject item in result)item.Dispose();
    }
   }
   return null;
  }
  void AddCut(Curve c,Point3dCollection cuts,Point3d p){Point3d q=c.GetClosestPointTo(p,false);if(q.DistanceTo(c.StartPoint)<=tolerance||q.DistanceTo(c.EndPoint)<=tolerance)return;foreach(Point3d other in cuts)if(q.DistanceTo(other)<=tolerance)return;if(++cutCount>10000)throw new InvalidOperationException("边界交点过多，请缩小框选范围。");cuts.Add(q);}
  void AddUnique(Curve c){if(Length(c)<=tolerance){c.Dispose();return;}foreach(Curve other in pieces)if(SameCurve(c,other,tolerance)){c.Dispose();return;}pieces.Add(c);}
  public int Find(Point3d point){
   int result=-1;for(int i=0;i<Faces.Count;i++)if(Contains(Faces[i].Outline,point))if(result<0||Math.Abs(SignedArea(Faces[i].Outline))<Math.Abs(SignedArea(Faces[result].Outline)))result=i;
   foreach(Curve c in pieces)if(point.DistanceTo(c.GetClosestPointTo(point,false))<=tolerance)return -1;return result;
  }
  public void Dispose(){foreach(Curve c in pieces)c.Dispose();foreach(Face f in Faces)f.Shape.Dispose();foreach(Line line in Repairs)line.Dispose();pieces.Clear();Faces.Clear();Repairs.Clear();}
 }
}
