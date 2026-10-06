# -*- coding: utf-8 -*-
"""BTVN#3 · Kết quả một lượt chạy — các đại lượng dùng để đánh giá (yêu cầu 03)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class KetQua:
    kich_ban: str
    mau: str
    dat: bool = False                 # tiêu chí hoàn thành kiểm bằng code có ĐẠT không
    stop_type: str = ""               # dat_muc_tieu | ke_hoach_loi_thoi | can_nguoi | lap | be_tac | ngan_sach | tran_cung
    model_calls: int = 0              # số lần gọi model (chi phí suy luận)
    tool_calls: int = 0               # số lần gọi tool
    lap_ke_hoach: int = 0             # số lần LẬP LẠI kế hoạch (chỉ mẫu Lai)
    kiem_quyen: list[str] = field(default_factory=list)   # các sự kiện qua cổng kiểm quyền
    rang_buoc: str | None = None      # kết quả check_rang_buoc (lớp 1) khi chốt kết quả
    ban_giao: dict | None = None      # gói bàn giao khi dừng bất thường
    cau_tra_loi: str = ""
    trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
