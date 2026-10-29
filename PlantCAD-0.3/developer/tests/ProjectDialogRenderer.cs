using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using PlantCADBridge;
class ProjectDialogRenderer {
 static int checks;
 static void Check(bool value,string message){if(!value)throw new Exception(message);checks++;}
 [STAThread] static void Main(string[] args){
  Application.EnableVisualStyles();var kinds=new List<string>{"乔木","灌木/藤本","花草/地被","灌木球","花境","草坪","竹类"};
  var rows=new List<string[]>();for(int i=0;i<7;i++)rows.Add(new[]{kinds[i],"P00"+i,"测试植物"+i,"100","80","12","——","株"});
  using(var f=new PlantProjectDialog(rows,kinds,3)){
   f.Show();Application.DoEvents();Check(f.FormBorderStyle==FormBorderStyle.Sizable&&f.MaximizeBox,"Resizable chrome missing");
   Check(f.Grid.Rows.Count==7&&f.Grid.Columns.Count==8,"Plant columns changed");Check((int)f.Grid.CurrentRow.Tag==3,"Initial selection changed");
   f.Size=new Size(800,420);Application.DoEvents();Check(f.Grid.ClientSize.Height>80&&f.Grid.Right<=f.ClientSize.Width,"Small window grid clipped");
   int small=f.Grid.Height;f.Size=new Size(1300,720);Application.DoEvents();Check(f.Grid.Height>small+150,"Growing window did not grow list");
   f.Category.SelectedIndex=4;Application.DoEvents();Check(f.Grid.Rows.Count==1&&(int)f.Grid.Rows[0].Tag==3,"Shrub-ball filter lost identity");
   f.Category.SelectedIndex=7;Application.DoEvents();Check(f.Grid.Rows.Count==1&&(int)f.Grid.Rows[0].Tag==6,"Bamboo filter lost identity");
   f.Category.SelectedIndex=0;f.Search.Text="p005";Application.DoEvents();Check(f.Grid.Rows.Count==1&&(int)f.Grid.Rows[0].Tag==5,"Code search failed");
   f.Search.Text="测试植物2";Application.DoEvents();Check(f.Grid.Rows.Count==1&&(int)f.Grid.Rows[0].Tag==2,"Name search failed");
   f.Search.Text="";f.Grid.Sort(f.Grid.Columns[1],System.ComponentModel.ListSortDirection.Descending);Application.DoEvents();
   f.Grid.CurrentCell=f.Grid.Rows[0].Cells[0];Check((int)f.Grid.CurrentRow.Tag==6,"Sorting lost original specification index");
   using(var image=new Bitmap(f.Width,f.Height)){f.DrawToBitmap(image,new Rectangle(0,0,f.Width,f.Height));image.Save(Path.Combine(args[0],"项目窗口缩放预览.png"));}
   f.Choose(3);Check(f.ActionCode==3&&f.SelectedIndex==6,"Edit targets wrong sorted row");
  }
  using(var f=new PlantProjectDialog(new List<string[]>(),kinds,0)){
   f.Show();Application.DoEvents();Check(f.Grid.Rows.Count==0,"Empty project failed");f.Choose(3);Check(f.Visible,"Empty edit closed the dialog");f.Choose(8);Check(f.Visible,"Empty delete closed the dialog");f.Choose(5);Check(f.ActionCode==5,"Cannot add to empty project");
  }
  using(var f=new PlantProjectDialog(new List<string[]>(),kinds,0)){
   f.Show();Application.DoEvents();f.Choose(4);Check(f.ActionCode==4&&f.SelectedIndex==-1,"Cannot collect drawing plants into an empty project");
  }
  using(var f=new PlantProjectDialog(rows,kinds,2,true)){
   f.Show();Application.DoEvents();Check(f.Text.Contains("具体规格"),"Ambiguous species picker not identified");
   f.Choose(1);Check(f.ActionCode==1&&f.SelectedIndex==2,"Ambiguous species picker lost selected specification");
  }
  using(var f=new PlantProjectDialog(rows,kinds,0)){
   f.Show();f.Category.SelectedIndex=7;Application.DoEvents();
   f.Choose(8);Check(f.ActionCode==8&&f.SelectedIndex==6,"Delete targets wrong filtered specification");
  }
  File.WriteAllText(Path.Combine(args[0],"project-dialog-render.txt"),"PASS "+checks);
 }
}
