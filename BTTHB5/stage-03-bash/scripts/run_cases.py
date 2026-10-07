"""Kiểm chứng bằng model thật; mỗi case là conversation mới, không chứa đáp án."""
import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
import agent
from config import PROJECT_NAME, RECURSION_LIMIT
from langchain_core.messages import HumanMessage
from observer import Observer
from trace import TraceWriter
from scripts.model_runtime import configure_model


def run_case(label, question, settings):
    observer = Observer(conversation_id=uuid.uuid4().hex)
    observer.start_turn(uuid.uuid4().hex)
    writer = TraceWriter(paths.TRACES_DIR, PROJECT_NAME, observer.conversation_id, observer.run_id, 1)
    working = [HumanMessage(content=question)]
    caps = agent.capabilities()
    writer.write(observer.record('user_submitted', {'text': question, 'tools': caps['tools'], 'skills': caps['skills']}))
    try:
        for mode, chunk in agent.build_agent(agent.build_model(settings)).stream(
            {'messages': working}, config={'recursion_limit': RECURSION_LIMIT}, stream_mode=['updates', 'custom']
        ):
            if mode == 'custom' and chunk.get('observer'):
                writer.write(observer.record(chunk['event'], chunk['data']))
            elif mode == 'updates':
                for update in chunk.values():
                    if isinstance(update, dict) and update.get('messages'):
                        working.extend(update['messages'])
                        observer.sync_messages(working)
        answer = next((m.text for m in reversed(working) if m.type == 'ai' and not m.tool_calls), '')
        writer.write(observer.record('run_completed', {'answer': answer, 'answer_chars': len(answer)}))
        result = {'case': label, 'question': question, 'trace': writer.path.name, 'answer': answer}
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result
    except Exception as exc:
        writer.write(observer.record('run_failed', {'error': type(exc).__name__}))
        raise RuntimeError(f'{label}: {type(exc).__name__}; trace: {writer.path.name}') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--case', help='Chỉ chạy một case; mặc định chạy tất cả case của stage')
    args = parser.parse_args()
    settings, missing = configure_model(args.env_file)
    if missing:
        parser.error('Thiếu cấu hình: ' + ', '.join(missing))
    if PROJECT_NAME == 'stage-03-bash':
        cases = [('python-bash', 'Dùng Python qua Bash để tính tổng hours theo owner trong data/workload.csv. Không chỉnh sửa file đầu vào. Cho biết cách xử lý dòng lỗi và task_id trùng.')]
    elif PROJECT_NAME == 'stage-04-script-skill':
        cases = [
            ('threshold-8', 'Kiểm tra data/workload.csv, người nào vượt 8 giờ? Ghi báo cáo vào output/workload.md.'),
            ('threshold-9', 'Kiểm tra data/workload.csv, người nào vượt 9 giờ? Ghi báo cáo vào output/workload-9.md.'),
            ('missing-threshold', 'Tính tổng giờ theo người trong data/workload.csv và xác định người quá tải.'),
            ('missing-file', 'Kiểm tra data/no-such-workload.csv, người nào vượt 8 giờ? Ghi báo cáo vào output/missing-file.md.'),
        ]
    else:
        cases = [('A', 'Tôi mua ngày 28/09/2026, yêu cầu hoàn ngày 06/10/2026, chưa kích hoạt. Tôi có được hoàn không?'),
                 ('B', 'Tôi mua ngày 02/10/2026, yêu cầu hoàn ngày 12/10/2026, chưa kích hoạt. Tôi có được hoàn không?')]
    if args.case:
        cases = [(label, question) for label, question in cases if label == args.case]
        if not cases:
            parser.error('Case không có trong stage này.')
    results = [run_case(label, question, settings) for label, question in cases]
    target = paths.TRACES_DIR / 'case-results.json'
    if args.case and target.is_file():
        previous = json.loads(target.read_text())
        results = [r for r in previous if r['case'] != args.case] + results
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
