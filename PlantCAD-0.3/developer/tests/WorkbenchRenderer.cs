using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
namespace PlantCADBridge {
 public static class WorkbenchRenderer {
  static void Prepare(Control control) {IntPtr handle=control.Handle;control.PerformLayout();foreach(Control child in control.Controls)Prepare(child);}
  static void Save(PlantWorkbench panel,string directory,string name,int width,int height) {
   panel.Parent.ClientSize=new Size(width,height);panel.Parent.PerformLayout();Prepare(panel.Parent);panel.PerformLayout();
   using(var bitmap=new Bitmap(width,height)){panel.DrawToBitmap(bitmap,new Rectangle(0,0,width,height));bitmap.Save(Path.Combine(directory,name),ImageFormat.Png);}
  }
  static Control FindTitle(Control control) {
   foreach(Control child in control.Controls){if(child is Label && child.Text.StartsWith("CountingTrees"))return child;Control found=FindTitle(child);if(found!=null)return found;}return null;
  }
  [STAThread]
  public static void Main(string[] args) {
   string directory=Path.GetFullPath(args[0]);Directory.CreateDirectory(directory);
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
   var dispatched=new List<string>();
   using(var host=new PlantWorkbenchForm()) {
    host.ClientSize=new Size(540,610);var panel=new PlantWorkbench(delegate(string action){dispatched.Add(action);});host.Controls.Add(panel);
    var values=new Dictionary<string,object>{
     {"name","银杏"},{"spec_no","P001"},{"crown_m",3.0},{"dbh_cm",12.0},{"caliper_cm",0.0},{"kind",0},{"diameter_mode","dbh"},{"style",0},{"units_per_m",1000.0},
     {"hint","点击开始布置，图例跟随鼠标；在底图单击放下一株。"},{"last_error",""}
    };
    Prepare(host);panel.UpdateState(values,"示例底图.dwg",false);
    Save(panel,directory,"操作浮窗.png",540,610);
    Save(panel,directory,"操作浮窗窄版.png",360,610);
    values["kind"]=1;values["name"]="桂花";values["spec_no"]="P002";values["crown_m"]=0.0;values["caliper_cm"]=0.0;values["diameter_mode"]="caliper";values["style"]=1;
    values["hint"]="当前规格尚缺冠幅，点击绿色按钮直接补填。";panel.UpdateState(values,"示例底图.dwg",false);
    Save(panel,directory,"操作浮窗待补冠幅.png",540,610);
    var field=typeof(PlantWorkbench).GetField("popups",BindingFlags.Instance|BindingFlags.NonPublic);
    var popups=(List<ContextMenuStrip>)field.GetValue(panel);int actions=0;
    foreach(ContextMenuStrip menu in popups)foreach(ToolStripMenuItem item in menu.Items){
     int before=dispatched.Count;item.PerformClick();if(dispatched.Count!=before+1)throw new Exception("Menu did not dispatch: "+item.Text);actions++;
    }
    if(popups.Count!=8 || actions<45)throw new Exception("Incomplete workflow menus");
    int collapsed=0,expanded=0;
    host.CollapseRequested+=delegate {collapsed++;};panel.CollapseRequested+=delegate {collapsed++;};
    var title=FindTitle(panel);
    typeof(Control).GetMethod("OnDoubleClick",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(title,new object[]{EventArgs.Empty});
    Message message=Message.Create(host.Handle,0x00A3,new IntPtr(2),IntPtr.Zero);
    typeof(PlantWorkbenchForm).GetMethod("WndProc",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(host,new object[]{message});
    if(collapsed!=2)throw new Exception("Double-click collapse did not fire");
    using(var badge=new PlantBadgeForm(delegate {expanded++;})) {
     Prepare(badge);
     var canvas=badge.Controls[0];
     canvas.GetType().GetMethod("OnMouseDoubleClick",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(canvas,new object[]{new MouseEventArgs(MouseButtons.Left,2,32,32,0)});
     if(expanded!=1)throw new Exception("Badge double-click did not expand");
     using(var bitmap=new Bitmap(64,64)){badge.DrawToBitmap(bitmap,new Rectangle(0,0,64,64));bitmap.Save(Path.Combine(directory,"植物小圆标.png"),ImageFormat.Png);}
    }
    string record="{\"passed\":true,\"same_control_render\":true,\"groups\":7,\"clickable_menu_actions\":"+actions+",\"states\":[\"selected_species\",\"narrow_scrollable\",\"missing_crown\",\"badge_expand_and_double_click_collapse\"]}";
    File.WriteAllText(Path.Combine(directory,"../../developer/ui-verification.json"),record);
    Console.WriteLine("WinForms render and "+actions+" actual menu click paths passed.");
   }
  }
 }
}
