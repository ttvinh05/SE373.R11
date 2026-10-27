"""Runtime cho tập con Python: diễn giải AST, không eval/exec code của model.

Worker chỉ nhận bản sao JSON của log qua stdin; không cung cấp API host cho code.
Đây là runtime bài tập có giới hạn, không phải sandbox Python tổng quát.
"""
import ast
import json
import operator
from pathlib import Path
import re
import subprocess
import sys


MAX_INPUT = 1_000_000
MAX_OUTPUT = 4096
FUNCTIONS = {'list_logs', 'read_log', 'emit', 'len', 'sorted', 'range'}
NODES = (ast.Module, ast.Assign, ast.AugAssign, ast.For, ast.If, ast.Expr,
         ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List, ast.Tuple,
         ast.Subscript, ast.Slice, ast.Call, ast.Attribute, ast.keyword,
         ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
         ast.BinOp, ast.Add, ast.Sub, ast.BoolOp, ast.And, ast.Or,
         ast.UnaryOp, ast.Not, ast.USub)


def parse(code):
    if not isinstance(code, str) or not 0 < len(code) <= 8000:
        raise ValueError('Code phải dài 1..8000 ký tự.')
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f'Code sai cú pháp ở dòng {exc.lineno}: {exc.msg}') from exc
    for node in ast.walk(tree):
        if not isinstance(node, NODES):
            raise ValueError('Cú pháp không được hỗ trợ: ' + type(node).__name__)
        if isinstance(node, ast.Name) and node.id.startswith('_'):
            raise ValueError('Không cho phép tên riêng tư/reflection.')
        if isinstance(node, ast.Attribute) and node.attr not in ('get', 'items', 'append'):
            raise ValueError('Chỉ cho phép dict.get/items và list.append.')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in FUNCTIONS:
            raise ValueError('Hàm không nằm trong allowlist: ' + node.func.id)
    return tree


def validate_result(result):
    if not isinstance(result, dict) or set(result) != {'files_scanned', 'records_scanned', 'counts'}:
        raise ValueError('emit chỉ nhận files_scanned, records_scanned, counts; không nhận raw log.')
    if any(type(result[k]) is not int or not 0 <= result[k] <= 100_000
           for k in ('files_scanned', 'records_scanned')):
        raise ValueError('Số file/record không hợp lệ.')
    counts = result['counts']
    if not isinstance(counts, dict) or len(counts) > 30:
        raise ValueError('counts phải là dict tối đa 30 nhóm.')
    for key, value in counts.items():
        if (not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}/[A-Za-z0-9_-]{1,40}', key)
                or type(value) is not int or not 0 <= value <= 100_000):
            raise ValueError('Nhóm/count không hợp lệ.')
    if len(json.dumps(result).encode()) > MAX_OUTPUT:
        raise ValueError('Kết quả vượt giới hạn output.')
    return result


class Runtime:
    def __init__(self, logs):
        self.logs, self.variables, self.output, self.fuel = logs, {}, [], 100_000

    def tick(self):
        self.fuel -= 1
        if self.fuel <= 0:
            raise ValueError('Code vượt step budget.')

    def assign(self, target, value):
        if isinstance(target, ast.Name) and target.id not in FUNCTIONS:
            self.variables[target.id] = value
        elif isinstance(target, ast.Subscript):
            container, key = self.expr(target.value), self.expr(target.slice)
            if type(container) not in (dict, list):
                raise ValueError('Chỉ gán phần tử dict/list.')
            container[key] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == len(value):
            for part, item in zip(target.elts, value):
                self.assign(part, item)
        else:
            raise ValueError('Đích gán không được hỗ trợ.')

    def block(self, nodes):
        for node in nodes:
            self.tick()
            if isinstance(node, ast.Assign):
                value = self.expr(node.value)
                for target in node.targets:
                    self.assign(target, value)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, (ast.Add, ast.Sub)):
                value = self.expr(node.target)
                delta = self.expr(node.value)
                self.assign(node.target, value + delta if isinstance(node.op, ast.Add) else value - delta)
            elif isinstance(node, ast.For) and not node.orelse:
                for value in self.expr(node.iter):
                    self.tick()
                    self.assign(node.target, value)
                    self.block(node.body)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expr(node.test) else node.orelse)
            elif isinstance(node, ast.Expr):
                self.expr(node.value)
            else:
                raise ValueError('Statement không được hỗ trợ.')

    def expr(self, node):
        self.tick()
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.variables[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.expr(e) for e in node.elts]
        if isinstance(node, ast.Dict) and all(k is not None for k in node.keys):
            return {self.expr(k): self.expr(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            return self.expr(node.value)[self.expr(node.slice)]
        if isinstance(node, ast.Slice):
            return slice(*(self.expr(e) if e else None for e in (node.lower, node.upper, node.step)))
        if isinstance(node, ast.BinOp):
            left, right = self.expr(node.left), self.expr(node.right)
            if isinstance(node.op, ast.Add):
                if isinstance(left, (str, list)) and len(left) + len(right) > 2000:
                    raise ValueError('Giá trị vượt giới hạn runtime.')
                return left + right
            return left - right
        if isinstance(node, ast.UnaryOp):
            value = self.expr(node.operand)
            return not value if isinstance(node.op, ast.Not) else -value
        if isinstance(node, ast.BoolOp):
            for part in node.values:
                value = self.expr(part)
                if isinstance(node.op, ast.And) and not value:
                    return value
                if isinstance(node.op, ast.Or) and value:
                    return value
            return value
        if isinstance(node, ast.Compare):
            comparisons = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
            left = self.expr(node.left)
            for op, part in zip(node.ops, node.comparators):
                right = self.expr(part)
                if not comparisons[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            args = [self.expr(a) for a in node.args]
            kwargs = {k.arg: self.expr(k.value) for k in node.keywords}
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name == 'list_logs' and not args and not kwargs:
                    return sorted(self.logs)
                if name == 'read_log' and len(args) == 1 and not kwargs:
                    if args[0] not in self.logs:
                        raise ValueError('File không nằm trong allowlist.')
                    # Bản sao: model không thể sửa snapshot của lần gọi sau.
                    return json.loads(json.dumps(self.logs[args[0]]))
                if name == 'emit' and len(args) == 1 and not kwargs:
                    if self.output:
                        raise ValueError('Chỉ được emit một lần.')
                    self.output.append(json.loads(json.dumps(validate_result(args[0]))))
                    return None
                if name == 'len' and len(args) == 1 and not kwargs:
                    return len(args[0])
                if name == 'sorted' and len(args) == 1 and set(kwargs) <= {'reverse'}:
                    return sorted(args[0], **kwargs)
                if name == 'range' and 1 <= len(args) <= 3 and not kwargs:
                    value = range(*args)
                    if len(value) <= 1000:
                        return value
            if isinstance(node.func, ast.Attribute) and not kwargs:
                value, method = self.expr(node.func.value), node.func.attr
                if type(value) is dict and method == 'get' and 1 <= len(args) <= 2:
                    return value.get(*args)
                if type(value) is dict and method == 'items' and not args:
                    return list(value.items())
                if type(value) is list and method == 'append' and len(args) == 1 and len(value) < 1000:
                    value.append(args[0])
                    return None
            raise ValueError('Lời gọi hàm/đối số không được hỗ trợ.')
        raise ValueError('Biểu thức không được hỗ trợ.')


def load_logs(root):
    paths = sorted(Path(root).glob('*.jsonl'))
    if not 1 <= len(paths) <= 20 or any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError('Cần 1..20 file log thường; không nhận symlink.')
    logs, size = {}, 0
    for path in paths:
        if path.stat().st_size > MAX_INPUT - size:
            raise ValueError('Log vượt giới hạn 1 MB.')
        with path.open('rb') as stream:
            data = stream.read(MAX_INPUT - size + 1)
        size += len(data)
        if size > MAX_INPUT:
            raise ValueError('Log vượt giới hạn 1 MB.')
        try:
            rows = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Log không phải JSONL hợp lệ.') from exc
        if len(rows) > 2000 or any(not isinstance(r, dict) for r in rows):
            raise ValueError('Log phải chứa tối đa 2000 JSON object mỗi file.')
        logs[path.name] = rows
    return logs


def run_code(code, root, timeout=5):
    parse(code)
    payload = json.dumps({'code': code, 'logs': load_logs(root)}, ensure_ascii=False)
    if len(payload) >= MAX_INPUT * 2:
        raise ValueError('Payload vượt giới hạn worker.')
    try:
        process = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker'],
                                 input=payload, capture_output=True, text=True, timeout=timeout,
                                 env={}, cwd='/')
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Runtime timeout; worker đã dừng, không tự retry.') from exc
    reply = json.loads(process.stdout)
    if process.returncode or not reply['ok']:
        raise ValueError(reply['error'])
    return validate_result(reply['result'])


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.read(MAX_INPUT * 2))
        runtime = Runtime(request['logs'])
        runtime.block(parse(request['code']).body)
        if len(runtime.output) != 1:
            raise ValueError('Code phải gọi emit đúng một lần.')
        print(json.dumps({'ok': True, 'result': runtime.output[0]}))
    except Exception as exc:
        # Exception có thể chứa giá trị lấy từ log (ví dụ khóa của KeyError).
        # Chỉ trả loại lỗi và hướng dẫn cố định, không trả str(exc)/traceback.
        hints = {
            KeyError: 'Không tìm thấy khóa; kiểm tra tên trường hoặc dùng dict.get.',
            IndexError: 'Chỉ số ngoài phạm vi; kiểm tra độ dài trước khi truy cập.',
            TypeError: 'Kiểu dữ liệu không phù hợp với phép toán hoặc lời gọi hàm.',
            ValueError: 'Code/emit không hợp lệ hoặc vượt giới hạn runtime/step budget.',
        }
        error = type(exc).__name__ + ': ' + hints.get(type(exc), 'Không thể thực thi code trong runtime.')
        print(json.dumps({'ok': False, 'error': error}))
        sys.exit(1)
