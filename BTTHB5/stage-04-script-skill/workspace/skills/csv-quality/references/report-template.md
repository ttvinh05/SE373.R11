# Báo cáo chất lượng và khối lượng công việc: `{đường dẫn CSV}`

Công cụ: `skills/csv-quality/scripts/check_csv.py` | exit code: {exit_code}

## Ngưỡng và tổng giờ hợp lệ

Ngưỡng người dùng cung cấp: **{max_hours} giờ**. Quá tải khi tổng giờ lớn hơn ngưỡng; bằng ngưỡng không quá tải.

| Người phụ trách | Tổng giờ từ hours_by_owner | Vượt ngưỡng? |
|---|---|---|
| {owner} | {total_hours} | {đối chiếu overloaded_owners} |

Người quá tải: {danh sách overloaded_owners, hoặc ghi rõ không có ai}.

## Các dòng bị loại

| Dòng CSV | task_id | Tất cả lý do từ excluded_rows |
|---|---|---|
| {line} | {task_id hoặc null} | {reasons} |

Mã lý do: wrong_field_count (sai số trường), missing_task_id (thiếu ID), duplicate_id (ID đã xuất hiện), missing_owner (thiếu người), invalid_hours (giờ không hợp lệ).

Header là dòng 1. Chỉ cộng dòng có đúng số trường, ID/owner không rỗng và giờ hữu hạn không âm. Chỉ giữ lần xuất hiện đầu của ID không rỗng, kể cả lần đó lỗi. Dòng trống được bỏ qua. Tổng này áp dụng cho dữ liệu hợp lệ, không phải mọi dòng gốc.

## Tổng quan chất lượng toàn bộ dữ liệu

| Chỉ số | Giá trị |
|---|---|
| Số dòng dữ liệu không trống | {row_count} |
| Dòng thiếu owner | {missing_owner_count} |
| Dòng hours không hợp lệ | {invalid_hours_count} |
| Số task_id bị lặp khác nhau | {duplicate_id_count} ({duplicate_ids}) |

## Chi tiết lỗi

| Dòng | Cột | Loại | task_id | Mô tả |
|---|---|---|---|---|
| {line} | {column} | {type} | {task_id} | {message} |

## Khuyến nghị

{Đề xuất xử lý dữ liệu lỗi; không tự sửa CSV nguồn.}
