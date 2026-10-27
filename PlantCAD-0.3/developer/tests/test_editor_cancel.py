"""A failed editor must release its DCL window without saving a partial plant."""
import unittest
import test_rules as fixtures
from lisp_harness import Sym, parse


class EditorCancellation(fixtures.Rules):
    def setUp(self):
        super().setUp()
        self.events=[]
        self.actions={}
        self.rt.builtins.update({
            'pl:dialog':lambda name:self.events.append('open') or 17,
            'pl:fill-edit':lambda p:self.events.append('fill'),
            'action_tile':lambda key,expression:self.actions.__setitem__(key,expression),
            'unload_dialog':lambda identifier:self.events.append(('unload',identifier)),
            'term_dialog':lambda:self.events.append('terminate'),
            'vl-catch-all-error-p':lambda value:isinstance(value,Exception),
            'vl-catch-all-apply':self.caught,
            'pl:rethrow':self.rethrow,
        })
        self.rt.env[Sym('pl:*require-crown*')]=None

    def caught(self,function,args):
        try:return self.rt.call(str(function),*(args or []))
        except Exception as error:return error

    @staticmethod
    def rethrow(error):
        raise error

    def test_initialization_error_closes_and_unloads_window(self):
        def broken(_):
            raise ValueError('catalogue initialization failed')
        self.rt.builtins['pl:fill-edit']=broken
        with self.assertRaisesRegex(ValueError,'catalogue initialization failed'):
            self.rt.call('pl:edit-dialog',self.p)
        self.assertIn('terminate',self.events)
        self.assertEqual(self.events.count(('unload',17)),1)
        self.assertIsNone(self.rt.env.get(Sym('pl:*edit-result*')))

    def test_dialog_loop_error_closes_and_unloads_window(self):
        def broken():
            raise ValueError('console break')
        self.rt.builtins['start_dialog']=broken
        with self.assertRaisesRegex(ValueError,'console break'):
            self.rt.call('pl:edit-dialog',self.p)
        self.assertIn('terminate',self.events)
        self.assertEqual(self.events.count(('unload',17)),1)

    def test_cancel_callback_discards_pending_result(self):
        def cancel():
            self.rt.env[Sym('pl:*edit-result*')]=self.put('crown',9.)
            for expression in parse(self.actions['cancel']):self.rt.eval(expression)
            return 0
        self.rt.builtins.update({'start_dialog':cancel,'done_dialog':lambda code:self.events.append(('done',code))})
        self.assertIsNone(self.rt.call('pl:edit-dialog',self.p))
        self.assertIsNone(self.rt.env.get(Sym('pl:*edit-result*')))
        self.assertIn(('done',0),self.events)
        self.assertEqual(self.events.count(('unload',17)),1)
        self.assertEqual(self.get('crown'),3.)

    def test_title_close_and_termination_never_return_a_saved_plant(self):
        for status in [0,-1]:
            with self.subTest(status=status):
                def close():
                    self.rt.env[Sym('pl:*edit-result*')]=self.put('crown',9.)
                    return status
                self.rt.builtins['start_dialog']=close
                self.assertIsNone(self.rt.call('pl:edit-dialog',self.p))
                self.assertIsNone(self.rt.env.get(Sym('pl:*edit-result*')))

    def test_valid_save_returns_the_result_after_unloading(self):
        expected=self.put('crown',4.)
        def accept():
            self.rt.env[Sym('pl:*edit-result*')]=expected
            return 1
        self.rt.builtins['start_dialog']=accept
        self.assertEqual(self.rt.call('pl:edit-dialog',self.p),expected)
        self.assertEqual(self.events[-1],('unload',17))


for name in dir(fixtures.Rules):
    if name.startswith('test_') and name not in EditorCancellation.__dict__:
        setattr(EditorCancellation,name,None)
if __name__=='__main__':unittest.main()
