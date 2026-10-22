using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;

namespace PlantCADBridge {
 public sealed partial class Bridge {
  static ObjectId OutputId(Database db,string handle) {
   long number;ObjectId id;
   if(!Int64.TryParse(handle,System.Globalization.NumberStyles.HexNumber,System.Globalization.CultureInfo.InvariantCulture,out number)||!db.TryGetObjectId(new Handle(number),out id)||id.IsErased)
    throw new ArgumentException("关联对象不存在："+handle);
   return id;
  }
  static ObjectId OutputLayer(Database db,Transaction tr,string name,short color,bool plot) {
   var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForRead);
   if(!layers.Has(name)) {
    layers.UpgradeOpen();var layer=new LayerTableRecord{Name=name,Color=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByAci,color),IsPlottable=plot};
    layers.Add(layer);tr.AddNewlyCreatedDBObject(layer,true);
   }
   var target=(LayerTableRecord)tr.GetObject(layers[name],OpenMode.ForRead);
   if(target.IsLocked||target.IsOff||target.IsFrozen)throw new InvalidOperationException("目标图层已锁定、关闭或冻结："+name);
   return target.ObjectId;
  }
  static void OutputMark(Database db,Transaction tr,Entity entity,string role,string source) {
   var apps=(RegAppTable)tr.GetObject(db.RegAppTableId,OpenMode.ForRead);
   if(!apps.Has("PLANTCAD01")){apps.UpgradeOpen();var app=new RegAppTableRecord{Name="PLANTCAD01"};apps.Add(app);tr.AddNewlyCreatedDBObject(app,true);}
   var data=new List<TypedValue>{new TypedValue(1001,"PLANTCAD01"),new TypedValue(1000,role)};
   if(!String.IsNullOrEmpty(source))data.Add(new TypedValue(1005,source));
   using(var buffer=new ResultBuffer(data.ToArray()))entity.XData=buffer;
  }
  static bool OutputLinked(Entity entity,string role,string source) {
   using(ResultBuffer data=entity.GetXDataForApplication("PLANTCAD01")) {
    if(data==null)return false;bool hasRole=false,hasSource=false;
    foreach(TypedValue v in data){if(v.TypeCode==1000&&Convert.ToString(v.Value)==role)hasRole=true;if(v.TypeCode==1005&&Convert.ToString(v.Value).Equals(source,StringComparison.OrdinalIgnoreCase))hasSource=true;}
    return hasRole&&hasSource;
   }
  }
  // Region edges retain arcs/splines; no tessellated replacement is used for hatch boundaries.
  static List<List<Curve>> OutputLoops(Entity boundary) {
   var result=new List<List<Curve>>();var pieces=new DBObjectCollection();var remaining=new List<Curve>();
   try{
    if(!CollectAreaBoundary(boundary,pieces,0)||pieces.Count==0)throw new InvalidOperationException("填充边界没有可用的完整曲线，请重新扫描面积。");
    foreach(DBObject piece in pieces)remaining.Add((Curve)piece);
   }catch{foreach(DBObject piece in pieces)piece.Dispose();throw;}
   double tolerance=Math.Max(1e-7,(boundary.GeometricExtents.MaxPoint-boundary.GeometricExtents.MinPoint).Length*1e-8);
   try {
    while(remaining.Count>0) {
     var loop=new List<Curve>();Curve first=remaining[0];remaining.RemoveAt(0);loop.Add(first);result.Add(loop);
     if(first.Closed)continue;
     Point3d start=first.StartPoint,end=first.EndPoint;
     while(end.DistanceTo(start)>tolerance) {
      int found=-1;bool reverse=false;
      for(int i=0;i<remaining.Count;i++) {
       if(end.DistanceTo(remaining[i].StartPoint)<=tolerance){found=i;break;}
       if(end.DistanceTo(remaining[i].EndPoint)<=tolerance){found=i;reverse=true;break;}
      }
      if(found<0)throw new InvalidOperationException("填充边界未闭合，请重新扫描面积。");
      // AutoCAD 2014 cannot ReverseCurve on some REGION edge curve classes.
      // Connectivity only needs a traversal direction; AppendLoop and CreateFromCurves
      // consume the original connected edges without changing their parameterization.
      Curve next=remaining[found];remaining.RemoveAt(found);loop.Add(next);end=reverse?next.StartPoint:next.EndPoint;
     }
    }
    // Largest loop is the outer boundary. All subsequent loops are islands.
    result.Sort((a,b)=>OutputLoopArea(b).CompareTo(OutputLoopArea(a)));
    return result;
   }catch{foreach(var loop in result)foreach(Curve c in loop)c.Dispose();foreach(Curve c in remaining)c.Dispose();throw;}
  }
  static double OutputLoopArea(List<Curve> loop) {
   var objects=new DBObjectCollection();foreach(Curve curve in loop)objects.Add(curve);
   var regions=Region.CreateFromCurves(objects);double area=0;
   foreach(DBObject obj in regions){var region=obj as Region;if(region!=null)area+=region.Area;obj.Dispose();}
   return area;
  }
  static bool[] OutputOuterLoops(List<List<Curve>> loops){
   var result=new bool[loops.Count];var regions=new List<Region>();
   Point3d origin=loops[0][0].StartPoint;var shift=Matrix3d.Displacement(Point3d.Origin-origin);
   try{
    foreach(var loop in loops){
     var copies=new DBObjectCollection();
     try{foreach(Curve curve in loop){var copy=(Curve)curve.Clone();copies.Add(copy);copy.TransformBy(shift);}
      var shapes=Region.CreateFromCurves(copies);if(shapes.Count!=1){foreach(DBObject shape in shapes)shape.Dispose();throw new InvalidOperationException("填充环无法唯一确定，请检查重叠边界。");}regions.Add((Region)shapes[0]);
     }finally{foreach(DBObject copy in copies)copy.Dispose();}
    }
    for(int i=0;i<regions.Count;i++){
     result[i]=true;var bounds=regions[i].GeometricExtents;
     for(int j=0;j<i;j++){
      var parent=regions[j].GeometricExtents;
      if(bounds.MinPoint.X<parent.MinPoint.X-1e-7||bounds.MinPoint.Y<parent.MinPoint.Y-1e-7||bounds.MaxPoint.X>parent.MaxPoint.X+1e-7||bounds.MaxPoint.Y>parent.MaxPoint.Y+1e-7)continue;
      double area=regions[i].Area;
      using(var overlap=(Region)regions[i].Clone())using(var outer=(Region)regions[j].Clone()){
       overlap.BooleanOperation(BooleanOperationType.BoolIntersect,outer);
       if(!overlap.IsNull&&Math.Abs(overlap.Area-area)<=Math.Max(1e-8,area*1e-9)){result[i]=false;break;}
      }
     }
    }
    return result;
   }finally{foreach(Region region in regions)region.Dispose();}
  }
  [LispFunction("pl:native-fill")]
  public ResultBuffer WriteAreaFill(ResultBuffer args) {
   try {
    TypedValue[] v=args.AsArray();if(v.Length!=5)throw new ArgumentException("填充参数无效。");
    string handle=Convert.ToString(v[0].Value),pattern=Convert.ToString(v[1].Value),layer=Convert.ToString(v[4].Value);
    double scale=Convert.ToDouble(v[2].Value),angle=Convert.ToDouble(v[3].Value);
    if(!Double.IsNaN(scale)&&!Double.IsInfinity(scale)&&scale>0){}else throw new ArgumentException("填充比例必须大于0。");
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;string output;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     var boundary=tr.GetObject(OutputId(db,handle),OpenMode.ForRead) as Entity;
     if(!(boundary is Region)&&!(boundary is Polyline&&((Polyline)boundary).Closed))throw new InvalidOperationException("请选择已扫描的有效面积。");
     var space=(BlockTableRecord)tr.GetObject(boundary.OwnerId,OpenMode.ForWrite);
     var old=new List<ObjectId>();foreach(ObjectId id in space){var entity=tr.GetObject(id,OpenMode.ForRead) as Entity;if(entity!=null&&(OutputLinked(entity,"AREA_FILL",handle)||OutputLinked(entity,"FILL_EDGE",handle)))old.Add(id);}
     // Validate every old layer before creating replacements. Any failure rolls back the whole transaction.
     foreach(ObjectId id in old){var entity=(Entity)tr.GetObject(id,OpenMode.ForRead);if(((LayerTableRecord)tr.GetObject(entity.LayerId,OpenMode.ForRead)).IsLocked)throw new InvalidOperationException("原填充图层已锁定，请先解锁。");}
     ObjectId fillLayer=OutputLayer(db,tr,layer,(short)(layer=="PL_灌木_填充"?8:3),true),edgeLayer=OutputLayer(db,tr,"PL_辅助_填充边界",8,false);
     var fillRecord=(LayerTableRecord)tr.GetObject(fillLayer,OpenMode.ForRead);
     if(layer=="PL_灌木_填充"&&(fillRecord.Color.ColorIndex==2||fillRecord.Color.ColorIndex==3)) {
      fillRecord.UpgradeOpen();fillRecord.Color=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByAci,8);
     }
     var loops=OutputLoops(boundary);
     try {
      bool[] outerLoops=OutputOuterLoops(loops);
      var hatch=new Hatch();hatch.SetDatabaseDefaults(db);hatch.LayerId=fillLayer;hatch.ColorIndex=256;hatch.Elevation=boundary is Region?((Region)boundary).GeometricExtents.MinPoint.Z:((Polyline)boundary).Elevation;
      space.AppendEntity(hatch);tr.AddNewlyCreatedDBObject(hatch,true);hatch.SetHatchPattern(HatchPatternType.PreDefined,pattern);
      hatch.PatternScale=scale;hatch.PatternAngle=angle;hatch.HatchStyle=HatchStyle.Normal;hatch.Associative=true;
      hatch.SetHatchPattern(HatchPatternType.PreDefined,pattern);
      for(int i=0;i<loops.Count;i++) {
       var ids=new ObjectIdCollection();foreach(Curve curve in loops[i]){curve.SetDatabaseDefaults(db);curve.LayerId=edgeLayer;curve.Visible=false;space.AppendEntity(curve);tr.AddNewlyCreatedDBObject(curve,true);OutputMark(db,tr,curve,"FILL_EDGE",handle);ids.Add(curve.ObjectId);}
       hatch.AppendLoop(outerLoops[i]?HatchLoopTypes.Outermost:HatchLoopTypes.Default,ids);
      }
      hatch.EvaluateHatch(true);OutputMark(db,tr,hatch,"AREA_FILL",handle);output=hatch.Handle.ToString();
      var order=(DrawOrderTable)tr.GetObject(space.DrawOrderTableId,OpenMode.ForWrite);order.MoveToBottom(new ObjectIdCollection(new[]{hatch.ObjectId}));
      foreach(ObjectId id in old)((Entity)tr.GetObject(id,OpenMode.ForWrite)).Erase();
      tr.Commit();
     }finally{foreach(var loop in loops)foreach(Curve curve in loop)curve.Dispose();}
    }
    return new ResultBuffer(new TypedValue((int)LispDataType.Text,output));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  static List<object> OutputArguments(ResultBuffer args) {
   // LispFunction arguments are an argument sequence. A leading point/list is
   // the first argument, not an outer wrapper around the whole sequence.
   var tokens=new List<LispToken>{new LispToken(5016,null)};foreach(TypedValue v in args) {
    if(v.Value is Point3d) {
     Point3d point=(Point3d)v.Value;tokens.Add(new LispToken(5016,null));tokens.Add(new LispToken(5001,point.X));tokens.Add(new LispToken(5001,point.Y));tokens.Add(new LispToken(5001,point.Z));tokens.Add(new LispToken(5017,null));
    }else tokens.Add(new LispToken(v.TypeCode,v.Value));
   }
   tokens.Add(new LispToken(5017,null));return (List<object>)LispValueReader.Decode(tokens.ToArray());
  }
  [LispFunction("pl:native-area-signature")]
  public ResultBuffer AreaOutputSignature(ResultBuffer args) {
   try {
    Document doc=AcadApp.DocumentManager.MdiActiveDocument;Database db=doc.Database;var parts=new List<string>();
    var cache=OutputSignatureCache(doc);ObjectId areaId=OutputId(db,Convert.ToString(args.AsArray()[0].Value));string saved;
    if(cache.TryGetValue(areaId,out saved))return new ResultBuffer(new TypedValue((int)LispDataType.Text,saved));
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     var entity=(Entity)tr.GetObject(areaId,OpenMode.ForRead);
     var loops=OutputLoops(entity);
     try {
      foreach(var loop in loops)foreach(Curve curve in loop) {
       for(int i=0;i<=8;i++) {
        Point3d point=curve.GetPointAtParameter(curve.StartParam+(curve.EndParam-curve.StartParam)*i/8.0);
        parts.Add(point.X.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+","+point.Y.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+","+point.Z.ToString("R",System.Globalization.CultureInfo.InvariantCulture));
       }
      }
     }finally{foreach(var loop in loops)foreach(Curve curve in loop)curve.Dispose();}
    }
    saved=String.Join(";",parts.ToArray());cache[areaId]=saved;
    return new ResultBuffer(new TypedValue((int)LispDataType.Text,saved));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  static readonly Dictionary<Document,Dictionary<ObjectId,string>> outputSignatures=new Dictionary<Document,Dictionary<ObjectId,string>>();
  static Dictionary<ObjectId,string> OutputSignatureCache(Document doc) {
   Dictionary<ObjectId,string> cache;
   if(!outputSignatures.TryGetValue(doc,out cache)){
    cache=new Dictionary<ObjectId,string>();outputSignatures.Add(doc,cache);
    doc.Database.ObjectModified+=OutputSignatureModified;doc.Database.ObjectErased+=OutputSignatureErased;
   }
   return cache;
  }
  static void OutputSignatureModified(object sender,ObjectEventArgs args){InvalidateOutputSignature(args.DBObject);}
  static void OutputSignatureErased(object sender,ObjectErasedEventArgs args){InvalidateOutputSignature(args.DBObject);}
  static void InvalidateOutputSignature(DBObject changed) {
   if(!(changed is Region)&&!(changed is Polyline))return;
   // Database properties can return different managed wrappers for the same native database.
   foreach(var cache in outputSignatures.Values)cache.Remove(changed.ObjectId);
  }
  static void ForgetOutputSignatures(Document doc) {
   if(outputSignatures.Remove(doc)){doc.Database.ObjectModified-=OutputSignatureModified;doc.Database.ObjectErased-=OutputSignatureErased;}
  }
  static void LegendText(Database db,Transaction tr,BlockTableRecord block,string value,double y,double height,ObjectId style) {
   if(String.IsNullOrEmpty(value))return;
   var text=new DBText{TextString=value,Height=height,TextStyleId=style,Layer="0",ColorIndex=0,
    HorizontalMode=TextHorizontalMode.TextCenter,VerticalMode=TextVerticalMode.TextVerticalMid,
    Position=new Point3d(0,y,0),AlignmentPoint=new Point3d(0,y,0)};
   block.AppendEntity(text);tr.AddNewlyCreatedDBObject(text,true);text.AdjustAlignment(db);
  }
  static ObjectId OutputLegend(Database db,Transaction tr,string token,List<object> layout,ObjectId textStyle) {
   var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead);
   string name="PL_LEGEND_"+token.Replace(":","_");
   if(layout!=null) {
    if(layout.Count!=5||Convert.ToDouble(layout[0])<=0)throw new ArgumentException("图例文字参数无效。");
    // Length-prefix every field: arbitrary Unicode plant names cannot alias a cache entry.
    string key=token+"|"+textStyle.Handle.ToString();
    foreach(object item in layout){string value=Convert.ToString(item,System.Globalization.CultureInfo.InvariantCulture);key+="|"+value.Length+":"+value;}
    using(var hash=System.Security.Cryptography.SHA256.Create())name="PL_LEGEND_V4_"+BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(key))).Replace("-","");
   }
   if(blocks.Has(name))return blocks[name];
   blocks.UpgradeOpen();var block=new BlockTableRecord{Name=name};blocks.Add(block);tr.AddNewlyCreatedDBObject(block,true);
   if(token.StartsWith("HATCH:",StringComparison.Ordinal)) {
    var border=new Polyline();border.AddVertexAt(0,new Point2d(-.5,-.4),0,0,0);border.AddVertexAt(1,new Point2d(.5,-.4),0,0,0);border.AddVertexAt(2,new Point2d(.5,.4),0,0,0);border.AddVertexAt(3,new Point2d(-.5,.4),0,0,0);border.Closed=true;border.ColorIndex=0;block.AppendEntity(border);tr.AddNewlyCreatedDBObject(border,true);
    var hatch=new Hatch();hatch.ColorIndex=0;block.AppendEntity(hatch);tr.AddNewlyCreatedDBObject(hatch,true);hatch.SetHatchPattern(HatchPatternType.PreDefined,token.Substring(6));hatch.PatternScale=.06;
    hatch.SetHatchPattern(HatchPatternType.PreDefined,token.Substring(6));
    hatch.AppendLoop(HatchLoopTypes.Outermost,new ObjectIdCollection(new[]{border.ObjectId}));hatch.EvaluateHatch(true);
   }else if(blocks.Has(token)) {
    var source=(BlockTableRecord)tr.GetObject(blocks[token],OpenMode.ForRead);
    foreach(ObjectId id in source) {
     var entity=tr.GetObject(id,OpenMode.ForRead) as Entity;
     if(entity==null||entity is AttributeDefinition)continue;
     var clone=(Entity)entity.Clone();clone.Layer="0";clone.ColorIndex=0;block.AppendEntity(clone);tr.AddNewlyCreatedDBObject(clone,true);
    }
   }else throw new ArgumentException("图例图块不存在："+token);
   if(layout!=null) {
    int kind=Convert.ToInt32(layout[1]);bool hatch=token.StartsWith("HATCH:",StringComparison.Ordinal);
    double h=hatch?.18:Convert.ToDouble(layout[0]);
    LegendText(db,tr,block,Convert.ToString(layout[2]),hatch?.4+.75*h:(kind==3?0:.75*h),h,textStyle);
    if(!hatch){LegendText(db,tr,block,Convert.ToString(layout[3]),-.75*h,h,textStyle);LegendText(db,tr,block,Convert.ToString(layout[4]),-2.25*h,h,textStyle);}
    var bounds=LegendBounds(tr,block.ObjectId);var center=bounds.MinPoint+(bounds.MaxPoint-bounds.MinPoint)*.5;
    var shift=Matrix3d.Displacement(Point3d.Origin-center);
    foreach(ObjectId child in block)((Entity)tr.GetObject(child,OpenMode.ForWrite)).TransformBy(shift);
   }
   return block.ObjectId;
  }
  static Extents3d LegendBounds(Transaction tr,ObjectId id) {
   Extents3d? bounds=null;
   foreach(ObjectId child in (BlockTableRecord)tr.GetObject(id,OpenMode.ForRead)){
    var entity=tr.GetObject(child,OpenMode.ForRead) as Entity;if(entity==null)continue;
    var extent=entity.GeometricExtents;
    if(bounds.HasValue){var combined=bounds.Value;combined.AddExtents(extent);bounds=combined;}else bounds=extent;
   }
   if(!bounds.HasValue)throw new ArgumentException("图例为空，无法缩放。");
   return bounds.Value;
  }
  static double LegendFitScale(Transaction tr,ObjectId id,double width,double height) {
   var bounds=LegendBounds(tr,id);var size=bounds.MaxPoint-bounds.MinPoint;
   return Math.Min(width/Math.Max(size.X,1e-9),height/Math.Max(size.Y,1e-9));
  }
  [LispFunction("pl:native-table-write")]
  public ResultBuffer WriteOutputTable(ResultBuffer args) {
   try {
    var v=OutputArguments(args);if(v.Count!=7&&v.Count!=8)throw new ArgumentException("表格参数无效。");
    string handle=Convert.ToString(v[0]),layer=Convert.ToString(v[2]),title=Convert.ToString(v[3]);
    var point=(List<object>)v[1];double height=Convert.ToDouble(v[4]);var headers=(List<object>)v[5];var rows=v[6] as List<object> ?? new List<object>();
    var layouts=v.Count==8?v[7] as List<object>:null;
    if(layouts!=null&&layouts.Count!=rows.Count)throw new ArgumentException("图例数量与表格行数不一致。");
    if(height<=0||Double.IsNaN(height)||Double.IsInfinity(height)||headers.Count<2)throw new ArgumentException("表格字高或列无效。");
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;string output;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     Table table;
     if(handle.Length==0) {
      table=new Table();table.SetDatabaseDefaults(db);table.TableStyle=db.Tablestyle;table.Position=new Point3d(Convert.ToDouble(point[0]),Convert.ToDouble(point[1]),Convert.ToDouble(point[2]));
      table.LayerId=OutputLayer(db,tr,layer,7,true);table.SetSize(Math.Max(3,rows.Count+2),headers.Count);table.SetRowHeight(height*2.8);table.SetColumnWidth(height*9);
      var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);space.AppendEntity(table);tr.AddNewlyCreatedDBObject(table,true);
     }else {
      table=tr.GetObject(OutputId(db,handle),OpenMode.ForWrite) as Table;if(table==null)throw new ArgumentException("关联表不存在。");
      if(((LayerTableRecord)tr.GetObject(table.LayerId,OpenMode.ForRead)).IsLocked)throw new InvalidOperationException("关联表图层已锁定。");
      int columns=headers.Count-table.Columns.Count;
      if(columns>0)table.InsertColumns(table.Columns.Count,height*9,columns);else if(columns<0)table.DeleteColumns(headers.Count,-columns);
      int count=Math.Max(3,rows.Count+2)-table.Rows.Count;
      if(count>0)table.InsertRows(table.Rows.Count,height*2.8,count);else if(count<0)table.DeleteRows(Math.Max(3,rows.Count+2),-count);
     }
     // A fixed-height drawing text style plus Contents.Clear resets data cells
     // to the style's 2.5-unit height. Apply text formatting AFTER content writes.
     var styles=(TextStyleTable)tr.GetObject(db.TextStyleTableId,OpenMode.ForRead);
     const string textStyle="PLANTCAD_表格";ObjectId styleId;
     if(styles.Has(textStyle))styleId=styles[textStyle];
     else {
      var sourceStyle=(TextStyleTableRecord)tr.GetObject(db.Textstyle,OpenMode.ForRead);
      var copy=(TextStyleTableRecord)sourceStyle.Clone();copy.Name=textStyle;copy.TextSize=0;
      styles.UpgradeOpen();styleId=styles.Add(copy);tr.AddNewlyCreatedDBObject(copy,true);
     }
     var tableStyle=(TextStyleTableRecord)tr.GetObject(styleId,OpenMode.ForWrite);tableStyle.TextSize=0;
     table.Cells[0,0].TextString=title;
     for(int col=0;col<headers.Count;col++)table.Cells[1,col].TextString=Convert.ToString(headers[col]);
     int legendColumn=headers.Count-1;
     for(int col=0;col<headers.Count;col++)if(Convert.ToString(headers[col])=="图例")legendColumn=col;
     table.Columns[legendColumn].Width=height*7;
     for(int row=0;row<Math.Max(1,rows.Count);row++) {
      var cells=row<rows.Count?(List<object>)rows[row]:new List<object>();
      for(int col=0;col<headers.Count;col++) {
       table.Cells[row+2,col].Contents.Clear();
       string text=col<cells.Count?Convert.ToString(cells[col]):"";
       if(col==legendColumn&&text.Length>0){
        var legend=OutputLegend(db,tr,text,layouts!=null?layouts[row] as List<object>:null,styleId);
        table.SetBlockTableRecordId(row+2,col,legend,layouts==null);
        if(layouts!=null)table.SetBlockScale(row+2,col,LegendFitScale(tr,legend,
         Math.Max(height*.1,table.Columns[col].Width-height*.6),Math.Max(height*.1,table.Rows[row+2].Height-height*.6)));
       }
       else table.Cells[row+2,col].TextString=text;
      }
     }
     table.Cells.TextStyleId=styleId;table.Cells.TextHeight=height;table.Cells.Alignment=CellAlignment.MiddleCenter;
     for(int row=0;row<table.Rows.Count;row++)for(int col=0;col<table.Columns.Count;col++)
      foreach(CellContent content in table.Cells[row,col].Contents)content.TextHeight=height;
     table.Columns[legendColumn].Width=height*7;table.GenerateLayout();OutputMark(db,tr,table,"TABLE",null);output=table.Handle.ToString();tr.Commit();
    }
    return new ResultBuffer(new TypedValue((int)LispDataType.Text,output));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  [LispFunction("pl:native-table-read")]
  public ResultBuffer ReadOutputTable(ResultBuffer args) {
   try {
    var values=new List<TypedValue>();Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     var table=tr.GetObject(OutputId(db,Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead) as Table;
     if(table==null)return null;
     values.Add(new TypedValue((int)LispDataType.Text,"TABLE_ROWS"));
     int legendColumn=table.Columns.Count-1;
     for(int col=0;col<table.Columns.Count;col++)if(table.Cells[1,col].TextString=="图例")legendColumn=col;
     for(int row=2;row<table.Rows.Count;row++) {
      values.Add(new TypedValue((int)LispDataType.ListBegin));
      // Canonical data order excludes the legend, preserving old-table edit import.
      for(int col=0;col<table.Columns.Count;col++)if(col!=legendColumn)values.Add(new TypedValue((int)LispDataType.Text,table.Cells[row,col].TextString??""));
      values.Add(new TypedValue((int)LispDataType.ListEnd));
     }
    }
    return new ResultBuffer(values.ToArray());
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  // Do not inspect XData or enqueue drawing writes from database/command reactors.
  // ERASE and UNDO must finish without rebuilding associated hatches or importing tables.
  // PlantCAD edits synchronize in pl:run; external CAD edits use an explicit sync command.
  [CommandMethod("PLANTCADASSOCIATIONSYNC",CommandFlags.Modal)]
  public void SyncPlantOutput() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   try {
    if(doc==null||!prepared.Contains(doc))return;
    using(var input=new ResultBuffer(new TypedValue((int)LispDataType.Text,"pl:sync-native")))
    using(ResultBuffer result=AcadApp.Invoke(input)){}
   }catch(System.Exception ex){doc.Editor.WriteMessage("\nCountingTrees（数树）关联更新失败："+ex.Message+"；可用U撤销或修正后执行PLANTCADSYNC。");}
  }
 }
}
