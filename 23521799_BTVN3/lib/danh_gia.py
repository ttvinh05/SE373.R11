# -*- coding: utf-8 -*-
"""BTVN#3 · Chạy ma trận kịch bản × mẫu, thu số liệu, xuất bảng so sánh (yêu cầu 03).

Mỗi cặp dùng kho mới, cùng dữ liệu và harness; chính sách trong model_gia
triển khai theo từng mẫu. Số liệu minh họa cách điều phối của các chính sách
cố định, không đo chất lượng suy luận hay chi phí token của LLM thật.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.du_lieu import KICH_BANS, KichBan
from lib.ket_qua import KetQua
from lib.react_agent import chay_react
from lib.plan_agent import chay_plan
from lib.hybrid_agent import chay_hybrid

MAUS = {"react": chay_react, "plan": chay_plan, "lai": chay_hybrid}

NHAN_STOP = {
    "dat_muc_tieu":     "ĐẠT (đích)",
    "ke_hoach_loi_thoi": "Kế hoạch lỗi thời → bàn giao",
    "can_nguoi":        "Cần người duyệt → bàn giao",
    "lap":              "Phát hiện lặp → bàn giao",
    "be_tac":           "Bế tắc → bàn giao",
    "ngan_sach":        "Hết ngân sách → bàn giao",
    "tran_cung":        "Trần cứng framework → bàn giao",
    "vi_pham_rang_buoc": "Vi phạm ràng buộc → bàn giao",
    "loi_runtime":      "Lỗi runtime → bàn giao",
}


def chay_mot(kb: KichBan, mau: str, che_do_duyet: str = "tu-dong") -> KetQua:
    """Mỗi lần chạy dựng KHO MỚI — không dính đặt chỗ của lần trước."""
    return MAUS[mau](kb, che_do_duyet=che_do_duyet)


def chay_ma_tran() -> list[KetQua]:
    """Ma trận đánh giá LUÔN dùng chế độ duyệt "tu-dong": kết quả phải xác định,
    không phụ thuộc ai đang gõ y/N. Chế độ hỏi/không duyệt chỉ dùng chạy đơn lẻ."""
    ra = []
    for ten_kich_ban, tao_kb in KICH_BANS.items():
        kb = tao_kb()
        for mau in kb.mau_cho_phep:
            ra.append(chay_mot(kb, mau, che_do_duyet="tu-dong"))
    return ra


def bang_so_sanh(danh_sach: list[KetQua]) -> str:
    """Bảng markdown: kết quả + chi phí cho từng cặp kịch bản × mẫu."""
    dong = ["| Kịch bản | Mẫu | Kết quả | Kiểu dừng | Gọi model | Gọi tool | Lập lại KH | Kiểm quyền |",
            "|---|---|---|---|---:|---:|---:|---:|"]
    for kq in danh_sach:
        kb = KICH_BANS[kq.kich_ban.split("_")[0]]()
        ten_kb = kb.ten
        dong.append(
            f"| {ten_kb} | **{kq.mau}** | {'✅ ĐẠT' if kq.dat else '❌ KHÔNG ĐẠT'} "
            f"| {NHAN_STOP.get(kq.stop_type, kq.stop_type)} "
            f"| {kq.model_calls} | {kq.tool_calls} | {kq.lap_ke_hoach} "
            f"| {len(kq.kiem_quyen)} |")
    return "\n".join(dong)


def luu_json(danh_sach: list[KetQua], duong_dan: str = "ket_qua_danh_gia.json") -> Path:
    duong = Path(duong_dan)
    duong.write_text(json.dumps([k.to_dict() for k in danh_sach],
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return duong


if __name__ == "__main__":
    ket_qua = chay_ma_tran()
    print(bang_so_sanh(ket_qua))
    duong = luu_json(ket_qua)
    print(f"\nĐã lưu chi tiết từng lượt chạy vào: {duong}")
