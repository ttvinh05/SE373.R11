"""Demo xuyên tiến trình. --codex: agent thật; --verify: kiểm lại log, không gọi model."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from memory_agent import prepare, read_store

ROOT = Path(__file__).resolve().parent
QUESTION = 'Đề xuất cách triển khai đăng nhập cho dự án này trong 3 gạch đầu dòng.'
SESSIONS = (
    ('session-1-write', 'Hãy nhớ quy ước dự án: authentication dùng JWT.'),
    ('session-2-request', QUESTION),
    ('session-3-update', 'Từ nay đổi quy ước authentication sang session cookie thay cho JWT. Hãy nhớ cho các session sau.'),
    ('session-4-request', QUESTION),
    ('control-request', QUESTION),
)


def verify_evidence(folder):
    folder = Path(folder).resolve()
    def load(name):
        return json.loads((folder / name).read_text(encoding='utf-8'))
    first, second, control = [load(name + '.json') for name in
                              ('session-2-request', 'session-4-request', 'control-request')]
    entries = read_store(folder / 'memory.json')['entries']
    active = [e for e in entries if e['status'] == 'active']
    old = [e for e in entries if e['status'] == 'superseded']
    assert len(active) == len(old) == 1 and active[0]['key'] == old[0]['key'] == 'auth'
    assert old[0]['superseded_by'] == active[0]['id']
    fields = ('key', 'value', 'source_session', 'created_at')
    assert json.loads(first['injected_memory']) == [{k: old[0][k] for k in fields}]
    assert json.loads(second['injected_memory']) == [{k: active[0][k] for k in fields}]
    assert 'JWT' in old[0]['value'] and 'session cookie' in active[0]['value']
    assert first['messages'][1] == second['messages'][1] == control['messages'][1]
    for request in (first, second, control):
        assert request['history_messages'] == 0
        assert [m['role'] for m in request['messages']] == ['system', 'user']
    assert control['injected_memory'] == '' and not control['memory_enabled']
    paths = [folder / (label + '.agent-result.json') for label, _ in SESSIONS]
    live = [json.loads(path.read_text()) for path in paths if path.exists()]
    if live:
        assert len(live) == 5 and all(r['status'] == 'completed' for r in live)
        thread_ids = [step['thread_id'] for r in live for step in r['llm_steps']]
        assert len(set(thread_ids)) == len(thread_ids)
        for result in (live[0], live[2]):
            assert result['model_steps'] >= 2
            assert any(e['type'] == 'tool_result' and e['tool'] == 'remember_memory'
                       and e['result']['ok'] for e in result['trace'])
        # Metadata giữ đường dẫn gốc để truy vết; kiểm tra file trong gói hiện tại.
        for label, _ in SESSIONS:
            assert (folder / (label + '.codex-answer.md')).read_text(encoding='utf-8').strip()
    summary = {
        'memory_checks': 'PASS', 'llm_executed': bool(live),
        'agent_loop_executed': bool(live), 'llm_sessions': live,
        'note': ('Đã kiểm tra store, injection và tool trace. Đọc câu trả lời để đánh giá ngữ nghĩa; '
                 'không chấm việc tuân thủ chỉ bằng từ khóa.') if live else
                'Chỉ kiểm chứng harness offline, không chạy agent/model.',
        'question': QUESTION, 'evidence_dir': str(folder),
    }
    (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--codex', action='store_true', help='Chạy 5 session agent thật, có dùng quota')
    modes.add_argument('--verify', type=Path, help='Kiểm lại thư mục bằng chứng sẵn có, không gọi model')
    args = parser.parse_args()
    if args.verify:
        summary = verify_evidence(args.verify)
    else:
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder = ROOT / 'evidence' / run_id
        folder.mkdir(parents=True)
        store = folder / 'memory.json'
        print('Bằng chứng:', folder, flush=True)
        for label, question in SESSIONS:
            path = folder / (label + '.json')
            if args.codex:
                request = prepare(store, label, question, without_memory=label == 'control-request')
                path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
                command = [sys.executable, '-B', str(ROOT / 'agent_loop.py'), str(path), '--store', str(store)]
                limit = 260
            else:
                command = [sys.executable, '-B', str(ROOT / 'memory_agent.py'), '--store', str(store)]
                if label in ('session-1-write', 'session-3-update'):
                    value = 'Authentication dùng JWT.' if label == 'session-1-write' else 'Authentication dùng session cookie.'
                    command += ['remember', '--session', label, '--key', 'auth', '--value', value]
                else:
                    command += ['prepare', '--session', label, '--question', question]
                    if label == 'control-request':
                        command.append('--without-memory')
                limit = 10
            process = subprocess.run(command, text=True, capture_output=True, timeout=limit)
            (folder / (label + '.stdout.txt')).write_text(process.stdout, encoding='utf-8')
            (folder / (label + '.stderr.txt')).write_text(process.stderr, encoding='utf-8')
            if process.returncode:
                raise RuntimeError(f'Lỗi ở {label}; xem {folder}. Không tự retry.')
            result = json.loads(process.stdout)
            if args.codex:
                print(f"\n{label}: {result['model_steps']} bước model, {result['tool_items']} tool\n"
                      + Path(result['answer_file']).read_text(), flush=True)
            else:
                path.write_text(process.stdout, encoding='utf-8')
        summary = verify_evidence(folder)
    print(json.dumps({k: v for k, v in summary.items() if k != 'llm_sessions'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
