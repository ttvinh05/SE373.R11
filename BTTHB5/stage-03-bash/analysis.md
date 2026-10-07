# Stage 03 — Python qua Bash, Block 2

Nguồn: https://pub.nndkhoa9.win/agentic-ai-engineering/d05-tool-use-skill-use/exercise-block-2.html

Giữ nguyên agent.py, config.py, app.py và toàn bộ tools của bản mẫu. Thêm workload.csv vào workspace/data và fixtures/data đúng 6 dòng đề cho. Agent có read_file/write_file/bash, tự sinh lệnh Python qua Bash, chưa dùng script csv-quality của stage 04.

Kết quả chạy thật: Lan 9, Minh 3. Được tính: dòng 2/3/4; bỏ dòng 5 hours=abc, dòng 6 T02 trùng dòng 3, dòng 7 thiếu owner. CSV trước/sau giữ nguyên. Trace ghi đầy đủ lệnh Python và stdout.

## Nhận xét cách xử lý

Lệnh sinh trong case CLI xử lý đúng CSV đề cho. Tuy nhiên nó chỉ thêm task_id vào tập seen sau khi dòng hợp lệ và không kiểm tra đầy đủ số hữu hạn/không âm. Vì thế không thể coi đó là thuật toán bảo đảm quy tắc first appearance cho mọi dữ liệu. Stage 04 chuyển các quy tắc này vào script cố định và kiểm thử tự động, gồm trường hợp ID đầu tiên có hours sai.

Phiên UI riêng tính đúng tổng nhưng phần diễn giải gọi nhầm T02 đầu tiên là dòng 2. Khi yêu cầu tính header là dòng 1, model sửa thành dòng 3. ui-results.json giữ nguyên cả câu trả lời và câu sửa; bảng dưới dùng case CLI có số dòng đúng.

## Kiểm chứng

Bộ kiểm thử riêng của stage: **51 passed**. Các test agent dùng mock; case trong bảng dưới chạy riêng bằng Gemini thật. `traces/case-results.json` lưu nguyên câu hỏi/câu trả lời và ánh xạ JSONL. `run_completed` trong trace chạy CLI có câu trả lời; UI dùng observer gốc, câu trả lời đối chiếu ở ui-results.json.

| Case | Trace | Tool result theo dòng JSONL |
|---|---|---|
| python-bash | `20261007-192217_578b4759_turn01_dad8c54f.jsonl` | 5: bash; 9: bash |


Các script launcher/run_cases và adapter chỉ xử lý cấu hình provider. Không chứa API key, không có đáp án hardcode. Có thể chạy từng case: `uv run python scripts/run_cases.py --env-file /duong/dan/model.env --case TEN_CASE`. Bỏ --case mới chạy tất cả, mỗi case bắt đầu bằng conversation mới.
