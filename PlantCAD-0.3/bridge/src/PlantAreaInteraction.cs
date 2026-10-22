using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  static PlantAreaGeometry areaGeometry;
  static Document areaDocument;
  static string areaLayer;
  static readonly HashSet<int> chosenFaces=new HashSet<int>();
  static void EndAreaSession(){if(areaGeometry!=null)areaGeometry.Dispose();areaGeometry=null;areaDocument=null;chosenFaces.Clear();}
  static bool Managed(Entity e){using(ResultBuffer data=e.GetXDataForApplication("PLANTCAD01"))return data!=null;}
  static bool Yellow(Entity e,Transaction tr){var color=e.Color;if(color.IsByLayer)color=((LayerTableRecord)tr.GetObject(e.LayerId,OpenMode.ForRead)).Color;return color.ColorIndex==2||(color.Red>220&&color.Green>220&&color.Blue<70);}
  [LispFunction("pl:native-area-begin")]
  public ResultBuffer BeginAreaSession(ResultBuffer args){
   try{return PrepareAreaSession(args);}catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  ResultBuffer PrepareAreaSession(ResultBuffer args){
   // Interactive selection belongs to AutoLISP. This function only consumes explicit handles.
   EndAreaSession();Document doc=AcadApp.DocumentManager.MdiActiveDocument;Editor ed=doc.Editor;
   if(args==null)throw new ArgumentException("缺少已确认的边界选择，请从布置菜单重新识别。");
   TypedValue[] values=args.AsArray();int cursor=0;
   if(values.Length==0||values[cursor++].TypeCode!=(int)LispDataType.ListBegin)throw new ArgumentException("无效的边界选择列表。");
   var selected=new HashSet<ObjectId>();
   while(cursor<values.Length&&values[cursor].TypeCode!=(int)LispDataType.ListEnd){
    long number;ObjectId id;TypedValue value=values[cursor++];
    if(value.TypeCode!=(int)LispDataType.Text||!Int64.TryParse(Convert.ToString(value.Value),System.Globalization.NumberStyles.HexNumber,System.Globalization.CultureInfo.InvariantCulture,out number))
     throw new ArgumentException("边界对象编号无效。");
    if(doc.Database.TryGetObjectId(new Handle(number),out id)&&!id.IsErased)selected.Add(id);
   }
   if(cursor>=values.Length)throw new ArgumentException("边界选择列表未结束。");cursor++;
   string requested=cursor<values.Length&&values[cursor].TypeCode==(int)LispDataType.Text?Convert.ToString(values[cursor++].Value):"";
   if(cursor!=values.Length)throw new ArgumentException("边界选择参数不匹配。");
   var yellow=new HashSet<string>();var byLayer=new Dictionary<string,List<ObjectId>>();int skipped=0;
   try{
    using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
     foreach(ObjectId id in selected){
      var entity=tr.GetObject(id,OpenMode.ForRead) as Curve;
      if(entity==null||entity.OwnerId!=doc.Database.CurrentSpaceId||Managed(entity)||!(entity is Line||entity is Arc||entity is Polyline||entity is Polyline2d||entity is Polyline3d||entity is Spline||entity is Circle||entity is Ellipse)){skipped++;continue;}
      if(!byLayer.ContainsKey(entity.Layer))byLayer[entity.Layer]=new List<ObjectId>();byLayer[entity.Layer].Add(id);
      if(Yellow(entity,tr))yellow.Add(entity.Layer);
     }
     if(byLayer.Count==0)throw new InvalidOperationException("选中的对象没有可计算的原始边线，请框选 LINE、PLINE 或 SPLINE 等曲线；植物图块和既有面积标注会跳过。");
     areaLayer=null;
     if(!String.IsNullOrEmpty(requested))areaLayer=requested;
     else if(yellow.Count==1){foreach(string name in yellow)areaLayer=name;}
     else if(byLayer.Count==1){foreach(string name in byLayer.Keys)areaLayer=name;}
     else {
      ed.WriteMessage("\n框选包含多个候选边线图层，请点一条灌木边线确认图层。其他图层继续显示。");
      return new ResultBuffer(new TypedValue((int)LispDataType.Text,"AREA_PICK_LAYER"));
     }
     if(!byLayer.ContainsKey(areaLayer))throw new InvalidOperationException("框选范围中没有该图层的有效原始曲线，请点框选范围内的灌木边线。");
     var sourceLayer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(doc.Database.LayerTableId,OpenMode.ForRead))[areaLayer],OpenMode.ForRead);
     if(sourceLayer.IsLocked)throw new InvalidOperationException("灌木边线图层已锁定："+areaLayer+"；请解锁后再自动归零及统一颜色。");
     var candidates=new List<Curve>();
     try {
      foreach(ObjectId id in byLayer[areaLayer]){
       var curve=(Curve)tr.GetObject(id,OpenMode.ForWrite);
       NormalizeAreaBoundary(curve,tr);candidates.Add((Curve)curve.Clone());
      }
     ed.WriteMessage("\n已确认 "+selected.Count+" 个对象；采用图层 "+areaLayer+" 的 "+candidates.Count+" 条边线进行几何计算（跳过 "+skipped+" 个非边界对象）。");
     int otherLayers=0;foreach(var entry in byLayer)if(entry.Key!=areaLayer)otherLayers+=entry.Value.Count;
     if(otherLayers>0)ed.WriteMessage("\n另有 "+otherLayers+" 条其他图层边线未参与本次计算；围合跨图层时可用“手动补面积→框选组成边线”。");
     // Numerical tolerance is separate from adaptive recovery on normalized detached copies.
     double extent=1;foreach(Curve c in candidates){Extents3d ex=c.GeometricExtents;extent=Math.Max(extent,(ex.MaxPoint-ex.MinPoint).Length);}
     areaGeometry=new PlantAreaGeometry(candidates,Math.Max(1e-7,extent*1e-9));areaDocument=doc;
     tr.Commit();
     ed.WriteMessage("\n已将所选灌木边线标高归零，颜色统一为随图层；其余图层及未选边线保持原样。可用 U 撤销。");
     }finally{foreach(Curve curve in candidates)curve.Dispose();}
    }
    double total=0;foreach(var face in areaGeometry.Faces)total+=face.Area;
    ed.WriteMessage("\n已按原线完成几何计算，合计："+total.ToString("0.######")+" 图纸单位²（尚未换算平方米）。");
     ed.WriteMessage("\n已识别图层："+areaLayer+"；闭合区域："+areaGeometry.Faces.Count+" 个；开放端点："+areaGeometry.OpenEnds+" 个（含多余尾线）；推定连接："+areaGeometry.Repairs.Count+" 段。将自动标注全部可识别区域。");
    if(areaGeometry.JoinedContours>0)ed.WriteMessage("\n另有 "+areaGeometry.JoinedContours+" 个闭环按数值容差统一微小接缝后生成面积；原始边线形状不变。");
    if(areaGeometry.FittedContours>0)ed.WriteMessage("\n其中 "+areaGeometry.FittedContours+" 处曲线接缝做了有面积误差上限的局部拟合，主要圆弧保留；可在范围属性中核对。");
    if(areaGeometry.UncertainContours>0)ed.WriteMessage("\n另有 "+areaGeometry.UncertainContours+" 个极窄轮廓低于当前几何精度，未当作有效种植面积；请核对该处重复线或微小错缝。");
    if(areaGeometry.InvalidContours>0)ed.WriteMessage("\n另有 "+areaGeometry.InvalidContours+" 处重叠或退化轮廓未得到有效面积，原线保留供核对。");
    if(areaGeometry.Faces.Count==0)ed.WriteMessage("\n自动恢复后仍未得到有效面积，缺失边界可能存在多种接法；请扩大框选范围核对。");
    return new ResultBuffer(new TypedValue((int)LispDataType.Int32,areaGeometry.Faces.Count));
   }catch{EndAreaSession();throw;}
  }
  [LispFunction("pl:native-label-lines")]
  public ResultBuffer ReadLabelLines(ResultBuffer args){
   var lines=new List<TypedValue>();
   try {
    long number;string handle=Convert.ToString(args.AsArray()[0].Value);
    if(!Int64.TryParse(handle,System.Globalization.NumberStyles.HexNumber,System.Globalization.CultureInfo.InvariantCulture,out number))return null;
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;ObjectId id;
    if(!db.TryGetObjectId(new Handle(number),out id)||id.IsErased)return null;
    using(Transaction tr=db.TransactionManager.StartTransaction()){
     Entity entity=tr.GetObject(id,OpenMode.ForRead) as Entity;int visited=0;
     CollectAreaLabelLines(entity,tr,lines,0,ref visited);
    }
   }catch(System.Exception ex){AcadApp.DocumentManager.MdiActiveDocument.Editor.WriteMessage("\n无法读取此标注文字："+ex.Message);}
   return lines.Count>0?new ResultBuffer(lines.ToArray()):null;
  }
  static void CollectAreaLabelLines(Entity entity,Transaction tr,List<TypedValue> lines,int depth,ref int visited){
   if(entity==null||depth>3||visited++>=128)return;
   var text=entity as DBText;var mtext=entity as MText;var leader=entity as MLeader;
   string content=text!=null?text.TextString:mtext!=null?mtext.Text:null;
   if(leader!=null&&leader.ContentType==ContentType.MTextContent){using(MText label=leader.MText)if(label!=null)content=label.Text;}
   if(content!=null){foreach(string line in content.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries))if(line.Trim().Length>0)lines.Add(new TypedValue((int)LispDataType.Text,line.Trim()));return;}
   var block=entity as BlockReference;
   if(block!=null)foreach(ObjectId id in block.AttributeCollection)CollectAreaLabelLines(tr.GetObject(id,OpenMode.ForRead) as Entity,tr,lines,depth+1,ref visited);
   // Loaded third-party annotations may expose ordinary text through Explode.
   // These are transient copies only; the source annotation is never exploded in the drawing.
   var pieces=new DBObjectCollection();
   try{entity.Explode(pieces);foreach(DBObject piece in pieces)if(visited<128)CollectAreaLabelLines(piece as Entity,tr,lines,depth+1,ref visited);}
   catch(Autodesk.AutoCAD.Runtime.Exception){}
   finally{foreach(DBObject piece in pieces)piece.Dispose();}
  }
  static Point3d AreaPoint(TypedValue[] v,ref int cursor){
   if(v[cursor].Value is Point3d)return (Point3d)v[cursor++].Value;
   if(v[cursor++].TypeCode!=(int)LispDataType.ListBegin)throw new ArgumentException("无效区域点。");
   var p=new Point3d(Convert.ToDouble(v[cursor++].Value),Convert.ToDouble(v[cursor++].Value),Convert.ToDouble(v[cursor++].Value));
   if(v[cursor++].TypeCode!=(int)LispDataType.ListEnd)throw new ArgumentException("无效区域点。");return p;
  }
  [LispFunction("pl:native-area-at")]
  public ResultBuffer AreaAtPoint(ResultBuffer args){
   try{return CreateAreaAtPoint(args);}catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  ResultBuffer CreateAreaAtPoint(ResultBuffer args){
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(areaGeometry==null||!Object.ReferenceEquals(doc,areaDocument))throw new InvalidOperationException("面积识别会话已结束，请重新框选。");
   TypedValue[] v=args.AsArray();int cursor=0;Point3d point=AreaPoint(v,ref cursor);string target=Convert.ToString(v[cursor].Value);
   int index=areaGeometry.Find(point);
   if(index<0){doc.Editor.WriteMessage("\n此处没有可识别的闭合色块；请点区域内部并检查缺口。");return null;}
   string handle=AppendAreaFace(index,target);
   return handle==null?null:new ResultBuffer(new TypedValue((int)LispDataType.Text,handle));
  }
  string AppendAreaFace(int index,string target){return AppendAreaFace(index,target,false);}
  string AppendAreaFace(int index,string target,bool reuseExisting){
   bool created;return AppendAreaFace(index,target,reuseExisting,out created);
  }
  string AppendAreaFace(int index,string target,bool reuseExisting,out bool created){
   created=false;
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(chosenFaces.Contains(index)){doc.Editor.WriteMessage("\n该色块本次已经计算，已跳过重复点击。");return null;}
   string handle=AppendAreaRegion(areaGeometry.Faces[index].Shape,target,reuseExisting,out created);
   chosenFaces.Add(index);return handle;
  }
  static string AppendAreaRegion(Region face,string target,bool reuseExisting){
   bool created;return AppendAreaRegion(face,target,reuseExisting,out created);
  }
  static string AppendAreaRegion(Region face,string target,bool reuseExisting,out bool created){
   created=false;
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;string handle;
   using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
    var layers=(LayerTable)tr.GetObject(doc.Database.LayerTableId,OpenMode.ForRead);
    var layer=(LayerTableRecord)tr.GetObject(layers[target],OpenMode.ForRead);
    if(layer.IsLocked||layer.IsOff||layer.IsFrozen)throw new InvalidOperationException("计算边界图层已锁定或隐藏，请先检查图层。");
    var space=(BlockTableRecord)tr.GetObject(doc.Database.CurrentSpaceId,OpenMode.ForWrite);
    foreach(ObjectId id in space){
     var old=tr.GetObject(id,OpenMode.ForRead) as Region;if(old==null||!Managed(old))continue;
     Extents3d bounds=face.GeometricExtents,previous=old.GeometricExtents;
     double scale=(bounds.MaxPoint-bounds.MinPoint).Length;
     double coordinate=Math.Max(Math.Max(Math.Abs(bounds.MinPoint.X),Math.Abs(bounds.MinPoint.Y)),Math.Max(Math.Abs(bounds.MaxPoint.X),Math.Abs(bounds.MaxPoint.Y)));
     double pointTolerance=Math.Max(1e-7,Math.Max(scale*1e-9,coordinate*2.2204460492503131e-16*16));
     // This is only a broad-phase filter. Old ACIS bodies can have slightly
     // different endpoint extents after normalization; the local intersection
     // or full-boundary comparison below must make the actual reuse decision.
     if(bounds.MinPoint.DistanceTo(previous.MinPoint)>pointTolerance*32||bounds.MaxPoint.DistanceTo(previous.MaxPoint)>pointTolerance*32)continue;
     double eps=Math.Max(Math.Max(1e-8,face.Area*1e-8),pointTolerance*scale*8);
     if(Math.Abs(old.Area-face.Area)>eps)continue;
     bool same=false;
     try{using(var overlap=(Region)old.Clone())using(var other=(Region)face.Clone()){
      // Compare in the same local frame used for construction. At large survey
      // coordinates an otherwise identical thin cell can fail a world-space
      // boolean and be inserted again on the next scan.
      Point3d origin=face.GeometricExtents.MinPoint;
      var shift=Matrix3d.Displacement(new Vector3d(-origin.X,-origin.Y,-origin.Z));
      overlap.TransformBy(shift);other.TransformBy(shift);
      double localArea=other.Area;
      overlap.BooleanOperation(BooleanOperationType.BoolIntersect,other);
      same=!overlap.IsNull&&Math.Abs(overlap.Area-localArea)<=eps;
     }}catch(Autodesk.AutoCAD.Runtime.Exception){}
     if(!same)same=SameAreaBoundary(old,face,pointTolerance*4);
     if(same){doc.Editor.WriteMessage(reuseExisting?"\n该区域已有面积记录，将检查并补齐区内文字。":"\n该区域已有面积记录，已跳过。可在统计中查看。");return reuseExisting?old.Handle.ToString():null;}
    }
    var region=(Region)face.Clone();region.SetDatabaseDefaults(doc.Database);region.LayerId=layer.ObjectId;region.ColorIndex=256;
    space.AppendEntity(region);tr.AddNewlyCreatedDBObject(region,true);handle=region.Handle.ToString();tr.Commit();created=true;
   }
   return handle;
  }
  static bool SameAreaBoundary(Region a,Region b,double tolerance){
   var first=new DBObjectCollection();var second=new DBObjectCollection();
   try{
    Point3d origin=b.GeometricExtents.MinPoint;var shift=Matrix3d.Displacement(new Vector3d(-origin.X,-origin.Y,-origin.Z));
    using(var left=(Region)a.Clone())using(var right=(Region)b.Clone()){
     left.TransformBy(shift);right.TransformBy(shift);
     if(!CollectAreaBoundary(left,first,0)||!CollectAreaBoundary(right,second,0))return false;
    }
    // ACIS closest-point queries can fail even on two identical very short
    // fitted joins. Compare complete primitive definitions before distance
    // sampling; retain the latter for geometrically equal split boundaries.
    if(SameBoundaryPrimitives(first,second,tolerance))return true;
    return BoundaryNear(first,second,tolerance)&&BoundaryNear(second,first,tolerance);
   }catch(Autodesk.AutoCAD.Runtime.Exception){return false;}
   finally{foreach(DBObject c in first)c.Dispose();foreach(DBObject c in second)c.Dispose();}
  }
  static bool SameBoundaryPrimitives(DBObjectCollection first,DBObjectCollection second,double tolerance){
   if(first.Count!=second.Count||first.Count==0)return false;var matched=new bool[second.Count];
   foreach(Curve a in first){bool found=false;
    for(int i=0;i<second.Count;i++)if(!matched[i]){
     var b=second[i] as Curve;if(b==null||a.GetType()!=b.GetType())continue;
     var circle=a as Circle;var otherCircle=b as Circle;
     if(circle!=null){if(circle.Center.DistanceTo(otherCircle.Center)>tolerance||Math.Abs(circle.Radius-otherCircle.Radius)>tolerance)continue;}
     else{
      if(!(a is Line)&&!(a is Arc))return false;
      bool ends=a.StartPoint.DistanceTo(b.StartPoint)<=tolerance&&a.EndPoint.DistanceTo(b.EndPoint)<=tolerance;
      bool reverse=a.StartPoint.DistanceTo(b.EndPoint)<=tolerance&&a.EndPoint.DistanceTo(b.StartPoint)<=tolerance;
      if(!ends&&!reverse)continue;
      var arc=a as Arc;var otherArc=b as Arc;
      if(arc!=null&&(arc.Center.DistanceTo(otherArc.Center)>tolerance||Math.Abs(arc.Radius-otherArc.Radius)>tolerance||a.GetPointAtParameter((a.StartParam+a.EndParam)/2).DistanceTo(b.GetPointAtParameter((b.StartParam+b.EndParam)/2))>tolerance))continue;
     }
     matched[i]=true;found=true;break;
    }
    if(!found)return false;
   }return true;
  }
  static bool CollectAreaBoundary(Entity source,DBObjectCollection target,int depth){
   if(depth>8||target.Count>4096)return false;
   var curve=source as Curve;if(curve!=null){target.Add((Curve)curve.Clone());return true;}
   if(!(source is Region))return false;
   // A region with disconnected components can explode into regions first.
   var parts=new DBObjectCollection();
   try{source.Explode(parts);if(parts.Count==0)return false;
    foreach(DBObject part in parts){var entity=part as Entity;if(entity==null||!CollectAreaBoundary(entity,target,depth+1))return false;}return true;
   }finally{foreach(DBObject part in parts)part.Dispose();}
  }
  static bool BoundaryNear(DBObjectCollection source,DBObjectCollection target,double tolerance){
   if(source.Count==0||target.Count==0)return false;
   foreach(DBObject item in source){
    var curve=item as Curve;if(!(curve is Line)&&!(curve is Arc)&&!(curve is Circle))return false;
    for(int i=0;i<=8;i++){
     Point3d point=curve.GetPointAtParameter(curve.StartParam+(curve.EndParam-curve.StartParam)*i/8.0);bool found=false;
     foreach(DBObject other in target){var candidate=other as Curve;if(candidate==null)return false;if(point.DistanceTo(candidate.GetClosestPointTo(point,false))<=tolerance){found=true;break;}}
     if(!found)return false;
    }
   }return true;
  }
  [LispFunction("pl:native-area-export-all")]
  public ResultBuffer ExportAllAreas(ResultBuffer args){
   try{
    Document doc=AcadApp.DocumentManager.MdiActiveDocument;
    if(areaGeometry==null||!Object.ReferenceEquals(doc,areaDocument))throw new InvalidOperationException("面积识别会话已结束。");
    string target=Convert.ToString(args.AsArray()[0].Value);
    var values=new List<TypedValue>{new TypedValue((int)LispDataType.Text,"AREA_BATCH")};int failed=0,created=0,reused=0;
    for(int i=0;i<areaGeometry.Faces.Count;i++){
     try{
      Point3d point=areaGeometry.InteriorPoint(i);double radius=PlantAreaGeometry.FaceClearance(areaGeometry.Faces[i],point);
      bool isNew;string handle=AppendAreaFace(i,target,true,out isNew);if(handle==null)continue;
      values.Add(new TypedValue((int)LispDataType.ListBegin));values.Add(new TypedValue((int)LispDataType.Text,handle));
      values.Add(new TypedValue((int)LispDataType.Point3d,point));values.Add(new TypedValue((int)LispDataType.Int32,areaGeometry.Faces[i].Repaired?1:0));
      values.Add(new TypedValue((int)LispDataType.Double,radius));values.Add(new TypedValue((int)LispDataType.Int32,areaGeometry.Faces[i].Fitted?1:0));values.Add(new TypedValue((int)LispDataType.ListEnd));if(isNew)created++;else reused++;
     }catch(System.Exception ex){failed++;doc.Editor.WriteMessage("\n区域 "+(i+1)+" 未生成："+ex.Message);}
    }
    if(created>0&&areaGeometry.Repairs.Count>0){try{AppendRepairGuides(doc);}catch(System.Exception ex){doc.Editor.WriteMessage("\n补线辅助图层未生成："+ex.Message+"；推定区域仍以约数标注。");}}
    doc.Editor.WriteMessage("\n新建 "+created+" 个区域；复查已有 "+reused+" 个区域；失败 "+failed+" 个。原线保留，带约数的区域使用了推定补线。");
    return new ResultBuffer(values.ToArray());
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  static void AppendRepairGuides(Document doc){
   Database db=doc.Database;
   using(Transaction tr=db.TransactionManager.StartTransaction()){
    var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForRead);
    const string name="PL_面积_推定补线";if(!layers.Has(name))return;
    var layer=(LayerTableRecord)tr.GetObject(layers[name],OpenMode.ForRead);if(layer.IsLocked||layer.IsOff||layer.IsFrozen)return;
    var apps=(RegAppTable)tr.GetObject(db.RegAppTableId,OpenMode.ForRead);
    if(!apps.Has("PLANTCAD01")){apps.UpgradeOpen();var app=new RegAppTableRecord{Name="PLANTCAD01"};apps.Add(app);tr.AddNewlyCreatedDBObject(app,true);}
    var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);
    foreach(Line repair in areaGeometry.Repairs){var line=(Line)repair.Clone();line.SetDatabaseDefaults(db);line.LayerId=layer.ObjectId;line.ColorIndex=256;space.AppendEntity(line);tr.AddNewlyCreatedDBObject(line,true);
     using(var data=new ResultBuffer(new TypedValue(1001,"PLANTCAD01"),new TypedValue(1000,"AREA_REPAIR")))line.XData=data;
    }tr.Commit();
   }
  }
  [LispFunction("pl:native-area-value")]
  public ResultBuffer ReadAreaValue(ResultBuffer args){
   string handle=Convert.ToString(args.AsArray()[0].Value);long number;
   if(!Int64.TryParse(handle,System.Globalization.NumberStyles.HexNumber,System.Globalization.CultureInfo.InvariantCulture,out number))return null;
   Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
   using(Transaction tr=db.TransactionManager.StartTransaction()){
    ObjectId id; if(!db.TryGetObjectId(new Handle(number),out id)||id.IsErased)return null;
    DBObject obj=tr.GetObject(id,OpenMode.ForRead);double area=0;
    var region=obj as Region;var poly=obj as Polyline;
    if(region!=null)area=region.Area;else if(poly!=null&&poly.Closed)area=poly.Area;
    if(area<=0)return null;
    return new ResultBuffer(new TypedValue((int)LispDataType.Double,area));
   }
  }
  [LispFunction("pl:native-area-total")]
  public ResultBuffer ReadGeometryTotal(ResultBuffer args){
   if(areaGeometry==null||!Object.ReferenceEquals(areaDocument,AcadApp.DocumentManager.MdiActiveDocument))return null;
   double total=0;foreach(var face in areaGeometry.Faces)total+=face.Area;
   return new ResultBuffer(new TypedValue((int)LispDataType.Double,total));
  }
  [LispFunction("pl:native-area-end")]
  public ResultBuffer CloseAreaSession(ResultBuffer args){EndAreaSession();return null;}
 }
}
