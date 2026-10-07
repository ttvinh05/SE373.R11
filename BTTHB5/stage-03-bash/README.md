# Stage 03 — Python qua Bash

Agent sinh Python và thực thi bằng tool Bash để tính tổng hours theo owner. agent.py, app.py, config.py và tools giữ nguyên bản mẫu. Các script launcher bổ sung cấu hình và adapter tương thích Gemini.

## Chạy độc lập

Trong thư mục stage-03-bash, cài dependencies và cấu hình model:

```bash
uv sync --locked
uv run python scripts/run_ui.py --env-file /path/to/model.env --port 8503
```

File cấu hình riêng sử dụng OPENAI_API_KEY, MODEL_NAME và OPENAI_BASE_URL (tùy chọn); hoặc GEMINI_API_KEY và GEMINI_MODEL. Với Gemini, launcher giữ metadata thought_signature để các lượt tool calling tiếp theo hợp lệ. Adapter không thay đổi logic nghiệp vụ hay đáp án.

Giao diện: http://127.0.0.1:8503. Mỗi trường hợp độc lập bắt đầu bằng Cuộc trò chuyện mới.

## Câu hỏi kiểm tra

1. Dùng Python qua Bash để tính tổng hours theo owner trong data/workload.csv. Không chỉnh sửa file đầu vào. Cho biết cách xử lý dòng lỗi và task_id trùng.

## Kiểm thử và bằng chứng

```bash
uv run pytest -q
```

- analysis.md: mô tả thay đổi, kết quả và vị trí trong trace.
- tests/: kiểm thử tự động, không cần API key.
- traces/case-results.json: câu trả lời model thật và tên trace.
- traces/*.jsonl: request, tool call và kết quả thực thi.
- workspace/output/: file agent tạo, nếu trường hợp yêu cầu ghi báo cáo.

Chạy lại các case model thật (cần cấu hình provider):

```bash
uv run python scripts/run_cases.py --env-file /path/to/model.env
```

workspace chứa dữ liệu đang sử dụng; fixtures dùng để khôi phục workspace. Lệnh uv run python reset_workspace.py xóa output và khôi phục dữ liệu từ fixtures, giữ traces.

Bash chạy với quyền của tiến trình trên máy, không phải sandbox; sử dụng trong môi trường lab với dữ liệu mẫu.
