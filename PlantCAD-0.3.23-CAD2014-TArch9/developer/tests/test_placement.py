import unittest
import test_rules as fixtures
from lisp_harness import Sym,chinese

class PlacementRegression(fixtures.Rules):
    def native_setup(self,points):
        self.rt.env[Sym('pl:*native-ui*')]=True
        self.rt.builtins.update({
            'boundp':lambda symbol:True,
            'getvar':lambda key:{'TILEMODE':1,'CVPORT':2}[key],
            'pl:db-get':lambda key,default:default,
            'pl:preview-point':lambda *args:points.pop(0),
            'pl:fail':lambda text:(_ for _ in ()).throw(ValueError(chinese(text))),
        })

    def insertion_setup(self,returned):
        inserted=[];converted=[]
        self.rt.env[Sym('pl:*native-ui*')]=True
        self.rt.builtins.update({
            'boundp':lambda _:True,'pl:doc':lambda:'DOC',
            'pl:native-insert':lambda *args:inserted.append(args) or returned,
            'handent':lambda handle:'ENTITY' if handle=='9F' else None,
            'vlax-ename->vla-object':lambda e:converted.append(e) or 'BLOCK',
            'pl:fail':lambda text:(_ for _ in ()).throw(ValueError(chinese(text))),
        })
        return inserted,converted

    def test_image5_nested_point_is_unwrapped_without_changing_coordinates(self):
        point=[218118.0,231230.0,0.0]
        self.native_setup([[point]])
        self.assertEqual(self.rt.call('pl:pick-placement',self.p,1000.),point)

    def test_flat_three_dimensional_and_two_dimensional_points(self):
        for raw,expected in [([12.,34.,5.],[12.,34.,5.]),([12.,34.],[12.,34.,0.])]:
            self.assertEqual(self.rt.call('pl:point-value',raw),expected)

    def test_cancel_does_not_turn_into_origin(self):
        for raw in [None,[None]]:
            self.native_setup([raw])
            self.assertIsNone(self.rt.call('pl:pick-placement',self.p,1000.))

    def test_invalid_preview_fails_before_insertion(self):
        for raw in [[[1.,'bad',0.]],[[[1.,2.,0.]]],[1.,2.,3.,4.],'bad']:
            self.native_setup([raw])
            with self.assertRaisesRegex(ValueError,'坐标格式'):
                self.rt.call('pl:pick-placement',self.p,1000.)

    def test_direct_and_wrapped_native_handles_find_the_inserted_entity(self):
        for returned in ['9F',['9F']]:
            inserted,converted=self.insertion_setup(returned)
            self.assertEqual(self.rt.call('pl:insert-symbol',self.p,[12.,34.,0.],3000.),'BLOCK')
            self.assertEqual(converted,['ENTITY'])
            self.assertEqual(inserted[0][1:3],([12.,34.,0.],3000.))

    def test_invalid_or_multiple_handles_are_not_treated_as_an_entity(self):
        for returned in [None,[],['9F','AA'],123,'']:
            inserted,converted=self.insertion_setup(returned)
            with self.assertRaisesRegex(ValueError,'句柄'):
                self.rt.call('pl:insert-symbol',self.p,[12.,34.,0.],3000.)
            self.assertEqual(converted,[])

    def test_unknown_handle_is_reported(self):
        self.insertion_setup(['DELETED'])
        with self.assertRaisesRegex(ValueError,'未找到图块'):
            self.rt.call('pl:insert-symbol',self.p,[12.,34.,0.],3000.)

    def test_invalid_center_does_not_call_native_insert(self):
        inserted,converted=self.insertion_setup(['9F'])
        with self.assertRaisesRegex(ValueError,'中心坐标无效'):
            self.rt.call('pl:insert-symbol',self.p,['bad',34.,0.],3000.)
        self.assertEqual(inserted,[])

    def test_complete_placement_transforms_ucs_once_then_marks_real_entity(self):
        raw=[218118.,231230.,0.]
        self.native_setup([[raw],None])
        inserted,converted=self.insertion_setup(['9F'])
        transforms=[];writes=[];marks=[]
        self.rt.builtins.update({
            'pl:init-layers':lambda:None,'pl:current':lambda:self.p,
            'pl:require-units':lambda:True,'pl:built-blocks':lambda:None,
            'pl:units':lambda:1000.,'pl:layer-issue':lambda _:None,
            'trans':lambda p,a,b:transforms.append((p,a,b)) or [1000000.-p[1],2000000.+p[0],p[2]],
            'vla-put-layer':lambda *args:None,'vla-put-color':lambda *args:None,
            'vlax-vla-object->ename':lambda obj:'ENTITY',
            'pl:mark':lambda e,role,h:marks.append((e,role)),
            'pl:data-put':lambda e,key,value:writes.append((key,value)),
            'pl:refresh-symbol':lambda e:True,
        })
        self.rt.call('pl:insert-work')
        self.assertEqual(transforms,[(raw,1,0)])
        self.assertEqual(len(inserted),1)
        self.assertEqual(inserted[0][1],[768770.,2218118.,0.])
        self.assertEqual(marks,[('ENTITY','TREE')])
        self.assertEqual(writes,[('PLANT',self.p),('UNITS',1000.)])

for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in PlacementRegression.__dict__:
        setattr(PlacementRegression,name,None)

if __name__=='__main__':unittest.main()
