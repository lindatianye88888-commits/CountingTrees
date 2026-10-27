using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;

namespace PlantCADBridge {
 // Reads a single plant annotation. Numbers in text are never a quantity source.
 internal sealed class PlantAnnotationRecord {
  internal string Name="",Spec="";
  internal bool Area,Block;
  internal double Dbh=-1,Caliper=-1,Height=-1,Crown=-1;
 }
 internal static class PlantAnnotationParser {
  const string Number=@"(?:\d+(?:\.\d+)?|\.\d+)";
  static readonly Regex Quantity=new Regex(@"(?:约\s*)?"+Number+@"\s*(?:平方米|平方[米]?|㎡|m[²2]|株|丛|棵)(?![A-Za-z])",RegexOptions.IgnoreCase);
  static readonly Regex Specification=new Regex(@"(?<![A-Za-z0-9])P\d{1,8}(?![A-Za-z0-9=])",RegexOptions.IgnoreCase);
  static readonly Regex Dimension=new Regex(@"(?<key>胸径|地径|高度|冠幅|D|d|H|h|P|p|Φ|φ|%%[cC])\s*(?:[=:：]\s*)?(?<value>"+Number+@")\s*(?<unit>cm|CM|厘米|公分|米|m)?(?![\d.])");
  internal static PlantAnnotationRecord Parse(IEnumerable<string> input,bool block){
   var record=new PlantAnnotationRecord{Block=block};var names=new List<string>();var bare=new List<double>();
   int length=0,lines=0;bool invalid=false;
   foreach(string raw in input){
    if(raw==null)continue;length+=raw.Length;if(++lines>128||length>4096)return null;
    foreach(string part in raw.Replace("\\P","\n").Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries)){
     string text=part.Replace("\\~"," ").Trim();
     text=Regex.Replace(text,@"[（(](?:补线推定|拟合|手动补面积)[^）)]*[）)]","");
     var amounts=Quantity.Matches(text);if(amounts.Count>1)return null;
     foreach(Match amount in amounts)if(Regex.IsMatch(amount.Value,@"平方米|平方|㎡|m[²2]",RegexOptions.IgnoreCase))record.Area=true;
     text=Quantity.Replace(text,"");
     text=Dimension.Replace(text,delegate(Match match){
      string key=match.Groups["key"].Value,unit=match.Groups["unit"].Value;
      // A bare P039 is a specification ID, not a crown width.
      if((key=="P"||key=="p")&&unit.Length==0&&match.Value.IndexOf('=')<0&&match.Value.IndexOf(':')<0&&match.Value.IndexOf('：')<0)return match.Value;
      double value=Double.Parse(match.Groups["value"].Value,CultureInfo.InvariantCulture);
      if(unit=="m"||unit=="米")value*=100;
      double previous=(key=="地径"||key=="d")?record.Caliper:(key=="高度"||key=="H"||key=="h")?record.Height:(key=="冠幅"||key=="P"||key=="p")?record.Crown:record.Dbh;
      if(previous>=0&&previous!=value)invalid=true;
      if(key=="地径"||key=="d")record.Caliper=value;
      else if(key=="高度"||key=="H"||key=="h")record.Height=value;
      else if(key=="冠幅"||key=="P"||key=="p")record.Crown=value;
      else record.Dbh=value;
      return "";
     });
     foreach(Match spec in Specification.Matches(text)){
      string value=spec.Value.ToUpperInvariant();if(record.Spec.Length>0&&record.Spec!=value)return null;record.Spec=value;
     }
     text=Specification.Replace(text,"");
     text=Regex.Replace(text,@"^(?:植物名称|植物|品种|名称)\s*[:：]\s*","").Trim(' ','\t','|','/','：',':','-');
     double number;if(Double.TryParse(text,NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out number)){if(!bare.Contains(number))bare.Add(number);continue;}
     if(text.Length==0)continue;
     if(text.Length>40||!Regex.IsMatch(text,@"^[\p{L}][\p{L}\p{N} ·（）()\-]*$"))return null;
     if(!names.Contains(text))names.Add(text);
    }
   }
   if(invalid||names.Count>1||names.Count==0&&record.Spec.Length==0||bare.Count>1)return null;
   if(names.Count==1)record.Name=names[0];
   // The second line on a single tree symbol is commonly a diameter, never a count.
   if(block&&!record.Area&&bare.Count==1&&record.Dbh<0&&record.Caliper<0)record.Dbh=bare[0];
   if(record.Dbh>=0&&record.Caliper>=0)return null;
   return record;
  }
 }
}
