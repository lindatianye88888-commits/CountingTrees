using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(OutputProbe))]
public class OutputProbe {
 static int checks;
 static Database DB {get{return Application.DocumentManager.MdiActiveDocument.Database;}}
 static void Check(bool value,string message){if(!value)throw new InvalidOperationException(message);checks++;}
 static string Text(ResultBuffer result){using(result){if(result==null)throw new InvalidOperationException("Null result");return Convert.ToString(result.AsArray()[0].Value);}}
 static Polyline Box(double x,double y,double w,double h){var p=new Polyline();p.AddVertexAt(0,new Point2d(x,y),0,0,0);p.AddVertexAt(1,new Point2d(x+w,y),0,0,0);p.AddVertexAt(2,new Point2d(x+w,y+h),0,0,0);p.AddVertexAt(3,new Point2d(x,y+h),0,0,0);p.Closed=true;return p;}
 static Region RegionOf(Curve curve){var collection=new DBObjectCollection();collection.Add(curve);return (Region)Region.CreateFromCurves(collection)[0];}
 static ObjectId Id(string handle){return DB.GetObjectId(false,new Handle(Int64.Parse(handle,System.Globalization.NumberStyles.HexNumber)),0);}
 static string Fill(string handle,string pattern){using(var args=new ResultBuffer(new TypedValue(5005,handle),new TypedValue(5005,pattern),new TypedValue(5001,.1),new TypedValue(5001,0.0),new TypedValue(5005,"PL_花境_填充")))return Text(new Bridge().WriteAreaFill(args));}
  static string Label(string handle,string area,string text,int layout,double height=.25){using(var args=new ResultBuffer(new TypedValue(5005,handle),new TypedValue(5005,area),new TypedValue(5009,new Point3d(2,2,0)),new TypedValue(5009,new Point3d(-8,-4,0)),new TypedValue(5005,text),new TypedValue(5001,height),new TypedValue(5005,"PL_灌木_标注"),new TypedValue(5003,layout)))return Text(new Bridge().WriteAreaLeader(args));}
  static string PickedLabel(string handle,string area,string text,int layout,Point3d elbow,Point3d tail,double height=1.0){using(var args=new ResultBuffer(new TypedValue(5005,handle),new TypedValue(5005,area),new TypedValue(5009,new Point3d(2,2,0)),new TypedValue(5009,tail),new TypedValue(5005,text),new TypedValue(5001,height),new TypedValue(5005,"PL_灌木_标注"),new TypedValue(5003,layout),new TypedValue(5009,elbow)))return Text(new Bridge().WriteAreaLeader(args));}
  static Point3d LandingEnd(MLeader leader){int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];using(var text=leader.MText)return leader.GetLastVertex(line)+leader.GetDogleg(index)*(leader.GetDoglegLength(index)+text.ActualWidth);}
 static void AddList(List<TypedValue> v,IEnumerable<string> strings){v.Add(new TypedValue(5016));foreach(string s in strings)v.Add(new TypedValue(5005,s));v.Add(new TypedValue(5017));}
 static string TableWrite(string handle,int rows,bool legendSecond=false,double height=.25,bool namedLegend=false){
  var v=new List<TypedValue>{new TypedValue(5005,handle),new TypedValue(5016),new TypedValue(5001,0.0),new TypedValue(5001,-10.0),new TypedValue(5001,0.0),new TypedValue(5017),new TypedValue(5005,"PL_表格_苗木"),new TypedValue(5005,"关联表测试"),new TypedValue(5001,height)};
  AddList(v,legendSecond?new[]{"编号","图例","植物","类","D","d","H","P","数量","单位"}:new[]{"编号","植物","类","D","d","H","P","数量","单位","图例"});
  v.Add(new TypedValue(5016));for(int i=0;i<rows;i++){string legend=i%2==0?"PC_OUTPUT_SYMBOL":"HATCH:ANSI32";AddList(v,legendSecond?new[]{"B001",legend,"灌木球","灌木球","","","100","100","2","株"}:new[]{"B001","灌木球","灌木球","","","100","100","2","株",legend});}v.Add(new TypedValue(5017));
  if(namedLegend){v.Add(new TypedValue(5016));for(int i=0;i<rows;i++){v.Add(new TypedValue(5016));v.Add(new TypedValue(5001,.25));v.Add(new TypedValue(5003,i==0?3:1));foreach(string s in new[]{i==0?"测试灌木球":"金森女贞","",""})v.Add(new TypedValue(5005,s));v.Add(new TypedValue(5017));}v.Add(new TypedValue(5017));}
  using(var args=new ResultBuffer(v.ToArray()))return Text(new Bridge().WriteOutputTable(args));
 }
 [CommandMethod("PC_OUTPUT_TEST")]
 public void Test(){
  string dir=Path.GetDirectoryName(Application.DocumentManager.MdiActiveDocument.Name);
  try {
   ObjectId areaId;
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var space=(BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForWrite);
    var existing=new List<ObjectId>();foreach(ObjectId id in space)existing.Add(id);foreach(ObjectId id in existing)((Entity)tr.GetObject(id,OpenMode.ForWrite)).Erase();
    using(var outer=Box(0,0,20,10))using(var hole=Box(8,3,4,4)) {
     Region region=RegionOf(outer);using(Region inner=RegionOf(hole))region.BooleanOperation(BooleanOperationType.BoolSubtract,inner);
     areaId=space.AppendEntity(region);tr.AddNewlyCreatedDBObject(region,true);
    }
    var blocks=(BlockTable)tr.GetObject(DB.BlockTableId,OpenMode.ForWrite);
    var block=new BlockTableRecord{Name="PC_OUTPUT_SYMBOL"};blocks.Add(block);tr.AddNewlyCreatedDBObject(block,true);
    var circle=new Circle(Point3d.Origin,Vector3d.ZAxis,.5);block.AppendEntity(circle);tr.AddNewlyCreatedDBObject(circle,true);tr.Commit();
   }
   string area=areaId.Handle.ToString(),first=Fill(area,"ANSI31");Check(!first.StartsWith("ERROR:"),"fill: "+first);
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var hatch=(Hatch)tr.GetObject(Id(first),OpenMode.ForWrite);Check(hatch.NumberOfLoops==2,"Island loop missing");hatch.EvaluateHatch(true);Check(hatch.Associative,"Hatch not associative");Check(hatch.GetAssociatedObjectIds().Count==8,"Island boundary association wrong");
   }
   string second=Fill(area,"ANSI32");Check(!second.StartsWith("ERROR:"),"replace: "+second);Check(Id(first).IsErased,"Old fill retained");
   string invalid=Fill(area,"PLANTCAD_NO_SUCH_PATTERN");Check(invalid.StartsWith("ERROR:"),"Invalid pattern accepted");Check(!Id(second).IsErased,"Failed fill erased good hatch");
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var layer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))["PL_花境_填充"],OpenMode.ForWrite);layer.IsLocked=true;tr.Commit();
   }
   Check(Fill(area,"ANSI33").StartsWith("ERROR:"),"Locked fill changed");Check(!Id(second).IsErased,"Locked original erased");
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var layer=(LayerTableRecord)tr.GetObject(((LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForRead))["PL_花境_填充"],OpenMode.ForWrite);layer.IsLocked=false;tr.Commit();
   }
   // A curved region and a concave region exercise native loop reconstruction too.
   foreach(bool curved in new[]{true,false}) {
    ObjectId id;
    using(Transaction tr=DB.TransactionManager.StartTransaction()) {
     var space=(BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForWrite);Region region;
     if(curved){using(var circle=new Circle(new Point3d(30,5,0),Vector3d.ZAxis,4))region=RegionOf(circle);}
     else{using(var p=Box(40,0,10,10)){p.AddVertexAt(3,new Point2d(44,4),0,0,0);region=RegionOf(p);}}
     id=space.AppendEntity(region);tr.AddNewlyCreatedDBObject(region,true);tr.Commit();
    }
    string fill=Fill(id.Handle.ToString(),"ANSI34");Check(!fill.StartsWith("ERROR:"),"curve/concave: "+fill);
    using(Transaction tr=DB.TransactionManager.StartTransaction()){var region=(Region)tr.GetObject(id,OpenMode.ForRead);var hatch=(Hatch)tr.GetObject(Id(fill),OpenMode.ForRead);Check(hatch.NumberOfLoops==1&&hatch.GetAssociatedObjectIds().Count>0,"Curved fill boundary missing");}
   }
   ObjectId compoundId;
   using(var tr=DB.TransactionManager.StartTransaction())using(var left=Box(60,0,5,5))using(var right=Box(80,0,5,5)){
    var compound=RegionOf(left);using(var other=RegionOf(right))compound.BooleanOperation(BooleanOperationType.BoolUnite,other);
    var parts=new DBObjectCollection();try{compound.Explode(parts);Check(parts.Count==2&&parts[0] is Region&&parts[1] is Region,"Compound fixture did not retain disconnected regions");}finally{foreach(DBObject part in parts)part.Dispose();}
    var space=(BlockTableRecord)tr.GetObject(DB.CurrentSpaceId,OpenMode.ForWrite);compoundId=space.AppendEntity(compound);tr.AddNewlyCreatedDBObject(compound,true);tr.Commit();
   }
   string compoundHandle=compoundId.Handle.ToString(),compoundFill=Fill(compoundHandle,"ANSI31");Check(!compoundFill.StartsWith("ERROR:"),"Compound region fill: "+compoundFill);
   using(var tr=DB.TransactionManager.StartTransaction()){
    var hatch=(Hatch)tr.GetObject(Id(compoundFill),OpenMode.ForRead);Check(hatch.NumberOfLoops==2&&hatch.GetAssociatedObjectIds().Count==8,"Compound outer loops were lost");
    Check((hatch.LoopTypeAt(0)&HatchLoopTypes.Outermost)!=0&&(hatch.LoopTypeAt(1)&HatchLoopTypes.Outermost)!=0,"Disconnected outer component was treated as a hole");
    // Hatch.Area is unavailable even for the simple hole fixture in Core
    // Console 2014. Verify the actual associated native boundary regions.
    var edges=new DBObjectCollection();try{foreach(ObjectId id in hatch.GetAssociatedObjectIds())edges.Add((DBObject)((Entity)tr.GetObject(id,OpenMode.ForRead)).Clone());var regions=Region.CreateFromCurves(edges);double total=0;try{foreach(Region region in regions)total+=region.Area;}finally{foreach(DBObject region in regions)region.Dispose();}Check(Math.Abs(total-50)<1e-7,"Compound hatch boundary area differs from source");}finally{foreach(DBObject edge in edges)edge.Dispose();}
    Check(Math.Abs(((Region)tr.GetObject(compoundId,OpenMode.ForRead)).Area-50)<1e-7,"Filling changed the compound source region");
   }
   using(var input=new ResultBuffer(new TypedValue(5005,compoundHandle))){string value=Text(new Bridge().AreaOutputSignature(input));Check(value.Length>0&&!value.StartsWith("ERROR:"),"Compound geometry signature is empty");}
   using(var tr=DB.TransactionManager.StartTransaction()){((TextStyleTableRecord)tr.GetObject(DB.Textstyle,OpenMode.ForWrite)).TextSize=2.5;tr.Commit();}
   string table=TableWrite("",2);Check(!table.StartsWith("ERROR:"),"table create: "+table);
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var t=(Table)tr.GetObject(Id(table),OpenMode.ForRead);Check(t.Rows.Count==4&&t.Columns.Count==10,"Table size");Check(!t.Cells[2,9].Contents[0].BlockTableRecordId.IsNull,"Symbol legend missing");Check(!t.Cells[3,9].Contents[0].BlockTableRecordId.IsNull,"Hatch legend missing");
   }
   Check(TableWrite(table,1)==table,"Table handle changed on resize");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){var t=(Table)tr.GetObject(Id(table),OpenMode.ForRead);Check(t.Rows.Count==3,"Table did not shrink");}
   Check(TableWrite(table,0)==table,"Empty table refresh failed");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){var t=(Table)tr.GetObject(Id(table),OpenMode.ForRead);Check(t.Cells[2,0].TextString=="","Empty table stale row");}
   Check(TableWrite(table,2,true,1000)==table,"Old-layout table migration replaced the table");
   using(var tr=DB.TransactionManager.StartTransaction()){
    var t=(Table)tr.GetObject(Id(table),OpenMode.ForRead);
    Check(t.Cells[2,0].TextString=="B001"&&t.Cells[2,2].TextString=="灌木球","Number/name columns lost during migration");
    Check(!t.Cells[2,1].Contents[0].BlockTableRecordId.IsNull&&!t.Cells[3,1].Contents[0].BlockTableRecordId.IsNull,"Legends not moved to second column");
    bool heights=true;for(int r=0;r<t.Rows.Count;r++)for(int c=0;c<t.Columns.Count;c++)foreach(CellContent content in t.Cells[r,c].Contents)if(content.TextHeight!=1000)heights=false;
    Check(heights,"Cell content reset to fixed style height after write");
    Check(((TextStyleTableRecord)tr.GetObject(t.Cells[2,0].TextStyleId.Value,OpenMode.ForRead)).TextSize==0,"Table text style retained fixed font height");
    Check(((TextStyleTableRecord)tr.GetObject(DB.Textstyle,OpenMode.ForRead)).TextSize==2.5,"User text style was altered");
   }
   using(var input=new ResultBuffer(new TypedValue(5005,table)))using(var result=new Bridge().ReadOutputTable(input)){
    var values=result.AsArray();Check(Convert.ToString(values[2].Value)=="B001"&&Convert.ToString(values[3].Value)=="灌木球","Canonical read order changed with legend placement");
   }
   Check(TableWrite(table,2,true,1000,true)==table,"Named legends replaced the table");
   using(var tr=DB.TransactionManager.StartTransaction()){
    var t=(Table)tr.GetObject(Id(table),OpenMode.ForRead);
    for(int row=2;row<4;row++){
     var block=(BlockTableRecord)tr.GetObject(t.Cells[row,1].Contents[0].BlockTableRecordId,OpenMode.ForRead);DBText name=null;Circle circle=null;Hatch hatch=null;Polyline border=null;
     foreach(ObjectId id in block){var e=tr.GetObject(id,OpenMode.ForRead);if(e is DBText)name=(DBText)e;if(e is Circle)circle=(Circle)e;if(e is Hatch)hatch=(Hatch)e;if(e is Polyline)border=(Polyline)e;}
     Check(name!=null&&name.TextString==(row==2?"测试灌木球":"金森女贞"),"Legend plant name missing or cross-contaminated");
     Check(name.Height==(row==2?.25:.18)&&name.HorizontalMode==TextHorizontalMode.TextCenter,"Legend text proportions or alignment changed");
     Check(row==2?circle!=null&&circle.Radius==.5&&name.AlignmentPoint.DistanceTo(circle.Center)<1e-8:hatch!=null&&border!=null&&Math.Abs(name.AlignmentPoint.Y-(border.GeometricExtents.MaxPoint.Y+border.GeometricExtents.MinPoint.Y)*.5-(.4+.75*.18))<1e-8,"Legend geometry or name location differs from symbol layout");
     Extents3d? bounds=null;foreach(ObjectId id in block){var extent=((Entity)tr.GetObject(id,OpenMode.ForRead)).GeometricExtents;if(bounds.HasValue){var b=bounds.Value;b.AddExtents(extent);bounds=b;}else bounds=extent;}
     var size=bounds.Value.MaxPoint-bounds.Value.MinPoint;double scale=t.Cells[row,1].Contents[0].Scale;
     Check(size.X*scale<=t.Columns[1].Width-299&&size.Y*scale<=t.Rows[row].Height-299,"Combined text and geometry overflow the legend cell");
    }
   }
   Check(typeof(Bridge).GetMethod("OutputObjectChanged",BindingFlags.Static|BindingFlags.NonPublic)==null,"Unsafe database callback remains");
   Check(typeof(Bridge).GetMethod("OutputCommandFinished",BindingFlags.Static|BindingFlags.NonPublic)==null,"Command completion can still queue full drawing writes");
   string signature;
   using(var input=new ResultBuffer(new TypedValue(5005,area)))signature=Text(new Bridge().AreaOutputSignature(input));
   using(var input=new ResultBuffer(new TypedValue(5005,area)))Check(Text(new Bridge().AreaOutputSignature(input))==signature,"Warm signature cache changed geometry");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){((Region)tr.GetObject(areaId,OpenMode.ForWrite)).TransformBy(Matrix3d.Displacement(new Vector3d(1,0,0)));tr.Commit();}
   using(var input=new ResultBuffer(new TypedValue(5005,area)))Check(Text(new Bridge().AreaOutputSignature(input))!=signature,"Geometry edit did not invalidate signature cache");
   using(Transaction tr=DB.TransactionManager.StartTransaction()){((Region)tr.GetObject(areaId,OpenMode.ForWrite)).TransformBy(Matrix3d.Displacement(new Vector3d(-1,0,0)));tr.Commit();}
   string label=Label("",area,"海桐\\P184.00 平方米",0);Check(!label.StartsWith("ERROR:"),"native label: "+label);
   Point3d moved;
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var leader=(MLeader)tr.GetObject(Id(label),OpenMode.ForWrite);Check(leader.LeaderLineCount==1&&leader.ContentType==ContentType.MTextContent,"Text is not part of native leader");
    Check(leader.ExtendLeaderToText&&leader.TextAttachmentType==TextAttachmentType.AttachmentBottomOfTopLine,"Two-line underline layout wrong");
    var lines=leader.GetLeaderLineIndexes((int)leader.GetLeaderIndexes()[0]);int line=(int)lines[0];
    Point3d text=leader.TextLocation,arrow=leader.GetFirstVertex(line);var shift=new Vector3d(3,4,0);
    leader.TransformBy(Matrix3d.Displacement(shift));Check(leader.TextLocation.DistanceTo(text+shift)<1e-7,"MOVE left text behind");Check(leader.GetFirstVertex(line).DistanceTo(arrow+shift)<1e-7,"MOVE left arrow behind");
    arrow=leader.GetFirstVertex(line);text=leader.TextLocation;leader.MoveMLeader(shift,MoveType.MoveContentAndDoglegPoints);
    Check(leader.GetFirstVertex(line).DistanceTo(arrow)<1e-7,"Content grip moved plant anchor");
    // Native MLeader can adjust X for text extents/dogleg when its content moves.
    // The content must move with its landing, while the plant anchor stays fixed.
    Check(Math.Abs(leader.TextLocation.Y-text.Y-shift.Y)<1e-7,"Content move left attached text behind");
    moved=leader.TextLocation;tr.Commit();
   }
   Check(Label(label,area,"红叶石楠  184.00 平方米",1)==label,"Refresh replaced moved leader");
   using(Transaction tr=DB.TransactionManager.StartTransaction()) {
    var leader=(MLeader)tr.GetObject(Id(label),OpenMode.ForRead);Check(leader.TextLocation.DistanceTo(moved)<1e-7,"Refresh reset native MOVE/grip position");
    Check(leader.TextAttachmentType==TextAttachmentType.AttachmentBottomLine,"Single-line underline layout wrong");
    using(MText text=leader.MText)Check(text.Contents.Contains("红叶石楠")&&!text.Contents.Contains("\\P"),"Refresh lost plant or layout");
   }
   Check(Label(label,area,"{\\fSimHei;\\H2x;鹅掌柴}\\P约 184.00 平方米（补线推定）",0,1.5)==label,"Resizing replaced the existing leader");
   using(var tr=DB.TransactionManager.StartTransaction()){
    var leader=(MLeader)tr.GetObject(Id(label),OpenMode.ForRead);
    Check(Math.Abs(leader.TextHeight-1.5)<1e-7&&Math.Abs(leader.ArrowSize-.45)<1e-7&&Math.Abs(leader.DoglegLength-3)<1e-7,"Text/arrow/landing did not resize together");
    Check(leader.TextLocation.DistanceTo(moved)<1e-7,"Resizing reset the text location");
   }
   using(var input=new ResultBuffer(new TypedValue(5005,label)))Check(Text(new Bridge().ReadEditedAreaName(input))=="鹅掌柴","Formatted two-line edited plant name was not read");
    Label(label,area,"小叶黄杨1号  12.50㎡",1);
    using(var input=new ResultBuffer(new TypedValue(5005,label)))Check(Text(new Bridge().ReadEditedAreaName(input))=="小叶黄杨1号","Plant name digits confused with area");
    foreach(int sign in new[]{1,-1})foreach(int layout in new[]{0,1})foreach(double span in new[]{50.0,4.0}){
     var elbow=new Point3d(sign*8,-4,0);var tail=elbow+new Vector3d(sign*span,0,0);string content=layout==0?"海桐\\P184.00 平方米":"海桐  184.00 平方米";
     string picked=PickedLabel("",area,content,layout,elbow,tail);Check(!picked.StartsWith("ERROR:"),"Picked leader failed: "+picked);
     ObjectId style,leaderStyle;Point3d movedElbow,movedTail;
     using(var tr=DB.TransactionManager.StartTransaction()){
      var leader=(MLeader)tr.GetObject(Id(picked),OpenMode.ForWrite);int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];
      Check(leader.GetLastVertex(line).DistanceTo(elbow)<1e-7,"Picked elbow moved");
      using(var text=leader.MText)Check(LandingEnd(leader).DistanceTo(elbow+new Vector3d(sign*Math.Max(span,text.ActualWidth),0,0))<1e-7,"Picked landing failed to extend for the configured font");
      Check(leader.GetFirstVertex(line).DistanceTo(new Point3d(2,2,0))<1e-7,"Picked arrow moved");
      var attachment=layout==0?TextAttachmentType.AttachmentBottomOfTopLine:TextAttachmentType.AttachmentBottomLine;
      Check(leader.GetTextAttachmentType(LeaderDirectionType.LeftLeader)==attachment&&leader.GetTextAttachmentType(LeaderDirectionType.RightLeader)==attachment,"Left/right layout differs");
      style=leader.TextStyleId;leaderStyle=leader.MLeaderStyle;using(var text=leader.MText)Check(text.Contents==content&&Math.Abs(text.TextHeight-1.0)<1e-7&&Math.Abs(leader.TextHeight-1.0)<1e-7,"Short landing changed the configured font size");
      leader.TransformBy(Matrix3d.Displacement(new Vector3d(3,4,0)));
      leader.MoveMLeader(new Vector3d(-2,3,0),MoveType.MoveContentAndDoglegPoints);
      movedElbow=leader.GetLastVertex(line);movedTail=LandingEnd(leader);tr.Commit();
     }
     using(var tr=DB.TransactionManager.StartTransaction()){
      var styles=(TextStyleTable)tr.GetObject(DB.TextStyleTableId,OpenMode.ForWrite);const string name="PC_ALT_AREA_TEXT";
      if(!styles.Has(name)){var alternate=(TextStyleTableRecord)((TextStyleTableRecord)tr.GetObject(DB.Textstyle,OpenMode.ForRead)).Clone();alternate.Name=name;alternate.FileName="simplex.shx";alternate.TextSize=3;styles.Add(alternate);tr.AddNewlyCreatedDBObject(alternate,true);}
      DB.Textstyle=styles[name];tr.Commit();
     }
     using(var tr=DB.TransactionManager.StartTransaction()){
      var styles=(DBDictionary)tr.GetObject(DB.MLeaderStyleDictionaryId,OpenMode.ForWrite);const string name="PC_ALT_AREA_LEADER";
      if(!styles.Contains(name)){var alternate=(MLeaderStyle)((MLeaderStyle)tr.GetObject(DB.MLeaderstyle,OpenMode.ForRead)).Clone();alternate.DoglegLength=99;alternate.TextHeight=5;styles.SetAt(name,alternate);tr.AddNewlyCreatedDBObject(alternate,true);}
      DB.MLeaderstyle=styles.GetAt(name);tr.Commit();
     }
     string changed=layout==0?"红叶石楠\\P185.00 平方米":"红叶石楠  185.00 平方米";
     Check(PickedLabel(picked,area,changed,layout,elbow,tail)==picked,"Refresh replaced picked leader");
     using(var tr=DB.TransactionManager.StartTransaction()){
      var leader=(MLeader)tr.GetObject(Id(picked),OpenMode.ForRead);int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];
      using(var text=leader.MText)Check(leader.GetLastVertex(line).DistanceTo(movedElbow)<1e-7&&LandingEnd(leader).DistanceTo(movedElbow+new Vector3d(sign*Math.Max(movedTail.DistanceTo(movedElbow),text.ActualWidth),0,0))<1e-7,"Refresh changed elbow or failed to fit longer text");
      Check(leader.TextStyleId==style,"Global TEXTSTYLE changed existing label font");
      using(var text=leader.MText)Check(text.Contents==changed,"Refresh lost selected layout or species");
     }
     string next=PickedLabel("",area,content,layout,elbow,tail);Check(!next.StartsWith("ERROR:"),"Create after global style change failed");
     using(var tr=DB.TransactionManager.StartTransaction()){
      var leader=(MLeader)tr.GetObject(Id(next),OpenMode.ForRead);
      Check(leader.TextStyleId==style&&leader.MLeaderStyle==leaderStyle,"Global TEXTSTYLE/CMLEADERSTYLE changed next label style");
     }
     Check(PickedLabel(picked,area,changed,layout,elbow,tail,2.0)==picked,"Font increase replaced the existing leader");
     using(var tr=DB.TransactionManager.StartTransaction()){
      var leader=(MLeader)tr.GetObject(Id(picked),OpenMode.ForRead);int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];
      using(var text=leader.MText)Check(Math.Abs(text.TextHeight-2.0)<1e-7&&Math.Abs(leader.TextHeight-2.0)<1e-7&&Math.Abs(leader.ArrowSize-.6)<1e-7,"Font increase was clamped by the original landing");
      Check(leader.GetLastVertex(line).DistanceTo(movedElbow)<1e-7,"Font increase reset the picked elbow");
     }
     using(var tr=DB.TransactionManager.StartTransaction()){((Entity)tr.GetObject(Id(picked),OpenMode.ForWrite)).Erase();((Entity)tr.GetObject(Id(next),OpenMode.ForWrite)).Erase();tr.Commit();}
    }
   using(Transaction tr=DB.TransactionManager.StartTransaction()){((Entity)tr.GetObject(Id(label),OpenMode.ForWrite)).Erase();tr.Commit();}
   File.WriteAllText(Path.Combine(dir,"native-result.txt"),"PASS "+checks+" "+area+" "+table);
  }catch(System.Exception ex){File.WriteAllText(Path.Combine(dir,"native-result.txt"),ex.ToString());}
 }
 [LispFunction("pc:edit-table")]
 public ResultBuffer EditTable(ResultBuffer args){
  var v=args.AsArray();using(Transaction tr=DB.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(Id(Convert.ToString(v[0].Value)),OpenMode.ForWrite);table.Cells[Convert.ToInt32(v[1].Value),Convert.ToInt32(v[2].Value)].TextString=Convert.ToString(v[3].Value);tr.Commit();
  }return new ResultBuffer(new TypedValue(5003,1));
 }
 [LispFunction("pc:edit-area-name")]
 public ResultBuffer EditAreaName(ResultBuffer args){
  var v=args.AsArray();using(var tr=DB.TransactionManager.StartTransaction()){
   var leader=(MLeader)tr.GetObject(Id(Convert.ToString(v[0].Value)),OpenMode.ForWrite);
   using(var text=leader.MText){text.Contents=Convert.ToString(v[1].Value);leader.MText=text;}tr.Commit();
  }return new ResultBuffer(new TypedValue(5003,1));
 }
 [LispFunction("pc:leader-style")]
 public ResultBuffer LeaderStyle(ResultBuffer args){
  using(var tr=DB.TransactionManager.StartTransaction()){
    var leader=(MLeader)tr.GetObject(Id(Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead);
    int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];
    return new ResultBuffer(new TypedValue(5001,leader.TextHeight),new TypedValue(5001,leader.ArrowSize),new TypedValue(5001,leader.DoglegLength),new TypedValue(5009,leader.TextLocation),new TypedValue(5009,leader.GetLastVertex(line)),new TypedValue(5009,LandingEnd(leader)));
  }
 }
 [LispFunction("pc:seed-output-layers")]
 public ResultBuffer SeedLayers(ResultBuffer args){
  using(Transaction tr=DB.TransactionManager.StartTransaction()){
   var layers=(LayerTable)tr.GetObject(DB.LayerTableId,OpenMode.ForWrite);
   foreach(TypedValue v in args)if(v.TypeCode==5005&&!layers.Has(Convert.ToString(v.Value))){var layer=new LayerTableRecord{Name=Convert.ToString(v.Value)};layers.Add(layer);tr.AddNewlyCreatedDBObject(layer,true);}tr.Commit();
  }return new ResultBuffer(new TypedValue(5003,1));
 }
 [LispFunction("pc:check-legends")]
 public ResultBuffer CheckLegends(ResultBuffer args){
  int count=0;using(Transaction tr=DB.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(Id(Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead);
   int col=table.Cells[1,1].TextString=="图例"?1:9;
   for(int row=2;row<table.Rows.Count;row++)if(table.Cells[row,col].Contents.Count>0&&!table.Cells[row,col].Contents[0].BlockTableRecordId.IsNull)count++;
  }return new ResultBuffer(new TypedValue(5003,count));
 }
 [LispFunction("pc:check-table-display")]
 public ResultBuffer CheckTableDisplay(ResultBuffer args){
  using(var tr=DB.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(Id(Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead);
   if(table.Cells[1,0].TextString!="编号"||table.Cells[1,1].TextString!="图例")return new ResultBuffer(new TypedValue(5003,0));
   double height=table.Cells[1,0].TextHeight.Value;
   for(int r=2;r<table.Rows.Count;r++)for(int c=0;c<table.Columns.Count;c++)
    foreach(CellContent content in table.Cells[r,c].Contents)if(Math.Abs(content.TextHeight-height)>1e-6)return new ResultBuffer(new TypedValue(5003,0));
   for(int r=2;r<table.Rows.Count;r++)if(table.Cells[r,0].TextString!=""&&table.Cells[r,2].TextString=="")return new ResultBuffer(new TypedValue(5003,0));
  }
  return new ResultBuffer(new TypedValue(5003,1));
 }
}
