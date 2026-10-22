"""Giao diện local cho Challenge A; Python chuẩn, không cài thêm package."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import threading
from uuid import UUID, uuid4
from urllib.parse import parse_qs, urlsplit

from memory_agent import prepare, read_store, remember
from agent_loop import build_agent_prompt, run_agent


ROOT = Path(__file__).resolve().parent


def text(value, name, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} cần có từ 1 đến {limit} ký tự.')
    return value.strip()


class Lab:
    def __init__(self, root, runner=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.lock = threading.RLock()
        self.pending = {}
        pointer = self.root / 'current.txt'
        if pointer.exists():
            self.demo_id = str(UUID(pointer.read_text().strip()))
        else:
            self.new_demo()

    @property
    def folder(self):
        return self.root / self.demo_id

    @property
    def store(self):
        return self.folder / 'memory.json'

    def state(self):
        with self.lock:
            return {'demo_id': self.demo_id, 'store': str(self.store),
                    'entries': read_store(self.store)['entries']}

    def new_demo(self):
        with self.lock:
            if any(item['status'] == 'running' for item in self.pending.values()):
                raise ValueError('Codex đang trả lời. Chờ xong rồi mở demo mới.')
            self.demo_id = str(uuid4())
            self.folder.mkdir()
            temporary = self.root / 'current.tmp'
            temporary.write_text(self.demo_id, encoding='utf-8')
            temporary.replace(self.root / 'current.txt')
            self.pending.clear()
            return self.state()

    def save_memory(self, key, value):
        key, value = text(key, 'Key', 40), text(value, 'Nội dung quy ước')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', key):
            raise ValueError('Key chỉ gồm chữ, số, dấu gạch ngang hoặc gạch dưới.')
        with self.lock:
            if any(p['status'] == 'running' for p in self.pending.values()):
                raise ValueError('Agent đang chạy. Chờ xong trước khi ghi thủ công.')
            record = remember(self.store, 'write-' + uuid4().hex[:8], key, value)
            return {'record': record, 'state': self.state()}

    def prepare_request(self, question, without_memory):
        question = text(question, 'Câu hỏi')
        if not isinstance(without_memory, bool):
            raise ValueError('without_memory phải là boolean.')
        with self.lock:
            request_id = str(uuid4())
            request = prepare(self.store, 'session-' + request_id[:8], question, without_memory)
            path = self.folder / (request_id + '.json')
            path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            self.pending[request_id] = {'path': path, 'status': 'ready', 'trace': []}
            return {'request_id': request_id, 'request': request, 'codex_prompt': build_agent_prompt(request)}

    def ask(self, request_id):
        item = self.claim(request_id)
        return self.execute(item)

    def claim(self, request_id):
        with self.lock:
            item = self.pending.get(request_id) if isinstance(request_id, str) else None
            if item is None:
                raise ValueError('Context không tồn tại. Hãy chuẩn bị context mới.')
            if item['status'] != 'ready':
                raise ValueError('Context này đã được gửi. Hãy chuẩn bị phiên mới để hỏi tiếp.')
            if any(p['status'] == 'running' for p in self.pending.values()):
                raise ValueError('Một phiên Codex đang chạy. Chờ phiên đó hoàn tất.')
            item['status'] = 'running'
            return item

    def execute(self, item):
        def on_event(event):
            with self.lock:
                item['trace'].append(event)
        try:
            metadata = (self.runner(item['path']) if self.runner else
                        run_agent(item['path'], self.store, on_event=on_event))
            answer_path = Path(str(item['path'].with_suffix('')) + '.codex-answer.md')
            result = {'answer': answer_path.read_text(encoding='utf-8'),
                      'thread_id': metadata['thread_id'], 'usage': metadata.get('usage'),
                      'tool_items': metadata['tool_items'], 'evidence': str(item['path'].parent),
                      'model_steps': metadata.get('model_steps', 1),
                      'trace': metadata.get('trace', []), 'state': self.state()}
        except Exception:
            with self.lock:
                item['status'] = 'failed'
                item['error'] = 'Agent chưa hoàn tất. Xem trace và log; không tự gửi lại để tránh ghi/gọi trùng.'
            raise
        with self.lock:
            item['status'] = 'done'
            item['result'] = result
        return result

    def start(self, request_id):
        item = self.claim(request_id)
        def work():
            try:
                self.execute(item)
            except Exception:
                # Lỗi đã được lưu vào trạng thái; không tự retry model hoặc thao tác ghi.
                pass
        worker = threading.Thread(target=work, daemon=True)
        with self.lock:
            item['worker'] = worker
            worker.start()
        return {'request_id': request_id, 'status': 'running'}

    def progress(self, request_id):
        with self.lock:
            item = self.pending.get(request_id)
            if item is None:
                raise ValueError('Không tìm thấy lượt chạy trong tiến trình server này.')
            return {'state': self.state(), **{
                key: item[key] for key in ('status', 'trace', 'result', 'error') if key in item
            }}


def make_server(lab, port=8765, codex_status='Chưa kiểm tra đăng nhập'):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print('Memory Lab:', fmt % args, flush=True)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy',
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
                             "base-uri 'none'; form-action 'self'")
            super().end_headers()

        def respond(self, status, payload, content_type='application/json; charset=utf-8'):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def local_request(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            return self.headers.get('Host') in allowed

        def do_GET(self):
            if not self.local_request():
                return self.respond(403, {'error': 'Chỉ phục vụ truy cập local.'})
            if self.path == '/api/state':
                try:
                    return self.respond(200, {**lab.state(), 'codex_status': codex_status})
                except (OSError, ValueError):
                    return self.respond(500, {'error': 'Không đọc được memory. Kiểm tra file trước khi tiếp tục.'})
            parsed = urlsplit(self.path)
            if parsed.path == '/api/progress':
                try:
                    request_id = parse_qs(parsed.query).get('request_id', [''])[0]
                    return self.respond(200, lab.progress(request_id))
                except ValueError as exc:
                    return self.respond(404, {'error': str(exc)})
            assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                      '/style.css': ('style.css', 'text/css')}
            if self.path not in assets:
                return self.respond(404, {'error': 'Không tìm thấy.'})
            name, mime = assets[self.path]
            self.respond(200, (ROOT / 'web' / name).read_bytes(), mime + '; charset=utf-8')

        def do_POST(self):
            origin = self.headers.get('Origin')
            allowed = {f'http://127.0.0.1:{self.server.server_port}',
                       f'http://localhost:{self.server.server_port}'}
            if (not self.local_request() or (origin is not None and origin not in allowed)
                    or self.headers.get('X-Memory-Lab') != '1'):
                return self.respond(403, {'error': 'Yêu cầu phải được gửi từ giao diện local.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.respond(415, {'error': 'Chỉ nhận JSON.'})
            if self.path not in ('/api/memory', '/api/prepare', '/api/ask', '/api/start', '/api/new-demo'):
                return self.respond(404, {'error': 'Không tìm thấy.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    return self.respond(413, {'error': 'Nội dung quá dài hoặc rỗng.'})
                self.connection.settimeout(10)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Nội dung phải là một JSON object.')
                if self.path == '/api/memory':
                    result = lab.save_memory(body.get('key'), body.get('value'))
                elif self.path == '/api/prepare':
                    result = lab.prepare_request(body.get('question'), body.get('without_memory', False))
                elif self.path == '/api/ask':
                    result = lab.ask(body.get('request_id'))
                elif self.path == '/api/start':
                    result = lab.start(body.get('request_id'))
                else:
                    result = lab.new_demo()
                self.respond(200, result)
            except (ValueError, UnicodeError) as exc:
                self.respond(400, {'error': str(exc)})
            except (OSError, RuntimeError, subprocess.SubprocessError, StopIteration):
                self.respond(502, {'error': 'Chưa nhận được kết quả Codex hợp lệ. Xem log ở Terminal và thư mục bằng chứng; không tự gửi lại để tránh gọi trùng.'})

        def do_OPTIONS(self):
            self.respond(403, {'error': 'Không cho phép truy cập từ website khác.'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        login = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True, timeout=10)
        status = 'Codex đã đăng nhập' if login.returncode == 0 else 'Chưa đăng nhập — chạy codex login'
    except (OSError, subprocess.SubprocessError):
        status = 'Chưa tìm thấy Codex CLI'
    server = make_server(Lab(ROOT / 'data' / 'ui'), args.port, status)
    print(f'Mở http://127.0.0.1:{server.server_port} — {status}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
