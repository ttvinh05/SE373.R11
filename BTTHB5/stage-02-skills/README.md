# Stage 02 — Refund policy skill

Agent sử dụng read_file, write_file, list_files và skill refund-policy. Skill hướng dẫn phát hiện tài liệu hiện có, chọn chính sách theo ngày mua, kiểm tra thông tin thiếu và trả lời có căn cứ.

## Chạy độc lập

Trong thư mục stage-02-skills, cài dependencies và cấu hình model:

```bash
uv sync --locked
uv run python scripts/run_ui.py --env-file /path/to/model.env --port 8502
```

File cấu hình riêng sử dụng OPENAI_API_KEY, MODEL_NAME và OPENAI_BASE_URL (tùy chọn); hoặc GEMINI_API_KEY và GEMINI_MODEL. Với Gemini, launcher giữ metadata thought_signature để các lượt tool calling tiếp theo hợp lệ. Adapter không thay đổi logic nghiệp vụ hay đáp án.

Giao diện: http://127.0.0.1:8502. Mỗi trường hợp độc lập bắt đầu bằng Cuộc trò chuyện mới.

## Câu hỏi kiểm tra

1. Tôi mua ngày 28/09/2026, yêu cầu hoàn ngày 06/10/2026, chưa kích hoạt. Tôi có được hoàn không?
2. Tôi mua ngày 02/10/2026, yêu cầu hoàn ngày 12/10/2026, chưa kích hoạt. Tôi có được hoàn không?
3. Tôi mua ngày 02/10/2026, muốn hoàn ngày 12/10/2026.

Kiểm tra đổi tên: đổi hai file trong workspace/data/policies thành document-alpha.md và document-beta.md, giữ nội dung; chạy lại A/B trong conversation mới, đối chiếu list_files, read_file và căn cứ câu trả lời. Khôi phục tên gốc sau kiểm tra.

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
