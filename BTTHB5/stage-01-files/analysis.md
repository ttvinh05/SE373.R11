# Stage 01 — File tools, Block 1

Đã thêm và export/đăng ký list_files trong agent có read_file, write_file. Tool trả các mục trực tiếp, sắp tên, name/path/type; dùng cùng kiểm tra đường dẫn/symlink với file tools. Không thêm skill catalog hay nội dung chính sách vào system prompt. Hai chính sách được đặt ở workspace và fixtures.

A: trước tháng 10, 8 ngày >7 nên không hoàn. B: từ tháng 10, 10 ngày <=14, chưa kích hoạt nên hoàn không phí. Đây là kiểm tra tool ở stage 01; quy trình refund-policy và khả năng tìm tài liệu sau đổi tên được chứng minh riêng tại stage 02.

`traces/tool-checks.jsonl`: dòng 1 thư mục chính sách thành công; 2 file không phải thư mục; 3 thư mục thiếu; 4 ../outside; 5 /tmp. Tests bao gồm symlink ra ngoài và không duyệt đệ quy.

## Phân biệt stage 01 và stage 02

Stage 01 cung cấp thao tác file. Stage 02 tái sử dụng các tool đó và bổ sung catalog/skill để chỉ dẫn tìm chính sách, chọn theo ngày mua, hỏi thông tin thiếu và trả lời theo mẫu. Tool cung cấp khả năng quan sát; skill hướng dẫn quy trình. Prompt không tự tạo khả năng liệt kê thư mục khi chưa có tool.

## Kiểm chứng

Bộ kiểm thử riêng của stage: **48 passed**. Các test agent dùng mock; case trong bảng dưới chạy riêng bằng Gemini thật. `traces/case-results.json` lưu nguyên câu hỏi/câu trả lời và ánh xạ JSONL. `run_completed` trong trace chạy CLI có câu trả lời; UI dùng observer gốc, câu trả lời đối chiếu ở ui-results.json.

| Case | Trace | Tool result theo dòng JSONL |
|---|---|---|
| A | `20261007-192417_bfe6fb52_turn01_2d1b4540.jsonl` | 5: list_files; 9: list_files; 13: list_files; 17: read_file; 21: read_file |
| B | `20261007-192439_48dc7dc8_turn01_df9e0e3d.jsonl` | 5: list_files; 9: list_files; 13: list_files; 17: read_file; 21: read_file |


Các script launcher/run_cases và adapter chỉ xử lý cấu hình provider. Không chứa API key, không có đáp án hardcode. Có thể chạy từng case: `uv run python scripts/run_cases.py --env-file /duong/dan/model.env --case TEN_CASE`. Bỏ --case mới chạy tất cả, mỗi case bắt đầu bằng conversation mới.
