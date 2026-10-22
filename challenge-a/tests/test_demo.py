import json
from pathlib import Path
import tempfile
import unittest

from demo import QUESTION, SESSIONS, verify_evidence
from memory_agent import prepare, remember


class DemoEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        store = self.root / 'memory.json'
        remember(store, 'session-1', 'auth', 'JWT')
        self.save('session-2-request.json', prepare(store, 'session-2', QUESTION))
        remember(store, 'session-3', 'auth', 'Authentication dùng session cookie thay cho JWT.')
        self.save('session-4-request.json', prepare(store, 'session-4', QUESTION))
        self.save('control-request.json', prepare(store, 'control', QUESTION, True))

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def test_new_rule_can_mention_what_it_replaces(self):
        result = verify_evidence(self.root)
        self.assertEqual(result['memory_checks'], 'PASS')
        self.assertFalse(result['llm_executed'])

    def test_later_request_loading_the_old_record_is_rejected(self):
        stale = json.loads((self.root / 'session-2-request.json').read_text())
        self.save('session-4-request.json', stale)
        with self.assertRaises(AssertionError):
            verify_evidence(self.root)

    def test_partial_live_run_never_counts_as_completed_demo(self):
        self.save('session-1-write.agent-result.json', {'status': 'completed'})
        with self.assertRaises(AssertionError):
            verify_evidence(self.root)

    def make_relocated_live_evidence(self):
        for label, _ in SESSIONS:
            (self.root / (label + '.codex-answer.md')).write_text('Câu trả lời thử nghiệm.', encoding='utf-8')
            self.save(label + '.agent-result.json', {
                'status': 'completed', 'model_steps': 2,
                'llm_steps': [{'thread_id': label}],
                'trace': [{'type': 'tool_result', 'tool': 'remember_memory', 'result': {'ok': True}}],
                'answer_file': str(self.root / 'old-machine' / (label + '.codex-answer.md')),
            })

    def test_live_evidence_can_be_verified_after_moving_to_another_machine(self):
        self.make_relocated_live_evidence()
        result = verify_evidence(self.root)
        self.assertTrue(result['agent_loop_executed'])

    def test_missing_local_answer_is_not_replaced_by_an_external_original(self):
        self.make_relocated_live_evidence()
        label = SESSIONS[0][0]
        (self.root / (label + '.codex-answer.md')).unlink()
        (self.root / 'old-machine').mkdir()
        for session, _ in SESSIONS:
            external = self.root / 'old-machine' / (session + '.codex-answer.md')
            external.write_text('Bản ở máy cũ.', encoding='utf-8')
        with self.assertRaises(FileNotFoundError):
            verify_evidence(self.root)
