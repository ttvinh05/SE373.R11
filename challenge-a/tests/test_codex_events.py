import unittest

from run_codex import inspect_events


class CodexEventTests(unittest.TestCase):
    def events(self, item):
        return [{"type": "thread.started", "thread_id": "new-thread"},
                {"type": "item.completed", "item": item},
                {"type": "turn.completed", "usage": {"input_tokens": 10}}]

    def test_startup_warning_is_diagnostic_not_tool_execution(self):
        events = self.events({"type": "error", "message": "Under-development features enabled"})
        result = inspect_events(events)
        self.assertEqual(result["tool_items"], 0)
        self.assertEqual(result["diagnostics"], ["Under-development features enabled"])

    def test_completed_shell_command_is_rejected(self):
        events = self.events({"type": "command_execution", "command": "cat memory.json"})
        with self.assertRaisesRegex(RuntimeError, "dùng tool"):
            inspect_events(events)


if __name__ == "__main__":
    unittest.main()
