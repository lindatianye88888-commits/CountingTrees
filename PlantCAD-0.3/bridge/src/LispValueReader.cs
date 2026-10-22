using System;
using System.Collections.Generic;
namespace PlantCADBridge {
 public sealed class LispToken {
  public int Code; public object Value;
  public LispToken(int code,object value) { Code=code; Value=value; }
 }
 // Tags keep empty arrays, objects and booleans unambiguous. Strings never pass
 // through a hand-written JSON escape routine in legacy GBK AutoLISP.
 public static class LispValueReader {
  public static object Decode(LispToken[] tokens) {
   int index=0;
   if (tokens.Length==0) throw new InvalidOperationException("Empty LISP result.");
   if (tokens[0].Code==5016) {
    object value=Read(tokens,ref index);
    if(index!=tokens.Length) throw new InvalidOperationException("Trailing LISP result.");
    return value;
   }
   var items=new List<object>();
   while(index<tokens.Length) items.Add(Read(tokens,ref index));
   return ConvertList(items);
  }
  static object Read(LispToken[] tokens,ref int index) {
   if(index>=tokens.Length) throw new InvalidOperationException("Incomplete LISP result.");
   LispToken token=tokens[index++];
   if(token.Code==5016) {
    var items=new List<object>();
    while(index<tokens.Length && tokens[index].Code!=5017) items.Add(Read(tokens,ref index));
    if(index>=tokens.Length) throw new InvalidOperationException("Unclosed LISP list.");
    index++;
    return ConvertList(items);
   }
   if(token.Code==5017) throw new InvalidOperationException("Unexpected list end.");
   if(token.Code==5019) return false;
   if(token.Code==5021) return true;
   if(token.Code==5005 || token.Code==5001 || token.Code==5003 || token.Code==5010) return token.Value;
   throw new InvalidOperationException("Unsupported LISP result type: "+token.Code);
  }
  static object ConvertList(List<object> items) {
   if(items.Count>0 && items[0] is string && (string)items[0]=="__object") {
    var result=new Dictionary<string,object>();
    for(int i=1;i<items.Count;i++) {
     var pair=items[i] as List<object>;
     if(pair==null || pair.Count!=2 || !(pair[0] is string))
      throw new InvalidOperationException("Invalid object field.");
     result.Add((string)pair[0],pair[1]);
    }
    return result;
   }
   if(items.Count>0 && items[0] is string && (string)items[0]=="__array") {
    items.RemoveAt(0); return items.ToArray();
   }
   return items;
  }
 }
}
