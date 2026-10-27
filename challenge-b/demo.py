"""Demo Challenge B. Mặc định offline; --codex mới gọi model và dùng quota."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

from code_runtime import run_code, load_logs
from context_agent import (run_b1, run_b2, write_json, normalized_stats,
                           CONTINUE_SCHEMA, CHECKPOINT_SCHEMA, ACTION_SCHEMA,
                           ANSWER_SCHEMA, validate_json, CONTINUE, COMPACT,
                           CODE_INSTRUCTIONS, serialize, compact_session)
from model_transport import inspect_events
from scenarios import B1_EXPECTED, QUESTION, create_logs, create_session


BASE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def expected_from_logs(logs):
    """Oracle độc lập với code do model viết; không được đưa vào prompt."""
    groups, records = Counter(), 0
    snapshot = load_logs(logs)
    for rows in snapshot.values():
        for event in rows:
            records += 1
            if event['level'] == 'ERROR':
                groups[event['service'] + '/' + event['error_code']] += 1
    return {'files_scanned': len(snapshot), 'records_scanned': records,
            'error_counts': [{'group': k, 'count': v} for k, v in sorted(groups.items())]}


def show_results(root, parts):
    """In câu trả lời và kết quả công cụ của các phần đã hoàn tất."""
    root = Path(root)
    for part in parts:
        report = read_json(root / part / 'result.json')
        if part == 'b1':
            print('\nB1 - Trước compact:\n' + report['before']['answer'])
            print('\nCheckpoint model tạo:\n' + serialize(read_json(root / part / 'checkpoint.json')))
            print('\nB1 - Sau compact:\n' + report['after']['answer'])
        else:
            baseline = ('đọc từng file' if report.get('baseline_kind') == 'read_file'
                        else 'toàn bộ raw log trong một prompt')
            print('\nB2 - Baseline (' + baseline + '):\n' + report['baseline']['answer'])
            print('\nB2 - Chương trình model viết:')
            for entry in report['trace']:
                if entry['type'] == 'model_action' and entry['action'] == 'run_code':
                    print(entry['code'])
                elif entry['type'] == 'tool_result':
                    print('\nRuntime:\n' + serialize(entry))
            print('\nB2 - Câu trả lời từ aggregate:\n' + report['final']['answer'])


def verify_run(root):
    """Đọc lại evidence sau restart/chuyển thư mục, không gọi model."""
    root = Path(root).resolve()
    summary = read_json(root / 'summary.json')
    if summary['status'] not in ('passed', 'offline_validated'):
        raise ValueError('Lần chạy chưa hoàn tất thành công.')
    expected = expected_from_logs(root / 'logs')
    if expected != read_json(root / 'expected.json'):
        raise ValueError('Expected không khớp log fixture.')
    if not summary['llm_executed']:
        if summary['status'] != 'offline_validated':
            raise ValueError('Offline không được báo model passed.')
        aggregate = run_code((BASE / 'example_program.py.txt').read_text(), root / 'logs')
        actual = {k: aggregate[k] for k in ('files_scanned', 'records_scanned')}
        actual['error_counts'] = [{'group': k, 'count': v} for k, v in sorted(aggregate['counts'].items())]
        if actual != expected or actual != read_json(root / 'offline-result.json'):
            raise ValueError('Offline result không khớp.')
        return {'status': 'offline_validated', 'llm_executed': False,
                'message': 'Chỉ chứng minh fixture/runtime; chưa chứng minh model.'}
    verified = {}
    thread_ids = []
    if (not summary['parts'] or len(set(summary['parts'])) != len(summary['parts'])
            or any(p not in ('b1', 'b2') for p in summary['parts'])):
        raise ValueError('Danh sách bài kiểm chứng không hợp lệ.')
    for part in summary['parts']:
        folder = root / part
        report = read_json(folder / 'result.json')
        if report['status'] != 'passed' or not report.get('checks') or not all(report['checks'].values()):
            raise ValueError(part + ' chưa đạt; xem result.json.')
        calls = report['calls']
        native = None
        if part == 'b2' and report.get('baseline_kind') == 'read_file':
            from native_baseline import verify_native
            native = verify_native(folder / 'native', root / 'logs', expected)
            thread_ids.extend(c['thread_id'] for c in native['calls'])
        names = [c['name'] for c in calls]
        if (part == 'b1' and names != ['before', 'compact', 'after'] or part == 'b2'
                and names not in ([['code-01', 'code-02'], ['code-01', 'code-02', 'code-03']] if native else
                                  [['baseline', 'code-01', 'code-02'],
                                   ['baseline', 'code-01', 'code-02', 'code-03']])):
            raise ValueError('Thứ tự/lượng model calls không hợp lệ.')
        for call in calls:
            prefix = folder / call['name']
            if call.get('simulated'):
                raise ValueError('Không nhận model giả lập làm evidence thật.')
            prompt = Path(str(prefix) + '.input.txt').read_text(encoding='utf-8')
            transported = Path(str(prefix) + '.codex-prompt.txt').read_text(encoding='utf-8')
            if transported != prompt + '\n' or len(prompt.encode()) != call['prompt_bytes']:
                raise ValueError('Prompt/transport không khớp.')
            inspected = inspect_events([json.loads(line) for line in
                Path(str(prefix) + '.codex-events.jsonl').read_text().splitlines() if line.strip()])
            if inspected['usage'] != call['usage'] or inspected['thread_id'] != call['thread_id']:
                raise ValueError('Usage/thread không khớp event thật.')
            thread_ids.append(inspected['thread_id'])
            response = read_json(Path(str(prefix) + '.response.json'))
            if response != read_json(Path(str(prefix) + '.codex-answer.md')):
                raise ValueError('Response không khớp output model.')
            if part == 'b1':
                schema = CHECKPOINT_SCHEMA if call['name'] == 'compact' else CONTINUE_SCHEMA
            else:
                schema = ANSWER_SCHEMA if call['name'] == 'baseline' else ACTION_SCHEMA
            validate_json(response, schema)
        inputs = [c['usage']['input_tokens'] for c in calls]
        if part == 'b1':
            before, after = (read_json(folder / (name + '.response.json')) for name in ('before', 'after'))
            for answer in (before, after):
                for key, value in B1_EXPECTED.items():
                    actual = answer[key]
                    if (sorted(actual) != sorted(value) if isinstance(value, list) else actual != value):
                        raise ValueError('B1 mất state: ' + key)
            active, archive = read_json(folder / 'active-session.json'), read_json(folder / 'archive-session.json')
            if active != compact_session(archive, read_json(folder / 'compact.response.json')):
                raise ValueError('B1 không thay working history trong cùng session.')
            if (folder / 'before.input.txt').read_text() != CONTINUE + serialize(archive):
                raise ValueError('B1 baseline không khớp archive.')
            if (folder / 'compact.input.txt').read_text() != COMPACT + serialize(archive):
                raise ValueError('B1 input compact không khớp archive.')
            after_prompt = (folder / 'after.input.txt').read_text(encoding='utf-8')
            if (after_prompt != CONTINUE + serialize(active) or 'RAW_LOG_ONLY' in after_prompt
                    or inputs[2] >= inputs[0]):
                raise ValueError('B1 chưa giảm context/input tokens.')
            if report['usage'] != {'before_input': inputs[0], 'compact_creation_input': inputs[1],
                    'after_input': inputs[2], 'compact_path_total_input': sum(inputs[1:]),
                    'continuation_reduction_percent': round((1 - inputs[2] / inputs[0]) * 100, 2)}:
                raise ValueError('B1 báo usage sai.')
        else:
            code_calls = calls if native else calls[1:]
            code_inputs = inputs if native else inputs[1:]
            baseline_input = native['total_input'] if native else inputs[0]
            if native:
                baseline = {**native['final']['result'], 'answer': native['final']['answer']}
            else:
                baseline = read_json(folder / 'baseline.response.json')
                raw = {p.name: p.read_text(encoding='utf-8') for p in sorted((root / 'logs').glob('*.jsonl'))}
                if (folder / 'baseline.input.txt').read_text() != QUESTION + '\nRAW LOG DATA (JSON):\n' + serialize(raw):
                    raise ValueError('Raw baseline không khớp fixture.')
            if (report['baseline'] != baseline or report['baseline_correct'] !=
                    (normalized_stats(baseline) == expected)):
                raise ValueError('B2 baseline không khớp evidence.')
            trace = read_json(folder / 'trace.json')
            if trace != report['trace']:
                raise ValueError('B2 trace không khớp report.')
            successful, cursor, tool_calls = None, 0, 0
            for call in code_calls:
                prompt = CODE_INSTRUCTIONS + '\nQUESTION:\n' + QUESTION + '\nTHIS SESSION TRACE:\n' + serialize(trace[:cursor])
                if (folder / (call['name'] + '.input.txt')).read_text() != prompt:
                    raise ValueError('B2 prompt không khớp trace đến bước hiện tại.')
                action = read_json(folder / (call['name'] + '.response.json'))
                if cursor >= len(trace) or trace[cursor] != {'type': 'model_action', **action}:
                    raise ValueError('B2 action không khớp model output.')
                cursor += 1
                if action['action'] == 'final':
                    if cursor != len(trace) or action['code'] or not action['answer'].strip():
                        raise ValueError('B2 final không hợp lệ.')
                    continue
                tool_calls += 1
                if (folder / ('program-' + call['name'][-2:] + '.py')).read_text() != action['code'] + '\n':
                    raise ValueError('B2 program không khớp model output.')
                try:
                    aggregate = run_code(action['code'], root / 'logs')
                    successful = {k: aggregate[k] for k in ('files_scanned', 'records_scanned')}
                    successful['error_counts'] = [{'group': k, 'count': v}
                                                  for k, v in sorted(aggregate['counts'].items())]
                    tool = {'type': 'tool_result', 'ok': True, 'result': successful}
                except ValueError as exc:
                    tool = {'type': 'tool_result', 'ok': False, 'error': str(exc)}
                if cursor >= len(trace) or trace[cursor] != tool:
                    raise ValueError('B2 tool result không khớp kết quả chạy code.')
                cursor += 1
            if cursor != len(trace) or tool_calls != report['tool_calls']:
                raise ValueError('B2 trace thiếu/thừa bước.')
            final = report['final']
            if (successful is None or normalized_stats(successful) != expected
                    or normalized_stats(final['result']) != expected):
                raise ValueError('B2 code/final không khớp oracle.')
            if final != read_json(folder / (calls[-1]['name'] + '.response.json')):
                raise ValueError('B2 final không khớp model output.')
            if any('RAW_LOG_ONLY' in (folder / (c['name'] + '.input.txt')).read_text()
                   for c in code_calls) or sum(code_inputs) >= baseline_input:
                raise ValueError('B2 raw log vào context hoặc chưa giảm tổng input token.')
            if report['usage'] != {'baseline_input': baseline_input, 'code_mode_total_input': sum(code_inputs),
                    'code_mode_final_input': inputs[-1],
                    'reduction_percent': round((1 - sum(code_inputs) / baseline_input) * 100, 2)}:
                raise ValueError('B2 báo usage sai.')
        verified[part] = report['usage']
    if not verified or len(set(thread_ids)) != len(thread_ids):
        raise ValueError('Không có kết quả hoặc đã dùng lại Codex thread.')
    return {'status': 'passed', 'llm_executed': True, 'verified': verified}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--codex', action='store_true', help='Gọi model thật, dùng quota Codex.')
    mode.add_argument('--verify', type=Path, metavar='EVIDENCE_DIR', help='Kiểm lại evidence, không gọi model.')
    parser.add_argument('--part', choices=('b1', 'b2', 'all'), default='all')
    parser.add_argument('--output', type=Path, help='Thư mục mới, không ghi đè.')
    parser.add_argument('--baseline', choices=('read_file', 'raw'), default='read_file',
                        help='B2: mặc định model đọc từng file; raw giữ phép đo cũ.')
    parser.add_argument('--seed', type=int, default=17, help='Seed fixture để thử bộ số liệu khác.')
    args = parser.parse_args(argv)
    if args.codex:
        logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    if args.verify:
        print(json.dumps(verify_run(args.verify), ensure_ascii=False, indent=2))
        show_results(args.verify, read_json(args.verify / 'summary.json')['parts'])
        return 0
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root = (args.output or BASE / 'evidence' / timestamp).resolve()
    root.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'llm_executed': args.codex,
               'fixture': 'synthetic investigation and logs', 'parts': [], 'seed': args.seed}
    write_json(root / 'summary.json', summary)
    print('Evidence:', root, flush=True)
    try:
        expected = create_logs(root / 'logs', seed=args.seed)
        write_json(root / 'expected.json', expected)
        if not args.codex:
            aggregate = run_code((BASE / 'example_program.py.txt').read_text(), root / 'logs')
            offline = {k: aggregate[k] for k in ('files_scanned', 'records_scanned')}
            offline['error_counts'] = [{'group': k, 'count': v} for k, v in sorted(aggregate['counts'].items())]
            if offline != expected:
                raise ValueError('Offline aggregate không khớp fixture.')
            write_json(root / 'offline-result.json', offline)
            summary['status'] = 'offline_validated'
            print('OFFLINE: example code đã quét log thật trên đĩa; chưa gọi model.', flush=True)
            print(json.dumps(offline, ensure_ascii=False, indent=2), flush=True)
        else:
            for part in ('b1', 'b2') if args.part == 'all' else (args.part,):
                print('\n' + part.upper(), flush=True)
                summary['parts'].append(part)
                write_json(root / 'summary.json', summary)
                report = (run_b1(root / part, create_session(root / 'logs')) if part == 'b1'
                          else run_b2(root / part, root / 'logs', expected, baseline_mode=args.baseline))
                result = {'part': part, 'status': report['status'], 'usage': report.get('usage'),
                          'checks': report.get('checks')}
                if 'context_bytes' in report:
                    result['context_bytes'] = report['context_bytes']
                print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
                if report['status'] != 'passed':
                    raise ValueError(part + ' chưa đạt; giữ nguyên evidence để kiểm tra.')
                show_results(root, [part])
            summary['status'] = 'passed'
    except Exception as exc:
        summary.update(status='failed', error=str(exc))
        print('FAILED:', exc, file=sys.stderr, flush=True)
    finally:
        write_json(root / 'summary.json', summary)
    if summary['status'] == 'failed':
        return 1
    print(json.dumps(verify_run(root), ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
