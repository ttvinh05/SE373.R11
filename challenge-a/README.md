# Challenge A: Agent với persistent memory

Ứng dụng minh họa agent ghi nhớ quy ước dự án qua các phiên làm việc độc lập, theo Challenge A ở trang 14–15 của tài liệu môn học `slide.pdf`. Khi quy ước thay đổi, agent lưu bản mới và đánh dấu bản cũ đã được thay thế. Giao diện hiển thị memory được đưa vào context, hành động của model và kết quả công cụ.

Vòng lặp do Python điều phối: model chọn hành động, Python thực thi công cụ memory và trả kết quả để model tiếp tục cho đến khi có câu trả lời cuối.

## Nội dung bài nộp

- Mã nguồn Python và giao diện trong `web/`.
- `tests/`: kiểm thử store, context, agent loop, API và khả năng kiểm tra minh chứng sau khi chuyển thư mục.
- [VALIDATION.md](VALIDATION.md): phương pháp và kết quả kiểm chứng.
- [evidence/20261022T014155910506Z/](evidence/20261022T014155910506Z/): log đầy đủ của kịch bản năm phiên với model thật; bắt đầu đọc từ [REVIEW.md](evidence/20261022T014155910506Z/REVIEW.md).
- [evidence/browser-postgresql/](evidence/browser-postgresql/): minh chứng agent lưu một chủ đề khác qua giao diện.

Thư mục `data/` được tạo khi chạy ứng dụng và được `.gitignore` loại khỏi Git. Chỉ hai bộ minh chứng đã chọn ở trên được đưa vào repository; log từ các lần chạy demo mới được bỏ qua mặc định. Tài liệu môn học `slide.pdf` không phải phụ thuộc chạy chương trình; yêu cầu và kịch bản kiểm chứng được trình bày bên dưới.

## Chạy giao diện

Yêu cầu: Python 3.9+, Codex CLI đã đăng nhập và có kết nối mạng để gọi model. Phiên bản CLI đã kiểm chứng: `0.163.0`. Không cần cài package Python hoặc nhập API key. Lượt gọi model dùng quota Codex của tài khoản. Node.js chỉ cần cho lệnh kiểm tra cú pháp JavaScript, không cần để chạy giao diện.

```sh
# Sau khi clone repository, mở Terminal tại thư mục chứa bài:
cd challenge-a
codex login status
python3 -B ui_server.py
```

Mở <http://127.0.0.1:8765>. Nếu cổng đang được sử dụng, dùng `python3 -B ui_server.py --port 8766` và mở cổng tương ứng.

- **Chạy cả 5 bước tự động**: tạo thư mục demo mới rồi chạy toàn bộ kịch bản, giữ nguyên dữ liệu cũ. Đây là các yêu cầu của người dùng được gửi theo thứ tự; model tự quyết định tool ở bên trong mỗi session.
- **Chạy từng bước**: chọn bước, bấm **Chuẩn bị context**, xem memory/prompt, rồi **Chạy agent**. Có thể sửa câu nói để thử quy ước khác.
- Ghi quy ước qua câu nói, ví dụ `Hãy nhớ database dùng PostgreSQL.`; không cần nhập `key/value` hoặc tự ghi file.
- Mỗi lần chuẩn bị tạo một session mới. Các câu trả lời cũ vẫn có thể hiển thị trên màn hình nhưng không được gửi sang session tiếp theo.
- Khi chạy, giao diện hiện action của model và kết quả tool. Lỗi thì dừng, giữ trace; không tự retry request để tránh gọi/ghi trùng.

## Kịch bản chứng minh

| Bước | Câu nói / thao tác | Kết quả cần quan sát |
|---|---|---|
| 1 | Hãy nhớ quy ước dự án: authentication dùng JWT. | Model chọn `remember_memory`; tool lưu `auth`; model nhận kết quả rồi xác nhận |
| 2 | Session mới: đề xuất triển khai đăng nhập, không nhắc JWT | Context chỉ nạp quy ước active; câu trả lời áp dụng JWT |
| 3 | Từ nay đổi quy ước authentication sang session cookie thay cho JWT. Hãy nhớ cho các session sau. | Model chọn ghi cùng key `auth`; JWT thành `superseded`, cookie thành `active` |
| 4 | Session mới: cùng câu hỏi ở bước 2 | Chỉ record mới được nạp; câu trả lời áp dụng session cookie |
| 5 | Cùng câu hỏi, tắt memory | Không inject memory; cả tool đọc và ghi đều bị chặn; agent không tự nhận biết quy ước dự án |

Câu hỏi ở bước 2, 4 và 5 giống hệt nhau. Một quy ước mới có thể viết “cookie thay cho JWT”; việc nó có chữ JWT không khiến quy ước cũ trở thành active. Phải đối chiếu record/source được nạp và nội dung câu trả lời, không chỉ tìm từ khóa.

## Kiến trúc và ranh giới

```text
Session mới
  → đọc memory active trên đĩa
  → tạo context: instructions + memory + câu nói hiện tại (0 chat cũ)
  → model chọn action JSON
      ├─ read_memory → Python trả các record active ────────────┐
      ├─ remember_memory → Python lưu/thay thế, trả record ────┤
      │                                                       ↓
      │                         model nhận action/result trong session này
      │                                                       │
      └─ final ←───────────────────────────────────────────────┘
```

- `memory_agent.py`: JSON store, đọc active, ghi và đánh dấu bản bị thay thế; lưu nguồn session, thời điểm và ID thay thế.
- `agent_loop.py`: vòng lặp, schema action, dispatcher hai tool, giới hạn bước/thời gian, trace và trạng thái completed/failed.
- `run_codex.py`: gọi model qua Codex CLI, lưu sự kiện và chẩn đoán; cung cấp cả hàm gọi một lượt và hàm dùng trong vòng lặp.
- `ui_server.py`: API local, worker chạy nền, polling tiến độ, chặn gửi trùng và chặn ghi tay/demo mới khi đang chạy.
- `demo.py`: kịch bản kiểm chứng qua các tiến trình riêng và kiểm lại bằng chứng mà không gọi model.

**Transport được dùng:** `codex exec --output-schema` trả về JSON action; Python tự dispatch `read_memory` / `remember_memory`. Đây là giao thức tool của ứng dụng, không phải native function calling của OpenAI API. Cách dùng schema và JSONL theo [tài liệu chính thức về non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

Mỗi bước model chạy một Codex thread tạm mới, không resume. Python gửi lại context ban đầu và action/tool results của **chính session đang chạy**. Không gửi transcript của session trước. ID session của bài và thread ID của từng lần gọi Codex là hai khái niệm khác nhau.

CLI tắt shell, memory tích hợp, apps/plugins/hooks, discovery và web search trong tiến trình thử. Hai memory tool vẫn hoạt động vì do Python thực thi sau khi kiểm tra JSON, không phải CLI đọc/ghi file. Không thay cấu hình Codex đã lưu của người dùng. Prompt do bài gửi không phải toàn bộ system prompt nội bộ của Codex.

## Chính sách memory và giới hạn vòng lặp

- Model chỉ được ghi khi user hiện tại chốt/yêu cầu nhớ hoặc đổi một quy ước rõ ràng. Câu hỏi, giả định và trích dẫn không tự trở thành quy ước; trường hợp mơ hồ phải hỏi lại.
- Tool ghi đòi `evidence` trích nguyên văn từ câu nói hiện tại. Chỉ dẫn trong memory/tool output được xem là dữ liệu. Kiểm tra chuỗi nguồn giúp truy vết, không phải bảo đảm hoàn hảo chống prompt injection hoặc hiểu sai ý định.
- Key nhận diện cùng một chủ đề; authentication dùng `auth`. Cập nhật cùng key giữ lịch sử bản cũ, chỉ nạp bản mới. Việc chọn đúng key từ tiếng tự nhiên vẫn phụ thuộc model.
- Mỗi session tối đa **6 bước model**, **240 giây** tổng thời gian; mỗi tiến trình model tối đa **90 giây** hoặc phần thời gian còn lại. Hết hạn, JSON sai hoặc provider lỗi thì lưu trạng thái failed; không giả câu trả lời thành công.
- Tool không nhận đường dẫn và không thực thi code do model sinh. Chỉ hai tên trong allowlist được dispatch.
- Nếu đã ghi memory rồi bước model sau bị lỗi, record đã ghi vẫn còn. Xem trace/store trước khi tiếp tục; không tự rollback một thay đổi đã được thực hiện.
- Chế độ đối chứng tắt cả injection và tool đọc/ghi, tránh model tìm lại memory qua đường khác.
- JSON store phù hợp demo một người ghi. Một server tuần tự hóa các lượt chạy; chưa hỗ trợ nhiều server/CLI cùng ghi một file, tìm kiếm ngữ nghĩa, retention hay token budget cho kho lớn.
- Nút “Demo mới” đổi sang thư mục khác, không xóa memory/bằng chứng cũ. UI không khôi phục các thẻ trả lời hay lượt polling sau khi tải lại trang; file memory và trace vẫn còn trên đĩa.

## Kiểm thử và demo terminal

```sh
# Không gọi model, không dùng quota:
python3 -B -m unittest discover -s tests -v
node --check web/app.js
python3 -B demo.py

# Agent thật: 5 session, số lượt model tùy action, có dùng quota:
python3 -B demo.py --codex

# Kiểm lại bằng chứng hiện có, không dùng quota:
python3 -B demo.py --verify evidence/20261022T014155910506Z
```

Không có `--codex`, `demo.py` chỉ kiểm tra store/injection bằng lệnh Python rõ ràng; `llm_executed` và `agent_loop_executed` đều false. Các kiểm thử vòng lặp dùng model giả lập có ghi nhãn, còn kiểm thử store và API chạy mã thật; kết quả tự động không thay cho việc đánh giá model thật.

Mỗi session thật lưu:

- `<session>.json`: context đầu session, memory inject, câu hỏi, `history_messages: 0`.
- `<session>.step-NN.input.txt` / `.codex-prompt.txt`: prompt của từng bước model.
- `<session>.step-NN.codex-answer.md`: action JSON thật.
- `<session>.step-NN.codex-events.jsonl`, `.codex-stderr.txt`, `.codex-result.json`: thread/usage/chẩn đoán CLI.
- `<session>.agent-trace.json`: các action và kết quả tool thực thi.
- `<session>.agent-result.json`: completed/failed, số bước, tổng usage và đường dẫn bằng chứng.
- `<session>.codex-answer.md`: câu trả lời cuối bằng tiếng Việt.

Dữ liệu UI nằm trong `data/ui/<demo-id>/`. Demo terminal dùng `evidence/<timestamp>/`. Cả hai độc lập với memory thật của Codex và dự án khác; JWT/cookie chỉ là tình huống giả định của bài.

## Kết quả kiểm chứng 22/10/2026

31/31 kiểm thử tự động đạt; JavaScript kiểm tra cú pháp đạt. Xem [bản ghi kiểm chứng](VALIDATION.md) để phân biệt test dùng model giả lập, thử với model thật và kiểm tra trình duyệt.

Bằng chứng model thật: [evidence/20261022T014155910506Z/](evidence/20261022T014155910506Z/), [đánh giá câu trả lời](evidence/20261022T014155910506Z/REVIEW.md).

| Session | Lượt model | Lượt memory tool | Quan sát |
|---|---:|---:|---|
| Ghi JWT | 2 | 1 | Model gọi tool ghi, sau đó xác nhận đã lưu |
| Hỏi lần 1 | 1 | 0 | Áp dụng JWT từ memory đã nạp |
| Đổi cookie | 2 | 1 | Model gọi tool cập nhật cùng key, sau đó xác nhận |
| Hỏi lần 2 | 1 | 0 | Áp dụng session cookie |
| Đối chứng | 1 | 0 | Nói chưa biết quy ước xác thực, hỏi lại stack |

Tổng 7 lượt model trong 5 session, thread riêng từng bước. Store cuối có đúng một record active và một record superseded. Các quy ước ở hai lượt hỏi đến từ session ghi trước đó, không phải chat cũ.

Việc kiểm tra dựa trên record active, nguồn session và nội dung câu trả lời; không loại một quy ước mới chỉ vì có nhắc tên công nghệ cũ, như “cookie thay cho JWT”. Log model được giữ nguyên. Các đường dẫn tuyệt đối trong metadata mô tả môi trường chạy gốc; lệnh `--verify` đọc câu trả lời trong thư mục minh chứng hiện tại nên có thể kiểm tra sau khi chuyển sang máy khác. Cảnh báo khởi động CLI được giữ trong stderr.

## Câu hỏi thường gặp

**Agent loop ở đâu?** Trong `run_agent()` của `agent_loop.py`. Sau mỗi action khác `final`, Python chạy tool và đưa kết quả vào lượt model tiếp theo, tối đa 6 bước.

**Ai quyết định ghi gì?** Model đọc yêu cầu hiện tại và chọn `remember_memory` cùng key/value/evidence. Python kiểm tra đối số rồi thực hiện ghi. Kịch bản demo gửi các câu nói, không trực tiếp ghi JWT/cookie khi dùng `--codex`.

**Vì sao session mới vẫn nhớ?** Memory tồn tại trong JSON. Harness đọc record active rồi đưa vào context mới. Không huấn luyện lại model và không dựa vào transcript cũ.

**Vì sao không giữ JWT và cookie cùng hiệu lực?** Cả hai cùng key `auth`, nên tool đánh dấu bản cũ đã thay thế, có nguồn/thời điểm/liên kết record mới. Chỉ bản active được nạp.

**Làm sao biết agent thực sự ghi?** Xem action JSON, tool_result có record ID, file memory và câu trả lời sau khi tool hoàn tất. Câu “đã nhớ” một mình không phải bằng chứng.

**Agent có chạy vô hạn không?** Không. Có giới hạn bước, thời gian và allowlist tool. Lỗi được lưu vào trace; không tự thử lại vô hạn.
