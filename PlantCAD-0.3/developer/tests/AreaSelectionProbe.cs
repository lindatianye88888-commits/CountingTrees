using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(AreaSelectionProbe))]
public sealed class AreaSelectionProbe {
 static readonly List<string> handles=new List<string>();
 static string extra;
 [CommandMethod("PC_SELECTION_INPUT")]
 public void Input(){
  handles.Clear();var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;
  using(var tr=db.TransactionManager.StartTransaction()){
   var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForWrite);
   string[] names={"PC_SOURCE_YELLOW","PC_FOREIGN_BLUE","PC_OTHER_YELLOW","PL_面积_计算边界","PL_标注_区域","PL_面积_推定补线","PL_树木_圆圈"};
   foreach(string name in names){if(!layers.Has(name)){var l=new LayerTableRecord{Name=name};layers.Add(l);tr.AddNewlyCreatedDBObject(l,true);}
    var layer=(LayerTableRecord)tr.GetObject(layers[name],OpenMode.ForWrite);layer.Color=Autodesk.AutoCAD.Colors.Color.FromColorIndex(Autodesk.AutoCAD.Colors.ColorMethod.ByAci,(short)(name=="PC_FOREIGN_BLUE"?5:2));layer.IsOff=name=="PL_树木_圆圈";
   }
   var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);
   Action<Entity,string,bool> add=(e,layer,selected)=>{e.SetDatabaseDefaults(db);e.LayerId=layers[layer];e.ColorIndex=256;space.AppendEntity(e);tr.AddNewlyCreatedDBObject(e,true);if(selected)handles.Add(e.Handle.ToString());else extra=e.Handle.ToString();};
   var corners=new[]{new Point3d(0,0,0),new Point3d(13000,0,0),new Point3d(13000,1000,0),new Point3d(0,1000,0)};
   for(int i=0;i<4;i++)add(new Line(corners[i],corners[(i+1)%4]),"PC_SOURCE_YELLOW",true);
   for(int i=1;i<13;i++)add(new Line(new Point3d(i*1000,0,0),new Point3d(i*1000,1000,0)),"PC_SOURCE_YELLOW",true);
   for(int i=0;i<12;i++)add(new Circle(new Point3d(500+i*1000,500,0),Vector3d.ZAxis,700),"PC_FOREIGN_BLUE",true);
   add(new Circle(new Point3d(50000,50000,0),Vector3d.ZAxis,1000),"PC_OTHER_YELLOW",false);
   tr.Commit();
  }
 }
 [LispFunction("pc:label-input")]
 public ResultBuffer LabelInput(ResultBuffer args){
  var values=new List<TypedValue>();var db=Application.DocumentManager.MdiActiveDocument.Database;
  using(var tr=db.TransactionManager.StartTransaction()){
   var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);
   Action<Entity> add=e=>{e.SetDatabaseDefaults(db);space.AppendEntity(e);tr.AddNewlyCreatedDBObject(e,true);values.Add(new TypedValue((int)LispDataType.Text,e.Handle.ToString()));};
   add(new DBText{TextString="红叶石楠",Position=new Point3d(20000,0,0),Height=100});
   add(new MText{Contents="{\\C2;红叶石楠}\\PP001",Location=new Point3d(20000,1000,0),TextHeight=100});
   var leader=new MLeader();leader.SetDatabaseDefaults(db);leader.ContentType=ContentType.MTextContent;
   using(var text=new MText{Contents="红叶石楠",TextHeight=100})leader.MText=text;
   add(leader);
   var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForWrite);
   var definition=new BlockTableRecord{Name="PC_LABEL_SAMPLE"};blocks.Add(definition);tr.AddNewlyCreatedDBObject(definition,true);
   var nested=new MText{Contents="红叶石楠",Location=Point3d.Origin,TextHeight=100};definition.AppendEntity(nested);tr.AddNewlyCreatedDBObject(nested,true);
   add(new BlockReference(new Point3d(20000,2000,0),definition.ObjectId));tr.Commit();
  }
  return new ResultBuffer(values.ToArray());
 }
 [LispFunction("pc:input-handles")]
 public ResultBuffer Handles(ResultBuffer args){var values=new List<TypedValue>();foreach(string handle in handles)values.Add(new TypedValue((int)LispDataType.Text,handle));return new ResultBuffer(values.ToArray());}
 [LispFunction("pc:extra-handle")]
 public ResultBuffer Extra(ResultBuffer args){return new ResultBuffer(new TypedValue((int)LispDataType.Text,extra));}
}
