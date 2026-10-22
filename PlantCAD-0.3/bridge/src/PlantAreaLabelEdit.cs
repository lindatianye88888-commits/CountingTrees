using System;
using System.Text.RegularExpressions;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  [LispFunction("pl:native-area-label-name")]
  public ResultBuffer ReadEditedAreaName(ResultBuffer args) {
   try {
    var db=Application.DocumentManager.MdiActiveDocument.Database;string plain;
    using(var tr=db.TransactionManager.StartTransaction()) {
     var entity=tr.GetObject(OutputId(db,Convert.ToString(args.AsArray()[0].Value)),OpenMode.ForRead);
     var leader=entity as MLeader;var text=entity as MText;
     if(leader!=null){using(var content=leader.MText)plain=content.Text;}
     else if(text!=null)plain=text.Text;
     else throw new ArgumentException("请选择关联灌木面积文字或整体引线。");
    }
    // Read the visible name, never trust manually edited area numbers as geometry.
    string name=Regex.Replace(plain,@"(?:\s+|^)(?:约\s*)?[-+]?\d+(?:\.\d+)?\s*(?:平方米|㎡|m[²2])(?:\s*[（(][^）)]*[）)])?\s*$","",RegexOptions.IgnoreCase|RegexOptions.CultureInvariant);
    name=name.Replace("\r","").Replace("\n","").Trim();
    if(name.Length==0||Regex.IsMatch(name,@"^[\d\s.约]+$"))return new ResultBuffer(new TypedValue(5005,""));
    if(name.Length>80||name.Contains("平方米")||name.Contains("㎡")||Regex.IsMatch(name,@"m[²2]",RegexOptions.IgnoreCase))
     throw new ArgumentException("名称与面积之间请保留空格或换行，面积由闭合边界计算。");
    return new ResultBuffer(new TypedValue(5005,name));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue(5005,"ERROR: "+ex.Message));}
  }
 }
}
