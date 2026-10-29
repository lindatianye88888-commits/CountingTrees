using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
namespace PlantCADBridge {
 public sealed partial class Bridge {
  [LispFunction("pl:native-project-delete-confirm")]
  public ResultBuffer ProjectDeleteConfirm(ResultBuffer args){
   try{
    var values=OutputArguments(args);if(values.Count!=3)throw new ArgumentException("删除确认参数无效。");
    string message="删除规格："+Convert.ToString(values[0])+"\n\n将删除 "+Convert.ToString(values[1])+" 个图上对象（含植物、标注、填充和计算区域），以及 "+Convert.ToString(values[2])+" 张仅含该规格的表。混合表会移除该规格的记录。\n\n确认删除？可在返回 CAD 后用 U 撤销。";
    var owner=Application.MainWindow==null?IntPtr.Zero:Application.MainWindow.Handle;
    var result=System.Windows.Forms.MessageBox.Show(new ProjectWindowOwner(owner),message,"CountingTrees（数树） - 删除规格",System.Windows.Forms.MessageBoxButtons.YesNo,System.Windows.Forms.MessageBoxIcon.Warning,System.Windows.Forms.MessageBoxDefaultButton.Button2);
    return new ResultBuffer(new TypedValue(5003,result==System.Windows.Forms.DialogResult.Yes?1:0));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue(5005,"ERROR: "+ex.Message));}
  }
  sealed class ProjectWindowOwner : System.Windows.Forms.IWin32Window {
   readonly IntPtr handle;internal ProjectWindowOwner(IntPtr value){handle=value;}public IntPtr Handle{get{return handle;}}
  }
  [LispFunction("pl:native-project-erase")]
  public ResultBuffer ProjectErase(ResultBuffer args){
   try{
    var values=OutputArguments(args);if(values.Count!=1)throw new ArgumentException("删除对象参数无效。");
    var handles=values[0] as List<object> ?? new List<object>();
    var allowed=new HashSet<string>(new[]{"TREE","AREA","PROJECT_SOURCE","LABEL","LEADER","AREA_LABEL","AREA_LEADER","AREA_ARROW","AREA_FILL","FILL_EDGE","TABLE"},StringComparer.Ordinal);
    var doc=Application.DocumentManager.MdiActiveDocument;if(doc==null)throw new InvalidOperationException("没有活动图纸。");int count=0;
    using(var guard=doc.LockDocument())using(var tr=doc.Database.TransactionManager.StartTransaction()){
     var targets=new List<Entity>();var seen=new HashSet<ObjectId>();
     foreach(object value in handles){
      ObjectId id=OutputId(doc.Database,Convert.ToString(value));if(!seen.Add(id))continue;
      var entity=tr.GetObject(id,OpenMode.ForRead) as Entity;string role=null;
      if(entity!=null)using(var data=entity.GetXDataForApplication("PLANTCAD01"))if(data!=null)foreach(TypedValue item in data)if(item.TypeCode==1000){role=Convert.ToString(item.Value);break;}
      if(role==null||!allowed.Contains(role))throw new InvalidOperationException("拒绝删除未受管理的对象："+Convert.ToString(value));
      if(((LayerTableRecord)tr.GetObject(entity.LayerId,OpenMode.ForRead)).IsLocked)throw new InvalidOperationException("待删除对象图层已锁定："+entity.Layer);
      targets.Add(entity);
     }
     // Validate the entire set before the first erase; failure rolls the transaction back.
     foreach(Entity entity in targets){entity.UpgradeOpen();entity.Erase();count++;}tr.Commit();
    }
    return new ResultBuffer(new TypedValue(5003,count));
   }catch(System.Exception ex){return new ResultBuffer(new TypedValue(5005,"ERROR: "+ex.Message));}
  }
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
