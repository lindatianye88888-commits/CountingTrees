using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  [LispFunction("pl:native-project-match")]
  public ResultBuffer ProjectMatch(ResultBuffer args){
   try{
    var values=OutputArguments(args);if(values.Count!=2)throw new ArgumentException("品种规格选择参数无效。");
    var rows=new List<string[]>();var kinds=new List<string>();
    foreach(object item in values[0] as List<object> ?? new List<object>()){
     var row=Convert.ToString(item).Split('\t');if(row.Length!=8)throw new ArgumentException("项目参数列无效。");rows.Add(row);
    }
    foreach(object item in (List<object>)values[1])kinds.Add(Convert.ToString(item));
    using(var form=new PlantProjectDialog(rows,kinds,0,true)){
     Application.ShowModalDialog(form);return new ResultBuffer(new TypedValue(5003,form.ActionCode==1?form.SelectedIndex:-1));
    }
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue(5005,"ERROR: "+ex.Message));}
  }
  [LispFunction("pl:native-project-dialog")]
  public ResultBuffer ProjectDialog(ResultBuffer args){
   try{
    var values=OutputArguments(args);if(values.Count!=3)throw new ArgumentException("项目窗口参数无效。");
    var rows=new List<string[]>();var kinds=new List<string>();
    foreach(object item in values[0] as List<object> ?? new List<object>()){var row=Convert.ToString(item).Split('\t');if(row.Length!=8)throw new ArgumentException("项目参数列无效。");rows.Add(row);}
    foreach(object item in (List<object>)values[1])kinds.Add(Convert.ToString(item));
    int action,index;
    using(var form=new PlantProjectDialog(rows,kinds,Convert.ToInt32(values[2]))){Application.ShowModalDialog(form);action=form.ActionCode;index=form.SelectedIndex;}
    return new ResultBuffer(new TypedValue(5003,action),new TypedValue(5003,index));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue(5005,"ERROR: "+ex.Message));}
  }
 }
}
