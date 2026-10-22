# Đánh giá minh chứng Challenge A với model thật

Ngày thử nghiệm: 22/10/2026. Phạm vi: năm session agent độc lập, bảy lần gọi model qua Codex CLI; mỗi session chạy từ một tiến trình Python riêng. Việc đánh giá đối chiếu các câu trả lời với request JSON, action/tool trace và store cuối.

| Yêu cầu | Bằng chứng | Đánh giá |
|---|---|---|
| Agent tự ghi từ câu nói | [Trace ghi JWT](session-1-write.agent-trace.json) có model action remember_memory, key auth và evidence trích từ user; tool_result trả record thành công; bước 2 model mới xác nhận | Đạt trong ca này |
| Session mới nhớ quy ước | [Request lần 1](session-2-request.json) không có chat cũ, nạp record JWT có nguồn session-1-write; [câu trả lời](session-2-request.codex-answer.md) xác định JWT là quy ước hiện hành và đề xuất cấp/kiểm tra token | Đạt trong ca này |
| Agent cập nhật quy ước | [Trace đổi cookie](session-3-update.agent-trace.json) gọi remember_memory cùng key auth; [store cuối](memory.json) giữ JWT superseded, cookie active, liên kết superseded_by đúng | Đạt trong ca này |
| Session sau dùng bản mới | [Request lần 2](session-4-request.json) chỉ nạp record cookie có nguồn session-3-update; [câu trả lời](session-4-request.codex-answer.md) chọn session phía server, cookie và vòng đời phiên | Đạt trong ca này |
| Kiểm chứng memory đã inject | Các request JSON, prompt từng bước và trace lưu trên đĩa; memory không bị trộn với transcript session trước | Có |
| Đối chứng | [Request đối chứng](control-request.json) có memory_enabled false, injected_memory rỗng; [câu trả lời](control-request.codex-answer.md) nói chưa biết quy ước, hỏi stack và nêu gợi ý có điều kiện | Không tự nhận biết quy ước |

Model không phải lần nào cũng cần gọi read_memory: harness đã nạp toàn bộ record active lúc mở session. Hai session ghi/cập nhật đều có hai bước model, ngăn nhầm một câu “đã nhớ” với hành động lưu thật.

Quy ước mới được model ghi là “Authentication dùng session cookie thay cho JWT.” Chữ JWT mô tả việc thay thế; store chỉ có một quy ước active. Vì vậy, tiêu chí kiểm tra là record/source được nạp và cách câu trả lời áp dụng quy ước, thay vì cấm xuất hiện một từ khóa. Các đầu ra model gốc được giữ nguyên.

Để kiểm tra cấu trúc minh chứng, chạy từ thư mục gốc: `python3 -B demo.py --verify evidence/20261022T014155910506Z`. Các đường dẫn tuyệt đối trong log là metadata của máy chạy thử; trình kiểm tra sử dụng file trong thư mục minh chứng hiện tại.

`summary.json` ghi các kiểm tra cấu trúc/store/tool trace. Bảng trên là đánh giá nội dung của ca thử đã lưu; không phải đánh giá thống kê nhiều lần chạy hoặc bảo đảm model luôn chọn đúng key/hiểu đúng ý định. Unit test riêng kiểm tra giới hạn bước/thời gian, tool lạ, đối chứng chặn tool và trường hợp lỗi sau khi đã ghi.
