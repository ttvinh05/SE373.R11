# -*- coding: utf-8 -*-
"""BTVN#3 · Dựng agent đặt vé máy bay bằng LangChain — entry point.

Chạy một lượt (in trace):
    python3 agent_dat_ve.py --mau react    --kich-ban s1 --in-trace
    python3 agent_dat_ve.py --mau lai      --kich-ban s2 --in-trace
    python3 agent_dat_ve.py --mau react    --kich-ban s2 --khong-duyet --in-trace
                                                  └── kiểm quyền DỪNG chờ người duyệt

Đánh giá trọn ma trận (yêu cầu 03 — xuất bảng + ket_qua_danh_gia.json):
    python3 agent_dat_ve.py --danh-gia

Tự kiểm 4 lớp harness và tool mockup:
    python3 -m lib.harness && python3 -m lib.tools_ve
"""
from __future__ import annotations

import argparse
import sys

from lib.danh_gia import MAUS, NHAN_STOP, bang_so_sanh, chay_ma_tran, chay_mot, luu_json
from lib.du_lieu import KICH_BANS


def in_ket_qua(kq, in_trace: bool) -> None:
    kb = KICH_BANS[kq.kich_ban.split("_")[0]]()
    print("=" * 78)
    print(f"Kịch bản: {kb.ten} — {kb.mo_ta}")
    print(f"Mẫu     : {kq.mau}")
    print("=" * 78)
    if in_trace:
        for dong in kq.trace:
            print("  " + dong)
        print("-" * 78)
    print(f"Kết quả    : {'✅ ĐẠT tiêu chí hoàn thành (kiểm bằng code)' if kq.dat else '❌ KHÔNG đạt'}")
    print(f"Kiểu dừng  : {NHAN_STOP.get(kq.stop_type, kq.stop_type)}")
    print(f"Chi phí    : {kq.model_calls} lần gọi model · {kq.tool_calls} lần gọi tool"
          + (f" · lập lại kế hoạch {kq.lap_ke_hoach} lần" if kq.mau == "lai" else ""))
    for sk in kq.kiem_quyen:
        print(f"Kiểm quyền : {sk}")
    if kq.rang_buoc:
        print(f"Ràng buộc  : {kq.rang_buoc}")
    print("Câu trả lời:")
    for dong in kq.cau_tra_loi.splitlines():
        print("  " + dong)


def main() -> int:
    p = argparse.ArgumentParser(description="BTVN#3 · agent đặt vé máy bay")
    p.add_argument("--mau", choices=[*MAUS, "tat-ca"], default="react",
                   help="mẫu thiết kế: react | plan | lai | tat-ca")
    p.add_argument("--kich-ban", choices=[*KICH_BANS, "tat-ca"], default="s1",
                   help="kịch bản đánh giá: s1 | s2 | s3 | s4 | s5 | tat-ca")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--duyet-tu-dong", dest="che_do_duyet", action="store_const",
                   const="tu-dong", default="tu-dong",
                   help="người duyệt đồng ý ngay khi cổng kiểm quyền bắn (mặc định)")
    g.add_argument("--hoi-duyet", dest="che_do_duyet", action="store_const",
                   const="hoi",
                   help="hỏi y/N trên terminal trước mỗi hành động vượt thẩm quyền (như demo trên lớp)")
    g.add_argument("--khong-duyet", dest="che_do_duyet", action="store_const",
                   const="khong",
                   help="không ai duyệt → dừng và bàn giao chờ phê duyệt")
    p.add_argument("--in-trace", action="store_true", help="in toàn bộ trace từng vòng")
    p.add_argument("--danh-gia", action="store_true",
                   help="chạy đủ ma trận kịch bản × mẫu và in bảng so sánh")
    args = p.parse_args()

    if args.danh_gia:
        ket_qua = chay_ma_tran()
        print(bang_so_sanh(ket_qua))
        duong = luu_json(ket_qua)
        print(f"\nĐã lưu chi tiết từng lượt chạy vào: {duong}")
        return 0

    kich_bans = list(KICH_BANS) if args.kich_ban == "tat-ca" else [args.kich_ban]
    maus = list(MAUS) if args.mau == "tat-ca" else [args.mau]
    for ten_kb in kich_bans:
        kb = KICH_BANS[ten_kb]()
        for mau in maus:
            if mau not in kb.mau_cho_phep:
                print(f"({kb.ten}: bỏ qua mẫu {mau} — kịch bản này chỉ dành cho {kb.mau_cho_phep})")
                continue
            in_ket_qua(chay_mot(kb, mau, che_do_duyet=args.che_do_duyet), args.in_trace)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
