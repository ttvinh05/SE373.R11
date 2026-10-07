# BTTH5 — Tool Use và Skill Use

**Họ và tên:** Trần Thành Vinh  
**MSSV:** 23521799  
**Lớp:** SE373.R11

## Nội dung

Bài thực hành gồm bốn stage về thao tác file, sử dụng skill và thực thi script qua Bash. Mỗi stage là một project Python độc lập.

| Thư mục | Nội dung | Phân tích và bằng chứng |
|---|---|---|
| [stage-01-files](stage-01-files) | Bổ sung và đăng ký tool list_files | [analysis.md](stage-01-files/analysis.md) |
| [stage-02-skills](stage-02-skills) | Skill refund-policy: chọn chính sách theo ngày mua, tìm tài liệu sau đổi tên, hỏi thông tin thiếu | [analysis.md](stage-02-skills/analysis.md) |
| [stage-03-bash](stage-03-bash) | Sinh và thực thi Python qua Bash để tính tổng giờ theo owner | [analysis.md](stage-03-bash/analysis.md) |
| [stage-04-script-skill](stage-04-script-skill) | Mở rộng csv-quality: kiểm tra dữ liệu, tính tổng và xác định người vượt ngưỡng | [analysis.md](stage-04-script-skill/analysis.md) |


## Kết quả

- Chính sách hoàn tiền: case A không đủ điều kiện (8 ngày > 7 ngày); case B đủ điều kiện (10 ngày <= 14 ngày), không thu phí. Đổi tên tài liệu không làm thay đổi kết luận. Thiếu trạng thái kích hoạt thì agent hỏi lại.
- Workload: Lan 9 giờ, Minh 3 giờ; loại dòng 5 vì hours sai, dòng 6 vì ID trùng và dòng 7 vì thiếu owner.
- Ngưỡng 8: Lan vượt ngưỡng. Ngưỡng 9: không ai vượt. Thiếu ngưỡng thì agent hỏi lại; thiếu file thì báo lỗi thực thi.
- Trường hợp ID đầu tiên có hours sai: lần xuất hiện sau vẫn bị loại vì trùng; Minh 0 giờ được tính hợp lệ.

| Stage | Số kiểm thử đạt |
|---|---:|
| 01 | 48 |
| 02 | 56 |
| 03 | 51 |
| 04 | 74 |

Kiểm thử agent sử dụng mock model. Các lượt chạy Gemini thật được lưu riêng trong traces: JSONL ghi các bước thực thi, case-results.json lưu câu trả lời và ánh xạ tới trace. Stage 04 có JSON chạy script trực tiếp và báo cáo Markdown trong workspace/output.

## Chạy chương trình

Cần Python 3.11+ và uv. Trong thư mục của stage cần kiểm tra:

```bash
uv sync --locked
```

Cấu hình model bằng file môi trường riêng, gồm OPENAI_API_KEY, MODEL_NAME và OPENAI_BASE_URL nếu sử dụng endpoint tương thích. Launcher cũng hỗ trợ GEMINI_API_KEY và GEMINI_MODEL.

```bash
uv run python scripts/run_ui.py --env-file /path/to/model.env --port 8504
```

Mở địa chỉ localhost theo cổng đã chọn. Các ví dụ câu hỏi và lệnh kiểm tra trực tiếp được ghi trong README của từng stage.

```bash
uv run pytest -q
```

