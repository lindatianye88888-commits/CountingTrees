using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Windows;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace PlantCADBridge {
 public sealed partial class Bridge {
  static PlantWorkbenchForm workbench;
  static PlantBadgeForm badge;
  static bool badgeStartupPending;
  static DateTime workbenchStarted;
  static bool panelActivated;
  static PlantWorkbench workView;
  static readonly HashSet<Document> prepared = new HashSet<Document>();
  static readonly HashSet<Document> observed = new HashSet<Document>();
  static readonly Dictionary<Document,string> loadErrors = new Dictionary<Document,string>();
  static Document preparing, displayed, actionDocument;
  static string afterLoad, requestedAction;
  static bool refreshQueued, refreshNeeded = true;
  static Document stableDocument;
  static DateTime stableSince=DateTime.UtcNow;
  static readonly Dictionary<string,string> uiCommands = new Dictionary<string,string> {
   {"choose","PLANTCADDESIGN"}, {"project","PLANTCADPLANT"},
   {"edit","PLANTCADEDITCURRENT"}, {"symbols","PLANTCADSYMBOLPICK"},
   {"settings","PLANTCADSET"}, {"place","PLANTCADARRANGE"},
   {"count","PLANTCADCOUNT"}, {"table","PLANTCADTABLE"},
   {"list","PLANTCADLISTTABLE"}, {"specs","PLANTCADSPECTABLE"},
   {"table_groups","PLANTCADTABLEGROUPS"}, {"table_species","PLANTCADTABLESPECIES"}, {"table_split","PLANTCADTABLESPLIT"},
   {"sync","PLANTCADSYNC"}, {"connect","PLANTCADCONNECT"},
   {"pick","PLANTCADPICK"},
   {"reuse","PLANTCADREUSE"},
   {"catalog_import","PLANTCADCATLOAD"},
   {"catalog_export","PLANTCADCATSAVE"},
   {"symbol_circle","PLANTCADCIRCLE"},
   {"symbol_simple","PLANTCADSIMPLE"},
   {"symbol_from_drawing","PLANTCADBLOCKPICK"},
   {"symbol_copy","PLANTCADSYMBOL"},
   {"along_line","PLANTCADLINE"},
   {"place_points","PLANTCADINSERT"}, {"in_area","PLANTCADGRID"},
   {"fill_area","PLANTCADFILL"}, {"output_area","PLANTCADLABELAREA"}, {"shrub_ball","PLANTCADBALL"},
   {"geometry_area","PLANTCADAREA"}, {"area_bind","PLANTCADAREABIND"}, {"area_from_label","PLANTCADAREAFROMLABEL"},
   {"manual_area","PLANTCADAREAADD"},
   {"shrub_area","PLANTCADSHRUB"},
   {"ground_area","PLANTCADGROUND"},
   {"size","PLANTCADSIZE"},
   {"replace","PLANTCADREPLACE"},
   {"style","PLANTCADSTYLE"},
   {"update","PLANTCADUPDATE"},
   {"info","PLANTCADDETAIL"},
   {"label_name","PLANTCADLABELNAME"},
   {"label_spec","PLANTCADLABELSPEC"},
   {"label_number","PLANTCADLABELNUMBER"},
   {"label_leader","PLANTCADLABELLEADER"},
   {"label_area","PLANTCADLABELAREA"},
   {"count_all","PLANTCADCOUNTALL"},
   {"count_selected","PLANTCADCOUNTSELECTED"},
   {"export","PLANTCADEXPORT"},
   {"layers","PLANTCADLAYERSTATUS"},
   {"help","PLANTCADHELP"}, {"calibrate","PLANTCADCALIBRATE"}, {"save_project","PLANTCADSAVE"}, {"save_info","PLANTCADSAVEINFO"}, {"instance","PLANTCADEDITINSTANCE"}
  };

  static void InitializeWorkbench() {
   refreshNeeded=true;badgeStartupPending=true;workbenchStarted=DateTime.UtcNow;
  }
  static void ShowBadge() {
   if(badge==null) {
    badge=new PlantBadgeForm(ShowWorkbench);
    Rectangle area=Screen.PrimaryScreen.WorkingArea;
    badge.Location=new Point(area.Right-88,area.Top+Math.Max(80,area.Height/2));
   }
   AcadApp.ShowModelessDialog((IWin32Window)null,badge,false);
   badgeStartupPending=false;
  }
  static void CollapseWorkbench() {
   if(workbench!=null)workbench.Hide();
   ShowBadge();
  }
  static void ShowWorkbench() {
   panelActivated=true;badgeStartupPending=false;
   if(badge!=null)badge.Hide();
   if(workbench == null) {
    workView = new PlantWorkbench(QueueAction);
    workbench = new PlantWorkbenchForm { Text="CountingTrees（数树） 植物工作台",FormBorderStyle=FormBorderStyle.SizableToolWindow,
     StartPosition=FormStartPosition.Manual,ShowInTaskbar=false,MinimizeBox=false,MaximizeBox=false,
     ClientSize=new Size(540,610),MinimumSize=new Size(360,500) };
    Rectangle area=Screen.PrimaryScreen.WorkingArea;
    workbench.Location=new Point(Math.Max(area.Left,area.Right-570),area.Top+Math.Max(35,(area.Height-650)/2));
    workbench.Controls.Add(workView);
    workbench.CollapseRequested+=CollapseWorkbench;workView.CollapseRequested+=CollapseWorkbench;
    workbench.FormClosing+=(sender,args)=> { if(args.CloseReason==CloseReason.UserClosing) { args.Cancel=true; CollapseWorkbench(); } };
    AcadApp.ShowModelessDialog((System.Windows.Forms.IWin32Window)null,workbench,false);
   } else {
    AcadApp.ShowModelessDialog((System.Windows.Forms.IWin32Window)null,workbench,false);
    workbench.BringToFront();
   }
   refreshNeeded = true;
  }

  static bool CadIsIdle(Document doc) {
   // IsQuiescent alone can be true inside AutoLISP/DCL nested message loops.
   return doc!=null && Convert.ToInt32(AcadApp.GetSystemVariable("CMDACTIVE"))==0 && doc.Editor.IsQuiescent;
  }
  static void QueueAction(string action) {
   Document doc = AcadApp.DocumentManager.MdiActiveDocument;
   if(doc == null) { workView.Message("请先打开已有底图。",true); return; }
   if(!CadIsIdle(doc) || preparing != null || requestedAction != null) {
    workView.Message("请先结束当前命令或关闭对话框，再点击功能。",true); return;
   }
   actionDocument=doc; requestedAction=action;
   doc.SendStringToExecute("PLANTCADUI\n",false,false,false);
  }

  static void BeginLoad(Document doc,string next) {
   if(preparing != null) return;
   string package=PackageRoot();
   string[] required={"plantcad.lsp","plantcad-core.lsp","plantcad-design.lsp","plantcad-ai.lsp","plantcad-ui.lsp","plantcad-workflow.lsp","plantcad-project-import.lsp","plantcad.dcl","plantcatalog.tsv"};
   foreach(string name in required) if(!File.Exists(Path.Combine(package,name))) {
    loadErrors[doc]="缺少配套文件："+name;
    workView.Message(loadErrors[doc],true); return;
   }
   preparing=doc; afterLoad=next; loadErrors.Remove(doc);
   workView.Loading(Path.GetFileName(doc.Name));
   // Absolute, paired package paths avoid other plug-ins' support search paths.
   doc.SendStringToExecute("(setq pl:*dir* "+Quote(package)+" pl:*native-ui* T)\n(load "+
    Quote(Path.Combine(package,"plantcad.lsp"))+")\nPLANTCADLOADED\n",false,false,false);
  }

  static void Observe(Document doc) {
   if(observed.Add(doc)) {
    doc.CommandEnded += OnPlantCommandFinished;
    doc.CommandCancelled += OnPlantCommandFinished;
   doc.CommandFailed += OnPlantCommandFinished;
   }
  }
  static void OnPlantCommandFinished(object sender,CommandEventArgs args) {
   if(!refreshQueued && preparing==null && (args.GlobalCommandName??"").IndexOf("PLANTCADPANELREFRESH",StringComparison.OrdinalIgnoreCase)<0)
    refreshNeeded=true;
  }
  static void ForgetDocument(Document doc) {
   ForgetOutputSignatures(doc);
   if(Object.ReferenceEquals(areaDocument,doc))EndAreaSession();
   prepared.Remove(doc); loadErrors.Remove(doc);
   if(observed.Remove(doc)) {
    doc.CommandEnded -= OnPlantCommandFinished;
    doc.CommandCancelled -= OnPlantCommandFinished;
   doc.CommandFailed -= OnPlantCommandFinished;
   }
   if(Object.ReferenceEquals(preparing,doc)) { preparing=null; afterLoad=null; }
   if(Object.ReferenceEquals(actionDocument,doc)) { actionDocument=null; requestedAction=null; }
   if(Object.ReferenceEquals(displayed,doc)) displayed=null;
   refreshQueued=false; refreshNeeded=true;
  }

  static void WorkbenchIdle() {
   DispatchInstanceEdit();
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(badgeStartupPending) {
    if((DateTime.UtcNow-workbenchStarted).TotalMilliseconds<1800) return;
    if(doc!=null && !CadIsIdle(doc)) return;
    if(AcadApp.MainWindow==null || AcadApp.MainWindow.Handle==IntPtr.Zero) return;
    ShowBadge();
   }
   if(!panelActivated) return;
   if(doc==null) { if(workView!=null) workView.NoDocument(); return; }
   // A document can exist before NEW/OPEN has attached its database.
   if(doc.Database==null || doc.Database.IsDisposed || doc.Database.BlockTableId.IsNull || String.IsNullOrEmpty(doc.Name)) return;
   if(!Object.ReferenceEquals(stableDocument,doc)) {
    stableDocument=doc; stableSince=DateTime.UtcNow;
    if(preparing!=null && !Object.ReferenceEquals(preparing,doc)) { preparing=null; afterLoad=null; }
    return;
   }
   if((DateTime.UtcNow-stableSince).TotalMilliseconds<700) return;
   Observe(doc);
   if(!CadIsIdle(doc)) return;
   if(workView==null) ShowWorkbench();
   if(!prepared.Contains(doc)) {
    if(preparing==null && !loadErrors.ContainsKey(doc)) BeginLoad(doc,null);
    return;
   }
   if(preparing==null && !refreshQueued && (refreshNeeded || !Object.ReferenceEquals(displayed,doc))) {
    refreshQueued=true; refreshNeeded=false;
    doc.SendStringToExecute("PLANTCADPANELREFRESH\n",false,false,false);
   }
  }

  static Dictionary<string,object> ReadPanelState() {
   var state=Invoke("panel_state",new Dictionary<string,object>()) as Dictionary<string,object>;
   if(state==null || !state.ContainsKey("ui_version") || Convert.ToString(state["ui_version"])!="0.3-float-2")
    throw new InvalidOperationException("当前图纸尚未加载配套的操作面板模块。请点击重新加载。");
   return state;
  }

  [CommandMethod("PLANTCAD",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  [CommandMethod("COUNTINGTREES",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  [CommandMethod("数树",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  public void OpenWorkbench() { ShowWorkbench(); }

  [CommandMethod("PLANTCADUI",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  public void DispatchWorkbench() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   string action=requestedAction;
   Document target=actionDocument;
   requestedAction=null; actionDocument=null;
   if(doc==null || !Object.ReferenceEquals(doc,target) || action==null) return;
   if(action=="reload") { prepared.Remove(doc); loadErrors.Remove(doc); BeginLoad(doc,null); return; }
   string command;
   if(!uiCommands.TryGetValue(action,out command)) return;
   if(!prepared.Contains(doc)) BeginLoad(doc,command);
   else doc.SendStringToExecute(command+"\n",false,false,false);
  }

  [CommandMethod("PLANTCADLOAD",CommandFlags.Modal)]
  public void ReloadWorkbench() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(doc!=null) { prepared.Remove(doc); loadErrors.Remove(doc); BeginLoad(doc,null); }
  }

  [CommandMethod("PLANTCADPLACE",CommandFlags.Modal)]
  public void PlaceFromWorkbench() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(doc==null) return;
   if(!prepared.Contains(doc)) BeginLoad(doc,"PLANTCADINSERT");
   else doc.SendStringToExecute("PLANTCADINSERT\n",false,false,false);
  }

  [CommandMethod("PLANTCADLOADED",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  public void WorkbenchLoaded() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   if(doc==null || !Object.ReferenceEquals(doc,preparing)) return;
   string next=afterLoad;
   try {
    Dictionary<string,object> state=ReadPanelState();
    prepared.Add(doc); loadErrors.Remove(doc);
    displayed=doc; workView.UpdateState(state,doc.Name,connected && Object.ReferenceEquals(boundDocument,doc));
    doc.Editor.WriteMessage("\nCountingTrees（数树） 操作面板已就绪。点击“选植物”或“开始布置”。");
   } catch(System.Exception ex) {
    loadErrors[doc]=ex.Message; next=null; workView.Message("加载失败："+ex.Message,true);
    doc.Editor.WriteMessage("\nCountingTrees（数树） 加载失败："+ex.Message);
   } finally { preparing=null; afterLoad=null; refreshNeeded=true; }
   if(next!=null) doc.SendStringToExecute(next+"\n",false,false,false);
  }

  [CommandMethod("PLANTCADPANELREFRESH",CommandFlags.Modal | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  public void RefreshWorkbench() {
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   try {
    if(doc==null || !prepared.Contains(doc)) return;
    Dictionary<string,object> state=ReadPanelState();
    workView.UpdateState(state,doc.Name,connected && Object.ReferenceEquals(boundDocument,doc));
    if(badge!=null)badge.SetPlant(Convert.ToString(state["name"]));
    displayed=doc; refreshNeeded=false;
   } catch(System.Exception ex) { workView.Message(ex.Message,true); }
   finally { refreshQueued=false; }
  }

  [LispFunction("pl:preview-point")]
  public ResultBuffer PickPreview(ResultBuffer arguments) {
   TypedValue[] v=arguments.AsArray();
   if(v.Length!=4) throw new ArgumentException("Invalid placement preview arguments.");
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   using(var jig=new PlantPlacementJig(doc,Convert.ToString(v[0].Value),Convert.ToDouble(v[1].Value),
         Convert.ToDouble(v[2].Value),Convert.ToString(v[3].Value))) {
    PromptResult result=doc.Editor.Drag(jig);
    if(result.Status!=PromptStatus.OK) return null;
    Point3d ucs=jig.Point.TransformBy(doc.Editor.CurrentUserCoordinateSystem.Inverse());
    return new ResultBuffer(new TypedValue((int)LispDataType.Point3d,ucs));
   }
  }

  [LispFunction("pl:native-insert")]
  public ResultBuffer InsertNativeSymbol(ResultBuffer arguments) {
   TypedValue[] v=arguments.AsArray();
   if(v.Length<4) throw new ArgumentException("Invalid insertion arguments.");
   int cursor=1;
   Point3d insertion;
   if(v[cursor].Value is Point3d) { insertion=(Point3d)v[cursor++].Value; }
   else if(v[cursor].TypeCode==(int)LispDataType.ListBegin && v.Length>=8) {
    cursor++;
    insertion=new Point3d(Convert.ToDouble(v[cursor++].Value),Convert.ToDouble(v[cursor++].Value),Convert.ToDouble(v[cursor++].Value));
    if(v[cursor++].TypeCode!=(int)LispDataType.ListEnd) throw new ArgumentException("Invalid insertion point.");
   } else throw new ArgumentException("Expected a three-dimensional insertion point.");
   if(cursor+2!=v.Length) throw new ArgumentException("Invalid insertion arguments.");
   double scale=Convert.ToDouble(v[cursor++].Value);
   string layerName=Convert.ToString(v[cursor].Value);
   if(Double.IsNaN(scale) || Double.IsInfinity(scale) || scale<=0) throw new ArgumentException("图例比例必须大于0。");
   Document doc=AcadApp.DocumentManager.MdiActiveDocument;
   Database db=doc.Database;
   string handle;
   using(Transaction tr=db.TransactionManager.StartTransaction()) {
    var blocks=(BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead);
    var layers=(LayerTable)tr.GetObject(db.LayerTableId,OpenMode.ForRead);
    string name=Convert.ToString(v[0].Value),layer=layerName;
    if(!blocks.Has(name) || !layers.Has(layer)) throw new InvalidOperationException("图例或目标图层缺失，请重新加载。");
    var target=(LayerTableRecord)tr.GetObject(layers[layer],OpenMode.ForRead);
    if(target.IsLocked || target.IsFrozen || target.IsOff) throw new InvalidOperationException("植物图层已锁定、冻结或关闭，请先检查图层。");
    var space=(BlockTableRecord)tr.GetObject(db.CurrentSpaceId,OpenMode.ForWrite);
    var reference=new BlockReference(insertion,blocks[name]);
    reference.SetDatabaseDefaults(db);
    reference.LayerId=layers[layer]; reference.ColorIndex=256;
    reference.ScaleFactors=new Scale3d(scale);
    space.AppendEntity(reference); tr.AddNewlyCreatedDBObject(reference,true);
    var definition=(BlockTableRecord)tr.GetObject(blocks[name],OpenMode.ForRead);
    foreach(ObjectId id in definition) {
     var attribute=tr.GetObject(id,OpenMode.ForRead) as AttributeDefinition;
     if(attribute==null || attribute.Constant) continue;
     var instance=new AttributeReference();
     instance.SetAttributeFromBlock(attribute,reference.BlockTransform);
     instance.TextString=attribute.TextString;
     reference.AttributeCollection.AppendAttribute(instance);
     tr.AddNewlyCreatedDBObject(instance,true);
    }
    handle=reference.Handle.ToString();
    tr.Commit();
   }
   return new ResultBuffer(new TypedValue((int)LispDataType.Text,handle));
  }
 }

 internal sealed class PlantPlacementJig : DrawJig, IDisposable {
  readonly BlockReference ghost;
  readonly DBText caption;
  readonly double height;
  readonly string name;
  public Point3d Point {get;private set;}
  public PlantPlacementJig(Document doc,string block,double scale,double textHeight,string text) {
   using(Transaction tr=doc.Database.TransactionManager.StartTransaction()) {
    var blocks=(BlockTable)tr.GetObject(doc.Database.BlockTableId,OpenMode.ForRead);
    if(!blocks.Has(block)) throw new InvalidOperationException("找不到当前植物图例。");
    ghost=new BlockReference(Point3d.Origin,blocks[block]);
    ghost.ScaleFactors=new Scale3d(scale); ghost.ColorIndex=3;
    caption=new DBText(); caption.TextString=text; caption.Height=textHeight;
    caption.TextStyleId=doc.Database.Textstyle; caption.ColorIndex=3;
    tr.Commit();
   }
   height=textHeight; name=text;
  }
  protected override SamplerStatus Sampler(JigPrompts prompts) {
   var options=new JigPromptPointOptions("\n"+name+" · 植物中心（回车结束）：");
   options.UserInputControls=UserInputControls.Accept3dCoordinates | UserInputControls.NullResponseAccepted;
   PromptPointResult result=prompts.AcquirePoint(options);
   if(result.Status!=PromptStatus.OK) return SamplerStatus.Cancel;
   if(result.Value.IsEqualTo(Point)) return SamplerStatus.NoChange;
   Point=result.Value; return SamplerStatus.OK;
  }
  protected override bool WorldDraw(Autodesk.AutoCAD.GraphicsInterface.WorldDraw draw) {
   ghost.Position=Point;
   caption.Position=Point+new Vector3d(0,height*.7,0);
   draw.Geometry.Draw(ghost); draw.Geometry.Draw(caption); return true;
  }
  public void Dispose() { ghost.Dispose(); caption.Dispose(); }
 }

}
