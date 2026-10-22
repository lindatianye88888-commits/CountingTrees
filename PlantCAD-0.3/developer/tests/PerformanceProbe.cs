using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using PlantCADBridge;
[assembly:CommandClass(typeof(PerformanceProbe))]
public class PerformanceProbe {
 [CommandMethod("PC_PERFORMANCE_PROBE")]
 public void Run(){
  var report=new Dictionary<string,object>();var counts=new Dictionary<string,int>();var roles=new Dictionary<string,int>();
  var areas=new List<string>();var failures=new List<object>();var samples=new List<object>();
  var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;var timer=Stopwatch.StartNew();
  try {
   using(Transaction tr=db.TransactionManager.StartTransaction()){
    var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead);
    foreach(ObjectId id in (BlockTableRecord)tr.GetObject(blocks[BlockTableRecord.ModelSpace],OpenMode.ForRead)){
     var e=tr.GetObject(id,OpenMode.ForRead) as Entity;if(e==null)continue;string name=e.GetType().Name;if(!counts.ContainsKey(name))counts[name]=0;counts[name]++;
     try{using(ResultBuffer data=e.GetXDataForApplication("PLANTCAD01"))if(data!=null){foreach(TypedValue v in data)if(v.TypeCode==1000){string role=Convert.ToString(v.Value);if(!roles.ContainsKey(role))roles[role]=0;roles[role]++;if(role=="AREA")areas.Add(e.Handle.ToString());break;}}}
     catch(System.Exception ex){failures.Add(new{stage="scan xdata",type=name,handle=e.Handle.ToString(),error=ex.Message});}
    }
   }
   report["scan_ms"]=timer.Elapsed.TotalMilliseconds;
   foreach(string handle in areas){
    timer.Restart();string signature,fill;
    using(var args=new ResultBuffer(new TypedValue(5005,handle)))using(ResultBuffer result=new Bridge().AreaOutputSignature(args))signature=result==null?"NULL":Convert.ToString(result.AsArray()[0].Value);
    double signatureMs=timer.Elapsed.TotalMilliseconds;timer.Restart();
    string repeated;
    using(var args=new ResultBuffer(new TypedValue(5005,handle)))using(ResultBuffer result=new Bridge().AreaOutputSignature(args))repeated=result==null?"NULL":Convert.ToString(result.AsArray()[0].Value);
    double repeatedMs=timer.Elapsed.TotalMilliseconds;timer.Restart();
    using(var args=new ResultBuffer(new TypedValue(5005,handle),new TypedValue(5005,"ANSI31"),new TypedValue(5001,100.0),new TypedValue(5001,0.0),new TypedValue(5005,"PL_灌木_填充")))using(ResultBuffer result=new Bridge().WriteAreaFill(args))fill=result==null?"NULL":Convert.ToString(result.AsArray()[0].Value);
    samples.Add(new{handle=handle,signature_ms=signatureMs,repeat_signature_ms=repeatedMs,repeat_equal=signature==repeated,signature_ok=!signature.StartsWith("ERROR:"),fill_ms=timer.Elapsed.TotalMilliseconds,fill=fill});
    if(fill.StartsWith("ERROR:")){
     try{using(Transaction tr=db.TransactionManager.StartTransaction()){
      var id=db.GetObjectId(false,new Handle(Int64.Parse(handle,System.Globalization.NumberStyles.HexNumber)),0);var boundary=(Entity)tr.GetObject(id,OpenMode.ForRead);
      object loops=typeof(Bridge).GetMethod("OutputLoops",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,new object[]{boundary});
      foreach(IEnumerable loop in (IEnumerable)loops)foreach(IDisposable curve in loop)curve.Dispose();
     }}catch(System.Exception ex){failures.Add(new{stage="OutputLoops",handle=handle,error=(ex.InnerException??ex).ToString()});}
    }
   }
   report["passed"]=true;
  }catch(System.Exception ex){report["fatal"]=ex.ToString();report["passed"]=false;}
  report["types"]=counts;report["roles"]=roles;report["areas"]=samples;report["failures"]=failures;
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(doc.Name),"performance.json"),new JavaScriptSerializer{MaxJsonLength=4194304}.Serialize(report));
 }
}
