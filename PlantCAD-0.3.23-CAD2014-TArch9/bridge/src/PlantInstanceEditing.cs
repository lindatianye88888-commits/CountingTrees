using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using AcadApp=Autodesk.AutoCAD.ApplicationServices.Application;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  static Document instanceDocument;
  static string instanceHandle;
  static DateTime instanceClick;
  static Document pendingInstanceDocument;
  static string pendingInstanceHandle;
  static void InitializeInstanceEditing(){AcadApp.BeginDoubleClick+=OnPlantDoubleClick;AcadApp.DocumentManager.DocumentLockModeChanged+=OnDoubleClickCommand;}
  static void TerminateInstanceEditing(){AcadApp.BeginDoubleClick-=OnPlantDoubleClick;AcadApp.DocumentManager.DocumentLockModeChanged-=OnDoubleClickCommand;instanceDocument=null;instanceHandle=null;pendingInstanceDocument=null;pendingInstanceHandle=null;}
  static void OnPlantDoubleClick(object sender,BeginDoubleClickEventArgs args){
   instanceDocument=null;instanceHandle=null;
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;if(doc==null||!CadIsIdle(doc))return;
   try{
    PromptSelectionResult selected=doc.Editor.SelectImplied();if(selected.Status!=PromptStatus.OK||selected.Value.Count!=1)return;
    using(Transaction tr=doc.Database.TransactionManager.StartTransaction()){
     var block=tr.GetObject(selected.Value.GetObjectIds()[0],OpenMode.ForRead) as BlockReference;if(block==null)return;
     using(ResultBuffer data=block.GetXDataForApplication("PLANTCAD01")){
      if(data==null)return;bool tree=false;foreach(TypedValue v in data)if(v.TypeCode==1000&&Convert.ToString(v.Value)=="TREE")tree=true;if(!tree)return;
     }
     // Pickfirst must also be under the double-click, so an old selection is never edited accidentally.
     Extents3d bounds=block.GeometricExtents;double margin=Math.Max(1e-6,(bounds.MaxPoint-bounds.MinPoint).Length*.01);
     if(args.Location.X<bounds.MinPoint.X-margin||args.Location.X>bounds.MaxPoint.X+margin||args.Location.Y<bounds.MinPoint.Y-margin||args.Location.Y>bounds.MaxPoint.Y+margin)return;
     instanceDocument=doc;instanceHandle=block.Handle.ToString();instanceClick=DateTime.UtcNow;tr.Commit();
    }
   }catch{instanceDocument=null;instanceHandle=null;}
  }
  static void OnDoubleClickCommand(object sender,DocumentLockModeChangedEventArgs args){
   if(instanceHandle==null||!Object.ReferenceEquals(instanceDocument,args.Document)||(DateTime.UtcNow-instanceClick).TotalMilliseconds>1500)return;
   string command=(args.GlobalCommandName??"").TrimStart('.','_').ToUpperInvariant();
   if(command!="EATTEDIT"&&command!="ATTEDIT"&&command!="DDEDIT")return;
   // Only this managed plant's standard double-click action is replaced; other blocks retain CAD behavior.
   args.Veto();pendingInstanceHandle=instanceHandle;pendingInstanceDocument=instanceDocument;instanceHandle=null;instanceDocument=null;

  }
  static void DispatchInstanceEdit(){
   if(pendingInstanceHandle==null)return;
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(!Object.ReferenceEquals(doc,pendingInstanceDocument)||!CadIsIdle(doc)||preparing!=null)return;
   string action="(setq pl:*edit-handle* "+Quote(pendingInstanceHandle)+")\nPLANTCADEDITINSTANCE";
   pendingInstanceHandle=null;pendingInstanceDocument=null;
   if(!prepared.Contains(doc)){if(workView==null)ShowWorkbench();BeginLoad(doc,action);}
   else doc.SendStringToExecute(action+"\n",false,false,false);
  }

 }
}
