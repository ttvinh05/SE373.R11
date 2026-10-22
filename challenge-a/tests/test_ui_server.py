import json
import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from ui_server import Lab, make_server
from agent_loop import run_agent


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []

        def runner(path):
            self.calls.append(json.loads(path.read_text()))
            Path(str(path.with_suffix('')) + '.codex-answer.md').write_text('Câu trả lời test double')
            return {'thread_id': 'test-thread', 'usage': {}, 'tool_items': 0}

        self.lab = Lab(self.root, runner=runner)

    def test_new_session_loads_only_current_rule_and_keeps_same_question(self):
        self.lab.save_memory('auth', 'Dùng JWT.')
        old = self.lab.prepare_request('Triển khai đăng nhập thế nào?', False)
        self.lab.save_memory('auth', 'Dùng session cookie.')
        new = self.lab.prepare_request('Triển khai đăng nhập thế nào?', False)
        self.assertNotEqual(old['request']['session_id'], new['request']['session_id'])
        self.assertIn('JWT', old['request']['injected_memory'])
        self.assertNotIn('JWT', new['request']['injected_memory'])
        self.assertIn('session cookie', new['request']['injected_memory'])
        self.assertEqual(old['request']['messages'][1], new['request']['messages'][1])
        self.assertEqual(new['request']['history_messages'], 0)
        entries = self.lab.state()['entries']
        self.assertEqual([e['status'] for e in entries], ['superseded', 'active'])

    def test_context_is_frozen_before_model_call_and_cannot_be_sent_twice(self):
        self.lab.save_memory('auth', 'JWT')
        prepared = self.lab.prepare_request('Đăng nhập?', False)
        self.lab.save_memory('auth', 'Cookie')
        result = self.lab.ask(prepared['request_id'])
        self.assertIn('JWT', self.calls[0]['injected_memory'])
        self.assertEqual(result['answer'], 'Câu trả lời test double')
        with self.assertRaisesRegex(ValueError, 'đã được gửi'):
            self.lab.ask(prepared['request_id'])
        self.assertEqual(len(self.calls), 1)

    def test_control_omits_memory_and_new_demo_preserves_previous_store(self):
        self.lab.save_memory('auth', 'JWT')
        previous = Path(self.lab.state()['store'])
        request = self.lab.prepare_request('Đăng nhập?', True)['request']
        self.assertEqual(request['injected_memory'], '')
        self.lab.new_demo()
        self.assertEqual(self.lab.state()['entries'], [])
        self.assertTrue(previous.exists())
        restored = Lab(self.root)
        self.assertEqual(restored.state()['demo_id'], self.lab.state()['demo_id'])

    def test_invalid_input_never_reaches_model(self):
        for key, value in [('auth', ' '), ('../file', 'JWT')]:
            with self.assertRaises(ValueError):
                self.lab.save_memory(key, value)
        with self.assertRaises(ValueError):
            self.lab.prepare_request('x' * 4001, False)
        with self.assertRaises(ValueError):
            self.lab.ask('../memory.json')
        self.assertEqual(self.calls, [])

    def test_default_runner_uses_agent_loop_and_returns_updated_state(self):
        lab = Lab(self.root)
        question = 'Hãy nhớ authentication dùng JWT.'
        responses = iter([
            dict(action='remember_memory', key='auth', value='JWT', evidence=question, answer=''),
            dict(action='final', key='', value='', evidence='', answer='Đã nhớ JWT.'),
        ])
        def model(prompt, prefix, timeout):
            return next(responses), {'thread_id': str(prefix)}
        def runner(path, store, on_event):
            return run_agent(path, store, model_step=model, on_event=on_event)
        with patch('ui_server.run_agent', side_effect=runner):
            context = lab.prepare_request(question, False)
            result = lab.ask(context['request_id'])
        self.assertEqual(result['model_steps'], 2)
        self.assertEqual(result['state']['entries'][0]['value'], 'JWT')
        self.assertEqual(len(result['trace']), 3)

    def test_background_run_prevents_duplicate_and_exposes_progress(self):
        entered, release = threading.Event(), threading.Event()
        original = self.lab.runner
        def blocking(path):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test timeout')
            return original(path)
        self.lab.runner = blocking
        prepared = self.lab.prepare_request('Đăng nhập?', False)
        request_id = prepared['request_id']
        self.lab.start(request_id)
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(self.lab.progress(request_id)['status'], 'running')
            with self.assertRaises(ValueError):
                self.lab.start(request_id)
            with self.assertRaises(ValueError):
                self.lab.save_memory('auth', 'cookie')
            with self.assertRaises(ValueError):
                self.lab.new_demo()
        finally:
            release.set()
        self.lab.pending[request_id]['worker'].join(2)
        self.assertEqual(self.lab.progress(request_id)['status'], 'done')
        self.assertEqual(self.lab.progress(request_id)['result']['answer'], 'Câu trả lời test double')

    def test_failed_background_run_is_not_retried_and_keeps_store(self):
        self.lab.save_memory('auth', 'JWT')
        def failing(path):
            raise RuntimeError('provider failed')
        self.lab.runner = failing
        request_id = self.lab.prepare_request('Đăng nhập?', False)['request_id']
        self.lab.start(request_id)
        self.lab.pending[request_id]['worker'].join(2)
        self.assertEqual(self.lab.progress(request_id)['status'], 'failed')
        self.assertEqual(self.lab.state()['entries'][0]['value'], 'JWT')
        with self.assertRaises(ValueError):
            self.lab.start(request_id)

    def test_http_rejects_foreign_origin_and_handles_local_memory_request(self):
        server = make_server(self.lab, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        self.addCleanup(connection.close)
        body = json.dumps({'key': 'auth', 'value': 'JWT'})
        headers = {'Content-Type': 'application/json', 'X-Memory-Lab': '1',
                   'Origin': 'https://unrelated.example'}
        connection.request('POST', '/api/memory', body, headers)
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()
        self.assertEqual(self.lab.state()['entries'], [])
        headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
        connection.request('POST', '/api/memory', body, headers)
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())['record']['value'], 'JWT')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
