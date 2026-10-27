import unittest
import test_rules as fixtures
from lisp_harness import Sym,Pair,gbk,chinese

class Abort(Exception):pass
class SelectionRules(fixtures.Rules):
 def setUp(self):
  super().setUp();self.calls=[];self.alerts=[]
  self.rt.builtins.update({'sslength':len,'ssname':lambda ss,i:ss[i],
   'sssetfirst':lambda *args:self.calls.append('clear'),
   'entget':lambda e:[Pair(5,e),Pair(8,'shrubs')],
   'alert':lambda s:self.alerts.append(chinese(s)),
   'vl-catch-all-error-message':lambda e:str(e),'vl-catch-all-error-p':lambda e:isinstance(e,Exception),
   'exit':lambda:(_ for _ in ()).throw(Abort('quit / exit abort'))})
  self.rt.env.update({Sym('pl:*failure*'):None,Sym('pl:*stage*'):None})
 def test_preselected_boundaries_are_consumed_once_without_second_prompt(self):
  def select(*args):
   self.calls.append(args)
   if len(args)==1:self.fail('Unexpected second selection prompt')
   return ['A','B']
  self.rt.builtins['ssget']=select
  self.assertEqual(self.rt.call('pl:area-selection'),['A','B'])
  self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[-1],'clear')
 def test_interactive_selection_is_requested_once_then_passes_handles(self):
  self.rt.builtins['ssget']=lambda *args:self.calls.append(args) or (['A','B'] if len(args)==1 else None)
  self.assertEqual(self.rt.call('pl:area-selection'),['A','B'])
  self.assertEqual([len(c) for c in self.calls if isinstance(c,tuple)],[2,1])
 def test_empty_selection_does_not_call_geometry(self):
  self.rt.builtins.update({'ssget':lambda *a:None,'pl:native-area-begin':lambda *a:self.fail('Geometry ran without selection')})
  self.rt.call('pl:geometry-session-work');self.assertEqual(self.calls,[])
 def test_ambiguous_layers_request_one_sample_then_use_original_handles(self):
  self.rt.builtins.update({'pl:native-area-begin':lambda handles,layer:self.calls.append((handles,layer)) or ([2] if layer else ['AREA_PICK_LAYER']),
   'entsel':lambda *a:['B',[0,0,0]]})
  self.assertEqual(self.rt.call('pl:area-prepare',['A','B']),2)
  self.assertEqual(self.calls,[(['A','B'],''),(['A','B'],'shrubs')])
 def test_cancel_layer_sample_does_not_compute_or_fail(self):
  self.rt.builtins.update({'pl:native-area-begin':lambda *a:['AREA_PICK_LAYER'],'entsel':lambda *a:None})
  self.assertIsNone(self.rt.call('pl:area-prepare',['A']));self.assertIsNone(self.rt.env[Sym('pl:*failure*')])
 def test_nested_cleanup_keeps_root_error_instead_of_exit_abort(self):
  reason=gbk('边界不是同一水平面')
  self.rt.env[Sym('pl:*failure*')]=reason;self.rt.env[Sym('pl:*stage*')]=gbk('计算边线围合面积')
  with self.assertRaises(Abort):self.rt.call('pl:rethrow',Abort('quit / exit abort'))
  self.rt.call('pl:report-error',Abort('quit / exit abort'))
  self.assertEqual(len(self.alerts),1);self.assertIn('边界不是同一水平面',self.alerts[0]);self.assertNotIn('quit / exit abort',self.alerts[0])
 def test_escape_is_normal_cancellation_without_alert(self):
  for message in ['Function cancelled','quit / exit abort',gbk('函数已取消')]:
   with self.assertRaises(Abort):self.rt.call('pl:rethrow',Abort(message))
   self.rt.call('pl:report-error',Abort('quit / exit abort'))
   self.assertIsNone(self.rt.env[Sym('pl:*failure*')])
  self.assertEqual(self.alerts,[])
 def test_unexpected_nested_exception_keeps_original_message(self):
  with self.assertRaises(Abort):self.rt.call('pl:rethrow',ValueError('eInvalidInput'))
  self.rt.call('pl:report-error',Abort('quit / exit abort'))
  self.assertIn('eInvalidInput',self.alerts[0])
 def test_explicit_fail_is_reported_even_if_reason_mentions_cancel(self):
  self.rt.env[Sym('pl:*failure*')]='eUserCancelledGeometry'
  self.rt.call('pl:report-error',Abort('quit / exit abort'))
  self.assertEqual(len(self.alerts),1)

for name in dir(fixtures.Rules):
 if name.startswith('test_') and name not in SelectionRules.__dict__:setattr(SelectionRules,name,None)
if __name__=='__main__':unittest.main()
