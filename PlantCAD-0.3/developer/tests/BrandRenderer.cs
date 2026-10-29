using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using PlantCADBridge;
class BrandRenderer {
 static void Check(bool value){if(!value)throw new Exception("Brand/about validation failed");}
 [STAThread] static void Main(string[] args){
  Application.EnableVisualStyles();string output=args[0];Directory.CreateDirectory(output);
  using(var bitmap=new Bitmap(512,512)){using(var g=Graphics.FromImage(bitmap))BrandMark.Draw(g,512);bitmap.Save(Path.Combine(output,"countingtrees-logo.png"));}
  using(var form=ProductIdentity.CreateAbout()){
   form.Show();Application.DoEvents();string text="";foreach(Control c in form.Controls)text+=c.Text;
   Check(text.Contains("梅梅的AI景观实验室")&&text.Contains("lindatianye88888@gmail.com")&&text.Contains("375803231@qq.com"));
   Check(form.CancelButton!=null&&form.AcceptButton!=null);Check(form.Controls[0] is BrandMark);
   using(var bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));bitmap.Save(Path.Combine(output,"about-countingtrees.png"));}
  }
  var kinds=new List<string>{"乔木","灌木/藤本","花草/地被","灌木球","花境","草坪","竹类"};
  var rows=new List<string[]>{new[]{"乔木","P001","香樟","600","400","12","——","株"},new[]{"乔木","P002","银杏","800","500","15","——","株"},new[]{"灌木球","P003","海桐球","120","100","——","——","株"},new[]{"灌木/藤本","P004","红叶石楠","60","40","——","——","平方米"},new[]{"花草/地被","P005","麦冬","20","15","——","——","平方米"},new[]{"竹类","P006","紫竹","300","150","——","——","丛"}};
  using(var form=new PlantProjectDialog(rows,kinds,0)){
   form.Size=new Size(1080,530);form.Show();Application.DoEvents();
   using(var bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));bitmap.Save(Path.Combine(output,"project-plants-demo.png"));}
  }
  File.WriteAllText(Path.Combine(output,"../../developer/brand-verification.json"),"{\"passed\":true,\"scope\":\"Actual WinForms about: author, both contacts, logo and close buttons; example project parameters\"}");
 }
}
