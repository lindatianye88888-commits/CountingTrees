using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
namespace PlantCADBridge {
 internal sealed class PlantWorkbench : UserControl {
  readonly Action<string> dispatch;
  public event Action CollapseRequested;
  readonly Label identity=new Label(),details=new Label(),status=new Label(),hint=new Label();
  readonly SymbolPreview preview=new SymbolPreview();
  readonly FlowLayoutPanel menus=new FlowLayoutPanel();
  readonly List<Button> groups=new List<Button>();
  readonly List<ContextMenuStrip> popups=new List<ContextMenuStrip>();
  readonly Button place=new Button(),choose=new Button(),project=new Button();
  readonly ToolTip tips=new ToolTip();
  public PlantWorkbench(Action<string> handler) {
   dispatch=handler; Dock=DockStyle.Fill; AutoScaleMode=AutoScaleMode.Font;
   BackColor=Color.FromArgb(246,248,245); Font=new Font("Microsoft YaHei UI",9F);
   var layout=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=1,RowCount=5,Padding=new Padding(12) };
   layout.RowStyles.Add(new RowStyle(SizeType.Absolute,26));
   layout.RowStyles.Add(new RowStyle(SizeType.Absolute,126));
   layout.RowStyles.Add(new RowStyle(SizeType.Absolute,43));
   layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));
   layout.RowStyles.Add(new RowStyle(SizeType.Absolute,86));
   var title=new Label {Text="CountingTrees / 数树 · 双击标题收起",Dock=DockStyle.Fill,ForeColor=Color.FromArgb(60,98,71),Font=new Font(Font.FontFamily,10F,FontStyle.Bold)};
   title.DoubleClick+=(sender,args)=>RequestCollapse();
   tips.SetToolTip(title,"双击标题或窗口标题栏，收起为植物小圆标。");
   var summary=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=2,RowCount=2,BackColor=Color.White,Padding=new Padding(6),Margin=new Padding(0,2,0,7) };
   summary.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,102));summary.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
   summary.RowStyles.Add(new RowStyle(SizeType.Absolute,45));summary.RowStyles.Add(new RowStyle(SizeType.Percent,100));
   preview.Dock=DockStyle.Fill; summary.Controls.Add(preview,0,0);summary.SetRowSpan(preview,2);
   identity.Dock=DockStyle.Fill;identity.Font=new Font(Font.FontFamily,11F,FontStyle.Bold);identity.ForeColor=Color.FromArgb(35,72,47);
   identity.AutoEllipsis=true;identity.Cursor=Cursors.Hand;identity.Click+=(s,e)=>dispatch("edit");
   tips.SetToolTip(identity,"点击修改当前植物规格。");
   details.Dock=DockStyle.Fill;details.ForeColor=Color.FromArgb(80,89,81);details.AutoEllipsis=true;
   summary.Controls.Add(identity,1,0);summary.Controls.Add(details,1,1);
   var quick=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=3,RowCount=1,Margin=Padding.Empty };
   quick.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,30));quick.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,30));quick.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,40));
   Configure(choose,"选植物","choose","搜索树种，建立项目规格。",false);
   Configure(project,"项目规格","project","调用当前图纸已有的植物规格。",false);
   Configure(place,"开始布置 ▾","place","点击后选择点放、灌木球、面积填充或引线标注。",true);
   var placement=new ContextMenuStrip {Font=Font,ShowImageMargin=false};
   foreach(string[] item in new[]{new[]{"连续点放植物","place_points"},new[]{"灌木球（单株）","shrub_ball"},new[]{"沿线等距布置","along_line"},new[]{"区域网格布置","in_area"},new[]{"已算面积自动填充","fill_area"},new[]{"已算面积引线标注","output_area"}}){
    string action=item[1];placement.Items.Add(item[0],null,(s,e)=>dispatch(action));
   }
   popups.Add(placement);
   place.Click+=(s,e)=>placement.Show(place,new Point(0,place.Height));
   quick.Controls.Add(choose,0,0);quick.Controls.Add(project,1,0);quick.Controls.Add(place,2,0);
   menus.Dock=DockStyle.Fill;menus.WrapContents=true;menus.AutoScroll=true;menus.Margin=Padding.Empty;
   AddGroup("选植物","植物库 / 项目 / 图中调用",new string[][] {
    new[]{"搜索植物库","choose"},new[]{"项目已有植物","project"},new[]{"从图中选为当前植物","pick"},new[]{"从图中选取并继续布置","reuse"},
    new[]{"导入植物库","catalog_import"},new[]{"导出植物库","catalog_export"}});
   AddGroup("图例","圆圈 / 树冠 / 自定义图块",new string[][] {
    new[]{"使用圆圈图例","symbol_circle"},new[]{"使用简笔树冠","symbol_simple"},new[]{"自定义图块与图例预览","symbols"},new[]{"从当前图纸选取图块","symbol_from_drawing"},new[]{"复制当前图例进行编辑","symbol_copy"}});
   AddGroup("布置","点放 / 沿线 / 几何面积",new string[][] {
    new[]{"灌木球（单株独立图层）","shrub_ball"},new[]{"已算面积自动填充","fill_area"},new[]{"已算面积出图引线标注","output_area"},new[]{"灌木线自动识别面积并标注","geometry_area"},new[]{"手动补面积（点闭合线/框选）","manual_area"},new[]{"连续点放","place_points"},new[]{"沿线等距布置","along_line"},new[]{"区域网格布置","in_area"},new[]{"灌木种植范围（平方米）","shrub_area"},new[]{"地被种植范围（平方米）","ground_area"}});
   AddGroup("编辑","改规格 / 换植物 / 批量更新",new string[][] {
    new[]{"已算面积关联当前植物","area_bind"},new[]{"从已有品种标注关联面积","area_from_label"},new[]{"修改当前植物规格","edit"},new[]{"编辑图中植物（双击也可）","instance"},new[]{"调整所选植物冠幅或显示系数","size"},new[]{"将所选植物替换为当前规格","replace"},new[]{"所选植物切换圆圈或树冠","style"},new[]{"按当前定义批量更新","update"},new[]{"查看植物或范围属性","info"}});
   AddGroup("标注","名称 / 规格 / 编号 / 引线",new string[][] {
    new[]{"植物名称","label_name"},new[]{"名称及完整规格","label_spec"},new[]{"规格编号","label_number"},new[]{"名称及引线","label_leader"},new[]{"区域编号或植物名称与面积","label_area"},new[]{"更新关联标注","sync"}});
   AddGroup("统计","全图 / 框选 / 表格 / 导出",new string[][] {
    new[]{"统计全部模型空间","count_all"},new[]{"统计所选范围","count_selected"},new[]{"生成苗木数量总表（全图全部类型）","table"},new[]{"分类数量表（乔木/灌木球/灌木地被）","table_groups"},new[]{"按品种生成数量表","table_species"},new[]{"拆分已有表格（按类别/品种）","table_split"},new[]{"生成植物名录表","list"},new[]{"生成植物规格表","specs"},new[]{"导出统计 CSV","export"}});
   AddGroup("设置","单位 / 比例 / 图层 / 连接",new string[][] {
    new[]{"图纸单位、比例与字高","settings"},new[]{"按已知长度校准单位","calibrate"},new[]{"保存项目到当前DWG","save_project"},new[]{"查看项目保存位置","save_info"},new[]{"检查植物图层状态","layers"},new[]{"连接当前图纸到 AI","connect"},new[]{"重新加载当前图纸","reload"},new[]{"使用帮助","help"}});
   menus.SizeChanged+=(s,e)=>LayoutGroups();
   var footer=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=1,RowCount=3,Margin=Padding.Empty};
   footer.RowStyles.Add(new RowStyle(SizeType.Absolute,23));footer.RowStyles.Add(new RowStyle(SizeType.Percent,100));
   footer.RowStyles.Add(new RowStyle(SizeType.Absolute,22));
   status.Dock=DockStyle.Fill;status.AutoEllipsis=true;
   hint.Dock=DockStyle.Fill;hint.AutoEllipsis=true;
   footer.Controls.Add(status,0,0);footer.Controls.Add(hint,0,1);
   var credits=new LinkLabel {Text=ProductIdentity.Author+" · 关于/联系",Dock=DockStyle.Fill,
    AutoEllipsis=true,TextAlign=ContentAlignment.MiddleLeft,Margin=Padding.Empty,
    LinkColor=Color.FromArgb(60,98,71),ActiveLinkColor=Color.FromArgb(35,72,47),LinkBehavior=LinkBehavior.HoverUnderline};
   credits.LinkClicked+=(s,e)=>ProductIdentity.ShowAbout(FindForm());
   tips.SetToolTip(credits,ProductIdentity.ContactText);footer.Controls.Add(credits,0,2);
   layout.Controls.Add(title,0,0);layout.Controls.Add(summary,0,1);layout.Controls.Add(quick,0,2);layout.Controls.Add(menus,0,3);layout.Controls.Add(footer,0,4);
   layout.DoubleClick+=(sender,args)=>RequestCollapse();
   preview.DoubleClick+=(sender,args)=>RequestCollapse();
   Controls.Add(layout);NoDocument();
  }
  internal void RequestCollapse(){if(CollapseRequested!=null)CollapseRequested();}
  void Configure(Button button,string text,string action,string tip,bool primary) {
   button.Text=text;button.Dock=DockStyle.Fill;button.Margin=new Padding(0,2,6,5);button.FlatStyle=FlatStyle.Flat;button.UseVisualStyleBackColor=false;
   button.FlatAppearance.BorderColor=Color.FromArgb(201,211,199);
   button.BackColor=primary ? Color.FromArgb(51,115,74) : Color.White;
   button.ForeColor=primary ? Color.White : Color.FromArgb(45,59,47);
   if(action!="place")button.Click+=(s,e)=>dispatch(action);tips.SetToolTip(button,tip);
  }
  void AddGroup(string title,string subtitle,string[][] items) {
   var button=new Button {Text=title+"  ▾\n"+subtitle,Height=59,TextAlign=ContentAlignment.MiddleLeft,Padding=new Padding(7,0,0,0),
    FlatStyle=FlatStyle.Flat,BackColor=Color.White,ForeColor=Color.FromArgb(45,69,49),Margin=new Padding(0,3,7,3)};
   button.FlatAppearance.BorderColor=Color.FromArgb(211,220,208);
   var popup=new ContextMenuStrip {Font=Font,ShowImageMargin=false};
   foreach(string[] item in items) {
    string action=item[1];var entry=new ToolStripMenuItem(item[0]);
    entry.Click+=(s,e)=>dispatch(action);popup.Items.Add(entry);
   }
   button.Click+=(s,e)=>popup.Show(button,new Point(0,button.Height));
   tips.SetToolTip(button,subtitle);popups.Add(popup);groups.Add(button);menus.Controls.Add(button);
  }
  void LayoutGroups() {
   int width=Math.Max(200,menus.ClientSize.Width-24);int columns=width>=430 ? 2 : 1;
   foreach(Button button in groups)button.Width=Math.Max(180,width/columns-7);
  }
  public void NoDocument() {
   identity.Text="当前植物：尚未选择";details.Text="打开已有底图，可先算几何面积或选择植物。";
   status.Text="等待图纸";hint.Text="可拖动浮窗标题栏，或拖动边缘调整大小。";preview.PlantName="";preview.Invalidate();
   place.Enabled=false;
  }
  public void Loading(string document) {
   identity.Text="正在准备当前图纸";details.Text=Path.GetFileName(document);
   status.Text="正在加载";hint.Text="请稍候";status.ForeColor=Color.DarkOrange;place.Enabled=false;
  }
  static string TextValue(Dictionary<string,object> v,string key) {object value;return v.TryGetValue(key,out value) ? Convert.ToString(value) : "";}
  static double Number(Dictionary<string,object> v,string key) {object value;return v.TryGetValue(key,out value) ? Convert.ToDouble(value) : 0;}
  public void UpdateState(Dictionary<string,object> values,string document,bool ai) {
   string name=TextValue(values,"name"),spec=TextValue(values,"spec_no");
   double crown=Number(values,"crown_m"),units=Number(values,"units_per_m");
   identity.Text=name.Length==0 ? "当前植物：尚未选择" : "当前植物："+name+"\n规格："+spec;
   tips.SetToolTip(identity,identity.Text+"\n点击修改当前规格。");
   string style=new[]{"圆圈","简笔树冠","自定义图块"}[Math.Max(0,Math.Min(2,(int)Number(values,"style")))];
   string unit=units==1000 ? "毫米" : units==1 ? "米" : units==100 ? "厘米" : units>0 ? "已按实长校准" : "未确认";
   bool ground=TextValue(values,"diameter_mode")=="caliper";double diameter=Number(values,ground ? "caliper_cm" : "dbh_cm");
   int kind=(int)Number(values,"kind");bool areaOnly=kind==2||kind==4||kind==5;
   details.Text="冠幅："+(crown>0 ? (crown*100.0).ToString("0.###")+" cm" : (areaOnly ? "按面积布置" : "待补填"))+
    (ground ? "    地径：" : "    胸径：")+(diameter>0 ? diameter.ToString("0.###")+" cm" : (Number(values,"kind")>0 ? "——" : "待填"))+"\n图例："+style+"    底图单位："+unit;
   status.Text="已加载 · "+Path.GetFileName(document)+(ai ? " · AI已连接" : " · 手动绘图可用");
   status.ForeColor=Color.FromArgb(39,100,57);tips.SetToolTip(status,status.Text);
   string error=TextValue(values,"last_error");hint.Text=error.Length>0 ? error : TextValue(values,"hint");
   hint.ForeColor=error.Length>0 ? Color.Firebrick : Color.FromArgb(75,88,73);tips.SetToolTip(hint,hint.Text);
   place.Text=name.Length>0 && crown<=0 && !areaOnly ? "补冠幅布置 ▾" : "开始布置 ▾";place.Enabled=true;
   preview.Style=(int)Number(values,"style");preview.PlantName=name;preview.Invalidate();
  }
  public void Message(string text,bool error) {hint.Text=text;hint.ForeColor=error ? Color.Firebrick : Color.FromArgb(75,88,73);tips.SetToolTip(hint,text);}
  protected override void Dispose(bool disposing) {
   if(disposing){tips.Dispose();foreach(ContextMenuStrip popup in popups)popup.Dispose();}
   base.Dispose(disposing);
  }
 }
 internal static class ProductIdentity {
  internal const string Author="梅梅的AI景观实验室";
  internal const string Gmail="lindatianye88888@gmail.com";
  internal const string QqMail="375803231@qq.com";
  internal const string ContactText="Gmail："+Gmail+"\nQQ邮箱："+QqMail;
  internal static void ShowAbout(IWin32Window owner) {
   using(var form=CreateAbout())form.ShowDialog(owner);
  }
  internal static Form CreateAbout(){
   var form=new Form{Text="关于 CountingTrees（数树）",ClientSize=new Size(490,310),FormBorderStyle=FormBorderStyle.FixedDialog,
    MaximizeBox=false,MinimizeBox=false,ShowInTaskbar=false,StartPosition=FormStartPosition.CenterParent,BackColor=Color.FromArgb(246,248,245),Font=new Font("Microsoft YaHei UI",10F)};
   form.Controls.Add(new BrandMark{Location=new Point(24,24),Size=new Size(90,90)});
   form.Controls.Add(new Label{Text="CountingTrees / 数树",Location=new Point(132,28),AutoSize=true,Font=new Font("Microsoft YaHei UI",17F,FontStyle.Bold)});
   form.Controls.Add(new Label{Text="景观植物绘图与数量统计 · 0.3.31 开发版",Location=new Point(134,76),AutoSize=true});
   form.Controls.Add(new Label{Text="署名："+Author+"\n\n"+ContactText,Location=new Point(28,134),Size=new Size(440,112)});
   var close=new Button{Text="关闭",DialogResult=DialogResult.Cancel,Location=new Point(352,264),Size=new Size(110,30)};
   form.Controls.Add(close);form.CancelButton=close;form.AcceptButton=close;return form;
  }
 }
 internal sealed class BrandMark : Control {
  internal BrandMark(){DoubleBuffered=true;}
  internal static void Draw(Graphics g,float size){
   var state=g.Save();g.ScaleTransform(size/256F,size/256F);g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
   using(var bg=new SolidBrush(Color.FromArgb(18,63,48)))g.FillRectangle(bg,0,0,256,256);
   using(var pen=new Pen(Color.FromArgb(230,244,225),7F)){
    pen.StartCap=pen.EndCap=System.Drawing.Drawing2D.LineCap.Round;
    g.DrawEllipse(pen,59,79,82,82);g.DrawEllipse(pen,115,79,82,82);g.DrawEllipse(pen,87,48,82,82);
    g.DrawLine(pen,128,121,128,199);g.DrawLine(pen,128,158,102,137);g.DrawLine(pen,128,176,155,151);g.DrawLine(pen,101,200,155,200);
   }
   using(var pen=new Pen(Color.FromArgb(159,204,135),4F)){
    g.DrawLines(pen,new[]{new PointF(25,62),new PointF(25,25),new PointF(62,25)});
    g.DrawLines(pen,new[]{new PointF(194,231),new PointF(231,231),new PointF(231,194)});
   }
   using(var dot=new SolidBrush(Color.FromArgb(211,180,97)))for(int i=0;i<3;i++)g.FillEllipse(dot,181+i*18,30,8,8);
   g.Restore(state);
  }
  protected override void OnPaint(PaintEventArgs e){base.OnPaint(e);Draw(e.Graphics,Math.Min(Width,Height));}
 }
 internal sealed class SymbolPreview : Control {
  public int Style;public string PlantName="";
  public SymbolPreview(){DoubleBuffered=true;}
  protected override void OnPaint(PaintEventArgs args) {
   base.OnPaint(args);var g=args.Graphics;g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
   float cx=Width/2F,cy=39F,r=Math.Min(Width*.32F,29F);
   using(var pen=new Pen(Color.FromArgb(58,119,77),1.8F)){
    if(Style==1){
     var points=new PointF[49];for(int i=0;i<49;i++){double a=2*Math.PI*i/48,rad=r*(1-.11*(1-Math.Cos(8*a)));points[i]=new PointF(cx+(float)(rad*Math.Cos(a)),cy+(float)(rad*Math.Sin(a)));}
     g.DrawLines(pen,points);g.DrawEllipse(pen,cx-3,cy-3,6,6);
    }else{if(Style==2)pen.DashStyle=System.Drawing.Drawing2D.DashStyle.Dash;g.DrawEllipse(pen,cx-r,cy-r,r*2,r*2);}
   }
   string label=Style==2 ? "自定义示意" : String.IsNullOrEmpty(PlantName) ? "图例预览" : PlantName;
   using(var brush=new SolidBrush(Color.FromArgb(37,78,49)))
   using(var format=new StringFormat {Alignment=StringAlignment.Center})
    g.DrawString(label,Font,brush,new RectangleF(0,76,Width,34),format);
  }
 }

 internal sealed class PlantWorkbenchForm : Form {
  public event Action CollapseRequested;
  protected override void WndProc(ref Message message) {
   if(message.Msg==0x00A3 && message.WParam.ToInt32()==2) {
    if(CollapseRequested!=null)CollapseRequested();return;
   }
   base.WndProc(ref message);
  }
 }
 internal sealed class PlantBadgeForm : Form {
  readonly BadgeCanvas canvas;
  public PlantBadgeForm(Action expand) {
   Text="CountingTrees（数树） 植物小圆标";FormBorderStyle=FormBorderStyle.None;
   ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;AutoScaleMode=AutoScaleMode.None;
   ClientSize=new Size(64,64);BackColor=Color.FromArgb(243,250,240);
   canvas=new BadgeCanvas(expand){Dock=DockStyle.Fill};Controls.Add(canvas);
   using(var path=new System.Drawing.Drawing2D.GraphicsPath()){path.AddEllipse(0,0,64,64);Region=new Region(path);}
  }
  internal void SetPlant(string name){canvas.SetPlant(name);}
  internal void ActivatePanel(){canvas.ActivatePanel();}
  sealed class BadgeCanvas : Control {
   readonly Action expand;readonly ToolTip tip=new ToolTip();
   Point cursorStart,windowStart;bool dragging,moved;
   public BadgeCanvas(Action action) {
    expand=action;DoubleBuffered=true;Cursor=Cursors.Hand;
    SetStyle(ControlStyles.StandardDoubleClick|ControlStyles.StandardClick,true);
    SetPlant("");
    var menu=new ContextMenuStrip {ShowImageMargin=false};
    menu.Items.Add("打开植物操作面板",null,(s,e)=>ActivatePanel());
    menu.Items.Add("关于 CountingTrees / 联系作者",null,(s,e)=>ProductIdentity.ShowAbout(FindForm()));ContextMenuStrip=menu;
   }
   public void SetPlant(string name){tip.SetToolTip(this,"CountingTrees（数树）"+(String.IsNullOrEmpty(name) ? "" : " · "+name)+"\n"+ProductIdentity.Author+"\n双击展开，拖动移动；右键查看联系方式");}
   public void ActivatePanel(){expand();}
   protected override void OnMouseDoubleClick(MouseEventArgs e){base.OnMouseDoubleClick(e);if(e.Button==MouseButtons.Left&&!moved)ActivatePanel();}
   protected override void OnMouseDown(MouseEventArgs e) {
    base.OnMouseDown(e);if(e.Button!=MouseButtons.Left)return;
    dragging=true;moved=false;cursorStart=Cursor.Position;windowStart=FindForm().Location;Capture=true;
   }
   protected override void OnMouseMove(MouseEventArgs e) {
    base.OnMouseMove(e);if(!dragging)return;
    int dx=Cursor.Position.X-cursorStart.X,dy=Cursor.Position.Y-cursorStart.Y;
    if(Math.Abs(dx)+Math.Abs(dy)>4)moved=true;
    if(!moved)return;
    Rectangle area=Screen.GetWorkingArea(Cursor.Position);
    FindForm().Location=new Point(Math.Max(area.Left,Math.Min(area.Right-Width,windowStart.X+dx)),
      Math.Max(area.Top,Math.Min(area.Bottom-Height,windowStart.Y+dy)));
   }
   protected override void OnMouseUp(MouseEventArgs e){base.OnMouseUp(e);dragging=false;Capture=false;}
   protected override void OnPaint(PaintEventArgs e) {
    base.OnPaint(e);var g=e.Graphics;g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
    g.Clear(Color.FromArgb(243,250,240));
    using(var border=new Pen(Color.FromArgb(57,112,66),2F))g.DrawEllipse(border,2,2,59,59);
    using(var leaves=new SolidBrush(Color.FromArgb(73,137,79))){
     g.FillEllipse(leaves,16,17,21,21);g.FillEllipse(leaves,29,17,21,21);g.FillEllipse(leaves,22,10,21,23);
    }
    using(var trunk=new Pen(Color.FromArgb(60,102,54),3F)){
     g.DrawLine(trunk,32,30,32,49);g.DrawLine(trunk,32,37,24,30);g.DrawLine(trunk,32,40,41,31);
     g.DrawLine(trunk,21,50,43,50);
    }
   }
   protected override void Dispose(bool disposing){if(disposing){tip.Dispose();if(ContextMenuStrip!=null)ContextMenuStrip.Dispose();}base.Dispose(disposing);}
  }
 }
}
