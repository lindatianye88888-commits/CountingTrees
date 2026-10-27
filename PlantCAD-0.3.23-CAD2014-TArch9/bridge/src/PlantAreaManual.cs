using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  static void AddManualCurve(Entity source,List<Curve> curves) {
   // Work on planar copies only; manual area measurement never edits source geometry.
   if(source is Region||source is Polyline2d||source is Polyline3d) {
    var pieces=new DBObjectCollection();
    try{source.Explode(pieces);foreach(DBObject piece in pieces){var e=piece as Entity;if(e!=null)AddManualCurve(e,curves);}}
    finally{foreach(DBObject piece in pieces)piece.Dispose();}
    return;
   }
   var curve=source as Curve;
   if(curve==null)throw new ArgumentException("请选择闭合多段线、圆、椭圆、样条或面域；散线可用框选边线辅助。");
   using(var plane=new Plane(Point3d.Origin,Vector3d.ZAxis)) {
    Extents3d box=curve.GeometricExtents;
    if(Math.Abs(box.MaxPoint.Z-box.MinPoint.Z)<1e-8) {
     var copy=(Curve)curve.Clone();copy.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-box.MinPoint.Z)));curves.Add(copy);
    }else {
     Curve copy=curve.GetOrthoProjectedCurve(plane);
     if(copy==null)throw new ArgumentException("此边线不能得到有效平面投影，请先整理边界。");
     curves.Add(copy);
    }
   }
  }
  static ResultBuffer ManualAreaBatch(List<Curve> curves,string target,Region exactRegion,bool single) {
   if(curves.Count==0)throw new ArgumentException("没有可计算的闭合边线。");
   double extent=1;foreach(Curve c in curves)extent=Math.Max(extent,(c.GeometricExtents.MaxPoint-c.GeometricExtents.MinPoint).Length);
   using(var geometry=new PlantAreaGeometry(curves,Math.Max(1e-7,extent*1e-9),false)) {
    if(geometry.Faces.Count==0)throw new ArgumentException("边界尚未真正闭合或已退化；请补齐缺口，或框选组成围合的全部边线。");
    if(single&&exactRegion==null&&geometry.Faces.Count!=1)throw new ArgumentException("所点边界存在自交或多个色块，请用框选边线确定。");
    var values=new List<TypedValue>{new TypedValue((int)LispDataType.Text,"AREA_BATCH")};int added=0;
    for(int i=0;i<geometry.Faces.Count;i++) {
     var face=geometry.Faces[i];
     if(exactRegion!=null) {
      double tolerance=Math.Max(1e-8,exactRegion.Area*1e-8);
      if(Math.Abs(face.Area-exactRegion.Area)>tolerance)continue;
      using(var overlap=(Region)face.Shape.Clone())using(var original=(Region)exactRegion.Clone()) {
       overlap.BooleanOperation(BooleanOperationType.BoolIntersect,original);
       if(overlap.IsNull||Math.Abs(overlap.Area-exactRegion.Area)>tolerance)continue;
      }
     }
     Point3d anchor=geometry.InteriorPoint(i);
     string handle=AppendAreaRegion(face.Shape,target,true);
     values.Add(new TypedValue((int)LispDataType.ListBegin));values.Add(new TypedValue((int)LispDataType.Text,handle));
     values.Add(new TypedValue((int)LispDataType.Point3d,anchor));values.Add(new TypedValue((int)LispDataType.Int32,0));
     values.Add(new TypedValue((int)LispDataType.Double,PlantAreaGeometry.FaceClearance(face,anchor)));values.Add(new TypedValue((int)LispDataType.Int32,face.Fitted?1:0));values.Add(new TypedValue((int)LispDataType.ListEnd));added++;
    }
    if(added==0)throw new ArgumentException("未得到与所点边界一致的面积，请检查内孔或自交。");
    return new ResultBuffer(values.ToArray());
   }
  }
  [LispFunction("pl:native-area-manual")]
  public ResultBuffer ManualArea(ResultBuffer args) {
   var curves=new List<Curve>();Region exact=null;
   try {
    var v=OutputArguments(args);if(v.Count!=2)throw new ArgumentException("手动面积参数无效。");
    var handles=v[0] as List<object>;if(handles==null||handles.Count==0)throw new ArgumentException("请先选择边界。");
    string target=Convert.ToString(v[1]);Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     foreach(object h in handles) {
      var entity=tr.GetObject(OutputId(db,Convert.ToString(h)),OpenMode.ForRead) as Entity;
      if(entity==null||entity.OwnerId!=db.CurrentSpaceId)throw new ArgumentException("请选择当前空间中的边界。");
      if(handles.Count==1&&entity is Region) {
       exact=(Region)entity.Clone();Extents3d box=exact.GeometricExtents;
       if(Math.Abs(box.MaxPoint.Z-box.MinPoint.Z)>1e-8)throw new ArgumentException("请先将倾斜面域转为平面边界。");
       exact.TransformBy(Matrix3d.Displacement(new Vector3d(0,0,-box.MinPoint.Z)));
      }
      AddManualCurve(entity,curves);
     }
    }
    return ManualAreaBatch(curves,target,exact,handles.Count==1);
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
   finally{foreach(Curve c in curves)c.Dispose();if(exact!=null)exact.Dispose();}
  }
 }
}
