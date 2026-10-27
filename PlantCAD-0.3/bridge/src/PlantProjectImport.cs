using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;

namespace PlantCADBridge {
 public sealed partial class Bridge {
  [LispFunction("pl:native-project-record")]
  public ResultBuffer ReadProjectRecord(ResultBuffer args){
   try{
    Database db=AcadApp.DocumentManager.MdiActiveDocument.Database;
    using(Transaction tr=db.TransactionManager.StartTransaction()){
     var entity=tr.GetObject(OutputId(db,Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead) as Entity;
     if(entity==null||entity is Table||entity is Curve||entity is Hatch)return null;
     var values=new List<TypedValue>();int visited=0;CollectAreaLabelLines(entity,tr,values,0,ref visited,true);
     if(visited>=128)return null; // Do not import a truncated plan block as a single plant.
     var lines=new List<string>();foreach(var value in values)lines.Add(Convert.ToString(value.Value));
     var record=PlantAnnotationParser.Parse(lines,entity is BlockReference);if(record==null)return null;
     return new ResultBuffer(new TypedValue(5005,"PROJECT_RECORD"),new TypedValue(5005,record.Name),new TypedValue(5005,record.Spec),
      new TypedValue(5003,record.Area?1:0),new TypedValue(5003,record.Block?1:0),
      new TypedValue(5001,record.Dbh),new TypedValue(5001,record.Caliper),new TypedValue(5001,record.Height),new TypedValue(5001,record.Crown));
    }
   }catch(System.Exception ex){
    AcadApp.DocumentManager.MdiActiveDocument.Editor.WriteMessage("\n此对象未采集："+ex.Message);return null;
   }
  }
 }
}
