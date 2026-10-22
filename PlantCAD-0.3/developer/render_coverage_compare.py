"""Render raw CAD audit geometry; colors show bounded cells, not plant classes."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.font_manager import FontProperties
p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);a=p.parse_args()
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
fig,axs=plt.subplots(1,2,figsize=(16,6));fig.patch.set_facecolor('white')
for ax,path,label in zip(axs,[a.before,a.after],['原版本','修复预览']):
 data=json.loads(path.read_text(encoding='utf-8-sig'))['PL_灌木_原始线'];run=data['runs'][1]
 for i,face in sorted(enumerate(run['faces']),key=lambda item:-item[1]['area']):
  ax.add_patch(Polygon(face['outline'],facecolor=plt.cm.tab20(i%20),alpha=.5))
  for hole in face['holes']:ax.add_patch(Polygon(hole,facecolor='white'))
 for c in data['sources']:
  pts=c['points'];ax.plot([p[0] for p in pts],[p[1] for p in pts],color='#333333',lw=.45)
 for pts in run['repairs']:ax.plot([p[0] for p in pts],[p[1] for p in pts],color='#dc2626',lw=.8)
 ax.set_aspect('equal');ax.axis('off');ax.set_title(label+'：'+str(len(run['faces']))+'个闭合区域',fontproperties=font,fontsize=15)
fig.text(.5,.045,'彩色为识别到的闭合图形，含停车格等非种植区；红线为推定补线。原始图纸未改。',ha='center',fontproperties=font,fontsize=10,color='#444444')
fig.tight_layout(rect=[0,.08,1,1]);target=Path(__file__).resolve().parents[1]/'docs/images/案例2面积漏算修复对照.png';fig.savefig(target,dpi=140);print(target)
