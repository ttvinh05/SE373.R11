"""Transport tái sử dụng từ Challenge A; CLI chỉ trả JSON, không chạy tool."""
import json
from pathlib import Path
import subprocess
import tempfile


def inspect_events(events):
    thread = next(e["thread_id"] for e in events if e["type"] == "thread.started")
    completed = next(e for e in events if e["type"] == "turn.completed")
    items = [e["item"] for e in events if e["type"] == "item.completed"]
    # CLI dùng item.error cả cho cảnh báo khởi động, không phải tool execution.
    diagnostics = [i["message"] for i in items if i["type"] == "error"]
    tools = [i for i in items if i["type"] not in ("agent_message", "reasoning", "error")]
    if tools:
        raise RuntimeError("Phiên thử đã dùng tool ngoài prompt; cần kiểm tra event log")
    return {"thread_id": thread, "tool_items": 0, "diagnostics": diagnostics,
            "usage": completed.get("usage")}


def invoke_codex(prompt, prefix, timeout=90, schema=None):
    """Transport CLI dùng chung; không cho CLI chạy tool ngoài dispatcher của bài."""
    prompt_path = Path(str(prefix) + ".codex-prompt.txt")
    answer_path = Path(str(prefix) + ".codex-answer.md")
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="challenge-b-codex-") as workspace:
        command = [
            "codex", "exec", "--ignore-user-config", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json",
            "--disable", "memories", "--disable", "apps", "--disable", "plugins",
            "--disable", "shell_tool", "--disable", "multi_agent",
            "--disable", "skill_search", "--disable", "hooks",
            "--enable", "skip_host_skill_discovery",
            "-c", "project_doc_max_bytes=0", "-c", 'web_search="disabled"',
            "--cd", workspace, "--output-last-message", str(answer_path), "-",
        ]
        if schema is not None:
            schema_path = Path(workspace) / 'response-schema.json'
            schema_path.write_text(json.dumps(schema), encoding='utf-8')
            command[-1:-1] = ['--output-schema', str(schema_path)]
        try:
            result = subprocess.run(command, input=prompt, text=True,
                                    capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            for suffix, output in [('events.jsonl', exc.stdout), ('stderr.txt', exc.stderr)]:
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='replace')
                Path(str(prefix) + '.codex-' + suffix).write_text(output or '', encoding='utf-8')
            raise
    Path(str(prefix) + ".codex-events.jsonl").write_text(result.stdout, encoding="utf-8")
    Path(str(prefix) + ".codex-stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Codex lỗi {result.returncode}; xem {prefix}.codex-stderr.txt")
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    inspected = inspect_events(events)
    answer = answer_path.read_text(encoding="utf-8").strip()
    if not answer:
        raise RuntimeError("Codex không trả lời")
    metadata = {**inspected, "answer_file": str(answer_path),
                "prompt_file": str(prompt_path),
                "transport": "CLI stdin; system/user được ghép thành một prompt",
                "command": command}
    Path(str(prefix) + ".codex-result.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return answer, metadata
