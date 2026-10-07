"""Chạy 5 cuộc trò chuyện mới với model thật; ghi trace, không chứa đáp án định sẵn."""
import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import os
from langchain_core.messages import HumanMessage

import paths
from agent import build_agent, build_model, capabilities
from config import PROJECT_NAME, RECURSION_LIMIT, load_settings
from observer import Observer
from trace import TraceWriter


def run_case(label, question, settings):
    observer = Observer(conversation_id=uuid.uuid4().hex)
    observer.start_turn(uuid.uuid4().hex)
    writer = TraceWriter(paths.TRACES_DIR, PROJECT_NAME, observer.conversation_id, observer.run_id, 1)
    working = [HumanMessage(content=question)]
    caps = capabilities()
    writer.write(observer.record('user_submitted', {'text': question, 'tools': caps['tools'], 'skills': caps['skills']}))
    try:
        model = build_model(settings)
        for mode, chunk in build_agent(model).stream(
            {'messages': working}, config={'recursion_limit': RECURSION_LIMIT}, stream_mode=['updates', 'custom']
        ):
            if mode == 'custom' and isinstance(chunk, dict) and chunk.get('observer'):
                writer.write(observer.record(chunk['event'], chunk['data']))
            elif mode == 'updates':
                for update in chunk.values():
                    if isinstance(update, dict) and update.get('messages'):
                        working.extend(update['messages'])
                        observer.sync_messages(working)
        answer = next((m.content for m in reversed(working) if m.type == 'ai' and not m.tool_calls), '')
        writer.write(observer.record('run_completed', {'answer_chars': len(str(answer))}))
        result = {'case': label, 'trace': writer.path.name, 'answer': answer}
        print(json.dumps(result, ensure_ascii=False))
        return result
    except Exception as exc:
        # Không ghi exception provider, có thể chứa thông tin cấu hình nhạy cảm.
        writer.write(observer.record('run_failed', {'error': type(exc).__name__}))
        raise RuntimeError(f'{label}: {type(exc).__name__}; trace: {writer.path.name}') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, help='File cấu hình model, không sao chép vào bài nộp')
    args = parser.parse_args()
    if args.env_file:
        values = dotenv_values(args.env_file)
        for target, source in [('OPENAI_API_KEY', 'GEMINI_API_KEY'), ('MODEL_NAME', 'GEMINI_MODEL')]:
            value = values.get(target) or values.get(source)
            if value:
                os.environ[target] = value
        base = values.get('OPENAI_BASE_URL')
        if not base and values.get('GEMINI_API_KEY'):
            base = 'https://generativelanguage.googleapis.com/v1beta/openai/'
        if base:
            os.environ['OPENAI_BASE_URL'] = base
    settings, missing = load_settings()
    if missing:
        parser.error('Thiếu cấu hình: ' + ', '.join(missing))
    a = 'Tôi mua ngày 28/09/2026, yêu cầu hoàn ngày 06/10/2026, chưa kích hoạt. Tôi có được hoàn không?'
    b = 'Tôi mua ngày 02/10/2026, yêu cầu hoàn ngày 12/10/2026, chưa kích hoạt. Tôi có được hoàn không?'
    results = [run_case('A', a, settings), run_case('B', b, settings)]
    directory = paths.WORKSPACE_DIR / 'data/policies'
    pairs = [(directory / 'policy-before-oct.md', directory / 'document-alpha.md'),
             (directory / 'policy-from-oct.md', directory / 'document-beta.md')]
    if any(not source.is_file() or dest.exists() for source, dest in pairs):
        parser.error('Cần hai file chính sách gốc và chưa có file document-alpha/beta để thử đổi tên.')
    renamed = []
    try:
        for source, dest in pairs:
            source.rename(dest)
            renamed.append((source, dest))
        results += [run_case('A-renamed', a, settings), run_case('B-renamed', b, settings)]
    finally:
        for source, dest in reversed(renamed):
            dest.rename(source)
    results.append(run_case('missing-activation', 'Tôi mua ngày 02/10/2026, muốn hoàn ngày 12/10/2026.', settings))
    (paths.TRACES_DIR / 'case-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
