using System;
using System.Collections.Generic;
using PlantCADBridge;
public static class AnnotationParserTests {
 static readonly List<string> Checks=new List<string>();
 static void Check(bool condition,string name){if(!condition)throw new Exception(name);Checks.Add(name);}
 public static string Run(){
  Checks.Clear();var r=PlantAnnotationParser.Parse(new[]{"海桐 3.13 平方米"},false);
  Check(r!=null&&r.Name=="海桐"&&r.Area&&!r.Block,"inline shrub name and area");
  r=PlantAnnotationParser.Parse(new[]{"紫珠", "2.21 ㎡"},false);Check(r.Name=="紫珠"&&r.Area,"stacked shrub name");
  r=PlantAnnotationParser.Parse(new[]{"鸢尾 约 18.05 平方米（补线推定）"},false);Check(r.Name=="鸢尾"&&r.Area,"repair qualifier");
  r=PlantAnnotationParser.Parse(new[]{"银杏","12"},true);Check(r.Name=="银杏"&&r.Dbh==12&&r.Block,"bare tree diameter");
  r=PlantAnnotationParser.Parse(new[]{"银杏 12株"},false);Check(r.Name=="银杏"&&r.Dbh<0,"explicit counts are not dimensions");
  r=PlantAnnotationParser.Parse(new[]{"香樟 D=18cm H=6m P=300cm"},true);Check(r.Name=="香樟"&&r.Dbh==18&&r.Height==600&&r.Crown==300,"dimension units");
  r=PlantAnnotationParser.Parse(new[]{"红叶石楠球 d=4cm H=100cm P=80cm"},true);Check(r.Name=="红叶石楠球"&&r.Caliper==4&&r.Dbh<0,"caliper differs from dbh");
  r=PlantAnnotationParser.Parse(new[]{"P039","国槐"},true);Check(r.Spec=="P039"&&r.Name=="国槐"&&r.Crown<0,"spec number is not crown width");
  r=PlantAnnotationParser.Parse(new[]{"P039"},false);Check(r.Spec=="P039"&&r.Name=="","spec only text");
  r=PlantAnnotationParser.Parse(new[]{"名称：金叶女贞"},false);Check(r.Name=="金叶女贞","name prefix");
  r=PlantAnnotationParser.Parse(new[]{"海桐\\P3.13m2"},false);Check(r.Name=="海桐"&&r.Area,"mtext separator");
  Check(PlantAnnotationParser.Parse(new[]{"银杏","桂花"},true)==null,"multiple plant plan block rejected");
  Check(PlantAnnotationParser.Parse(new[]{"海桐 3.13平方米 紫珠 2.21平方米"},false)==null,"multiple quantities rejected");
  Check(PlantAnnotationParser.Parse(new[]{"P001","P002","银杏"},true)==null,"ambiguous specification rejected");
  Check(PlantAnnotationParser.Parse(new[]{"12","20"},true)==null,"numbers without name rejected");
  Check(PlantAnnotationParser.Parse(new[]{new string('树',4097)},true)==null,"input size bounded");
  Check(PlantAnnotationParser.Parse(new[]{"总表 | 名称 | 数量"},false)==null,"schedule row rejected");
  r=PlantAnnotationParser.Parse(new[]{"银杏","12","银杏","12"},true);Check(r!=null&&r.Dbh==12,"duplicated exploded attribute text");
  Check(PlantAnnotationParser.Parse(new[]{"银杏 D=12cm","银杏 D=18cm"},true)==null,"conflicting explicit dimensions rejected");
  return "PASS "+Checks.Count+"\n"+String.Join("\n",Checks.ToArray());
 }
}
