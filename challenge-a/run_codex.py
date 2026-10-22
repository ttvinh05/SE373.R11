"""Gửi context đã chuẩn bị vào một phiên Codex CLI mới, lưu bằng chứng thật."""
import argparse
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


def build_prompt(request):
    messages = request["messages"]
    if [m["role"] for m in messages] != ["system", "user"]:
        raise ValueError("Request phải chỉ có system và user; không mang history cũ")
    # CLI nhận một prompt, không phải HTTP messages. Giữ rõ phần chuyển đổi này.
    return ("Chỉ trả lời yêu cầu bên dưới, không dùng tool hoặc đọc file.\n\n"
              "HƯỚNG DẪN VÀ NGỮ CẢNH DỰ ÁN:\n" + messages[0]["content"]
              + "\n\nYÊU CẦU HIỆN TẠI:\n" + messages[1]["content"])


def invoke_codex(prompt, prefix, timeout=90, schema=None):
    """Transport CLI dùng chung; không cho CLI chạy tool ngoài dispatcher của bài."""
    prompt_path = Path(str(prefix) + ".codex-prompt.txt")
    answer_path = Path(str(prefix) + ".codex-answer.md")
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="challenge-a-codex-") as workspace:
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


def run_codex(request_path):
    """Adapter một lượt cũ, giữ để đọc/chạy lại bằng chứng demo trước đây."""
    request_path = Path(request_path).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    answer, metadata = invoke_codex(build_prompt(request), request_path.with_suffix(''), timeout=240)
    metadata.update(session_id=request['session_id'], history_messages=0)
    print(f"\n=== Codex thật: {request['session_id']} ===\n{answer}\n", flush=True)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    run_codex(parser.parse_args().request)
