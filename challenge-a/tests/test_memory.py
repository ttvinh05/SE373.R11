import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "memory_agent.py"


class MemoryChallengeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Path(self.tmp.name) / "memory.json"

    def run_cli(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--store", str(self.store), *args],
            capture_output=True, text=True, timeout=10,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def remember(self, value, session="session-1", key="auth"):
        return self.run_cli("remember", "--session", session, "--key", key,
                            "--value", value)

    def prepare(self, session="session-2", *extra):
        return self.run_cli("prepare", "--session", session, *extra,
                            "--question", "Đề xuất cách triển khai đăng nhập.")

    def test_new_process_reads_memory_without_old_chat(self):
        self.remember("Dùng JWT.")
        request = self.prepare()
        self.assertEqual(request["history_messages"], 0)
        self.assertEqual([m["role"] for m in request["messages"]],
                         ["system", "user"])
        self.assertIn("Dùng JWT.", request["injected_memory"])
        self.assertIn(request["injected_memory"], request["messages"][0]["content"])
        self.assertNotIn("JWT", request["messages"][1]["content"])

    def test_changed_rule_supersedes_old_rule_in_later_process(self):
        old = self.remember("Dùng JWT.")
        new = self.remember("Dùng session cookie.", session="session-3")
        request = self.prepare("session-4")
        self.assertIn("Dùng session cookie.", request["injected_memory"])
        self.assertNotIn("JWT", request["injected_memory"])
        entries = json.loads(self.store.read_text())["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["status"], "superseded")
        self.assertEqual(entries[0]["superseded_by"], new["id"])
        self.assertEqual(entries[1]["status"], "active")
        self.assertEqual(old["source_session"], "session-1")
        self.assertTrue(entries[0]["superseded_at"])
        self.assertTrue(new["created_at"])

    def test_unchanged_rule_does_not_duplicate_and_other_keys_survive(self):
        self.remember("PostgreSQL", key="database")
        first = self.remember("Dùng JWT.")
        again = self.remember("Dùng JWT.", session="session-2")
        self.assertEqual(first["id"], again["id"])
        self.remember("Dùng session cookie.", session="session-3")
        self.assertIn("PostgreSQL", self.prepare()["injected_memory"])
        self.assertEqual(len(json.loads(self.store.read_text())["entries"]), 3)

    def test_control_without_memory_has_same_question_and_no_injection(self):
        self.remember("Dùng JWT.")
        normal = self.prepare()
        control = self.prepare("control", "--without-memory")
        self.assertEqual(control["injected_memory"], "")
        self.assertEqual(normal["messages"][1], control["messages"][1])
        self.assertNotIn("JWT", control["messages"][0]["content"])

    def test_corrupt_store_is_reported_and_preserved(self):
        self.store.write_text("broken json", encoding="utf-8")
        result = self.run_cli("prepare", "--session", "new", "--question", "Hello", ok=False)
        self.assertIn("Không đọc được memory", result.stderr)
        self.assertEqual(self.store.read_text(), "broken json")

    def test_empty_value_is_rejected_without_writing(self):
        result = self.run_cli("remember", "--session", "one", "--key", "auth",
                              "--value", "   ", ok=False)
        self.assertIn("Không được để trống", result.stderr)
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
