using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
namespace PlantCADBridge {
 internal sealed partial class PlantAreaGeometry {
  public readonly List<Line> Repairs=new List<Line>();
  sealed class Endpoint {public Point3d Point;public Vector3d Out;public int Node,Component;public double Length;}
  sealed class RepairPlan {public int A,B=-1;public double Score;public List<Line> Lines=new List<Line>();}
  void SplitCurves(List<Curve> original){
   var cuts=new List<Point3dCollection>();foreach(Curve c in original)cuts.Add(new Point3dCollection());
   for(int i=0;i<original.Count;i++)for(int j=i+1;j<original.Count;j++){
    Curve a=original[i],b=original[j];Extents3d ba=a.GeometricExtents,bb=b.GeometricExtents;
    if(ba.MaxPoint.X+tolerance<bb.MinPoint.X||bb.MaxPoint.X+tolerance<ba.MinPoint.X||ba.MaxPoint.Y+tolerance<bb.MinPoint.Y||bb.MaxPoint.Y+tolerance<ba.MinPoint.Y)continue;
    var hits=new Point3dCollection();
    if(!PlanarIntersections(a,b,hits))a.IntersectWith(b,Intersect.OnBothOperands,hits,IntPtr.Zero,IntPtr.Zero);
    foreach(Point3d p in new[]{a.StartPoint,a.EndPoint,b.StartPoint,b.EndPoint})if(p.DistanceTo(a.GetClosestPointTo(p,false))<=tolerance&&p.DistanceTo(b.GetClosestPointTo(p,false))<=tolerance)hits.Add(p);
    foreach(Point3d p in hits){AddCut(a,cuts[i],p);AddCut(b,cuts[j],p);}
   }
   for(int i=0;i<original.Count;i++){
    if(cuts[i].Count==0)AddUnique((Curve)original[i].Clone());
    else {
     // AutoCAD requires cut locations in increasing curve parameter order. Unsorted
     // hits on a reversed/shared edge can produce overlapping or missing pieces.
     var parameters=new List<double>();foreach(Point3d point in cuts[i])parameters.Add(SplitParameter(original[i],point));parameters.Sort();
     foreach(DBObject obj in original[i].GetSplitCurves(new DoubleCollection(parameters.ToArray())))AddUnique((Curve)obj);
    }
   }
  }
  bool PlanarIntersections(Curve a,Curve b,Point3dCollection hits){
   var la=a as Line;var lb=b as Line;var aa=a as Arc;var ab=b as Arc;
   if(la!=null&&lb!=null){
    Vector3d u=la.EndPoint-la.StartPoint,v=lb.EndPoint-lb.StartPoint,w=lb.StartPoint-la.StartPoint;
    double cross=Cross(u,v);if(Math.Abs(cross)>u.Length*v.Length*1e-14){double t=Cross(w,v)/cross,s=Cross(w,u)/cross;
     if(t>=-tolerance/u.Length&&t<=1+tolerance/u.Length&&s>=-tolerance/v.Length&&s<=1+tolerance/v.Length)hits.Add(la.StartPoint+u*Math.Max(0,Math.Min(1,t)));
    }return true;
   }
   if(la!=null&&ab!=null){LineArcIntersections(la,ab,hits);return true;}
   if(lb!=null&&aa!=null){LineArcIntersections(lb,aa,hits);return true;}
   if(aa!=null&&ab!=null){
    Vector3d delta=ab.Center-aa.Center;double distance=delta.Length;if(distance<=tolerance)return true;
    double along=(aa.Radius*aa.Radius-ab.Radius*ab.Radius+distance*distance)/(2*distance);
    double heightSquared=aa.Radius*aa.Radius-along*along;
    double error=(aa.Radius*aa.Radius+ab.Radius*ab.Radius+distance*distance+along*along)*2.2204460492503131e-16*64;
    // Coordinates of nominally tangent curves have already been rounded in the
    // source DWG. Do not turn a sub-tolerance radial error into two remote cuts.
    if(Math.Abs(distance-aa.Radius-ab.Radius)<=tolerance||Math.Abs(distance-Math.Abs(aa.Radius-ab.Radius))<=tolerance)heightSquared=0;
    if(heightSquared < -error)return true;if(Math.Abs(heightSquared)<=error)heightSquared=0;
    Vector3d direction=delta/distance,side=new Vector3d(-direction.Y,direction.X,0);Point3d center=aa.Center+direction*along;
    double height=Math.Sqrt(heightSquared);
    AddPlanarIntersection(aa,ab,center+side*height,hits);if(height>tolerance)AddPlanarIntersection(aa,ab,center-side*height,hits);
    return true;
   }
   return false;
  }
  void LineArcIntersections(Line line,Arc arc,Point3dCollection hits){
   Vector3d u=line.EndPoint-line.StartPoint,w=arc.Center-line.StartPoint;double lengthSquared=u.LengthSqrd;if(lengthSquared==0)return;
   double middle=w.DotProduct(u)/lengthSquared,cross=Cross(w,u);
   double heightSquared=arc.Radius*arc.Radius-cross*cross/lengthSquared;
   double perpendicular=Math.Abs(cross)/Math.Sqrt(lengthSquared);
   double error=(arc.Radius+perpendicular)*(arc.Radius+perpendicular+w.Length)*2.2204460492503131e-16*64;
   if(Math.Abs(Math.Abs(cross)/Math.Sqrt(lengthSquared)-arc.Radius)<=tolerance)heightSquared=0;
   if(heightSquared < -error)return;if(Math.Abs(heightSquared)<=error)heightSquared=0;
   double shift=Math.Sqrt(heightSquared/lengthSquared);
   AddPlanarIntersection(line,arc,line.StartPoint+u*(middle-shift),hits);
   if(shift*u.Length>tolerance)AddPlanarIntersection(line,arc,line.StartPoint+u*(middle+shift),hits);
  }
  void AddPlanarIntersection(Curve a,Curve b,Point3d point,Point3dCollection hits){
   if(point.DistanceTo(a.GetClosestPointTo(point,false))<=tolerance&&point.DistanceTo(b.GetClosestPointTo(point,false))<=tolerance)hits.Add(point);
  }
  double SplitParameter(Curve curve,Point3d point){
   double value;
   var line=curve as Line;var arc=curve as Arc;
   // At survey coordinates, CAD's inverse point lookup can reject a point that
   // GetClosestPointTo just returned. Work in local vectors for lines and arcs.
   if(line!=null){var direction=line.EndPoint-line.StartPoint;
    value=line.StartParam+(point-line.StartPoint).DotProduct(direction)/direction.LengthSqrd*(line.EndParam-line.StartParam);
   }else if(arc!=null){var start=arc.StartPoint-arc.Center;var radial=point-arc.Center;
    double angle=Math.Atan2(start.CrossProduct(radial).DotProduct(arc.Normal),start.DotProduct(radial));if(angle<0)angle+=2*Math.PI;
    value=arc.StartParam+angle/arc.TotalAngle*(arc.EndParam-arc.StartParam);
   }else value=curve.GetParameterAtPoint(point);
   value=Math.Max(curve.StartParam,Math.Min(curve.EndParam,value));
   if(curve.GetPointAtParameter(value).DistanceTo(point)>tolerance)
    throw new InvalidOperationException("切分点无法准确落在"+curve.GetType().Name+"边线上，请检查该处重叠或退化边线。");
   return value;
  }
  static int Root(int[] parent,int n){while(parent[n]!=n){parent[n]=parent[parent[n]];n=parent[n];}return n;}
  static double Cross(Vector3d a,Vector3d b){return a.X*b.Y-a.Y*b.X;}
  List<Line> PlanRepairs(){
   nodes.Clear();var ends=new List<int[]>();var incident=new Dictionary<int,List<int>>();var lengths=new List<double>();
   foreach(Curve c in pieces){int a=Node(c.StartPoint),b=Node(c.EndPoint);ends.Add(new[]{a,b});lengths.Add(Length(c));}
   int[] parent=new int[nodes.Count];for(int i=0;i<parent.Length;i++)parent[i]=i;
   for(int i=0;i<ends.Count;i++){
    int a=ends[i][0],b=ends[i][1];parent[Root(parent,a)]=Root(parent,b);
    foreach(int n in ends[i]){if(!incident.ContainsKey(n))incident[n]=new List<int>();incident[n].Add(i);}
   }
   var compLength=new Dictionary<int,double>();var compEdges=new Dictionary<int,int>();var compNodes=new Dictionary<int,int>();var compOpen=new Dictionary<int,int>();
   for(int i=0;i<parent.Length;i++){int root=Root(parent,i);if(!compNodes.ContainsKey(root)){compNodes[root]=0;compOpen[root]=0;compLength[root]=0;compEdges[root]=0;}compNodes[root]++;if(incident[i].Count==1)compOpen[root]++;}
   for(int i=0;i<pieces.Count;i++){int root=Root(parent,ends[i][0]);compLength[root]+=lengths[i];compEdges[root]++;}
   var open=new List<Endpoint>();
   foreach(var pair in incident)if(pair.Value.Count==1){
    int id=pair.Value[0];Curve c=pieces[id];bool start=ends[id][0]==pair.Key;double d=lengths[id]*1e-5;
    Vector3d outward=start?c.StartPoint-c.GetPointAtDist(d):c.EndPoint-c.GetPointAtDist(lengths[id]-d);
    if(outward.Length>tolerance*1e-3)open.Add(new Endpoint{Point=nodes[pair.Key],Node=pair.Key,Out=outward.GetNormal(),Length=lengths[id],Component=Root(parent,pair.Key)});
   }
   var result=new List<Line>();if(open.Count==0)return result;
   if(open.Count>1600)throw new InvalidOperationException("开放线头过多，请分区识别。");
   lengths.Sort();double median=lengths[lengths.Count/2];Point3d low=nodes[0],high=nodes[0];
   foreach(Point3d p in nodes){low=new Point3d(Math.Min(low.X,p.X),Math.Min(low.Y,p.Y),p.Z);high=new Point3d(Math.Max(high.X,p.X),Math.Max(high.Y,p.Y),p.Z);}
   double diagonal=low.DistanceTo(high),baseGap=Math.Max(tolerance*100,Math.Min(diagonal*.04,median*.15));
   var plans=new List<RepairPlan>();
   for(int i=0;i<open.Count;i++){
    Endpoint a=open[i];
    for(int j=i+1;j<open.Count;j++){
     Endpoint b=open[j];Vector3d vector=b.Point-a.Point;double distance=vector.Length;if(distance<=tolerance)continue;
     Vector3d direction=vector/distance;double forwardA=a.Out.DotProduct(direction),forwardB=b.Out.DotProduct(-direction);
     bool chain=a.Component==b.Component&&compOpen[a.Component]==2&&compEdges[a.Component]==compNodes[a.Component]-1&&compLength[a.Component]>distance*1.6;
     bool band=a.Component!=b.Component&&a.Out.DotProduct(b.Out)>.92&&Math.Abs(forwardA)<.35&&distance<Math.Min(a.Length,b.Length)*.45;
     double limit=Math.Max(baseGap,Math.Min(diagonal*.08,Math.Min(a.Length,b.Length)*.3));
     if(!chain&&!band&&(distance>limit||forwardA<-.2||forwardB<-.2))continue;
     double scale=chain?Math.Max(limit,compLength[a.Component]*.5):band?Math.Max(limit,Math.Min(a.Length,b.Length)*.45):limit;
     var plan=new RepairPlan{A=i,B=j,Score=distance/scale+(chain?.35:band?.25:0)+(2-forwardA-forwardB)*.08};
     double denominator=Cross(a.Out,b.Out);bool corner=false;
     if(Math.Abs(denominator)>1e-6){
      double ta=Cross(vector,b.Out)/denominator,tb=Cross(vector,a.Out)/denominator;
      if(ta>tolerance&&tb>tolerance&&ta+tb<distance*2.5){Point3d meet=a.Point+a.Out*ta;plan.Lines.Add(new Line(a.Point,meet));plan.Lines.Add(new Line(meet,b.Point));corner=true;}
     }
     if(!corner)plan.Lines.Add(new Line(a.Point,b.Point));plans.Add(plan);
    }
    for(int j=0;j<pieces.Count;j++){
     if(ends[j][0]==a.Node||ends[j][1]==a.Node)continue;Curve target=pieces[j];Point3d q=target.GetClosestPointTo(a.Point,false);double distance=q.DistanceTo(a.Point);
     if(distance<=tolerance||q.DistanceTo(target.StartPoint)<=tolerance||q.DistanceTo(target.EndPoint)<=tolerance)continue;
     double limit=Math.Max(baseGap,Math.Min(diagonal*.08,Math.Min(a.Length,Length(target))*.3));
     if(distance>limit)continue;Vector3d direction=(q-a.Point)/distance;double forward=a.Out.DotProduct(direction);if(forward<.15)continue;
     // Extend an incoming straight/tangent direction to the target whenever possible.
     using(var ray=new Line(a.Point,a.Point+a.Out*limit*2)){
      var hits=new Point3dCollection();ray.IntersectWith(target,Intersect.ExtendThis,hits,IntPtr.Zero,IntPtr.Zero);
      double best=limit*2;
      foreach(Point3d hit in hits){Vector3d v=hit-a.Point;double projection=v.DotProduct(a.Out);if(projection>tolerance&&projection<best){best=projection;q=hit;}}
     }
     distance=q.DistanceTo(a.Point);if(distance>limit*2)continue;
     var plan=new RepairPlan{A=i,Score=distance/limit+(1-forward)*.15};plan.Lines.Add(new Line(a.Point,q));plans.Add(plan);
    }
   }
   plans.Sort((a,b)=>a.Score.CompareTo(b.Score));var consumed=new HashSet<int>();
   foreach(RepairPlan plan in plans){
    if(consumed.Contains(plan.A)||(plan.B>=0&&consumed.Contains(plan.B))){foreach(Line l in plan.Lines)l.Dispose();continue;}
    consumed.Add(plan.A);if(plan.B>=0)consumed.Add(plan.B);result.AddRange(plan.Lines);
    if(result.Count+Repairs.Count>800){foreach(Line l in result)l.Dispose();throw new InvalidOperationException("需补线的位置过多，请按区分批识别。");}
   }
   return result;
  }
  bool UsesRepair(List<int> ring){
   foreach(int id in ring){Curve c=edges[id].Curve;if(!(c is Line))continue;
    foreach(Line repair in Repairs)if(c.StartPoint.DistanceTo(repair.GetClosestPointTo(c.StartPoint,false))<=tolerance&&c.EndPoint.DistanceTo(repair.GetClosestPointTo(c.EndPoint,false))<=tolerance)return true;
   }return false;
  }
  static double SegmentDistanceSquared(Point3d p,Point3d a,Point3d b){
   double dx=b.X-a.X,dy=b.Y-a.Y,length=dx*dx+dy*dy;
   double t=length>0?Math.Max(0,Math.Min(1,((p.X-a.X)*dx+(p.Y-a.Y)*dy)/length)):0;
   double x=a.X+t*dx-p.X,y=a.Y+t*dy-p.Y;return x*x+y*y;
  }
  bool EnclosesLoop(List<Point3d> outer,List<Point3d> inner){
   foreach(Point3d p in inner){if(!Contains(outer,p))return false;Point3d previous=outer[outer.Count-1];foreach(Point3d q in outer){if(SegmentDistanceSquared(p,previous,q)<=tolerance*tolerance)return false;previous=q;}}
   return true;
  }
  static bool InFace(Face face,Point3d p){if(!Contains(face.Outline,p))return false;foreach(var hole in face.Holes)if(Contains(hole,p))return false;return true;}
  static double BorderDistance(Face face,Point3d point){
   double best=Double.MaxValue;var rings=new List<List<Point3d>>{face.Outline};rings.AddRange(face.Holes);
   foreach(var ring in rings){Point3d previous=ring[ring.Count-1];foreach(Point3d p in ring){best=Math.Min(best,SegmentDistanceSquared(point,previous,p));previous=p;}}
   return (InFace(face,point)?1:-1)*Math.Sqrt(best);
  }
  public static double FaceClearance(Face face,Point3d point){return Math.Max(0,BorderDistance(face,point));}
  sealed class LabelCell {public Point3d Point;public double Half,Distance,Upper;}
  static void HeapPush(List<LabelCell> heap,LabelCell cell){int n=heap.Count;heap.Add(cell);while(n>0){int p=(n-1)/2;if(heap[p].Upper>=cell.Upper)break;heap[n]=heap[p];n=p;}heap[n]=cell;}
  static LabelCell HeapPop(List<LabelCell> heap){LabelCell top=heap[0],last=heap[heap.Count-1];heap.RemoveAt(heap.Count-1);int i=0;while(i*2+1<heap.Count){int c=i*2+1;if(c+1<heap.Count&&heap[c+1].Upper>heap[c].Upper)c++;if(heap[c].Upper<=last.Upper)break;heap[i]=heap[c];i=c;}if(heap.Count>0)heap[i]=last;return top;}
  public Point3d InteriorPoint(int index){
   Face face=Faces[index];double loX=Double.MaxValue,loY=Double.MaxValue,hiX=Double.MinValue,hiY=Double.MinValue,z=face.Outline[0].Z;
   foreach(Point3d p in face.Outline){loX=Math.Min(loX,p.X);loY=Math.Min(loY,p.Y);hiX=Math.Max(hiX,p.X);hiY=Math.Max(hiY,p.Y);}
   var best=new LabelCell{Point=new Point3d((loX+hiX)/2,(loY+hiY)/2,z)};best.Distance=BorderDistance(face,best.Point);
   double width=hiX-loX,height=hiY-loY,perimeter=0;Point3d prev=face.Outline[face.Outline.Count-1];
   foreach(Point3d p in face.Outline){perimeter+=prev.DistanceTo(p);prev=p;}
   double precision=Math.Max(tolerance*10,Math.Min(Math.Min(width,height)*.03,face.Area/Math.Max(perimeter,tolerance)*.2)),size=Math.Max(width,height)/8;
   prev=face.Outline[face.Outline.Count-1];
   foreach(Point3d p in face.Outline){Vector3d v=p-prev;if(v.Length>tolerance){double offset=Math.Min(v.Length*.01,face.Area/Math.Max(perimeter,tolerance)*.2);
    for(int k=0;k<6;k++){Point3d candidate=prev+v*.5+new Vector3d(-v.Y,v.X,0).GetNormal()*offset;double d=BorderDistance(face,candidate);if(d>best.Distance)best=new LabelCell{Point=candidate,Distance=d};offset/=2;}}
    prev=p;
   }
   var heap=new List<LabelCell>();
   if(size<=tolerance)return best.Point;
   for(double x=loX;x<hiX;x+=size)for(double y=loY;y<hiY;y+=size){var c=new LabelCell{Point=new Point3d(x+size/2,y+size/2,z),Half=size/2};c.Distance=BorderDistance(face,c.Point);c.Upper=c.Distance+c.Half*Math.Sqrt(2);HeapPush(heap,c);}
   int visits=0;
   while(heap.Count>0&&visits++<20000){LabelCell c=HeapPop(heap);if(c.Distance>best.Distance)best=c;if(c.Upper-best.Distance<=precision)continue;
    double h=c.Half/2;foreach(int x in new[]{-1,1})foreach(int y in new[]{-1,1}){var child=new LabelCell{Point=c.Point+new Vector3d(x*h,y*h,0),Half=h};child.Distance=BorderDistance(face,child.Point);child.Upper=child.Distance+h*Math.Sqrt(2);HeapPush(heap,child);}}
   if(best.Distance<=0)throw new InvalidOperationException("区域过窄，无法可靠确定内部标注点。");return best.Point;
  }
 }
}
