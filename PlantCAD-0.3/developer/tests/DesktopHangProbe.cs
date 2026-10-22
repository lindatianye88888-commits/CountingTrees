using System;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
[assembly:CommandClass(typeof(DesktopHangProbe))]
public class DesktopHangProbe {
 static System.Windows.Forms.Timer projectTimer;
 static int projectPhase,projectChecks,smallGrid;
 static string projectRoot;
 static System.Windows.Forms.Control FindControl(System.Windows.Forms.Control parent,Type kind,string text){
  foreach(System.Windows.Forms.Control c in parent.Controls){if(kind.IsInstanceOfType(c)&&(text==null||c.Text==text))return c;var nested=FindControl(c,kind,text);if(nested!=null)return nested;}return null;
 }
 static void ProjectCheck(bool value,string message){if(!value)throw new InvalidOperationException(message);projectChecks++;}
 [CommandMethod("PC_PROJECT_OBSERVE",CommandFlags.Modal|CommandFlags.NoUndoMarker|CommandFlags.NoHistory)]
 public void ObserveProject(){
  projectRoot=Path.GetDirectoryName(AcadApp.DocumentManager.MdiActiveDocument.Name);projectPhase=0;projectChecks=0;
  projectTimer=new System.Windows.Forms.Timer{Interval=250};projectTimer.Tick+=(s,e)=>{
   try{
    System.Windows.Forms.Form form=null;foreach(System.Windows.Forms.Form f in System.Windows.Forms.Application.OpenForms)if(f.Text=="PlantCAD - 项目植物与规格")form=f;
    if(form==null)return;
    var grid=(System.Windows.Forms.DataGridView)FindControl(form,typeof(System.Windows.Forms.DataGridView),null);
    if(projectPhase==0){
     ProjectCheck(form.FormBorderStyle==System.Windows.Forms.FormBorderStyle.Sizable&&form.MaximizeBox,"Resize border missing");
     ProjectCheck(grid.Columns.Count==8,"Project columns changed");
     int allKinds=0;foreach(System.Windows.Forms.DataGridViewRow row in grid.Rows)if(Convert.ToString(row.Cells[2].Value).StartsWith("界面对齐"))allKinds++;
     ProjectCheck(allKinds==6,"Six project categories missing");form.Size=new System.Drawing.Size(800,420);projectPhase=1;return;
    }
    if(projectPhase==1){smallGrid=grid.Height;ProjectCheck(smallGrid>40,"Small window clips plant rows");form.Size=new System.Drawing.Size(1300,720);projectPhase=2;return;}
    ProjectCheck(grid.Height>smallGrid+100,"List does not grow with window");
    using(var image=new System.Drawing.Bitmap(form.Width,form.Height)){form.DrawToBitmap(image,new System.Drawing.Rectangle(0,0,form.Width,form.Height));image.Save(Path.Combine(projectRoot,"project-dialog.png"));}
    var category=(System.Windows.Forms.ComboBox)FindControl(form,typeof(System.Windows.Forms.ComboBox),null);
    var query=(System.Windows.Forms.TextBox)FindControl(form,typeof(System.Windows.Forms.TextBox),null);
    category.SelectedIndex=4;bool balls=grid.Rows.Count>0;foreach(System.Windows.Forms.DataGridViewRow row in grid.Rows)balls&=Convert.ToString(row.Cells[0].Value)=="灌木球";
    ProjectCheck(balls,"Ball category filter failed");category.SelectedIndex=0;query.Text="UI5";
    ProjectCheck(grid.Rows.Count==1&&Convert.ToString(grid.Rows[0].Cells[1].Value)=="UI5","Spec number filtering lost selection");
    var accept=(System.Windows.Forms.Button)FindControl(form,typeof(System.Windows.Forms.Button),"设为当前规格");ProjectCheck(accept!=null&&accept.Enabled,"Selected specification action missing");
    projectTimer.Stop();projectTimer.Dispose();projectTimer=null;
    File.WriteAllText(Path.Combine(projectRoot,"project-probe.txt"),"PASS "+projectChecks);accept.PerformClick();
   }catch(System.Exception ex){projectTimer.Stop();projectTimer.Dispose();projectTimer=null;File.WriteAllText(Path.Combine(projectRoot,"project-probe.txt"),ex.ToString());}
  };projectTimer.Start();
 }
 static string root;
 static DateTime lastIdle;
 static void Log(string message){File.AppendAllText(Path.Combine(root,"events.log"),DateTime.UtcNow.ToString("O")+" "+message+Environment.NewLine);}
 [CommandMethod("PC_HANG_OBSERVE")]
 public void Observe(){
  Document doc=AcadApp.DocumentManager.MdiActiveDocument;
  root=Path.GetDirectoryName(doc.Name);
  doc.CommandWillStart+=(s,e)=>Log("START "+e.GlobalCommandName);
  doc.CommandEnded+=(s,e)=>Log("END "+e.GlobalCommandName);
  doc.CommandFailed+=(s,e)=>Log("FAILED "+e.GlobalCommandName);
  doc.CommandCancelled+=(s,e)=>Log("CANCELLED "+e.GlobalCommandName);
  AcadApp.Idle+=(s,e)=>{if((DateTime.UtcNow-lastIdle).TotalSeconds>1){lastIdle=DateTime.UtcNow;Log("IDLE");}};
  Log("OBSERVED");
 }
 [CommandMethod("PC_HANG_SNAPSHOT",CommandFlags.Modal|CommandFlags.NoUndoMarker|CommandFlags.NoHistory)]
 public void Snapshot(){
  Document doc=AcadApp.DocumentManager.MdiActiveDocument;
  int entities=0,fills=0,trees=0;
  using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
   var space=(BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(doc.Database),OpenMode.ForRead);
   foreach(ObjectId id in space){
    entities++;
    var entity=tr.GetObject(id,OpenMode.ForRead) as Entity;
    using(ResultBuffer data=entity.GetXDataForApplication("PLANTCAD01")){
     if(data==null)continue;
     foreach(TypedValue v in data){if(v.TypeCode==1000&&Convert.ToString(v.Value)=="AREA_FILL")fills++;if(v.TypeCode==1000&&Convert.ToString(v.Value)=="TREE")trees++;}
    }
   }
  }
  Log("SNAPSHOT "+entities+" "+fills+" "+trees);
 }
 [LispFunction("pc:leader-points")]
 public ResultBuffer LeaderPoints(ResultBuffer args){
  Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
  ObjectId id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(args.AsArray()[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(Transaction tr=db.TransactionManager.StartTransaction()){
   var leader=(MLeader)tr.GetObject(id,OpenMode.ForRead);
   int index=(int)leader.GetLeaderIndexes()[0],line=(int)leader.GetLeaderLineIndexes(index)[0];
   return new ResultBuffer(new TypedValue(5009,leader.TextLocation),new TypedValue(5009,leader.GetFirstVertex(line)));
  }
 }
 [LispFunction("pc:table-display-check")]
 public ResultBuffer TableDisplay(ResultBuffer args){
  var db=AcadApp.DocumentManager.MdiActiveDocument.Database;
  var id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(args.AsArray()[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(var tr=db.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(id,OpenMode.ForRead);bool ok=table.Cells[1,0].TextString=="编号"&&table.Cells[1,1].TextString=="图例";
   double height=table.Cells[1,0].TextHeight.Value;
   for(int r=2;r<table.Rows.Count;r++)for(int c=0;c<table.Columns.Count;c++)foreach(CellContent content in table.Cells[r,c].Contents)if(Math.Abs(content.TextHeight-height)>1e-6)ok=false;
   return new ResultBuffer(new TypedValue(5003,ok?1:0));
  }
 }
 [LispFunction("pc:edit-area-name")]
 public ResultBuffer EditAreaName(ResultBuffer args){
  var db=AcadApp.DocumentManager.MdiActiveDocument.Database;var v=args.AsArray();
  var id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(v[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(var tr=db.TransactionManager.StartTransaction()){
   var leader=(MLeader)tr.GetObject(id,OpenMode.ForWrite);
   using(var text=leader.MText){text.Contents=Convert.ToString(v[1].Value);leader.MText=text;}tr.Commit();
  }return new ResultBuffer(new TypedValue(5003,1));
 }
 [LispFunction("pc:leader-style")]
 public ResultBuffer LeaderStyle(ResultBuffer args){
  var db=AcadApp.DocumentManager.MdiActiveDocument.Database;
  var id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(args.AsArray()[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(var tr=db.TransactionManager.StartTransaction()){
   var leader=(MLeader)tr.GetObject(id,OpenMode.ForRead);
   return new ResultBuffer(new TypedValue(5001,leader.TextHeight),new TypedValue(5001,leader.ArrowSize),new TypedValue(5001,leader.DoglegLength),new TypedValue(5009,leader.TextLocation));
  }
 }
 [LispFunction("pc:table-heights")]
 public ResultBuffer TableHeights(ResultBuffer args){
  var db=AcadApp.DocumentManager.MdiActiveDocument.Database;
  var id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(args.AsArray()[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(var tr=db.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(id,OpenMode.ForRead);
   return new ResultBuffer(new TypedValue(5001,table.Cells[1,0].TextHeight.Value),new TypedValue(5001,table.Cells[2,0].TextHeight.Value));
  }
 }
 [LispFunction("pc:table-named-legends-check")]
 public ResultBuffer NamedLegends(ResultBuffer args){
  var db=AcadApp.DocumentManager.MdiActiveDocument.Database;
  var id=db.GetObjectId(false,new Handle(Int64.Parse(Convert.ToString(args.AsArray()[0].Value),System.Globalization.NumberStyles.HexNumber)),0);
  using(var tr=db.TransactionManager.StartTransaction()){
   var table=(Table)tr.GetObject(id,OpenMode.ForRead);bool ok=true;
   for(int row=2;row<table.Rows.Count;row++){
    var content=table.Cells[row,1].Contents;bool found=false;
    if(content.Count>0&&!content[0].BlockTableRecordId.IsNull){
     var block=(BlockTableRecord)tr.GetObject(content[0].BlockTableRecordId,OpenMode.ForRead);
     Autodesk.AutoCAD.DatabaseServices.Extents3d? bounds=null;
     foreach(ObjectId child in block){
      var entity=(Entity)tr.GetObject(child,OpenMode.ForRead);var text=entity as DBText;
      if(text!=null&&text.TextString==table.Cells[row,2].TextString)found=true;
      var extent=entity.GeometricExtents;if(bounds.HasValue){var combined=bounds.Value;combined.AddExtents(extent);bounds=combined;}else bounds=extent;
     }
     if(bounds.HasValue){var size=bounds.Value.MaxPoint-bounds.Value.MinPoint;double scale=content[0].Scale;
      ok&=size.X*scale<table.Columns[1].Width&&size.Y*scale<table.Rows[row].Height;
     }
    }
    ok&=found;
   }
   return new ResultBuffer(new TypedValue(5003,ok?1:0));
  }
 }
}
