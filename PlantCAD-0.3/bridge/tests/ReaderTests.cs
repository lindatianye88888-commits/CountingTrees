using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using PlantCADBridge;
public static class ReaderTests {
 static LispToken T(int c,object v=null){return new LispToken(c,v);}
 static void Assert(bool value){if(!value)throw new Exception("Reader assertion failed.");}
 public static void Main(){
  var data=new[]{
   T(5016),T(5005,"__object"),
   T(5016),T(5005,"ok"),T(5021),T(5017),
   T(5016),T(5005,"name"),T(5005,"植物名称{A}\\P\"银杏表"),T(5017),
   T(5016),T(5005,"plants"),T(5016),T(5005,"__array"),T(5017),T(5017),
   T(5016),T(5005,"locked"),T(5019),T(5017),
   T(5016),T(5005,"crown"),T(5001,5.0),T(5017),T(5017)};
  var result=(Dictionary<string,object>)LispValueReader.Decode(data);
  Assert(Object.Equals(result["ok"],true));Assert(Object.Equals(result["locked"],false));
  Assert(((object[])result["plants"]).Length==0);Assert((double)result["crown"]==5);
  var json=new JavaScriptSerializer();
  var copy=json.Deserialize<Dictionary<string,object>>(json.Serialize(result));
  Assert((string)copy["name"]=="植物名称{A}\\P\"银杏表");
  var flat=new[]{T(5005,"__object"),T(5016),T(5005,"ok"),T(5021),T(5017)};
  Assert(Object.Equals(((Dictionary<string,object>)LispValueReader.Decode(flat))["ok"],true));
  int rejected=0;
  foreach(var bad in new[]{new[]{T(5016),T(5005,"__array")},new[]{T(5017)},new[]{T(5016),T(5005,"__object"),T(5005,"invalid"),T(5017)}})
   try{LispValueReader.Decode(bad);}catch(InvalidOperationException){rejected++;}
  Assert(rejected==3);
  Console.WriteLine("LispValueReader: structured UTF-8, booleans, empty arrays, flat/nested results and malformed input passed.");
 }
}
