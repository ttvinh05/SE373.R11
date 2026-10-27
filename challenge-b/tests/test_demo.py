"""Verifier tests dùng event envelope tổng hợp, không gọi provider thật."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from context_agent import run_b1, run_b2, write_json
from demo import main, verify_run
from scenarios import B1_EXPECTED, create_logs, create_session
from test_context import CHECKPOINT
from test_runtime import PROGRAM


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make_synthetic_evidence(self, part, native=False):
        """Chỉ kiểm định dạng/đối chiếu nội bộ; không chứng minh model thật."""
        expected = create_logs(self.root / 'logs')
        write_json(self.root / 'expected.json', expected)
        answer = {**B1_EXPECTED, 'answer': 'Tiếp tục kiểm tra critical section.'}
        if part == 'b1':
            replies = [answer, CHECKPOINT, answer]
        else:
            empty = {'files_scanned': 0, 'records_scanned': 0, 'error_counts': []}
            replies = [{**expected, 'answer': 'Đã đếm'},
                       {'action': 'run_code', 'code': PROGRAM, 'result': empty, 'answer': ''},
                       {'action': 'final', 'code': '', 'result': expected, 'answer': 'Đã đếm'}]
        if native:
            from test_native import NativeTests
            helper = NativeTests()
            helper.root, helper.expected = self.root, expected
            replies = helper.actions() + replies[1:]
        responses = iter(replies)
        call_number = []

        def synthetic_transport(prompt, prefix, timeout=90, schema=None):
            call_number.append(1)
            response = next(responses)
            thread = f'unit-test-envelope-{part}-{len(call_number)}'
            usage = {'input_tokens': len(prompt.encode()) // 3, 'output_tokens': 20}
            Path(str(prefix) + '.codex-prompt.txt').write_text(prompt + '\n')
            write_json(Path(str(prefix) + '.codex-answer.md'), response)
            events = [{'type': 'thread.started', 'thread_id': thread},
                      {'type': 'turn.completed', 'usage': usage}]
            Path(str(prefix) + '.codex-events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            return json.dumps(response), {'thread_id': thread, 'usage': usage}

        if part == 'b1':
            run_b1(self.root / part, create_session(self.root / 'logs'), synthetic_transport)
        else:
            run_b2(self.root / part, self.root / 'logs', expected, synthetic_transport,
                   baseline_mode='read_file' if native else 'raw')
        write_json(self.root / 'summary.json', {'status': 'passed', 'parts': [part], 'llm_executed': True})
        self.assertEqual(verify_run(self.root)['status'], 'passed')

    def test_completed_part_is_printed_even_if_next_part_fails(self):
        output = io.StringIO()
        def completed_b1(folder, session):
            folder.mkdir()
            report = {'status': 'passed', 'usage': {}, 'checks': {'state_retained': True},
                      'before': {'answer': 'Trước compact'},
                      'after': {'answer': 'B1 đã tiếp tục từ checkpoint'}}
            write_json(folder / 'checkpoint.json', CHECKPOINT)
            write_json(folder / 'result.json', report)
            return report
        with patch('demo.logging.basicConfig'), \
                patch('demo.run_b1', side_effect=completed_b1), \
                patch('demo.run_b2', side_effect=RuntimeError('provider timeout')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(['--codex', '--output', str(self.root / 'run')])
        self.assertEqual(code, 1)
        self.assertIn('B1 đã tiếp tục từ checkpoint', output.getvalue())
        self.assertNotIn('HÌNH', output.getvalue())
        self.assertEqual(json.loads((self.root / 'run/summary.json').read_text())['status'], 'failed')

    def test_per_file_baseline_is_replayed_and_usage_tampering_rejected(self):
        self.make_synthetic_evidence('b2', native=True)
        path = self.root / 'b2' / 'result.json'
        report = json.loads(path.read_text())
        report['usage']['baseline_input'] -= 1
        write_json(path, report)
        with self.assertRaises(ValueError):
            verify_run(self.root)

    def test_offline_default_and_replay_do_not_claim_model_executed(self):
        path = self.root / 'offline'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--output', str(path)]), 0)
        self.assertEqual(verify_run(path)['status'], 'offline_validated')
        self.assertFalse(verify_run(path)['llm_executed'])
        write_json(path / 'offline-result.json', {})
        with self.assertRaises(ValueError):
            verify_run(path)

    def test_existing_output_is_preserved(self):
        sentinel = self.root / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            main(['--output', str(self.root)])
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_verifier_rejects_modified_tool_result(self):
        self.make_synthetic_evidence('b2')
        path = self.root / 'b2' / 'result.json'
        report = json.loads(path.read_text())
        tool = next(item for item in report['trace'] if item['type'] == 'tool_result')
        tool['result']['records_scanned'] = 0
        write_json(path, report)
        write_json(self.root / 'b2' / 'trace.json', report['trace'])
        with self.assertRaises(ValueError):
            verify_run(self.root)

    def test_verifier_requires_after_prompt_to_equal_checkpoint_context(self):
        self.make_synthetic_evidence('b1')
        folder = self.root / 'b1'
        prompt = (folder / 'after.input.txt').read_text() + '\nUNEXPECTED OLD CHAT'
        (folder / 'after.input.txt').write_text(prompt)
        (folder / 'after.codex-prompt.txt').write_text(prompt + '\n')
        report = json.loads((folder / 'result.json').read_text())
        report['calls'][-1]['prompt_bytes'] = len(prompt.encode())
        write_json(folder / 'result.json', report)
        with self.assertRaises(ValueError):
            verify_run(self.root)

    def test_verifier_rejects_failed_summary(self):
        self.make_synthetic_evidence('b1')
        write_json(self.root / 'summary.json', {'status': 'failed', 'parts': ['b1'], 'llm_executed': True})
        with self.assertRaises(ValueError):
            verify_run(self.root)


if __name__ == '__main__':
    unittest.main()
