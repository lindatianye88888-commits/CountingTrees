using System;
using System.Collections.Generic;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
public sealed class ProjectImportProbe {
 static readonly List<string> Handles=new List<string>();
 static void Add(BlockTableRecord space,Transaction tr,Entity entity){space.AppendEntity(entity);tr.AddNewlyCreatedDBObject(entity,true);Handles.Add(entity.Handle.ToString());}
 static DBText Text(string value,double x,double y){return new DBText{TextString=value,Position=new Point3d(x,y,0),Height=.25};}
 [CommandMethod("PC_IMPORT_SEED")]
 public void Seed(){
  var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;
  var parent=new DirectoryInfo(Path.GetDirectoryName(doc.Name));
  if(!parent.Name.StartsWith("project-import-")||parent.Parent.Name!="host-output")throw new InvalidOperationException("Test seed only accepts an owned project-import-* / host-output drawing copy.");
  Handles.Clear();
  using(var tr=db.TransactionManager.StartTransaction()){
   var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);
   var old=new List<ObjectId>();foreach(ObjectId id in space)old.Add(id);foreach(var id in old)((Entity)tr.GetObject(id,OpenMode.ForWrite)).Erase();
   var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForWrite);
   var symbol=new BlockTableRecord{Name="PC_IMPORT_SYMBOL"};blocks.Add(symbol);tr.AddNewlyCreatedDBObject(symbol,true);
   var circle=new Circle(Point3d.Origin,Vector3d.ZAxis,.5);symbol.AppendEntity(circle);tr.AddNewlyCreatedDBObject(circle,true);
   var name=Text("银杏",-.2,.15);symbol.AppendEntity(name);tr.AddNewlyCreatedDBObject(name,true);
   var diameter=Text("12",-.1,-.25);symbol.AppendEntity(diameter);tr.AddNewlyCreatedDBObject(diameter,true);
   Add(space,tr,new BlockReference(Point3d.Origin,symbol.ObjectId));
   Add(space,tr,new BlockReference(new Point3d(3,0,0),symbol.ObjectId));
   using(var box=new Polyline()){
    box.AddVertexAt(0,new Point2d(0,3),0,0,0);box.AddVertexAt(1,new Point2d(3.13,3),0,0,0);
    box.AddVertexAt(2,new Point2d(3.13,4),0,0,0);box.AddVertexAt(3,new Point2d(0,4),0,0,0);box.Closed=true;
    var curves=new DBObjectCollection();curves.Add(box);var shapes=Region.CreateFromCurves(curves);Add(space,tr,(Region)shapes[0]);
   }
   Add(space,tr,Text("银杏",-4,0));
   Add(space,tr,new MText{Contents="海桐\\P3.13 平方米",Location=new Point3d(-4,3,0),TextHeight=.25,Width=8});
   Add(space,tr,Text("紫珠",-4,5));
   Add(space,tr,new MText{Contents="八宝景天",Location=new Point3d(-4,7,0),TextHeight=.25,Width=8});
   using(var content=new MText{Contents="海桐 9999 平方米",TextHeight=.25,Width=8}){
    var leader=new MLeader{ContentType=ContentType.MTextContent,MText=content,TextLocation=new Point3d(-4,9,0)};Add(space,tr,leader);
   }
   Add(space,tr,new BlockReference(new Point3d(6,0,0),symbol.ObjectId));
   tr.Commit();
  }
 }
 [LispFunction("pc:import-fixtures")]
 public ResultBuffer Fixtures(ResultBuffer args){var values=new List<TypedValue>();foreach(string h in Handles)values.Add(new TypedValue(5005,h));return new ResultBuffer(values.ToArray());}
}
