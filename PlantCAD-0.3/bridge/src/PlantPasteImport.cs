using System;
using System.Collections.Generic;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;

namespace PlantCADBridge {
 public sealed partial class Bridge {
  static readonly Dictionary<Document,PasteTracker> pasteTrackers=new Dictionary<Document,PasteTracker>();
  static readonly HashSet<string> pasteRoles=new HashSet<string> {
   "TREE","AREA","PROJECT_SOURCE","LABEL","LEADER","AREA_LABEL","AREA_LEADER","AREA_ARROW","AREA_FILL","FILL_EDGE"
  };

  static void InitializePasteImport() {
   AcadApp.DocumentManager.DocumentCreated+=OnPasteDocumentCreated;
   foreach(Document doc in AcadApp.DocumentManager) WatchPastes(doc);
  }
  static void OnPasteDocumentCreated(object sender,DocumentCollectionEventArgs args) { WatchPastes(args.Document); }
  static void WatchPastes(Document doc) {
   if(!pasteTrackers.ContainsKey(doc)) pasteTrackers.Add(doc,new PasteTracker(doc));
  }
  static void ForgetPastes(Document doc) {
   PasteTracker tracker;
   if(!pasteTrackers.TryGetValue(doc,out tracker)) return;
   tracker.Dispose();
   pasteTrackers.Remove(doc);
  }
  static void TerminatePasteImport() {
   AcadApp.DocumentManager.DocumentCreated-=OnPasteDocumentCreated;
   foreach(PasteTracker tracker in pasteTrackers.Values) tracker.Dispose();
   pasteTrackers.Clear();
  }
  static void DispatchPasteImport() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   PasteTracker tracker;
   if(doc!=null && pasteTrackers.TryGetValue(doc,out tracker) && tracker.HasPending && CadIsIdle(doc))
    tracker.Dispatch();
  }

  [LispFunction("pl:native-paste-batches")]
  public ResultBuffer TakePasteBatches(ResultBuffer args) {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   PasteTracker tracker;
   if(doc==null || !pasteTrackers.TryGetValue(doc,out tracker)) return null;
   return tracker.TakeBatches();
  }

  sealed class PasteTracker : IDisposable {
   readonly Document doc;
   readonly List<List<ObjectId>> completed=new List<List<ObjectId>>();
   readonly List<List<string>> ready=new List<List<string>>();
   List<ObjectId> appending;
   Database watchedDatabase;

   internal PasteTracker(Document doc) {
    this.doc=doc;
    doc.CommandWillStart+=OnStart;
    doc.CommandEnded+=OnEnd;
    doc.CommandCancelled+=OnAbort;
    doc.CommandFailed+=OnAbort;
   }
   static bool IsPaste(CommandEventArgs args) {
    return String.Equals(args.GlobalCommandName,"PASTECLIP",StringComparison.OrdinalIgnoreCase)
     || String.Equals(args.GlobalCommandName,"PASTEORIG",StringComparison.OrdinalIgnoreCase);
   }
   void OnStart(object sender,CommandEventArgs args) {
    if(!IsPaste(args) || watchedDatabase!=null) return;
    watchedDatabase=doc.Database;
    appending=new List<ObjectId>();
    watchedDatabase.ObjectAppended+=OnAppend;
   }
   void OnAppend(object sender,ObjectEventArgs args) {
    // Opening objects while AutoCAD is cloning can interfere with its transaction.
    if(appending!=null && args.DBObject is Entity) appending.Add(args.DBObject.ObjectId);
   }
   void OnEnd(object sender,CommandEventArgs args) {
    if(!IsPaste(args) || appending==null) return;
    if(appending.Count>0) completed.Add(appending);
    StopCapture();
   }
   void OnAbort(object sender,CommandEventArgs args) {
    if(IsPaste(args)) StopCapture();
   }
   void StopCapture() {
    if(watchedDatabase!=null && !watchedDatabase.IsDisposed) watchedDatabase.ObjectAppended-=OnAppend;
    watchedDatabase=null;
    appending=null;
   }

   internal bool HasPending { get { return completed.Count>0 && appending==null; } }
   internal void Dispatch() {
    try {
     int queuedBatches=ready.Count;
     foreach(List<ObjectId> batch in completed) {
      List<string> handles=ManagedHandles(batch);
      if(handles.Count>0) ready.Add(handles);
     }
     if(ready.Count==queuedBatches) return;
     string package=PackageRoot();
     // Take the captured IDs before loading LISP so a failed load cannot hold the queue open.
     doc.SendStringToExecute("((lambda (batches / pl:*paste-load*) (if batches (progn "+
      "(if (not (boundp 'pl:*paste-import-loaded*)) (progn "+
      "(setq pl:*paste-load* T pl:*dir* "+Quote(package)+") (load "+Quote(Path.Combine(package,"plantcad.lsp"))+"))) "+
      "(pl:import-pasted-batches batches))) (princ)) (cdr (pl:native-paste-batches)))\n",false,false,false);
    } catch(System.Exception ex) {
     ready.Clear();
     doc.Editor.WriteMessage("\nCountingTrees（数树）粘贴识别失败："+ex.Message);
    } finally { completed.Clear(); }
   }
   List<string> ManagedHandles(List<ObjectId> batch) {
    var handles=new List<string>();
    var seen=new HashSet<ObjectId>();
    Database db=doc.Database;
    using(Transaction tr=db.TransactionManager.StartOpenCloseTransaction()) {
     var apps=(RegAppTable)tr.GetObject(db.RegAppTableId,OpenMode.ForRead);
     if(!apps.Has("PLANTCAD01")) return handles;
     foreach(ObjectId id in batch) {
      if(id.IsNull || !id.IsValid || id.IsErased || !seen.Add(id)) continue;
      var entity=tr.GetObject(id,OpenMode.ForRead) as Entity;
      if(entity==null || entity.OwnerId.IsNull || entity.OwnerId.IsErased) continue;
      using(ResultBuffer data=entity.GetXDataForApplication("PLANTCAD01")) {
       if(data==null) continue;
       string role=null;
       foreach(TypedValue item in data) {
        if(item.TypeCode==1000) { role=Convert.ToString(item.Value); break; }
       }
       if(!pasteRoles.Contains(role)) continue;
      }
      var owner=tr.GetObject(entity.OwnerId,OpenMode.ForRead) as BlockTableRecord;
      if(owner!=null && owner.IsLayout) handles.Add(entity.Handle.ToString());
     }
     tr.Commit();
    }
    return handles;
   }
   internal ResultBuffer TakeBatches() {
    if(ready.Count==0) return null;
    var result=new ResultBuffer(new TypedValue((int)LispDataType.Text,"PASTE_BATCHES"));
    foreach(List<string> batch in ready) AddValue(result,batch);
    ready.Clear();
    return result;
   }
   public void Dispose() {
    StopCapture();
    doc.CommandWillStart-=OnStart;
    doc.CommandEnded-=OnEnd;
    doc.CommandCancelled-=OnAbort;
    doc.CommandFailed-=OnAbort;
   }
  }
 }
}
