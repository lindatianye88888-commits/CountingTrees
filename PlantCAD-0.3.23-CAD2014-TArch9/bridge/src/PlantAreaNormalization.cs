using System;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  static Point3d Ground(Point3d point){return new Point3d(point.X,point.Y,0);}
  static void NormalizeAreaBoundary(Curve curve,Transaction tr){
   // This user-authorized edit is limited to selected curves on the confirmed boundary layer.
   // A single surrounding transaction rolls it all back if normalization/calculation fails.
   var line=curve as Line;var poly=curve as Polyline;var oldPoly=curve as Polyline2d;var spatial=curve as Polyline3d;
   if(line!=null){line.StartPoint=Ground(line.StartPoint);line.EndPoint=Ground(line.EndPoint);}
   else if(poly!=null&&Math.Abs(Math.Abs(poly.Normal.Z)-1)<1e-10)poly.Elevation=0;
   else if(oldPoly!=null&&Math.Abs(Math.Abs(oldPoly.Normal.Z)-1)<1e-10)oldPoly.Elevation=0;
   else if(spatial!=null){foreach(ObjectId id in spatial){var vertex=(PolylineVertex3d)tr.GetObject(id,OpenMode.ForWrite);vertex.Position=Ground(vertex.Position);}}
   else if(curve is Arc&&Math.Abs(Math.Abs(((Arc)curve).Normal.Z)-1)<1e-10)curve.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-((Arc)curve).Center.Z)));
   else if(curve is Circle&&Math.Abs(Math.Abs(((Circle)curve).Normal.Z)-1)<1e-10)curve.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-((Circle)curve).Center.Z)));
   else if(curve is Ellipse&&Math.Abs(Math.Abs(((Ellipse)curve).Normal.Z)-1)<1e-10)curve.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-((Ellipse)curve).Center.Z)));
   else {
    Extents3d box=curve.GeometricExtents;
    if(Math.Abs(box.MaxPoint.Z-box.MinPoint.Z)<1e-10){if(box.MinPoint.Z!=0)curve.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-box.MinPoint.Z)));}
    else using(var plane=new Plane(Point3d.Origin,Vector3d.ZAxis))using(Curve projected=curve.GetOrthoProjectedCurve(plane)){
     if(projected==null||projected.GetType()!=curve.GetType())throw new InvalidOperationException("边线 "+curve.Handle+" 为倾斜曲线，无法在保持对象类型的同时归零，请先转为平面边线。");
     var spline=curve as Spline;
     if(spline==null)throw new InvalidOperationException("边线 "+curve.Handle+" 为倾斜曲线，请先转为平面边线。");
     // Replace geometry only. DBObject.CopyFrom also replaces the extension dictionary.
     spline.NurbsData=((Spline)projected).NurbsData;
    }
   }
   Extents3d flat=curve.GeometricExtents;
   if(Math.Abs(flat.MinPoint.Z)>1e-6||Math.Abs(flat.MaxPoint.Z)>1e-6)throw new InvalidOperationException("边线 "+curve.Handle+" 未能归零，原始修改已取消。");
   curve.ColorIndex=256;
  }
 }
}
