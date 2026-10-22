using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace PlantCADBridge {
 internal sealed class PlantProjectDialog : Form {
  static Size previousSize=new Size(1140,570);
  readonly List<string[]> source;
  internal readonly DataGridView Grid=new DataGridView();
  internal readonly ComboBox Category=new ComboBox();
  internal readonly TextBox Search=new TextBox();
  readonly List<Button> selectedButtons=new List<Button>();
  internal int ActionCode,SelectedIndex=-1;
  internal PlantProjectDialog(List<string[]> rows,List<string> kinds,int index){
   source=rows;Text="CountingTrees（数树） - 项目植物与规格";Font=new Font("Microsoft YaHei",9F);
   AutoScaleMode=AutoScaleMode.Dpi;FormBorderStyle=FormBorderStyle.Sizable;MaximizeBox=true;MinimizeBox=false;
   ShowInTaskbar=false;StartPosition=FormStartPosition.CenterParent;MinimumSize=new Size(780,390);
   Size=previousSize;
   var working=Screen.PrimaryScreen.WorkingArea;Size=new Size(Math.Min(Width,working.Width),Math.Min(Height,working.Height));
   Padding=new Padding(10);
   var layout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=6};Controls.Add(layout);
   layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
   layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));
   for(int i=0;i<3;i++)layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
   layout.Controls.Add(new Label{Text="按分类排列，可按名称或编号检索；不同尺寸使用独立规格编号。",AutoSize=true,Margin=new Padding(0,0,0,8)},0,0);
   var filters=new TableLayoutPanel{Dock=DockStyle.Top,AutoSize=true,AutoSizeMode=AutoSizeMode.GrowAndShrink,ColumnCount=5,RowCount=1,Margin=new Padding(0,0,0,8)};
   filters.RowStyles.Add(new RowStyle(SizeType.AutoSize));
   filters.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));filters.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,190));
   filters.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));filters.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));filters.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,80));
   filters.Controls.Add(new Label{Text="分类",AutoSize=true,Anchor=AnchorStyles.Left},0,0);
   Category.DropDownStyle=ComboBoxStyle.DropDownList;Category.Dock=DockStyle.Fill;Category.Items.Add("全部分类");foreach(string k in kinds)Category.Items.Add(k);
   filters.Controls.Add(Category,1,0);filters.Controls.Add(new Label{Text="名称/编号检索",AutoSize=true,Anchor=AnchorStyles.Left},2,0);
   Search.Dock=DockStyle.Fill;filters.Controls.Add(Search,3,0);var find=new Button{Text="检索",Anchor=AnchorStyles.Left|AnchorStyles.Right,AutoSize=true};filters.Controls.Add(find,4,0);
   layout.Controls.Add(filters,0,1);
   Grid.Dock=DockStyle.Fill;Grid.AllowUserToAddRows=false;Grid.AllowUserToDeleteRows=false;Grid.ReadOnly=true;
   Grid.AllowUserToResizeColumns=true;Grid.AllowUserToResizeRows=false;Grid.RowHeadersVisible=false;Grid.MultiSelect=false;
   Grid.SelectionMode=DataGridViewSelectionMode.FullRowSelect;Grid.AutoSizeColumnsMode=DataGridViewAutoSizeColumnsMode.Fill;
   Grid.BackgroundColor=Color.White;Grid.BorderStyle=BorderStyle.FixedSingle;Grid.RowTemplate.Height=27;
   string[] headers={"分类","编号","植物名称","高度H/cm","冠幅P/cm","胸径D/cm","地径d/cm","单位"};
   float[] weights={17,12,24,12,12,12,12,10};
   for(int c=0;c<headers.Length;c++){int n=Grid.Columns.Add("column"+c,headers[c]);Grid.Columns[n].FillWeight=weights[c];Grid.Columns[n].MinimumWidth=c==2?120:65;Grid.Columns[n].SortMode=DataGridViewColumnSortMode.Automatic;}
   layout.Controls.Add(Grid,0,2);
   var actions=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill,Margin=new Padding(0,7,0,0)};
   actions.Controls.Add(Action("从品种库建规格",2,false));actions.Controls.Add(Action("手动新增",5,false));
   actions.Controls.Add(Action("复制新规格",6,true));var edit=Action("修改规格",3,true);actions.Controls.Add(edit);actions.Controls.Add(Action("更新已有植物",4,true));
   layout.Controls.Add(actions,0,3);
   layout.Controls.Add(new Label{Text="修改项目规格会同步图中对象及所有关联表；双击单株只修改该株。",AutoSize=true,Margin=new Padding(0,5,0,5)},0,4);
   var finish=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill,Margin=new Padding(0)};
   finish.Controls.Add(Action("设为当前并开始布置",7,true));finish.Controls.Add(Action("设为当前规格",1,true));
   var close=new Button{Text="关闭",AutoSize=true,MinimumSize=new Size(110,30),DialogResult=DialogResult.Cancel};finish.Controls.Add(close);layout.Controls.Add(finish,0,5);
   AcceptButton=edit;CancelButton=close;
   Category.SelectedIndexChanged+=(s,e)=>Filter();Search.TextChanged+=(s,e)=>Filter();find.Click+=(s,e)=>Filter();
   Grid.SelectionChanged+=(s,e)=>UpdateActions();Grid.CellDoubleClick+=(s,e)=>{if(e.RowIndex>=0)Choose(3);};
   Category.SelectedIndex=0;
   if(index>=0&&index<source.Count)foreach(DataGridViewRow row in Grid.Rows)if((int)row.Tag==index){Grid.CurrentCell=row.Cells[0];break;}
   FormClosing+=(s,e)=>{previousSize=WindowState==FormWindowState.Normal?Size:RestoreBounds.Size;};
  }
  Button Action(string text,int code,bool selection){
   var button=new Button{Text=text,AutoSize=true,MinimumSize=new Size(110,30),Margin=new Padding(0,0,8,5)};
   if(selection)selectedButtons.Add(button);button.Click+=(s,e)=>Choose(code);return button;
  }
  void UpdateActions(){foreach(var button in selectedButtons)button.Enabled=Grid.CurrentRow!=null;}
  internal void Filter(){
   int previous=Grid.CurrentRow==null?-1:(int)Grid.CurrentRow.Tag;Grid.Rows.Clear();
   string kind=Category.SelectedIndex>0?Convert.ToString(Category.SelectedItem):null,query=Search.Text.Trim();
   for(int i=0;i<source.Count;i++){var row=source[i];if(kind!=null&&row[0]!=kind)continue;
    if(query.Length>0&&row[1].IndexOf(query,StringComparison.OrdinalIgnoreCase)<0&&row[2].IndexOf(query,StringComparison.OrdinalIgnoreCase)<0)continue;
    int added=Grid.Rows.Add(row);Grid.Rows[added].Tag=i;
   }
   if(Grid.Rows.Count>0){Grid.CurrentCell=Grid.Rows[0].Cells[0];foreach(DataGridViewRow row in Grid.Rows)if((int)row.Tag==previous){Grid.CurrentCell=row.Cells[0];break;}}
   UpdateActions();
  }
  internal void Choose(int code){
   if(code!=2&&code!=5&&Grid.CurrentRow==null)return;
   ActionCode=code;SelectedIndex=Grid.CurrentRow==null?-1:(int)Grid.CurrentRow.Tag;DialogResult=DialogResult.OK;Close();
  }
 }
}
