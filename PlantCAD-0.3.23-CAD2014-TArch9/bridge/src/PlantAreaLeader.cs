using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  // Text and leader belong to one native entity. CAD handles MOVE, grips and UNDO
  // without a database reactor, queued command, or separate text-position repair.
  [LispFunction("pl:native-area-leader")]
  public ResultBuffer WriteAreaLeader(ResultBuffer args) {
   try {
    var v=OutputArguments(args);
    if(v.Count!=8&&v.Count!=9)throw new ArgumentException("面积引线参数无效。");
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
    string existing=Convert.ToString(v[0]),source=Convert.ToString(v[1]),text=Convert.ToString(v[4]),layer=Convert.ToString(v[6]);
    Point3d anchor=OutputPoint(v[2]),point=OutputPoint(v[3]);
    bool pickedLanding=v.Count==9;Point3d elbow=pickedLanding?OutputPoint(v[8]):point;
    double height=Convert.ToDouble(v[5]);int layout=Convert.ToInt32(v[7]);
    if(Double.IsNaN(height)||Double.IsInfinity(height)||height<=0)throw new ArgumentException("标注字高必须大于0。");
    string handle;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     Entity area=(Entity)tr.GetObject(OutputId(db,source),OpenMode.ForRead);
     ObjectId layerId=OutputLayer(db,tr,layer,7,true);
     MLeader leader=null;bool created=String.IsNullOrEmpty(existing);
     if(!created){leader=tr.GetObject(OutputId(db,existing),OpenMode.ForWrite) as MLeader;if(leader==null)throw new ArgumentException("请选择整体面积引线。");}
     else {
      leader=new MLeader();leader.SetDatabaseDefaults(db);
      leader.MLeaderStyle=AreaLeaderStyle(db,tr);leader.Scale=1.0;
      leader.Annotative=AnnotativeStates.False;
      leader.ContentType=ContentType.MTextContent;
      leader.LeaderLineType=LeaderType.StraightLeader;
      leader.EnableLanding=true;leader.EnableDogleg=true;
      leader.LandingGap=0;
      leader.TextStyleId=AreaLeaderTextStyle(db,tr);
     }
     // Capture native grip/MOVE geometry BEFORE assigning MText. Stored pick
     // coordinates are creation hints, never a reason to reset a moved label.
     int pickedIndex=-1,pickedLine=-1;double landingSpan=0;Vector3d landingDirection=Vector3d.XAxis;
     if(pickedLanding){
      if(created){landingSpan=Math.Abs(point.X-elbow.X);landingDirection=point.X<elbow.X?-Vector3d.XAxis:Vector3d.XAxis;}
      else{
       pickedIndex=(int)leader.GetLeaderIndexes()[0];pickedLine=(int)leader.GetLeaderLineIndexes(pickedIndex)[0];
       elbow=leader.GetLastVertex(pickedLine);landingDirection=leader.GetDogleg(pickedIndex);
       using(var previous=leader.MText)landingSpan=leader.GetDoglegLength(pickedIndex)+previous.ActualWidth;
      }
      if(Double.IsNaN(landingSpan)||Double.IsInfinity(landingSpan)||landingSpan<=1e-8)throw new ArgumentException("横线尾端须位于折点的左侧或右侧。");
     }
     Point3d location=created?point:leader.TextLocation;
     leader.ArrowSize=height*0.3;if(!pickedLanding)leader.DoglegLength=height*2;
     leader.LayerId=layerId;leader.ColorIndex=256;
     leader.LeaderLineColor=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByLayer,256);
     leader.TextColor=leader.LeaderLineColor;
     leader.TextHeight=height;leader.TextAlignmentType=TextAlignmentType.LeftAlignment;
     var attachment=layout==0?TextAttachmentType.AttachmentBottomOfTopLine:TextAttachmentType.AttachmentBottomLine;
     leader.SetTextAttachmentType(attachment,LeaderDirectionType.LeftLeader);
     leader.SetTextAttachmentType(attachment,LeaderDirectionType.RightLeader);
     leader.ExtendLeaderToText=true;
     // Preserve the designer's native MOVE/grip position when refreshing contents.
     using(MText contents=created?new MText():leader.MText) {
      if(created)contents.SetDatabaseDefaults(db);
      contents.TextStyleId=leader.TextStyleId;
      contents.Contents=text;contents.TextHeight=height;contents.Width=0;
      contents.Attachment=AttachmentPoint.MiddleLeft;contents.Location=location;
      leader.MText=contents;
     }
     // Assigning MText or changing attachment can recalculate the native landing.
     // Restore the actual designer position after those operations.
     if(!created&&!pickedLanding)leader.TextLocation=location;
     if(created) {
      var space=(BlockTableRecord)tr.GetObject(area.OwnerId,OpenMode.ForWrite);
      space.AppendEntity(leader);tr.AddNewlyCreatedDBObject(leader,true);
      int index=leader.AddLeader(),line=leader.AddLeaderLine(index);
      leader.AddFirstVertex(line,anchor);
      leader.AddLastVertex(line,pickedLanding?elbow:new Point3d(point.X-height*2,point.Y,point.Z));
      if(pickedLanding){pickedIndex=index;pickedLine=line;}
      else{leader.SetDogleg(index,Vector3d.XAxis);leader.TextLocation=point;}
      OutputMark(db,tr,leader,"AREA_LABEL",source);
     }
     if(pickedLanding)SetAreaLanding(leader,pickedIndex,pickedLine,elbow,landingDirection,landingSpan,height);
     handle=leader.Handle.ToString();tr.Commit();
    }
    return new ResultBuffer(new TypedValue((int)LispDataType.Text,handle));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue((int)LispDataType.Text,"ERROR: "+ex.Message));}
  }
  static ObjectId AreaLeaderTextStyle(Database db,Transaction tr){
   // Freeze the first chosen font for this drawing's output annotations. A
   // later TEXTSTYLE switch must not change the appearance of the next bed.
   const string name="PLANTCAD_面积标注";var styles=(TextStyleTable)tr.GetObject(db.TextStyleTableId,OpenMode.ForRead);
   if(styles.Has(name))return styles[name];
   var source=(TextStyleTableRecord)tr.GetObject(db.Textstyle,OpenMode.ForRead);
   var copy=(TextStyleTableRecord)source.Clone();copy.Name=name;copy.TextSize=0;
   styles.UpgradeOpen();ObjectId id=styles.Add(copy);tr.AddNewlyCreatedDBObject(copy,true);return id;
  }
  static ObjectId AreaLeaderStyle(Database db,Transaction tr){
   const string name="PLANTCAD_面积引线";
   var styles=(DBDictionary)tr.GetObject(db.MLeaderStyleDictionaryId,OpenMode.ForRead);
   if(styles.Contains(name))return styles.GetAt(name);
   var copy=(MLeaderStyle)((MLeaderStyle)tr.GetObject(db.MLeaderstyle,OpenMode.ForRead)).Clone();
   styles.UpgradeOpen();ObjectId id=styles.SetAt(name,copy);tr.AddNewlyCreatedDBObject(copy,true);return id;
  }
  static void SetAreaLanding(MLeader leader,int index,int line,Point3d elbow,Vector3d direction,double span,double height){
   // Extended native landings include the actual text width. Reserve only the
   // remaining distance for the dogleg, and keep the designer's two endpoints.
   double width;
   using(var text=leader.MText){
    width=text.ActualWidth;
    if(width>span){height*=span/width;text.TextHeight=height;leader.MText=text;}
   }
   leader.TextHeight=height;leader.ArrowSize=height*.3;
   using(var text=leader.MText)width=text.ActualWidth;
   leader.SetDogleg(index,direction);leader.SetDoglegLength(index,Math.Max(0,span-width));
   // Setting the text location/attachment can move the last vertex in CAD.
   // Set the picked elbow last, after all native text and dogleg calculations.
   leader.SetLastVertex(line,elbow);
  }
  static Point3d OutputPoint(object value) {
   var p=value as System.Collections.Generic.List<object>;
   if(p==null||p.Count!=3)throw new ArgumentException("需要三维坐标。");
   return new Point3d(Convert.ToDouble(p[0]),Convert.ToDouble(p[1]),Convert.ToDouble(p[2]));
  }
  [LispFunction("pl:native-leader-text")]
  public ResultBuffer ReadAreaLeaderText(ResultBuffer args) {
   try {
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
    using(Transaction tr=db.TransactionManager.StartTransaction()) {
     var leader=tr.GetObject(OutputId(db,Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead) as MLeader;
     if(leader==null)return null;
     using(MText text=leader.MText)return new ResultBuffer(new TypedValue((int)LispDataType.Text,text.Contents));
    }
   }catch{return null;}
  }
 }
}
