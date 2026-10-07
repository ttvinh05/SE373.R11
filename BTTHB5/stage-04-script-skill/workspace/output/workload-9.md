# Báo cáo chất lượng và khối lượng công việc: `data/workload.csv`

Công cụ: `skills/csv-quality/scripts/check_csv.py` | exit code: 0

## Ngưỡng và tổng giờ hợp lệ

Ngưỡng người dùng cung cấp: **9.0 giờ**. Quá tải khi tổng giờ lớn hơn ngưỡng; bằng ngưỡng không quá tải.

| Người phụ trách | Tổng giờ từ hours_by_owner | Vượt ngưỡng? |
|---|---|---|
| Lan | 9.0 | Không |
| Minh | 3.0 | Không |

Người quá tải: Không có ai.

## Các dòng bị loại

| Dòng CSV | task_id | Tất cả lý do từ excluded_rows |
|---|---|---|
| 5 | T04 | invalid_hours |
| 6 | T02 | duplicate_id |
| 7 | T05 | missing_owner |

Mã lý do: wrong_field_count (sai số trường), missing_task_id (thiếu ID), duplicate_id (ID đã xuất hiện), missing_owner (thiếu người), invalid_hours (giờ không hợp lệ).

Header là dòng 1. Chỉ cộng dòng có đúng số trường, ID/owner không rỗng và giờ hữu hạn không âm. Chỉ giữ lần xuất hiện đầu của ID không rỗng, kể cả lần đó lỗi. Dòng trống được bỏ qua. Tổng này áp dụng cho dữ liệu hợp lệ, không phải mọi dòng gốc.

## Tổng quan chất lượng toàn bộ dữ liệu

| Chỉ số | Giá trị |
|---|---|
| Số dòng dữ liệu không trống | 6 |
| Dòng thiếu owner | 1 |
| Dòng hours không hợp lệ | 1 |
| Số task_id bị lặp khác nhau | 1 (T02) |

## Chi tiết lỗi

| Dòng | Cột | Loại | task_id | Mô tả |
|---|---|---|---|---|
| 5 | hours | invalid_hours | T04 | hours 'abc' không phải số hữu hạn không âm. |
| 6 | task_id | duplicate_id | T02 | task_id T02 đã xuất hiện ở line 3. |
| 7 | owner | missing_owner | T05 | owner trống. |

## Khuyến nghị

- Bổ sung hoặc chỉnh sửa giá trị `hours` ở dòng 5 (task_id T04) thành số hợp lệ.
- Xử lý dòng 6 bị trùng lặp `task_id` T02 (đã xuất hiện ở dòng 3).
- Bổ sung `owner` cho dòng 7 (task_id T05).
- Không tự sửa file CSV gốc khi chưa có xác nhận từ người quản lý dữ liệu.
