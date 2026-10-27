import copy
import json
from pathlib import Path
import tempfile
import unittest

from context_agent import compact_session, validate_json, CHECKPOINT_SCHEMA, run_b1, run_b2
from scenarios import B1_EXPECTED, create_logs, create_session
from test_runtime import PROGRAM


CHECKPOINT = {
    'goal': 'Điều tra refresh token', 'current_state': 'ISSUE-17 chưa giải quyết; ISSUE-09 đã sửa',
    'constraints': ['C-API: backward compatible', 'C-DEPS: không thêm dependency'],
    'findings': ['test_refresh_concurrent: hai request cùng đọc token trước invalidate'],
    'failed_attempts': ['TRY-01: tăng TTL không giúp', 'TRY-02: backoff không giúp'],
    'files': ['auth.py', 'session.py', 'test_refresh.py'],
    'next_action': 'NEXT-03: kiểm tra critical section đọc/invalidate/rotate và atomic lock',
}


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.expected = create_logs(self.root / 'logs')
        self.session = create_session(self.root / 'logs')
        self.prompts = []

    def fake(self, replies):
        replies = iter(replies)

        def step(prompt, prefix, timeout=90, schema=None):
            self.prompts.append(prompt)
            return json.dumps(next(replies), ensure_ascii=False), {
                'thread_id': 'fake-test-only', 'simulated': True,
                'usage': {'input_tokens': len(prompt.encode()) // 3, 'output_tokens': 50},
            }
        return step

    def test_compaction_replaces_history_retains_session_and_does_not_mutate_archive(self):
        original = copy.deepcopy(self.session)
        compacted = compact_session(self.session, CHECKPOINT)
        self.assertEqual(self.session, original)
        self.assertEqual(compacted['session_id'], self.session['session_id'])
        self.assertNotIn('history', compacted)
        self.assertNotIn('RAW_LOG_ONLY', json.dumps(compacted))
        self.assertLess(len(json.dumps(compacted)), len(json.dumps(self.session)) // 5)
        self.assertEqual(compacted['checkpoint']['failed_attempts'], CHECKPOINT['failed_attempts'])

    def test_missing_empty_or_extra_checkpoint_fields_are_rejected(self):
        for change in ({'next_action': ''}, {'files': []}, {'raw_history': 'x'}):
            checkpoint = {**CHECKPOINT, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_json(checkpoint, CHECKPOINT_SCHEMA)

    def test_b1_continuation_uses_checkpoint_only_and_reports_compaction_cost(self):
        answer = {**B1_EXPECTED, 'answer': 'Kiểm tra critical section trước khi sửa.'}
        result = run_b1(self.root / 'b1', self.session,
                        self.fake([answer, CHECKPOINT, answer]))
        self.assertEqual(result['status'], 'passed')
        self.assertIn('RAW_LOG_ONLY', self.prompts[0])
        self.assertIn('RAW_LOG_ONLY', self.prompts[1])
        self.assertNotIn('RAW_LOG_ONLY', self.prompts[2])
        self.assertLess(result['usage']['after_input'], result['usage']['before_input'])
        self.assertEqual(result['usage']['compact_path_total_input'],
                         result['usage']['compact_creation_input'] + result['usage']['after_input'])

    def test_b1_lost_state_fails_even_when_provider_returned_valid_json(self):
        answer = {**B1_EXPECTED, 'answer': 'Tiếp tục'}
        wrong = {**answer, 'next_action_id': 'NEXT-01'}
        result = run_b1(self.root / 'b1', self.session, self.fake([answer, CHECKPOINT, wrong]))
        self.assertEqual(result['status'], 'failed')

    def test_b2_executes_model_program_and_no_raw_log_reaches_code_mode_prompts(self):
        baseline = {**self.expected, 'answer': 'Đã đếm.'}
        empty = {'files_scanned': 0, 'records_scanned': 0, 'error_counts': []}
        result = run_b2(self.root / 'b2', self.root / 'logs', self.expected, baseline_mode='raw', model=self.fake([
            baseline, {'action': 'run_code', 'code': PROGRAM, 'result': empty, 'answer': ''},
            {'action': 'final', 'code': '', 'result': self.expected, 'answer': 'Đã đếm.'},
        ]))
        self.assertEqual(result['status'], 'passed')
        self.assertIn('RAW_LOG_ONLY', self.prompts[0])
        self.assertTrue(all('RAW_LOG_ONLY' not in p for p in self.prompts[1:]))
        self.assertEqual(result['tool_calls'], 1)

    def test_b2_cannot_claim_success_without_executing_code(self):
        with self.assertRaisesRegex(ValueError, 'tool thành công'):
            run_b2(self.root / 'b2', self.root / 'logs', self.expected, baseline_mode='raw', model=self.fake([
                {**self.expected, 'answer': 'Đã đếm.'},
                {'action': 'final', 'code': '', 'result': self.expected, 'answer': 'Đoán'},
            ]))
        result = json.loads((self.root / 'b2' / 'result.json').read_text())
        self.assertEqual(result['status'], 'failed')

    def test_b2_retry_receives_error_type_without_raw_log(self):
        empty = {'files_scanned': 0, 'records_scanned': 0, 'error_counts': []}
        broken = ('files = list_logs()\nrows = read_log(files[0])\n'
                  'lookup = {}\nx = lookup[rows[0]["message"]]')
        result = run_b2(self.root / 'retry', self.root / 'logs', self.expected,
                       baseline_mode='raw', model=self.fake([
            {**self.expected, 'answer': 'Đã đếm.'},
            {'action': 'run_code', 'code': broken, 'result': empty, 'answer': ''},
            {'action': 'run_code', 'code': PROGRAM, 'result': empty, 'answer': ''},
            {'action': 'final', 'code': '', 'result': self.expected, 'answer': 'Đã đếm.'},
        ]))
        self.assertIn('KeyError', self.prompts[2])
        self.assertTrue(all('RAW_LOG_ONLY' not in p for p in self.prompts[1:]))
        self.assertEqual(result['tool_calls'], 2)
        self.assertTrue(result['checks']['tool_correct'])
        self.assertTrue(result['checks']['final_matches_tool'])
        self.assertTrue(result['checks']['raw_log_absent_from_all_code_mode_prompts'])

    def test_provider_failure_is_saved_and_not_retried(self):
        calls = []

        def broken(*args, **kwargs):
            calls.append(1)
            raise RuntimeError('provider unavailable')

        with self.assertRaisesRegex(RuntimeError, 'provider unavailable'):
            run_b1(self.root / 'b1', self.session, broken)
        self.assertEqual(len(calls), 1)
        result = json.loads((self.root / 'b1' / 'result.json').read_text())
        self.assertEqual(result['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
