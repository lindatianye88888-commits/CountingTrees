using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
[assembly:CommandClass(typeof(TableDisplayAudit))]
public class TableDisplayAudit {
 [CommandMethod("PC_TABLE_DISPLAY_AUDIT")]
 public void Run(){var doc=Application.DocumentManager.MdiActiveDocument;var db=doc.Database;var tables=new List<object>();
  using(var tr=db.TransactionManager.StartTransaction()) {
   var space=(BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db),OpenMode.ForRead);
   foreach(ObjectId id in space){var table=tr.GetObject(id,OpenMode.ForRead) as Table;if(table==null)continue;
    var rows=new List<object>();for(int row=0;row<Math.Min(5,table.Rows.Count);row++){var cells=new List<object>();
     for(int col=0;col<table.Columns.Count;col++){var cell=table.Cells[row,col];var contents=new List<object>();
      foreach(CellContent content in cell.Contents)contents.Add(new{text=content.TextString,height=content.TextHeight});
      var style=(TextStyleTableRecord)tr.GetObject(cell.TextStyleId??db.Textstyle,OpenMode.ForRead);
      cells.Add(new{col,text=cell.TextString,height=cell.TextHeight,style=style.Name,font=style.FileName,fixed_height=style.TextSize,contents});}
     rows.Add(new{row,height=table.Rows[row].Height,cells});}
    tables.Add(new{handle=table.Handle.ToString(),layer=table.Layer,rows=table.Rows.Count,columns=table.Columns.Count,sample=rows});
   }
  }
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(doc.Name),"table-display-audit.json"),new JavaScriptSerializer{MaxJsonLength=10000000}.Serialize(tables));
 }
}
