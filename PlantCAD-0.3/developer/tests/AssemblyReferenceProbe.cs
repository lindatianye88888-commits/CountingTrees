// Metadata only: reference assemblies are never executed or loaded as a CAD host.
using System;using System.Reflection;
public static class AssemblyReferenceProbe {
 public static void Main(string[] args){
  var assembly=Assembly.ReflectionOnlyLoadFrom(args[0]);
  foreach(var reference in assembly.GetReferencedAssemblies()){
   string name=reference.Name.ToLowerInvariant();
   if(name=="acmgd"||name=="acdbmgd"||name=="accoremgd")Console.WriteLine(name+"|"+reference.Version);
  }
 }
}
