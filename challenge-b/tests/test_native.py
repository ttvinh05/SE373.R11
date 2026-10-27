"""Native-style JSON actions: model chooses each read; no provider calls in tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from context_agent import write_json
from scenarios import create_logs
from native_baseline import run_native, verify_native


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.expected = create_logs(self.root / 'logs')
        self.prompts = []

    def actions(self):
        empty = {'files_scanned': 0, 'records_scanned': 0, 'error_counts': []}
        def action(tool, filename=''):
            return dict(action=tool, filename=filename, result=empty, answer='')
        return [action('list_logs')] + [action('read_log', p.name) for p in
            sorted((self.root / 'logs').glob('*.jsonl'))] + [dict(
                action='final', filename='', result=self.expected, answer='Đã đếm đủ file.')]

    def transport(self, replies):
        replies = iter(replies)
        def model(prompt, prefix, timeout=90, schema=None):
            self.assertEqual(timeout, 240)
            self.prompts.append(prompt)
            response = next(replies)
            usage = {'input_tokens': len(prompt.encode()) // 3, 'output_tokens': 20}
            thread = 'synthetic-native-test-' + str(len(self.prompts))
            Path(str(prefix) + '.codex-prompt.txt').write_text(prompt + '\n')
            write_json(Path(str(prefix) + '.codex-answer.md'), response)
            events = [{'type': 'thread.started', 'thread_id': thread},
                      {'type': 'turn.completed', 'usage': usage}]
            Path(str(prefix) + '.codex-events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            return json.dumps(response), dict(thread_id=thread, usage=usage)
        return model

    def test_reads_each_file_in_model_loop_and_sums_all_input(self):
        report = run_native(self.root / 'native', self.root / 'logs', self.expected,
                            self.transport(self.actions()))
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['tool_calls'], 7)
        self.assertEqual(len(report['calls']), 8)
        self.assertNotIn('RAW_LOG_ONLY', self.prompts[0])
        self.assertIn('RAW_LOG_ONLY', self.prompts[-1])
        self.assertEqual(report['total_input'], sum(c['usage']['input_tokens'] for c in report['calls']))
        self.assertEqual(verify_native(self.root / 'native', self.root / 'logs', self.expected), report)
        trace_path = self.root / 'native' / 'trace.json'
        trace = json.loads(trace_path.read_text())
        trace[3]['result'][0]['level'] = 'TAMPERED'
        write_json(trace_path, trace)
        report['trace'] = trace
        write_json(self.root / 'native' / 'result.json', report)
        with self.assertRaises(ValueError):
            verify_native(self.root / 'native', self.root / 'logs', self.expected)

    def test_final_without_reading_all_logs_is_rejected(self):
        with self.assertRaises(ValueError):
            run_native(self.root / 'native', self.root / 'logs', self.expected,
                       self.transport([self.actions()[-1]]))
        self.assertEqual(json.loads((self.root / 'native' / 'result.json').read_text())['status'], 'failed')

    def test_path_escape_and_duplicate_reads_are_rejected(self):
        for filename in ('../secret.jsonl', 'unknown.jsonl'):
            actions = self.actions()[:2]
            actions[1]['filename'] = filename
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                run_native(self.root / filename.replace('/', '_'), self.root / 'logs', self.expected,
                           self.transport(actions))
        actions = self.actions()[:2]
        actions.append(copy.deepcopy(actions[-1]))
        with self.assertRaises(ValueError):
            run_native(self.root / 'duplicate', self.root / 'logs', self.expected, self.transport(actions))

    def test_incorrect_counts_fail_despite_all_logs_read(self):
        actions = self.actions()
        actions[-1]['result'] = {**self.expected, 'records_scanned': 1}
        report = run_native(self.root / 'wrong', self.root / 'logs', self.expected,
                            self.transport(actions))
        self.assertEqual(report['status'], 'failed')
