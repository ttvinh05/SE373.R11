# Stage 04 — CSV quality script skill

Skill csv-quality được cập nhật đồng bộ script, SKILL.md và reference ở workspace và fixtures. Script bắt buộc --max-hours và trả JSON gồm tổng giờ, người vượt ngưỡng, các dòng bị loại cùng thống kê chất lượng. agent.py, app.py, config.py và tools giữ nguyên bản mẫu.

## Chạy độc lập

Trong thư mục stage-04-script-skill, cài dependencies và cấu hình model:

```bash
uv sync --locked
uv run python scripts/run_ui.py --env-file /path/to/model.env --port 8504
```

File cấu hình riêng sử dụng OPENAI_API_KEY, MODEL_NAME và OPENAI_BASE_URL (tùy chọn); hoặc GEMINI_API_KEY và GEMINI_MODEL. Với Gemini, launcher giữ metadata thought_signature để các lượt tool calling tiếp theo hợp lệ. Adapter không thay đổi logic nghiệp vụ hay đáp án.

Giao diện: http://127.0.0.1:8504. Mỗi trường hợp độc lập bắt đầu bằng Cuộc trò chuyện mới.

## Câu hỏi kiểm tra

1. Kiểm tra data/workload.csv, người nào vượt 8 giờ? Ghi báo cáo vào output/workload.md.
2. Kiểm tra data/workload.csv, người nào vượt 9 giờ? Ghi báo cáo vào output/workload-9.md.
3. Tính tổng giờ theo người trong data/workload.csv và xác định người quá tải.
4. Kiểm tra data/no-such-workload.csv, người nào vượt 8 giờ? Ghi báo cáo vào output/missing-file.md.

## Kiểm tra script trực tiếp

```bash
uv run python workspace/skills/csv-quality/scripts/check_csv.py --input workspace/data/workload.csv --max-hours 8
uv run python workspace/skills/csv-quality/scripts/check_csv.py --input workspace/data/workload.csv --max-hours 9
uv run python workspace/skills/csv-quality/scripts/check_csv.py --input workspace/data/workload-edge.csv --max-hours 0
```

CSV chính: Lan 9 giờ, Minh 3 giờ. Ngưỡng 8 chỉ Lan vượt; ngưỡng 9 không ai vượt. CSV edge: chỉ Minh 0 giờ; E01 đầu tiên sai hours, lần sau vẫn trùng ID. Script chỉ đọc CSV. Phân tích được dữ liệu thì exit 0 kể cả có dòng bị loại; lỗi đọc/schema/parse CSV thì exit 1 và stderr. Thiếu/ngưỡng không hợp lệ thì exit 2.

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
