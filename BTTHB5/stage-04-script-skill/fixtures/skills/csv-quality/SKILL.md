---
name: csv-quality
description: Kiểm tra chất lượng CSV công việc có task_id, owner, hours, tính tổng giờ hợp lệ theo người và xác định người vượt ngưỡng do người dùng cung cấp. Dùng khi người dùng yêu cầu kiểm tra CSV, tính khối lượng công việc hoặc xác định người quá tải; ghi báo cáo Markdown nếu được yêu cầu.
---

# Kiểm tra chất lượng và khối lượng công việc

## Xác định ngưỡng

- Đọc ngưỡng từ yêu cầu hiện tại. Nếu không có ngưỡng, hỏi người dùng trước khi chạy script hoặc kết luận quá tải.
- Không tự chọn ngưỡng và không dùng ngưỡng từ yêu cầu cũ cho yêu cầu hiện tại. Nếu người dùng đang trả lời câu hỏi bổ sung về ngưỡng, dùng giá trị họ vừa cung cấp.
- Ngưỡng phải là số hữu hạn không âm. Nếu không hợp lệ, yêu cầu làm rõ.

## Chạy script

Dùng tool `bash` (cwd là workspace):

```text
python skills/csv-quality/scripts/check_csv.py --input <đường dẫn CSV> --max-hours <ngưỡng người dùng cung cấp>
```

Thay cả hai placeholder bằng giá trị thật; đặt đường dẫn trong dấu nháy khi cần. Không sửa CSV đầu vào. Không cần đọc source script để chạy; chỉ đọc khi cần hiểu hành vi chưa được mô tả.

## Kiểm tra kết quả

- `exit_code` 0: phân tích thành công. `stdout` có các trường chất lượng cũ: `row_count`, `missing_owner_count`, `invalid_hours_count`, `duplicate_id_count`, `duplicate_ids`, `issues`; và các trường `max_hours`, `hours_by_owner`, `overloaded_owners`, `excluded_rows`. Có lỗi dữ liệu hoặc người quá tải vẫn là exit 0.
- `exit_code` khác 0: lỗi đầu vào hoặc tham số CLI. Đọc `stderr`, báo không phân tích được. Không bịa thống kê và không ghi báo cáo như thể đã phân tích.
- `timed_out` true hoặc `ok` false: lệnh không chạy xong; báo lỗi, không suy đoán kết quả.
- Phân biệt lỗi dữ liệu trong `issues` với lỗi thực thi khi exit khác 0.

## Diễn giải và viết báo cáo

1. Đọc `skills/csv-quality/references/report-template.md`.
2. Lấy mọi con số từ JSON của script, không tự đếm bằng mắt.
3. Chỉ cộng các dòng hợp lệ. Giữ lần xuất hiện đầu của mỗi ID không rỗng, kể cả lần đầu lỗi; mọi lần sau bị loại. Owner được trim nhưng phân biệt hoa/thường. Giờ 0 hợp lệ.
4. Quá tải khi tổng lớn hơn ngưỡng; bằng ngưỡng không quá tải. Liệt kê người quá tải theo `overloaded_owners`.
5. Liệt kê `excluded_rows` một lần cho mỗi dòng, kèm tất cả mã lý do. Header là dòng 1. Thống kê chất lượng vẫn xét toàn bộ dòng dữ liệu không trống.
6. Nếu được yêu cầu, ghi báo cáo bằng `write_file` vào đường dẫn người dùng chỉ định (mặc định `output/csv-quality.md`), rồi trả lời đường dẫn và tóm tắt. Phân biệt tổng trên dữ liệu hợp lệ với tổng mọi dòng gốc.
7. Không sửa CSV khi người dùng chỉ yêu cầu kiểm tra. Có thể đề xuất cách sửa trong phần khuyến nghị.
