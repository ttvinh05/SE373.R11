# Phương pháp và kết quả kiểm chứng

Ngày kiểm chứng: 22/10/2026. Phạm vi: Challenge A — ghi nhớ quy ước qua các phiên độc lập và cập nhật quy ước khi có thay đổi.

## Kiểm tra tự động

Chạy các lệnh sau tại thư mục gốc của bài nộp:

```sh
python3 -B -m unittest discover -s tests -v
node --check web/app.js
python3 -B demo.py
python3 -B demo.py --verify evidence/20261022T014155910506Z
```

| Kiểm tra | Kết quả | Phạm vi chứng minh |
|---|---|---|
| Bộ kiểm thử Python | 31 kiểm thử, OK | Persistence xuyên tiến trình, thay thế quy ước, context mới, vòng lặp model/tool/result, kiểm tra đối số và nguồn ghi, giới hạn bước/thời gian, xử lý lỗi, chạy nền và chặn gửi trùng |
| Cú pháp JavaScript | Exit code 0 | `web/app.js` hợp lệ về cú pháp |
| Demo offline | PASS | Store và memory injection; không gọi model |
| Kiểm lại minh chứng model thật | PASS | Store, context và tool trace của năm phiên đã lưu |
| Kiểm tra bản sao ở thư mục khác | PASS | Các lệnh kiểm thử và xác minh minh chứng không phụ thuộc đường dẫn máy gốc |

Hai kiểm thử hồi quy kiểm tra việc đọc câu trả lời sau khi chuyển thư mục và từ chối trường hợp thư mục minh chứng thiếu câu trả lời dù file ở vị trí cũ vẫn tồn tại. Metadata lịch sử được giữ nguyên; trình kiểm tra đọc các file trong thư mục hiện tại.

Các kiểm thử vòng lặp dùng model giả lập để tái hiện có kiểm soát tình huống thành công và lỗi. Chúng kiểm tra hành vi chương trình, không đánh giá khả năng hiểu tiếng tự nhiên của model thật.

## Thử nghiệm với model thật

[Kịch bản năm phiên](evidence/20261022T014155910506Z/REVIEW.md) có tổng cộng bảy lượt model. Mỗi phiên chạy bằng một tiến trình Python riêng, không nhận transcript của phiên trước:

1. Agent gọi công cụ lưu quy ước JWT, nhận kết quả rồi xác nhận.
2. Phiên mới áp dụng JWT từ memory đã nạp.
3. Agent gọi công cụ đổi quy ước sang session cookie; JWT được đánh dấu `superseded`.
4. Phiên mới áp dụng session cookie từ record `active`.
5. Phiên đối chứng tắt memory nói chưa biết quy ước xác thực.

[Thử nghiệm PostgreSQL qua giao diện](evidence/browser-postgresql/63a96189-b59b-4101-9688-fc6d4e8a3abd.agent-result.json) dùng câu “Hãy nhớ quy ước dự án: database dùng PostgreSQL.” Agent chọn key `database`, ghi bằng công cụ rồi xác nhận, với hai bước model và một lượt công cụ. Memory vẫn hiển thị sau khi tải lại trang. Ca này bổ sung bằng chứng rằng agent có thể chọn chủ đề khác ngoài authentication.

Các file request, action, tool result, câu trả lời, sự kiện CLI và store được giữ nguyên để đối chiếu. `summary.json` là kết quả kiểm tra cấu trúc; đánh giá nội dung câu trả lời nằm trong `REVIEW.md`.

## Kiểm tra giao diện

Các thao tác được kiểm tra bằng Chrome DevTools trong browser context riêng:

- Với model thật: chuẩn bị context, gửi yêu cầu ghi PostgreSQL, quan sát action/tool result và đối chiếu câu trả lời với file trên đĩa.
- Với model giả lập có nhãn `TEST DOUBLE`: chạy tự động đủ năm bước; giao diện hiện năm thẻ trả lời, cookie active và JWT superseded. Ca này kiểm tra frontend/API/worker, không dùng để kết luận về model thật.
- Kiểm tra bố cục desktop 1440px và màn hình hẹp 320px. Ở màn hình hẹp, `document.scrollWidth` và `innerWidth` đều bằng 320, không tràn ngang.
- Console không có error/warn/issue trong các lượt kiểm tra.
- Nội dung model và người dùng được hiển thị dưới dạng văn bản, không được thực thi như HTML.

## Phạm vi và giới hạn

Kết quả trên đáp ứng kịch bản Challenge A. Đây là kiểm chứng trên các ca đã lưu, không phải đánh giá thống kê hay bảo đảm model luôn hiểu đúng ý định và chọn đúng key.

JSON store giả định một server/người ghi tại một thời điểm. UI không khôi phục thẻ trả lời hoặc polling sau khi tải lại trang; memory và log vẫn được lưu trên đĩa. Khi vòng lặp lỗi sau một thao tác ghi thành công, record đã ghi được giữ lại và trạng thái lỗi được ghi vào trace.

JWT, cookie và PostgreSQL trong minh chứng là dữ liệu tình huống của bài tập. Thông tin đăng nhập Codex không được lưu trong repository; `data/` và log demo mới được `.gitignore` loại khỏi Git. Việc chạy lại model cần tài khoản Codex của người thực hiện.
