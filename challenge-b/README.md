# Challenge B: Quản lý context cho agent

Bài thực hành triển khai yêu cầu Challenge B ở slide 32–33 của tài liệu môn học: rút gọn context nhưng bảo toàn trạng thái công việc (B1 – Compaction) và phân tích nhiều file log bằng code mà không đưa log thô vào context (B2 – Code Mode). Python điều phối các lượt gọi model qua Codex CLI, kiểm tra kết quả và ghi nhận `usage.input_tokens`.

## Yêu cầu

- Python 3.9 trở lên, chỉ sử dụng thư viện chuẩn.
- Codex CLI đã đăng nhập bằng `codex login` và có kết nối mạng khi gọi model.

Các lệnh dưới đây được thực hiện trong cùng một phiên Terminal, tại thư mục `challenge-b/`.

## Quy trình chạy và thu thập minh chứng

### 1. Kiểm tra môi trường và kiểm thử tự động

Từ thư mục gốc repository:

```sh
cd challenge-b
python3 --version
codex --version
codex login status
python3 -B -m unittest discover -s tests -v
```

Điều kiện tiếp tục: Codex đã đăng nhập và bộ kiểm thử kết thúc với trạng thái `OK`. Kiểm thử tự động không gọi model và không sử dụng quota Codex.

### 2. Chạy B1 và B2 với model thật

```sh
CHALLENGE_B_RUN="evidence/bao-cao-$(date +%Y%m%d-%H%M%S)"
python3 -u -B demo.py --codex --part all --baseline read_file --output "$CHALLENGE_B_RUN"
```

Chương trình tạo dữ liệu mới, chạy B1 rồi B2 và tự kiểm lại kết quả ở cuối. Lệnh sử dụng quota Codex. Thư mục kết quả được in ở dòng `Evidence:`; dữ liệu các lần chạy trước được giữ nguyên.

Chờ lệnh kết thúc và Terminal trở lại dấu nhắc lệnh. Một lần chạy đầy đủ phải có `status: passed`, `llm_executed: true` và hai mục `b1`, `b2` trong phần `verified` cuối cùng. Nếu có `FAILED`, traceback hoặc kết quả chưa đạt, lần chạy chưa đủ điều kiện làm minh chứng hoàn tất.

Nếu timeout, chương trình lưu trạng thái thất bại và dừng; không tự gửi lại request. Baseline đọc từng file chờ tối đa 240 giây mỗi lượt model, các lượt khác tối đa 90 giây.

### 3. Kiểm lại và hiển thị kết quả đã lưu

```sh
python3 -B demo.py --verify "$CHALLENGE_B_RUN"
```

Lệnh đọc evidence của lần chạy ở bước 2, đối chiếu prompt, phản hồi, trace, usage và chạy lại chương trình phân tích log. Lệnh không gọi thêm model. Kết quả kiểm lại phải có `status: passed` và đủ hai phần `b1`, `b2`.

Biến `CHALLENGE_B_RUN` chỉ tồn tại trong phiên Terminal đã khai báo. Khi mở Terminal khác, cần gán lại biến bằng đường dẫn được ghi ở dòng `Evidence:` của lần chạy cần kiểm chứng.

### 4. Hiển thị số liệu và kiểm tra context

```sh
python3 -B - "$CHALLENGE_B_RUN" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for part in ("b1", "b2"):
    folder = root / part
    report = json.loads((folder / "result.json").read_text())
    print("\n" + part.upper() + " - INPUT TOKENS")
    print(json.dumps(report["usage"], ensure_ascii=False, indent=2))
    print("\n" + part.upper() + " - KIEM CHUNG")
    print(json.dumps(report["checks"], ensure_ascii=False, indent=2))

print("\nCODE MODE - KIEM TRA LOG THO TRONG PROMPT")
for path in sorted((root / "b2").glob("code-*.input.txt")):
    print(path.name, "| raw log marker present:", "RAW_LOG_ONLY" in path.read_text())
PY
```

Các prompt Code Mode của lần chạy đạt yêu cầu có kết quả `raw log marker present: False`; các bước kiểm chứng có giá trị `true`. Việc tìm dấu nhận diện log là một kiểm tra trên dữ liệu giả lập, được dùng cùng với đối chiếu cấu trúc prompt và trace ở bước 3.

### 5. Nội dung ảnh minh chứng

| Ảnh | Nội dung cần thể hiện | Nguồn hiển thị |
|---|---|---|
| 1 | Checkpoint giữ lỗi đang mở, các cách đã thử, bước tiếp theo và câu trả lời sau compact | Kết quả bước 3, phần B1 |
| 2 | Code do model sinh và số liệu tổng hợp runtime trả về | Kết quả bước 3, phần B2 |
| 3 | Số input token trước/sau compact và baseline/Code Mode | Kết quả bước 4, các mục `INPUT TOKENS` |
| 4 | Kết quả kiểm chứng B2 và kiểm tra log thô trong prompt | Kết quả bước 4, phần cuối |
| 5 | Số kiểm thử đã chạy và trạng thái `OK` | Kết quả bước 1 |

Báo cáo sử dụng số liệu từ cùng lần chạy với ảnh minh chứng. Số token và nội dung model trả lời có thể thay đổi giữa các lần chạy; không dùng số token của lần chạy khác để mô tả ảnh mới.

## Các chế độ bổ sung

Kiểm tra dữ liệu giả lập và runtime bằng chương trình mẫu, không gọi model:

```sh
python3 -B demo.py
```

Chế độ này có trạng thái `offline_validated`, không dùng để kết luận model đã tạo checkpoint hoặc tự viết code.

Chạy riêng từng phần với model thật:

```sh
python3 -u -B demo.py --codex --part b1
python3 -u -B demo.py --codex --part b2 --baseline read_file
```

Phép so sánh khác, gửi toàn bộ raw log trong một prompt:

```sh
python3 -u -B demo.py --codex --part b2 --baseline raw
```

Baseline `raw` và `read_file` là hai phương pháp riêng; báo cáo cần ghi đúng phương pháp được sử dụng. Có thể thay bộ dữ liệu bằng tham số `--seed`, ví dụ `--seed 29`.

## Kết quả và dữ liệu sinh ra

Mỗi thư mục chạy chứa log giả lập, prompt, response, event usage và kết quả đối chiếu. Tên thư mục được in ngay khi bắt đầu. `--output PATH` chỉ nhận đường dẫn chưa tồn tại, không ghi đè lần chạy trước.

Kiểm tra một lần chạy đã hoàn tất mà không gọi lại model:

```sh
python3 -B demo.py --verify /duong/dan/thu/muc/ket/qua
```

Repository giữ bộ minh chứng đã chọn tại [`evidence/bao-cao-20261027-090612/`](evidence/bao-cao-20261027-090612/). Các thư mục kết quả mới, cache và `.env` được Git bỏ qua mặc định. Dữ liệu đầu vào được tạo lại bằng `scenarios.py`.

## Báo cáo và minh chứng bàn giao

- [`ChallengeB_Nhom9.pdf`](ChallengeB_Nhom9.pdf): báo cáo gồm phương pháp, kết quả, ảnh minh chứng và giới hạn kết luận.
- [`evidence/bao-cao-20261027-090612/summary.json`](evidence/bao-cao-20261027-090612/summary.json): trạng thái lần chạy với model thật, gồm đủ B1 và B2.
- [`b1/result.json`](evidence/bao-cao-20261027-090612/b1/result.json): kết quả compaction, kích thước dữ liệu và token từng lượt.
- [`b2/result.json`](evidence/bao-cao-20261027-090612/b2/result.json): kết quả Code Mode và so sánh với baseline đọc từng file.
- [`b2/native/result.json`](evidence/bao-cao-20261027-090612/b2/native/result.json): các lượt đọc file của baseline và tổng input token.

Kiểm lại bộ minh chứng bàn giao sau khi tải repository, tại thư mục `challenge-b/`:

```sh
python3 -B demo.py --verify evidence/bao-cao-20261027-090612
```

Lệnh không yêu cầu đăng nhập Codex hoặc kết nối mạng, không gọi model. Bộ kiểm chứng đọc prompt, phản hồi, sự kiện usage và trace trong thư mục hiện tại, rồi chạy lại chương trình phân tích log. Các đường dẫn tuyệt đối trong metadata ghi nhận môi trường chạy gốc; việc kiểm chứng không phụ thuộc vào các đường dẫn đó.

Kết quả lần chạy ngày 27/10/2026:

| Chỉ số | Kết quả |
|---|---|
| Kích thước dữ liệu phiên B1 | 43.371 → 1.571 byte UTF-8 |
| Input token lượt tiếp tục B1 | 27.372 → 15.504, giảm 43,36% |
| Input token tạo checkpoint B1 | 27.403 |
| Tổng input token tạo checkpoint và tiếp tục B1 | 42.907 |
| Dữ liệu B2 | 6 file, 360 bản ghi, 74 bản ghi ERROR |
| Tổng input token B2 | Baseline đọc từng file: 217.336; Code Mode: 31.217, giảm 85,64% |

Các con số trên mô tả bộ minh chứng được bàn giao; lần chạy mới có thể cho số token khác.

## Cấu trúc

| Thành phần | Chức năng |
|---|---|
| `demo.py` | CLI chạy, in kết quả và kiểm lại một lần chạy |
| `context_agent.py` | B1, Code Mode và kiểm tra action JSON |
| `native_baseline.py` | Baseline model đọc từng file |
| `code_runtime.py` | Runtime diễn giải tập con Python có giới hạn |
| `model_transport.py` | Gọi Codex CLI, lưu phản hồi và usage |
| `scenarios.py` | Sinh lịch sử điều tra và các file log giả lập |
| `example_program.py.txt` | Chương trình mẫu chỉ dùng trong chế độ offline và kiểm thử |
| `tests/` | Kiểm thử runtime, điều phối, baseline và verifier |

## Phạm vi

B1 kích hoạt compact khi JSON session vượt 20.000 byte UTF-8; checkpoint tối đa 6.000 byte. Đây là ngưỡng của demo, không phải số token. Python quản lý logical session và gửi context chủ động qua các thread CLI tạm riêng, không dùng auto-compaction của Codex.

Baseline `read_file` sử dụng các hành động JSON `list_logs` và `read_log` do model chọn. Python thực thi một hành động mỗi lượt; các bản ghi log được tích lũy trong context cho đến khi model trả lời. Giao thức công cụ được triển khai tại ứng dụng. Với Code Mode, model viết chương trình xử lý dữ liệu trong runtime và chỉ nhận kết quả tổng hợp.

B2 dùng mặc định 6 file, 360 bản ghi. Runtime diễn giải AST của tập con Python, không dùng `eval`/`exec` để chạy code model. Runtime không cung cấp shell, mạng hay quyền đọc file tùy ý; có giới hạn kích thước dữ liệu, số bước, thời gian chạy và output. Lỗi trong worker chỉ trả loại lỗi và hướng dẫn cố định, không trả giá trị exception có thể chứa log. Đây là runtime phục vụ bài tập, chưa phải sandbox Python tổng quát cho production.

Dữ liệu điều tra và log là giả lập; checkpoint và code ở chế độ `--codex` do model tạo. Kiểm thử điều phối dùng model giả lập để kiểm tra ứng dụng; bằng chứng phản hồi của model thật được thu riêng qua chế độ `--codex`. Token lấy từ usage CLI, bao gồm phần context nội bộ của CLI. Tổng input của Code Mode tính tất cả lượt viết code, sửa code nếu có và trả lời cuối; baseline tính tất cả lượt đọc dữ liệu và trả lời. B1 ghi riêng token tạo checkpoint và token của lượt tiếp tục; context nhỏ hơn không tự chứng minh tổng token thấp hơn. Tỷ lệ giảm token chỉ mô tả lần chạy và dữ liệu đã đo.
