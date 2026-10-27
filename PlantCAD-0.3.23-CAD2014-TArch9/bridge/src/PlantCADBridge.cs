// PlantCAD 0.3. Compiled against the installed AutoCAD 2014 SDK.
// Receives structured local JSON; never executes a script supplied by an MCP client.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(PlantCADBridge.Bridge))]
[assembly: CommandClass(typeof(PlantCADBridge.Bridge))]
[assembly: System.Reflection.AssemblyTitle("CountingTrees（数树）")]
[assembly: System.Reflection.AssemblyProduct("CountingTrees")]
[assembly: System.Reflection.AssemblyDescription("数树 · 植物布置、面积统计与关联出图")]

namespace PlantCADBridge {
 public sealed partial class Bridge : IExtensionApplication {
  static Document boundDocument;
  static string sessionId;
  static string root;
  static bool connected, queued, loading;
  static FileStream ownerLock;
  static DateTime lastHeartbeat = DateTime.MinValue;
  static System.Windows.Forms.Timer timer;
  static readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 4194304 };
  static readonly HashSet<string> allowed = new HashSet<string> {
   "get_plants", "catalogue", "preview_adjust", "apply_adjust", "plot_settings"
  };
  static double Now() { return (DateTime.UtcNow - new DateTime(1970,1,1)).TotalSeconds; }
  static string PackageRoot() { return Directory.GetParent(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)).FullName; }
  static string RuntimeRoot() {
   string config=Path.Combine(PackageRoot(),"bridge","queue-root.json");
   if(File.Exists(config)) {
    var settings=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(config,Encoding.UTF8));
    if(settings!=null && settings.ContainsKey("queue_root"))
     return Path.GetFullPath(Convert.ToString(settings["queue_root"]));
   }
   return Path.Combine(PackageRoot(),"bridge","runtime");
  }
  static string Quote(string s) { return "\"" + s.Replace("\\","/").Replace("\"","\\\"") + "\""; }
  static void Atomic(string path, object value) {
   Directory.CreateDirectory(Path.GetDirectoryName(path));
   string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
   File.WriteAllText(temp, json.Serialize(value), new UTF8Encoding(false));
   if (File.Exists(path)) File.Replace(temp,path,null); else File.Move(temp,path);
  }
  static void Session(string message) {
   if (root == null || boundDocument == null) return;
   bool active = Object.ReferenceEquals(AcadApp.DocumentManager.MdiActiveDocument,boundDocument);
   bool busy = true;
   try { busy = !CadIsIdle(boundDocument); } catch { }
   Atomic(Path.Combine(root,"session.json"),new Dictionary<string,object> {
    {"protocol",1},{"version","0.3"},{"connected",connected},{"session_id",sessionId},
    {"document",boundDocument.Name},{"process_id",Process.GetCurrentProcess().Id},
    {"active_document",active},{"busy",busy},{"heartbeat",Now()},{"message",message},
    {"capabilities",new string[] {"read_plants","preview_adjust","apply_adjust","move_plants","plot_settings","managed_tables"}}
   });
  }
  public void Initialize() {
   // Core Console can load the bundle for interop tests, but has no desktop widgets.
   if(Process.GetCurrentProcess().ProcessName.Equals("accoreconsole",StringComparison.OrdinalIgnoreCase)) return;
   InitializeWorkbench();
   InitializeInstanceEditing();
   timer = new System.Windows.Forms.Timer();
   timer.Interval = 500;
   timer.Tick += OnIdle;
   timer.Start();
   AcadApp.Idle += OnIdle;
   AcadApp.DocumentManager.DocumentToBeDestroyed += OnDocumentClosing;
  }
  public void Terminate() {
   TerminateInstanceEditing();EndAreaSession();
   AcadApp.Idle -= OnIdle;
   AcadApp.DocumentManager.DocumentToBeDestroyed -= OnDocumentClosing;
   if (timer != null) { timer.Stop(); timer.Dispose(); timer = null; }
   CloseSession();
   if (workbench != null) { workbench.Dispose(); workbench = null; workView = null; }
   if (badge != null) { badge.Dispose(); badge = null; }
  }
  static void OnDocumentClosing(object sender,DocumentCollectionEventArgs args) {
   ForgetDocument(args.Document);
   if (Object.ReferenceEquals(args.Document,boundDocument)) CloseSession();
  }
  static void CloseSession() {
   connected = false; queued = false; loading = false;
   try { Session("CAD bridge disconnected."); } catch { }
   if (ownerLock != null) { ownerLock.Dispose(); ownerLock = null; }
   boundDocument = null;
  }
  [CommandMethod("PLANTCADCONNECT",CommandFlags.Modal)]
  public void ConnectNamespaced() { Connect(); }
  public void Connect() {
   Document doc = AcadApp.DocumentManager.MdiActiveDocument;
   if (doc == null) return;
   CloseSession();
   root = RuntimeRoot();
   Directory.CreateDirectory(root);
   Directory.CreateDirectory(Path.Combine(root,"requests"));
   Directory.CreateDirectory(Path.Combine(root,"responses"));
   Directory.CreateDirectory(Path.Combine(root,"processed"));
   try { ownerLock = new FileStream(Path.Combine(root,"owner.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None); }
   catch (IOException) { doc.Editor.WriteMessage("\nAnother CAD process owns this bridge. Disconnect it first."); return; }
   boundDocument = doc; sessionId = Guid.NewGuid().ToString("N"); loading = true;
   Session("Loading CountingTrees（数树） for this drawing.");
   string package = PackageRoot();
   string main = Path.Combine(package,"plantcad.lsp"), ai = Path.Combine(package,"plantcad-ai.lsp");
   if (!File.Exists(main) || !File.Exists(ai)) { CloseSession(); doc.Editor.WriteMessage("\nIncomplete CountingTrees（数树） 0.3 package."); return; }
   doc.SendStringToExecute("(setq pl:*dir* " + Quote(package) + ")\n(load " + Quote(main) + ")\n(load " + Quote(ai) + ")\nPLANTCADAIREADY\n",false,false,false);
  }
  [CommandMethod("PLANTCADAIREADY",CommandFlags.Modal | CommandFlags.UsePickSet | CommandFlags.Redraw | CommandFlags.NoUndoMarker | CommandFlags.NoHistory)]
  public void Ready() {
   if (!loading || !Object.ReferenceEquals(boundDocument,AcadApp.DocumentManager.MdiActiveDocument)) return;
   try {
    object probe = Invoke("get_plants",new Dictionary<string,object> { {"target",new Dictionary<string,object>{{"scope","model"}}},{"limit",1}});
    var state = probe as Dictionary<string,object>;
    if (state == null || !state.ContainsKey("ok") || !Object.Equals(state["ok"],true))
     throw new InvalidOperationException("CountingTrees（数树） initialization did not return success.");
    loading = false; connected = true; prepared.Add(boundDocument); refreshNeeded = true; Session("CountingTrees（数树） ready.");
    boundDocument.Editor.WriteMessage("\nCountingTrees（数树） AI connected. Use the desktop MCP tools to inspect and adjust plants.");
   } catch (System.Exception ex) {
    loading = false; connected = false; Session("LISP bridge load failed: " + ex.Message);
    boundDocument.Editor.WriteMessage("\nCountingTrees（数树） bridge load failed: " + ex.Message);
   }
  }
  [CommandMethod("PLANTCADDISCONNECT",CommandFlags.Modal)]
  public void DisconnectNamespaced() { CloseSession(); }
  public void Disconnect() { CloseSession(); }
  static void OnIdle(object sender,EventArgs args) {
   try { if (!(sender is System.Windows.Forms.Timer)) WorkbenchIdle(); } catch (System.Exception ex) { if (workView != null) workView.Message(ex.Message,true); }
   if (boundDocument == null) return;
   try {
    if ((DateTime.UtcNow-lastHeartbeat).TotalSeconds >= 1) {
     Session(connected ? "CountingTrees（数树） ready." : "Loading CountingTrees（数树）.");
     lastHeartbeat = DateTime.UtcNow;
    }
    if (!connected || queued || !Object.ReferenceEquals(boundDocument,AcadApp.DocumentManager.MdiActiveDocument)) return;
    if (!CadIsIdle(boundDocument)) return;
    if (Directory.GetFiles(Path.Combine(root,"requests"),"*.json").Length == 0) return;
    queued = true;
    boundDocument.SendStringToExecute("PLANTCADAIEXEC\n",false,false,false);
   } catch (System.Exception ex) {
    connected = false; queued = false;
    try { Session("CAD bridge stopped: " + ex.Message); } catch { }
   }
  }
  [CommandMethod("PLANTCADAIEXEC",CommandFlags.Modal | CommandFlags.UsePickSet | CommandFlags.Redraw)]
  public void Execute() {
   string path = null, id = null;
   try {
    if (!connected || !Object.ReferenceEquals(boundDocument,AcadApp.DocumentManager.MdiActiveDocument)) return;
    string[] files = Directory.GetFiles(Path.Combine(root,"requests"),"*.json");
    Array.Sort(files,StringComparer.Ordinal);
    if (files.Length == 0) return;
    path = files[0]; id = Path.GetFileNameWithoutExtension(path);
    if (!Regex.IsMatch(id,"^[0-9a-f]{32}$")) { File.Move(path,Path.Combine(root,"processed",Path.GetFileName(path)+".invalid")); return; }
    string processing = Path.Combine(root,"processed",id+".working");
    File.Move(path,processing);
    path = processing;
    if (File.Exists(Path.Combine(root,"responses",id+".json"))) return;
    var request = json.Deserialize<Dictionary<string,object>>(File.ReadAllText(path,Encoding.UTF8));
    if (Convert.ToString(request["id"]) != id || Convert.ToString(request["session_id"]) != sessionId)
     throw new InvalidOperationException("Drawing session mismatch. Reconnect and preview again.");
    if (Convert.ToInt32(request["protocol"]) != 1) throw new InvalidOperationException("Protocol mismatch.");
    double expires = Convert.ToDouble(request["expires"]);
    if (Double.IsNaN(expires) || expires < Now() || expires > Now()+90)
     throw new InvalidOperationException("Request expired. It was not executed.");
    string action = Convert.ToString(request["action"]);
    if (!allowed.Contains(action)) throw new InvalidOperationException("Unsupported action.");
    var arguments = request["arguments"] as Dictionary<string,object>;
    if (arguments == null) throw new InvalidOperationException("Invalid arguments.");
    // Preserve the preselected objects when entering the native bridge command.
    var selected = new List<string>();
    PromptSelectionResult selection = boundDocument.Editor.SelectImplied();
    if (selection.Status == PromptStatus.OK)
     foreach (ObjectId objectId in selection.Value.GetObjectIds()) selected.Add(objectId.Handle.ToString());
    arguments["selected_handles"] = selected.ToArray();
    object result = Invoke(action,arguments);
    Reply(id,result);
   } catch (System.Exception ex) {
    if (id != null && Regex.IsMatch(id,"^[0-9a-f]{32}$"))
     try { Reply(id,new Dictionary<string,object>{{"ok",false},{"error",ex.Message},{"check_before_retry",true}}); } catch { }
   } finally {
    queued = false;
    if (path != null && File.Exists(path) && path.EndsWith(".working",StringComparison.Ordinal))
     try { File.Move(path,path.Substring(0,path.Length-8)+".done"); } catch { }
   }
  }
  static void Reply(string id,object result) {
   Atomic(Path.Combine(root,"responses",id+".json"),new Dictionary<string,object>{{"id",id},{"session_id",sessionId},{"result",result}});
  }
  static object Invoke(string action,Dictionary<string,object> arguments) {
   using (var buffer = new ResultBuffer()) {
    buffer.Add(new TypedValue((int)LispDataType.Text,"pl:ai-dispatch"));
    buffer.Add(new TypedValue((int)LispDataType.Text,action));
    AddValue(buffer,arguments);
    using (ResultBuffer result = AcadApp.Invoke(buffer)) {
     if (result == null) throw new InvalidOperationException("No result from CountingTrees（数树） LISP.");
     TypedValue[] values = result.AsArray();
     var tokens = new LispToken[values.Length];
     for(int i=0;i<values.Length;i++) tokens[i]=new LispToken(values[i].TypeCode,values[i].Value);
     return LispValueReader.Decode(tokens);
    }
   }
  }
  static void AddValue(ResultBuffer buffer,object value) {
   var dictionary = value as Dictionary<string,object>;
   if (dictionary != null) {
    buffer.Add(new TypedValue((int)LispDataType.ListBegin));
    foreach (var pair in dictionary) {
     buffer.Add(new TypedValue((int)LispDataType.ListBegin));
     buffer.Add(new TypedValue((int)LispDataType.Text,pair.Key));
     AddValue(buffer,pair.Value);
     buffer.Add(new TypedValue((int)LispDataType.ListEnd));
    }
    buffer.Add(new TypedValue((int)LispDataType.ListEnd));
   } else if (value is string) buffer.Add(new TypedValue((int)LispDataType.Text,value));
   else if (value is IEnumerable) {
    buffer.Add(new TypedValue((int)LispDataType.ListBegin));
    foreach (object item in (IEnumerable)value) AddValue(buffer,item);
    buffer.Add(new TypedValue((int)LispDataType.ListEnd));
   } else if (value == null) buffer.Add(new TypedValue((int)LispDataType.Nil));
   else if (value is bool) buffer.Add(new TypedValue((bool)value ? 5021 : (int)LispDataType.Nil));
   else {
    double number = Convert.ToDouble(value);
    if (Double.IsNaN(number) || Double.IsInfinity(number)) throw new InvalidOperationException("Non-finite number.");
    buffer.Add(new TypedValue((int)LispDataType.Double,number));
   }
  }
 }
}
