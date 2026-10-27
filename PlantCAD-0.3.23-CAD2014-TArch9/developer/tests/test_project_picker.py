import unittest
import test_rules as fixtures
from lisp_harness import Sym

class ProjectPicker(unittest.TestCase):
    setUp=fixtures.Rules.setUp
    put=fixtures.Rules.put
    def prepare(self,result):
        self.rows=[self.p,self.rt.call('pl:put',Sym('id'),'OTHER',self.p)]
        self.rt.env[Sym('pl:*native-ui*')]=True
        self.rt.builtins['pl:defs']=lambda:self.rows
        self.rt.builtins['mapcar']=lambda function,items:[self.rt.call(function,item) for item in (items or [])]
        self.rt.builtins['pl:native-project-dialog']=lambda *args:result

    def test_native_selection_uses_original_project_index(self):
        self.prepare([3,1])
        self.assertEqual(self.rt.call('pl:project-dialog',0),3)
        self.assertEqual(self.rt.env[Sym('pl:*index*')],1)
        self.assertEqual(self.rt.env[Sym('pl:*project-visible*')],self.rows)

    def test_empty_project_can_request_manual_add(self):
        self.prepare([5,-1]);self.rows=[]
        self.assertEqual(self.rt.call('pl:project-dialog',0),5)
        self.assertEqual(self.rt.env[Sym('pl:*index*')],0)

    def test_close_does_not_save_or_change_current_plant(self):
        self.prepare([0,1]);writes=[]
        self.rt.builtins['pl:db-put']=lambda *args:writes.append(args)
        self.rt.builtins['pl:save-project-spec']=lambda *args:writes.append(args)
        self.rt.call('pl:design-library');self.assertEqual(writes,[])

    def test_edit_targets_selected_specification_and_returns_to_list(self):
        self.prepare(None);answers=iter([[3,1],[0,1]]);saved=[]
        self.rt.builtins['pl:native-project-dialog']=lambda *args:next(answers)
        self.rt.builtins['pl:edit-project-dialog']=lambda plant:plant
        self.rt.builtins['pl:save-project-spec']=lambda plant:saved.append(plant)
        self.rt.call('pl:design-library');self.assertEqual(saved,[self.rows[1]])
