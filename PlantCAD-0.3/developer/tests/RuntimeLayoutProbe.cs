using System;using System.IO;using System.Reflection;using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;using Autodesk.AutoCAD.Runtime;using PlantCADBridge;
[assembly:CommandClass(typeof(RuntimeLayoutProbe))]
public class RuntimeLayoutProbe {
 [CommandMethod("CT_LAYOUT_TEST")] public void Test(){
  var type=typeof(Bridge);var flags=BindingFlags.Static|BindingFlags.NonPublic;
  string package=(string)type.GetMethod("PackageRoot",flags).Invoke(null,null);
  string queue=(string)type.GetMethod("RuntimeRoot",flags).Invoke(null,null);
  string directory=Path.GetDirectoryName(Application.DocumentManager.MdiActiveDocument.Name);
  File.WriteAllText(Path.Combine(directory,"layout-result.json"),new JavaScriptSerializer().Serialize(new {package=package,queue=queue,receiver=type.Assembly.Location,paired=File.Exists(Path.Combine(package,"plantcad.dcl"))}));
 }
}
