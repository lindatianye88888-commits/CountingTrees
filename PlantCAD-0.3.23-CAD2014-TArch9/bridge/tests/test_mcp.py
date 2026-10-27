from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
SERVER=Path(__file__).resolve().parents[1]/'mcp_server.py'
spec=importlib.util.spec_from_file_location('plantcad_server',SERVER)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.bridge=m.QueueBridge(self.root,timeout=.3)
        self.server=m.MCPServer(self.bridge)
    def tearDown(self): self.tmp.cleanup()
    def request(self,method,params=None):
        return self.server.handle({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})
    def connect(self,**changes):
        value={'connected':True,'session_id':'test-session','heartbeat':time.time(),'active_document':True}
        value.update(changes);m.atomic_json(self.root/'session.json',value)
    def fake_cad(self,wrong_session=False):
        def work():
            until=time.monotonic()+2
            while time.monotonic()<until:
                paths=list((self.root/'requests').glob('*.json'))
                if paths:
                    request=json.loads(paths[0].read_text(encoding='utf-8'))
                    m.atomic_json(self.root/'responses'/paths[0].name,
                        {'id':request['id'],'session_id':'wrong' if wrong_session else request['session_id'],
                         'result':{'ok':True,'received':request['action'],'args':request['arguments']}})
                    return
                time.sleep(.01)
        worker=threading.Thread(target=work);worker.start();return worker
    def test_initialize_supported_version_and_six_tools(self):
        self.assertEqual(self.request('initialize',{'protocolVersion':'2024-11-05'})['result']['protocolVersion'],'2024-11-05')
        self.assertEqual(len(self.request('tools/list')['result']['tools']),6)
        self.assertIsNone(self.server.handle({'method':'notifications/initialized'}))
    def test_offline_read_status_does_not_create_queue(self):
        result=self.request('tools/call',{'name':'plantcad_status'})['result']['structuredContent']
        self.assertFalse(result['connected']);self.assertFalse((self.root/'requests').exists())
    def test_unknown_method_and_unknown_tool(self):
        self.assertEqual(self.request('erase')['error']['code'],-32601)
        self.assertIn('error',self.request('tools/call',{'name':'plantcad_run_script'}))
    def test_reject_invalid_changes_and_nonfinite_numbers(self):
        for changes in [{'crown':0},{'dbh':-1},{'factor':float('nan')},{'dx_m':float('inf')},
                        {'height':True},{'style':'random'},{'script':'erase'},
                        {'new_species_category':2.5},{'name':'名字\n换行'},{'name':'😀'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError): m.validate(m.CHANGE_SCHEMA,changes)
    def test_literal_text_not_interpreted_as_code(self):
        name='品种{A}\\P$(text)'
        m.validate(m.CHANGE_SCHEMA,{'name':name})
        self.connect();worker=self.fake_cad()
        result=self.bridge.call('preview_adjust',{'target':{'scope':'model'},'changes':{'name':name}})
        worker.join()
        self.assertEqual(result['args']['changes']['name'],name)
        self.assertRegex(result['args']['plan_id'],'^[0-9a-f]{32}$')
    def test_request_and_response_bound_to_session(self):
        self.connect();worker=self.fake_cad()
        self.assertTrue(self.bridge.call('get_plants',{})['ok']);worker.join()
    def test_reject_other_drawing_response(self):
        self.connect();worker=self.fake_cad(True)
        with self.assertRaisesRegex(RuntimeError,'会话'): self.bridge.call('get_plants',{})
        worker.join()
    def test_expired_pending_request_removed_after_timeout(self):
        self.connect()
        with self.assertRaises(TimeoutError): self.bridge.call('get_plants',{})
        self.assertEqual(list((self.root/'requests').glob('*.json')),[])
    def test_stale_or_inactive_session_never_queues(self):
        for changes in [{'heartbeat':time.time()-60},{'active_document':False}]:
            self.connect(**changes)
            with self.assertRaises(RuntimeError): self.bridge.call('get_plants',{})
        self.assertFalse((self.root/'requests').exists())
    def test_stdio_handshake_and_status_round_trip(self):
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'plantcad_status','arguments':{}}}]
        process=subprocess.run([sys.executable,'-B',str(SERVER),'--queue-root',str(self.root)],
                               input='\n'.join(json.dumps(r) for r in requests)+'\n',
                               encoding='utf-8',capture_output=True,timeout=5,check=True)
        replies=[json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([r['id'] for r in replies],[1,2,3])
        self.assertEqual(replies[2]['result']['isError'],False)
        self.assertEqual(process.stderr,'')
if __name__=='__main__': unittest.main()
