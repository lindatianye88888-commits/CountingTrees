// Test doubles exercise the exact production SetAreaLanding method. This is
// not an AutoCAD-host rendering test; extents scale linearly with font height.
using System;
public struct Point3d { public double X,Y,Z;public Point3d(double x,double y,double z){X=x;Y=y;Z=z;} }
public struct Vector3d { public double X;public Vector3d(double x){X=x;} }
public sealed class MText : IDisposable {
 public double TextHeight,WidthAtUnit;
 public double ActualWidth {get{return TextHeight*WidthAtUnit;}}
 public MText Copy(){return new MText{TextHeight=TextHeight,WidthAtUnit=WidthAtUnit};}
 public void Dispose(){}
}
public sealed class MLeader {
 MText text;
 public MText MText {get{return text.Copy();}set{text=value.Copy();}}
 public double TextHeight,ArrowSize,DoglegLength;public Point3d Elbow;public Vector3d Direction;
 public void SetDogleg(int index,Vector3d value){Direction=value;}
 public void SetDoglegLength(int index,double value){DoglegLength=value;}
 public void SetLastVertex(int line,Point3d point){Elbow=point;}
}
public static class AreaLandingSizingTests {
 /* PRODUCTION_METHOD */
 public static string Run(){
  int checks=0;
  foreach(double height in new[]{.1,1.0,2.0})foreach(double span in new[]{4.0,50.0})foreach(int sign in new[]{-1,1}){
   var leader=new MLeader{TextHeight=height,MText=new MText{TextHeight=height,WidthAtUnit=20.0}};
   var elbow=new Point3d(10,15,0);
   SetAreaLanding(leader,0,0,elbow,new Vector3d(sign),span,height);
   using(var text=leader.MText){
    if(Math.Abs(text.TextHeight-height)>1e-9||Math.Abs(leader.TextHeight-height)>1e-9)throw new Exception("Short landing silently shrank the configured font");
    if(Math.Abs(leader.ArrowSize-height*.3)>1e-9)throw new Exception("Arrow no longer follows font size");
    if(Math.Abs(leader.DoglegLength+text.ActualWidth-Math.Max(span,text.ActualWidth))>1e-9)throw new Exception("Landing does not fit text at the configured height");
    if(leader.Direction.X!=sign||leader.Elbow.X!=elbow.X||leader.Elbow.Y!=elbow.Y)throw new Exception("Font update changed elbow or leader direction");
   }
   checks++;
  }
  return "PASS "+checks;
 }
}
