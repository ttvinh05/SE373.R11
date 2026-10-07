# Stage 04 — CSV quality script skill, Block 2

Nguồn: https://pub.nndkhoa9.win/agentic-ai-engineering/d05-tool-use-skill-use/exercise-block-2.html

Giữ nguyên agent.py, config.py, app.py và tools của bản mẫu; không thêm tool. Sửa business logic ở skills/csv-quality/scripts/check_csv.py, cập nhật SKILL.md và references/report-template.md; toàn bộ ba file đồng bộ byte-for-byte ở fixtures/skills và workspace/skills.

## Quy tắc thực thi

--max-hours bắt buộc, hữu hạn >=0. Trim ba trường; owner phân biệt hoa/thường. ID không rỗng được giữ ngay lần xuất hiện đầu tiên, kể cả dòng đầu lỗi. Chỉ dòng đúng số cột, ID/owner có giá trị, hours hữu hạn >=0 và không trùng được cộng. Dòng lỗi chứa đủ các reasons theo thứ tự đề; thống kê chất lượng vẫn tính mọi dòng dữ liệu không trắng. Vượt ngưỡng dùng >, không dùng >=.

JSON thêm max_hours, hours_by_owner, overloaded_owners và excluded_rows; danh sách owner và dòng bị loại sắp xếp. Dữ liệu lỗi/quá tải vẫn exit 0; lỗi đọc/schema/parse giữ exit 1 và stderr. Thiếu/ngưỡng không hợp lệ bị argparse từ chối exit 2. Không sửa CSV đầu vào.

## Bằng chứng kết quả

- script-threshold-8.json: Lan 9, Minh 3; Lan vượt 8; loại dòng 5 invalid_hours, 6 duplicate_id, 7 missing_owner.
- script-threshold-9.json: cùng tổng; không ai vượt 9.
- script-edge.json: E01 lần đầu sai hours, lần sau vẫn duplicate; Minh 0 được tính; ngưỡng 0 không ai vượt.
- direct-errors.json: thiếu/ngưỡng âm/nan/inf/abc bị từ chối; thiếu file stdout rỗng, stderr có lỗi, exit 1.
- Model ghi báo cáo thật workspace/output/workload.md và workload-9.md. Thiếu ngưỡng: hỏi lại và không chạy Bash. Thiếu file: Bash exit 1 và không tạo missing-file.md. UI cũng hỏi lại khi một yêu cầu mới không cho ngưỡng dù lượt trước từng dùng 8.
- Tests mới kiểm tra edge invalid-first, 0 hợp lệ, trim/case, nhiều lỗi một dòng, strict threshold, CLI errors, thống kê mọi dòng và input bất biến.

## Câu hỏi cuối bài: script làm gì, model làm gì?

Script thực hiện parse, kiểm tra dữ liệu, giữ ID lần đầu, loại dòng, tính tổng, so ngưỡng và xuất JSON có thể kiểm tra lặp lại. Model chọn skill, hỏi ngưỡng thiếu, truyền đúng tham số cho Bash, đọc exit code/stdout/stderr và trình bày/ghi báo cáo từ kết quả. Model không tự thay phép tính của script.

Nếu chỉ sửa script, SKILL.md cũ có thể gọi thiếu --max-hours và thất bại, hoặc hiểu sai việc có lỗi dữ liệu vẫn được tính từ dòng hợp lệ. Reference cũ có thể bỏ mất ngưỡng, tổng, người vượt và nguyên nhân loại dòng. Vì vậy phải đồng bộ script + hướng dẫn dùng + mẫu báo cáo, ở cả workspace và fixtures để reset không quay lại phiên bản cũ.

## Kiểm chứng

Bộ kiểm thử riêng của stage: **74 passed**. Các test agent dùng mock; case trong bảng dưới chạy riêng bằng Gemini thật. `traces/case-results.json` lưu nguyên câu hỏi/câu trả lời và ánh xạ JSONL. `run_completed` trong trace chạy CLI có câu trả lời; UI dùng observer gốc, câu trả lời đối chiếu ở ui-results.json.

| Case | Trace | Tool result theo dòng JSONL |
|---|---|---|
| threshold-8 | `20261007-192132_7ffce37c_turn01_9ca0d713.jsonl` | 5: read_file; 10: read_file; 11: bash; 15: write_file |
| threshold-9 | `20261007-192155_e4f7af24_turn01_116f6831.jsonl` | 5: read_file; 10: read_file; 11: bash; 15: write_file |
| missing-threshold | `20261007-192221_5709aa55_turn01_92a5f0b9.jsonl` | 5: read_file |
| missing-file | `20261007-192230_9fb3b84d_turn01_173cf133.jsonl` | 5: read_file; 9: bash |


Các script launcher/run_cases và adapter chỉ xử lý cấu hình provider. Không chứa API key, không có đáp án hardcode. Có thể chạy từng case: `uv run python scripts/run_cases.py --env-file /duong/dan/model.env --case TEN_CASE`. Bỏ --case mới chạy tất cả, mỗi case bắt đầu bằng conversation mới.
