# BTVN#3 · Dựng agent đặt vé máy bay bằng LangChain

- **Sinh viên:** Trần Thành Vinh · MSSV 23521799
- **Môn:** SE373 — Kỹ thuật xây dựng hệ thống Agentic AI · Bài 03: Agent fundamentals
- **Yêu cầu:** (01) đủ 4 lớp harness — ràng buộc là dữ liệu, tiêu chí hoàn thành kiểm bằng code, kiểm quyền, bàn giao; (02) agent với 3 mẫu thiết kế ReAct / Plan-then-Execute / Lai; (03) đánh giá hiệu quả 3 mẫu.
- **Chạy không cần API key** — model được giả lập bằng chính sách cố định (`lib/model_gia.py`), kết quả xác định và tái lập được.

## Cài đặt

```bash
cd 23521799_BTVN3
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Chạy

```bash
# Một lượt chạy, in trace từng vòng (đổi --mau: react | plan | lai | tat-ca)
python3 agent_dat_ve.py --mau react --kich-ban s1 --in-trace

# Chuyến rẻ nhất đã hết ghế — chuyển chuyến và kiểm quyền
python3 agent_dat_ve.py --mau lai    --kich-ban s2 --in-trace

# Hỏi y/N ngay trên terminal trước hành động vượt thẩm quyền
python3 agent_dat_ve.py --mau react  --kich-ban s2 --hoi-duyet --in-trace

# Không ai duyệt → dừng và bàn giao chờ phê duyệt
python3 agent_dat_ve.py --mau react  --kich-ban s2 --khong-duyet --in-trace

# Model cứng đầu lặp vô ích → bộ phát hiện lặp bắn (S39)
python3 agent_dat_ve.py --mau react  --kich-ban s4 --in-trace

# Đánh giá trọn ma trận kịch bản × mẫu (yêu cầu 03) → bảng + ket_qua_danh_gia.json (ma trận LUÔN dùng chế độ duyệt tự động để kết quả xác định, tái lập được)
python3 agent_dat_ve.py --danh-gia

# Tự kiểm 4 lớp harness và tool mockup
python3 -m lib.harness
python3 -m lib.tools_ve

# Kiểm thử hồi quy ràng buộc, kiểm quyền, ngân sách, lỗi runtime và bàn giao
python3 -m unittest discover -s tests -v
```

## Năm kịch bản

| Kịch bản | Ý nghĩa |
|---|---|
| `s1_thuan_loi` | Dò là thấy, đặt là được — cả ba mẫu phải đạt |
| `s2_rao_can` | Chuyến rẻ nhất thoả ràng buộc **đã hết ghế** → phải chuyển sang vé không hoàn → kích hoạt kiểm quyền |
| `s3_doi_huong` | Ngày 07/10 hết mọi lựa chọn thoả → phải dò thêm ngày 08/10 |
| `s4_cung_dau` | Model cứ gọi lại `check_seat('VJ604')` bất kể quan sát → bẫy chứng minh lớp phát hiện lặp |
| `s5_mat_ghze_sau_kiem` | Ghế biến mất **thật giữa chừng**: check còn 1 ghế, đến đặt thì khách khác đã lấy (`flight_full`) → thử khả năng thích nghi với kho biến động |

Báo cáo nộp: [23521799_BTTH3.pdf](23521799_BTTH3.pdf).

Kiểm chứng: 21 kiểm thử hồi quy; 13 lượt trong ma trận đánh giá trên 5 kịch bản. Plan dừng an toàn ở s2/s3/s5 vì không tự lập lại kế hoạch; s4 cố ý kiểm tra phát hiện lặp. ReAct/Lai đạt s1/s2/s3/s5.

Phạm vi: ReAct dùng `create_agent` và LangGraph; Plan/Lai dùng executor Python với planner chính sách. Số lần gọi model là số lần thử invoke chính sách, không phải đo chi phí token của LLM thật. Ràng buộc được kiểm trước `book_seat`/`pay` và kiểm lại khi hoàn thành. Ngân sách tool của Plan/Lai bao gồm cả lần xác minh cuối.
