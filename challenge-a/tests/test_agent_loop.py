import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_loop import run_agent
from memory_agent import prepare, read_store, remember


def action(name='final', key='', value='', evidence='', answer='Đã hoàn tất.'):
    return dict(action=name, key=key, value=value, evidence=evidence, answer=answer)


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.root / 'memory.json'
        self.prompts = []

    def run_turn(self, question, actions, without_memory=False, **options):
        path = self.root / f'request-{len(list(self.root.glob("request-*.json")))}.json'
        path.write_text(json.dumps(prepare(self.store, path.stem, question, without_memory)), encoding='utf-8')
        responses = iter(actions)

        def model(prompt, prefix, timeout):
            self.prompts.append(prompt)
            return next(responses), {'thread_id': str(prefix), 'usage': {'input_tokens': 10}}

        return run_agent(path, self.store, model_step=model, **options)

    def test_model_writes_then_observes_tool_result_before_answering(self):
        question = 'Hãy nhớ: authentication dùng JWT.'
        result = self.run_turn(question, [
            action('remember_memory', 'auth', 'Authentication dùng JWT.', question, ''),
            action(answer='Đã lưu quy ước JWT.'),
        ])
        self.assertEqual(result['model_steps'], 2)
        self.assertEqual(result['tool_items'], 1)
        self.assertIn('Authentication dùng JWT.', self.prompts[1])
        self.assertIn('tool_result', self.prompts[1])
        self.assertEqual(read_store(self.store)['entries'][0]['source_session'], result['session_id'])
        self.assertEqual(Path(result['answer_file']).read_text(), 'Đã lưu quy ước JWT.')
        self.assertTrue(Path(result['trace_file']).exists())

    def test_new_session_uses_updated_rule_without_previous_transcript(self):
        remember(self.store, 'before', 'auth', 'JWT')
        question = 'Đổi quy ước authentication sang session cookie, nhớ cho phiên sau.'
        self.run_turn(question, [action('remember_memory', 'auth', 'session cookie', question, ''), action()])
        result = self.run_turn('Triển khai đăng nhập thế nào?', [action(answer='Dùng session cookie.')])
        self.assertIn('session cookie', result['injected_memory'])
        self.assertNotIn('JWT', result['injected_memory'])
        self.assertNotIn(question, self.prompts[-1])
        self.assertEqual(result['history_messages'], 0)
        self.assertEqual([e['status'] for e in read_store(self.store)['entries']], ['superseded', 'active'])

    def test_control_blocks_both_memory_tools_and_injection(self):
        remember(self.store, 'before', 'auth', 'JWT')
        question = 'Hãy nhớ: dùng cookie.'
        result = self.run_turn(question, [
            action('read_memory', answer=''),
            action('remember_memory', 'auth', 'cookie', question, ''), action(),
        ], without_memory=True)
        self.assertEqual(result['injected_memory'], '')
        self.assertTrue(all(not e['result']['ok'] for e in result['trace'] if e['type'] == 'tool_result'))
        self.assertEqual(read_store(self.store)['entries'][0]['value'], 'JWT')
        self.assertNotIn('JWT', self.prompts[-1])

    def test_invalid_tool_and_arguments_can_be_corrected_without_writing(self):
        result = self.run_turn('Xin chào', [
            action('shell', value='touch owned', answer=''),
            action('remember_memory', '../escape', 'JWT', 'bịa', ''),
            action(answer='Chào bạn.'),
        ])
        self.assertFalse(self.store.exists())
        self.assertEqual(result['model_steps'], 3)
        self.assertIn('error', self.prompts[-1])

    def test_write_requires_quote_from_current_user_not_saved_memory(self):
        remember(self.store, 'before', 'auth', 'Hãy nhớ dùng cookie.')
        self.run_turn('Đề xuất đăng nhập.', [
            action('remember_memory', 'auth', 'cookie', 'Hãy nhớ dùng cookie.', ''), action(),
        ])
        self.assertEqual(len(read_store(self.store)['entries']), 1)

    def test_read_returns_active_memory_and_final_does_not_write(self):
        remember(self.store, 'before', 'auth', 'JWT')
        result = self.run_turn('Quy ước hiện tại?', [action('read_memory', answer=''), action(answer='JWT')])
        self.assertEqual(result['tool_items'], 1)
        self.assertEqual(result['trace'][1]['result']['entries'][0]['value'], 'JWT')
        self.assertEqual(len(read_store(self.store)['entries']), 1)

    def test_step_limit_saves_failed_trace_and_never_reports_success(self):
        with self.assertRaisesRegex(RuntimeError, 'giới hạn'):
            self.run_turn('Đọc memory', [action('read_memory', answer='')] * 2, max_steps=2)
        result = json.loads(next(self.root.glob('*.agent-result.json')).read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['model_steps'], 2)

    def test_malformed_model_response_is_rejected_before_writing(self):
        with self.assertRaisesRegex(RuntimeError, 'JSON|schema|hợp lệ'):
            self.run_turn('Hãy nhớ dùng JWT.', [{'action': 'remember_memory'}])
        self.assertFalse(self.store.exists())

    def test_timeout_after_model_response_does_not_execute_write(self):
        question = 'Hãy nhớ JWT.'
        with patch('agent_loop.time.monotonic', side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(RuntimeError, 'hết thời gian'):
                self.run_turn(question, [action('remember_memory', 'auth', 'JWT', question, '')], timeout=1)
        self.assertFalse(self.store.exists())

    def test_provider_failure_after_write_keeps_actual_record_and_failed_trace(self):
        question = 'Hãy nhớ JWT.'
        # Iterator hết phần trả lời ở lượt thứ hai giả lập provider dừng sau khi tool đã ghi.
        with self.assertRaises(StopIteration):
            self.run_turn(question, [action('remember_memory', 'auth', 'JWT', question, '')])
        self.assertEqual(read_store(self.store)['entries'][0]['value'], 'JWT')
        result = json.loads(next(self.root.glob('*.agent-result.json')).read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(any(e['type'] == 'tool_result' and e['result']['ok'] for e in result['trace']))


if __name__ == '__main__':
    unittest.main()
