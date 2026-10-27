"""Settings must reach existing shrub annotations without changing measured areas."""
import unittest
import test_rules as fixtures
from lisp_harness import Pair,Sym,gbk

class AnnotationSettings(unittest.TestCase):
 setUp=fixtures.Rules.setUp
 put=fixtures.Rules.put
 def prepare(self,units=1.,scale=100.,paper=2.5):
  self.settings=[Pair(Sym('scale'),scale),Pair(Sym('paper_height'),paper)]
  self.data={'A':{'UNITS':1000.,'AREA_LABEL_RADIUS':.001}}
  self.writes=[]
  self.rt.builtins.update({'pl:units':lambda:units,'pl:db-get':lambda key,default:self.settings if key=='PLOT_OPTIONS' else default,
   'pl:data-get':lambda e,key:self.data.get(e,{}).get(key),
   'pl:data-put':lambda e,key,value:self.data.setdefault(e,{}).__setitem__(key,value) or value,
   'entget':lambda e:[Pair(0,'MULTILEADER' if e=='L' else 'REGION'),Pair(5,e),Pair(8,'LABEL')],
   'pl:area-label-text':lambda e:gbk('海桐\\P3.13 平方米'),
   'pl:output-area-text':lambda *args:gbk('海桐 3.13 平方米'),
   'equal':lambda a,b,fuzz=0:abs(a-b)<=fuzz if isinstance(a,(int,float)) and isinstance(b,(int,float)) else a==b})
 def test_existing_leader_uses_current_drawing_units(self):
  self.prepare(units=1.)
  self.assertEqual(self.rt.call('pl:area-annotation-height','A',[Pair(Sym('layout'),1)]),.25)
  self.assertEqual(self.data['A']['UNITS'],1000.)
 def test_scale_and_paper_height_each_control_existing_leader(self):
  for scale,paper,height in [(100,2.5,.25),(200,2.5,.5),(200,5.,1.)]:
   self.prepare(units=1.,scale=scale,paper=paper)
   self.assertEqual(self.rt.call('pl:area-annotation-height','A',[Pair(Sym('layout'),0)]),height)
 def test_unconfigured_drawing_can_fall_back_to_recorded_units(self):
  self.prepare(units=None)
  self.assertEqual(self.rt.call('pl:area-annotation-height','A',[Pair(Sym('layout'),1)]),250.)
 def test_interior_area_label_does_not_cap_font_at_the_old_fit_radius(self):
  self.prepare(units=1.,scale=200.,paper=5.)
  self.assertEqual(self.rt.call('pl:area-annotation-height','A',None),1.)
 def test_paper_space_ignores_model_plot_scale(self):
  self.prepare(units=1000.,scale=500.)
  self.rt.builtins['entget']=lambda e:[Pair(0,'REGION'),Pair(5,e),Pair(67,1)]
  self.assertEqual(self.rt.call('pl:area-annotation-height','A',[Pair(Sym('layout'),1)]),2.5)
 def test_new_interior_label_uses_same_height_as_existing_labels(self):
  self.prepare(units=1.,scale=200.,paper=5.)
  self.rt.builtins.update({'pl:layer-issue':lambda layer:None,'getvar':lambda key:'STANDARD',
   'pl:make':lambda data:self.writes.append(data) or 'L','pl:mark':lambda *args:None})
  self.rt.call('pl:create-area-label','A',[1.,2.,0.])
  self.assertEqual(next(p.cdr for p in self.writes[0] if isinstance(p,Pair) and p.car==40),1.)
 def test_new_leader_passes_current_setting_to_native_writer(self):
  self.prepare(units=1.,scale=200.)
  self.rt.builtins.update({'apply':lambda fn,args:self.rt.call(str(fn),*args),
   'pl:native-area-leader':lambda *args:self.writes.append(args) or ['L'],
   'pl:area-label-layer':lambda e:'LABEL','handent':lambda h:h})
  self.rt.call('pl:write-native-area-label','A',[0.,0.,0.],[-10.,2.,0.],[Pair(Sym('layout'),1)],None,None)
  self.assertEqual(self.writes[0][5],.5)
  self.assertEqual(self.data['L']['OUTPUT_HEIGHT'],.5)
  self.assertEqual(self.data['L']['OUTPUT_STYLE_VERSION'],3)
 def test_version_two_label_refreshes_even_when_requested_height_is_unchanged(self):
  self.prepare(units=1.)
  self.data['A']['UNITS']=1.
  options=[Pair(Sym('layout'),1)];text=gbk('海桐 3.13 平方米')
  self.data['L']={'OUTPUT_OPTIONS':options,'OUTPUT_HEIGHT':.25,'OUTPUT_STYLE_VERSION':2,'AREA_LABEL_TEXT':text,'ANCHOR':[0.,0.,0.]}
  self.rt.builtins.update({'pl:all-labels':lambda:['L'],'pl:role':lambda e:'AREA_LABEL','pl:writable':lambda e:True,
   'pl:source':lambda e:'A','pl:area-annotation-raw':lambda e:text,'pl:area-label-layer':lambda e:'LABEL',
   'pl:write-native-area-label':lambda *args:self.writes.append(args) or 'L'})
  self.rt.call('pl:sync-area-labels')
  self.assertEqual(len(self.writes),1)
 def test_font_unit_change_never_reinterprets_existing_area_measurement(self):
  self.prepare(units=1.);self.rt.env[Sym('pl:*native-ui*')]=True
  self.rt.builtins.update({'pl:role':lambda e:'AREA','pl:native-area-value':lambda h:[1000000.],
   'vl-catch-all-error-p':lambda result:False})
  self.assertEqual(self.rt.call('pl:uncached-area-value','A'),1.)
  self.assertEqual(self.data['A']['UNITS'],1000.)
 def settings_command(self,accept):
  database={'UNIT':0,'PLOT_OPTIONS':[Pair(Sym('scale'),100.),Pair(Sym('paper_height'),2.5)]};events=[]
  tiles={'unit':'1','plot_scale':'200','paper_height':'0.25','show_number':'0'}
  self.rt.env[Sym('pl:*dict*')]='TEST'
  self.rt.builtins.update({'pl:doc':lambda:'DOC','vla-startundomark':lambda d:events.append('begin'),
   'vla-endundomark':lambda d:events.append('end'),'pl:dialog':lambda name:1,
   'pl:db-get':lambda key,default:database.get(key,default),
   'vlax-ldata-put':lambda dictionary,key,value:database.__setitem__(key,value) or value,
   'pl:popup':lambda *args:None,'set_tile':lambda *args:None,'get_tile':lambda key:tiles[key],
   'getvar':lambda name:4,'action_tile':lambda *args:None,'unload_dialog':lambda d:None,'done_dialog':lambda value:value,
   'itoa':lambda value:str(value) if isinstance(value,int) else (_ for _ in ()).throw(TypeError('AutoLISP itoa requires an integer')),
   'start_dialog':lambda:(self.rt.call('pl:accept-settings') or 1) if accept else 0,
   'vl-catch-all-apply':lambda fn,args:self.rt.call(str(fn),*(args or [])),
   'vl-catch-all-error-p':lambda result:False,
   'pl:refresh-all-symbols':lambda:events.append('extra symbol refresh'),
   'pl:sync-drawing':lambda:events.append(('all annotations',database['UNIT'],self.rt.call('pl:plot-text-height','A'))),
   'pl:data-get':lambda e,key:1000. if key=='UNITS' else None,
   'entget':lambda e:[Pair(0,'REGION'),Pair(5,e)]})
  self.rt.call('pl:run',Sym('pl:settings-work'));return database,events
 def test_settings_command_synchronizes_all_annotations_once_after_accept(self):
  database,events=self.settings_command(True)
  self.assertEqual(events,['begin',('all annotations',1,.5),'end'])
  self.assertEqual(self.rt.call('pl:get',Sym('paper_height'),database['PLOT_OPTIONS']),2.5)
 def test_cancel_settings_does_not_change_units_or_refresh_annotations(self):
  database,events=self.settings_command(False)
  self.assertEqual(database['UNIT'],0);self.assertEqual(events,['begin','end'])
 def test_unit_or_calibration_change_invalidates_existing_annotation_sizes(self):
  self.rt.builtins['vlax-ldata-put']=lambda *args:args[-1]
  for key,value in [('UNIT',1),('UNITS_PER_M',100.)]:
   self.rt.env[Sym('pl:*drawing-changed*')]=None
   self.rt.call('pl:db-put',key,value)
   self.assertTrue(self.rt.call('pl:run-needs-sync',Sym('pl:calibrate-work')))

if __name__=='__main__':unittest.main()
