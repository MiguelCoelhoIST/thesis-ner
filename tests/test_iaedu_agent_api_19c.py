"""No network. Synthetic credentials/metadata and fully injected HTTP responses."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import test_stj_pilot_19c as fixtures
from src.annotation import iaedu_agent_api_19c as api
from src.annotation import prepare_second_llm_pilot_19c as package

ENV={'IAEDU_ENDPOINT':'https://api.iaedu.pt/agent-chat//api/v1/agent/invented-agent/stream',
     'IAEDU_CHANNEL_ID':'invented-channel','IAEDU_API_KEY':'synthetic-env-credential'}


class Response:
    def __init__(self,body,status=200,fail=False):
        self.body=body;self.status_code=status;self.headers={'Content-Type':'application/x-ndjson','X-Request-ID':'invented-request'}
        self.fail=fail
    def iter_content(self,chunk_size):
        # Arbitrary chunk boundaries, including within UTF-8/JSON lines.
        for n in range(0,len(self.body),3):yield self.body[n:n+3]
        if self.fail:raise RuntimeError('unsafe_exception_'+ENV['IAEDU_API_KEY'])
    def close(self):pass


class TransportTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.enterContext(patch.dict(os.environ,ENV,clear=True))
        self.enterContext(patch.object(api,'private_new_output',side_effect=lambda p:p))
    def invoke(self,response,name='capture'):
        session=Mock();session.post.return_value=response
        report=api.stream_one('invented message',self.root/name,network_authorized=True,session=session)
        return report,session
    def test_unique_threads_and_multipart_auth_only_in_header(self):
        report,session=self.invoke(Response(b'{"type":"token","content":"inventado"}\n'))
        args,kwargs=session.post.call_args
        self.assertEqual(args,(ENV['IAEDU_ENDPOINT'],))
        self.assertEqual(kwargs['headers'],{'x-api-key':ENV['IAEDU_API_KEY']})
        self.assertNotIn('Content-Type',kwargs['headers'])
        self.assertEqual(set(kwargs['files']),{'channel_id','thread_id','user_info','message'})
        self.assertEqual(kwargs['files']['user_info'],(None,'{}'))
        self.assertFalse(kwargs['allow_redirects']);self.assertTrue(kwargs['stream'])
        self.assertEqual(len({api.form_fields('invented','invented')['thread_id'] for _ in range(30)}),30)
        self.assertEqual(report['status'],'captured')
        for p in (self.root/'capture').iterdir():
            self.assertNotIn(ENV['IAEDU_API_KEY'].encode(),p.read_bytes())

    def test_default_denies_network_before_using_client(self):
        session=Mock()
        with self.assertRaisesRegex(ValueError,'not_authorized'):
            api.stream_one('invented',self.root/'denied',session=session)
        session.post.assert_not_called();self.assertFalse((self.root/'denied').exists())

    def test_raw_response_events_and_metadata_preserved_without_guessing_model(self):
        events=[{'type':'metadata','model':'invented-returned-model','usage':{'total_tokens':42}},
                {'type':'token','content':'Olá '},{'type':'token','content':'mundo'}]
        raw=('\r\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\r\n').encode('utf-8')
        report,_=self.invoke(Response(raw))
        folder=self.root/'capture'
        self.assertEqual((folder/'response_body.bin').read_bytes(),raw)
        parsed=json.loads((folder/'stream_frames_PRIVATE.json').read_text(encoding='utf-8'))
        self.assertEqual(parsed['events'],events)
        self.assertEqual((folder/'assistant_output.txt').read_bytes(),'Olá mundo'.encode('utf-8'))
        self.assertEqual(report['response_headers']['X-Request-ID'],'invented-request')
        self.assertEqual(report['agent_label_reported_by_user'],'OpenAI GPT-5.5')
        self.assertFalse(report['human_validated']);self.assertTrue(report['requires_review'])

    def test_partial_bad_framing_and_http_failure_are_kept_not_silently_accepted(self):
        for name,response in (('partial',Response(b'{"type":"token","content":"x"}\n',fail=True)),
                              ('sse',Response(b'data: {"type":"token","content":"x"}\n')),
                              ('bad_utf8',Response(b'\xff\n')),
                              ('api_error',Response(b'{"type":"token","content":"x"}\n{"type":"error","error":"invented"}\n')),
                              ('http',Response(b'{"error":"invented failure"}\n',status=401))):
            report,_=self.invoke(response,name)
            self.assertEqual(report['status'],'captured_with_errors')
            self.assertEqual((self.root/name/'response_body.bin').read_bytes(),response.body)
            self.assertNotIn(ENV['IAEDU_API_KEY'],json.dumps(report))

    def test_credential_echo_is_never_persisted_even_when_json_escaped(self):
        key=ENV['IAEDU_API_KEY']
        escaped=''.join('\\u%04x'%ord(c) for c in key)
        for n,raw in enumerate((key.encode(),('{"type":"token","content":"'+escaped+'"}\n').encode())):
            report,_=self.invoke(Response(raw),'echo'+str(n))
            self.assertEqual(report['error_code'],'credential_echo_detected')
            self.assertEqual({p.name for p in (self.root/('echo'+str(n))).iterdir()},{'run.json'})
            self.assertNotIn(key,json.dumps(report))

    def test_config_rejects_unofficial_hosts_or_embedded_credentials(self):
        for endpoint in ('https://api.iaedu.pt.evil/agent-chat/api/v1/agent/invented/stream',
                         'http://api.iaedu.pt/agent-chat/api/v1/agent/invented/stream',
                         'https://synthetic:credential'+'@'+'api.iaedu.pt/agent-chat/api/v1/agent/invented/stream'):
            with patch.dict(os.environ,{'IAEDU_ENDPOINT':endpoint}),self.assertRaises(ValueError):api.configuration()


class PlanTests(unittest.TestCase):
    def test_plan_has_exact_same_30_messages_and_never_reads_key_or_posts(self):
        fixture=fixtures.PilotBundleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        source,_=fixture.write_saved_pilot();folder=fixture.root/'package'
        with patch.object(package,'private_new_output',side_effect=lambda p:p):
            manifest=package.prepare_package(fixture.input,fixture.selection,source/'run.json',folder)
        original_get=os.environ.get
        def guarded_get(name,*args):
            if name=='IAEDU_API_KEY':raise AssertionError('Offline must not read key')
            return original_get(name,*args)
        output=fixture.root/'plan'
        with (patch.dict(os.environ,ENV),patch.object(os.environ,'get',side_effect=guarded_get),
              patch.object(api,'private_new_output',side_effect=lambda p:p),
              patch('requests.sessions.Session.request',side_effect=AssertionError('No network'))):
            report=api.prepare_plan(folder,output)
        self.assertEqual(len(report['requests']),30);self.assertEqual(report['LLM_calls'],0)
        self.assertFalse(report['external_transmission_authorized'])
        for item,request in zip(manifest['mapping'],report['requests']):
            self.assertEqual(request['fields']['message'],(folder/item['manual_text_file']).read_bytes().decode('utf-8'))
            self.assertEqual(request['id'],item['id'])
            self.assertNotIn('suggested_label',request['fields'])

    def test_cli_has_no_execution_switch_and_does_not_echo_unknown_secret_args(self):
        stdout=io.StringIO();stderr=io.StringIO()
        with (patch('sys.argv',['api','--send',ENV['IAEDU_API_KEY']]),redirect_stdout(stdout),redirect_stderr(stderr),
              self.assertRaises(SystemExit)):
            api.main()
        self.assertNotIn(ENV['IAEDU_API_KEY'],stdout.getvalue()+stderr.getvalue())


class SyntheticConnectionTests(unittest.TestCase):
    setUp=TransportTests.setUp
    def test_single_invented_request_never_opens_pilot_and_shows_returned_metadata(self):
        events=[{'type':'metadata','metadata':{'model':'invented-backend','provider':'invented-provider'}},
                {'type':'token','content':'invented assistant answer'}]
        raw=('\n'.join(json.dumps(e) for e in events)+'\n').encode()
        session=Mock();session.post.return_value=Response(raw)
        with (patch.object(api,'validated_package',side_effect=AssertionError('No real package')),
              patch.object(api.core,'load_pilot',side_effect=AssertionError('No pilot'))):
            report=api.synthetic_connection_test(self.root/'synthetic',session=session)
        self.assertEqual(session.post.call_count,1)
        sent=session.post.call_args.kwargs['files']['message'][1]
        self.assertIn('[ENTITY] AA [/ENTITY]',sent);self.assertIn('pessoa fictícia',sent)
        self.assertTrue(report['assistant_message_extracted']);self.assertEqual(report['http_status'],200)
        self.assertFalse(report['real_pilot_read']);self.assertFalse(report['real_contexts_transmitted'])
        self.assertFalse(report['real_dataset_external_transmission_authorized'])
        self.assertEqual([f['value'] for f in report['model_metadata_returned']],['invented-backend','invented-provider'])
        self.assertEqual((self.root/'synthetic/response_body.bin').read_bytes(),raw)

    def test_model_fields_from_headers_and_metadata_not_self_claimed_in_text(self):
        events=[{'type':'token','content':'{"model":"self-claimed"}'},
                {'type':'token','content':{'model':'also-not-metadata'}},
                {'type':'metadata','response_metadata':{'model_version':'invented-version','modelName':'invented-camel-case'}}]
        found=api.returned_model_metadata(events,{'X-Model':'invented-header-model'})
        self.assertEqual([f['value'] for f in found],['invented-version','invented-camel-case','invented-header-model'])

    def test_no_model_metadata_never_falls_back_to_ui_label(self):
        for n,response in enumerate((Response(b'{"type":"token","content":"invented answer"}\n'),
                                     Response(b'{"error":"invented HTTP error"}\n',status=401))):
            session=Mock();session.post.return_value=response
            report=api.synthetic_connection_test(self.root/('probe'+str(n)),session=session)
            self.assertEqual(report['model_metadata_returned'],[])
            self.assertEqual(report['model_metadata_status'],'not_found_in_parsed_metadata')
            self.assertEqual(report['http_status'],response.status_code)
            self.assertEqual(report['assistant_message_extracted'],n==0)

    def test_cli_probe_sends_once_and_prints_summary_without_secret_or_assistant_text(self):
        session=Mock();session.post.return_value=Response(b'{"type":"metadata","model":"invented-model"}\n'
                                                        b'{"type":"token","content":"private_test_answer"}\n')
        stdout=io.StringIO();argv=['api','--synthetic-connection-test','--output-dir',str(self.root/'cli')]
        with (patch('sys.argv',argv),patch('requests.Session',return_value=session),redirect_stdout(stdout),
              patch.object(api,'validated_package',side_effect=AssertionError('No package'))):
            mask=os.umask(0o077)
            try:api.main()
            finally:os.umask(mask)
        report=json.loads(stdout.getvalue())
        self.assertTrue(report['assistant_message_extracted']);self.assertEqual(session.post.call_count,1)
        self.assertNotIn(ENV['IAEDU_API_KEY'],stdout.getvalue())
        self.assertNotIn('private_test_answer',stdout.getvalue())

    def test_cli_rejects_package_or_message_override_in_synthetic_mode(self):
        for extra in (['--package-dir','never-open'],['--message','never-send-this']):
            argv=['api','--synthetic-connection-test','--output-dir',str(self.root/'blocked')]+extra
            with (patch('sys.argv',argv),patch.object(api,'stream_one') as send,
                  redirect_stderr(io.StringIO()),self.assertRaises(SystemExit)):
                api.main()
            send.assert_not_called()


if __name__=='__main__':unittest.main()
