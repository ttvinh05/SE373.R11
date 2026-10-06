# -*- coding: utf-8 -*-
"""BTVN#3 · Tool mockup đặt vé máy bay (domain theo slide S21, S37, S41).

Dữ liệu tĩnh. Mỗi tool trả observation CÓ CẤU TRÚC theo đúng nguyên tắc S65:
luôn có `status`, lỗi thì kèm mã lỗi và hướng đi tiếp — không bao giờ trả
chuỗi mơ hồ khiến agent phải tự diễn dịch.

    search_flights(di, den, ngay) -> danh sách chuyến (KHÔNG kèm số ghế trống)
    check_seat(so_hieu, ngay)     -> số ghế trống + giá xác nhận của một chuyến
    book_seat(so_hieu, ngay)      -> giữ ghế, trả mã đặt chỗ (held)
    pay(ma_dat, the)              -> thanh toán mã đặt chỗ (paid)
    get_booking(ma_dat)           -> đọc lại đặt chỗ; sau pay thì confirmed
"""
from __future__ import annotations

import json
from typing import Any, Callable


class KhoChuyenBay:
    """Store chuyến bay + đặt chỗ của MỘT kịch bản. Mỗi lần chạy dùng kho mới.

    mat_ghze_sau_check (s5): sự kiện môi trường — sau lần check_seat thứ N trên
    một chuyến, ghế về 0 (khách khác lấy chỗ) để mô phỏng kho THAY ĐỔI thật
    giữa chừng, không phải bất khả dụng tĩnh như s2.
    """

    TUYEN = ("SGN", "DAD")     # dữ liệu mock chỉ mô phỏng một tuyến

    def __init__(self, chuyen_theo_ngay: dict[str, list[dict]], mat_ghze_sau_check: dict | None = None):
        self._bang = {ngay: {c["so_hieu"]: dict(c) for c in ds}
                      for ngay, ds in chuyen_theo_ngay.items()}
        self.dat_cho: dict[str, dict] = {}
        self._so_dat = 0
        self._mat_ghze = mat_ghze_sau_check
        self._dem_check: dict[tuple[str, str], int] = {}

    def chuyen(self, so_hieu: str, ngay: str | None = None) -> dict | None:
        """Tra chuyến THEO ĐÚNG NGÀY khi biết ngày (VN214 ngày 09/10 là KHÔNG tồn tại)."""
        if ngay is not None:
            return self._bang.get(ngay, {}).get(so_hieu)
        for ds in self._bang.values():
            if so_hieu in ds:
                return ds[so_hieu]
        return None

    def ghi_nhan_check(self, so_hieu: str, ngay: str) -> None:
        """Gọi sau khi trả kết quả check_seat — có thể làm cạn ghế SAU KHI agent kiểm."""
        if not self._mat_ghze or so_hieu != self._mat_ghze.get("so_hieu"):
            return
        if self._mat_ghze.get("ngay", ngay) != ngay:
            return
        key = (ngay, so_hieu)
        self._dem_check[key] = self._dem_check.get(key, 0) + 1
        if self._dem_check[key] >= self._mat_ghze.get("sau_lan", 1):
            c = self.chuyen(so_hieu, ngay)
            if c:
                c["con"] = 0

    def ve(self, ma_dat: str) -> dict | None:
        return self.dat_cho.get(ma_dat)

    def dat_moi(self, so_hieu: str, ngay: str, gio: str) -> dict:
        self._so_dat += 1
        ma = f"4XJ{self._so_dat}"
        c = self.chuyen(so_hieu, ngay)
        self.dat_cho[ma] = {"ma_dat": ma, "so_hieu": so_hieu, "gia": c["gia"],
                            "hoan": c["hoan"], "trang_thai": "held", "paid": False,
                            "ngay": ngay, "gio": gio,
                            "di": self.TUYEN[0], "den": self.TUYEN[1]}
        return self.dat_cho[ma]


# ================================================================ 5 tool mock
def _dinh_dang(v: Any) -> Any:
    """Đảm bảo observation luôn là JSON-được (tool trả dict, không trả văn mơ hồ)."""
    return json.loads(json.dumps(v, ensure_ascii=False, default=str))


def tao_tools(kho: KhoChuyenBay) -> tuple[list[Callable], dict[str, Callable]]:
    """Trả (tools_langchain, tools_dict) cùng cài đặt.

    tools_dict: chạy trực tiếp cho mẫu Plan/Lai (gọi hàm Python thuần).
    tools_langchain: bọc @tool cho create_agent (mẫu ReAct).
    """

    def search_flights(di: str, den: str, ngay: str) -> dict:
        """Tìm chuyến bay một chặng theo ngày. Trả danh sách chuyến kèm giá;
        KHÔNG cho biết còn ghế hay không — phải gọi check_seat từng chuyến."""
        if (di, den) != kho.TUYEN:
            return _dinh_dang({"status": "ok", "di": di, "den": den, "ngay": ngay,
                               "matched": 0, "flights": [],
                               "ghi_chu": f"dữ liệu mock chỉ chứa tuyến {kho.TUYEN[0]}→{kho.TUYEN[1]}"})
        ds = kho._bang.get(ngay)
        if ds is None:
            return _dinh_dang({"status": "ok", "di": di, "den": den, "ngay": ngay,
                               "matched": 0, "flights": [],
                               "ghi_chu": "không có chuyến nào trong dữ liệu ngày này"})
        flights = [{"so_hieu": c["so_hieu"], "gio": c["gio"], "gia": c["gia"],
                    "hoan": c["hoan"]} for c in ds.values()]
        return _dinh_dang({"status": "ok", "di": di, "den": den, "ngay": ngay,
                           "matched": len(flights), "flights": flights})

    def check_seat(so_hieu: str, ngay: str) -> dict:
        """Xem số ghế trống và giá xác nhận của một chuyến NGAY ĐÓ."""
        c = kho.chuyen(so_hieu, ngay)
        if c is None:
            return _dinh_dang({"status": "error", "error": "flight_not_found_on_date",
                               "so_hieu": so_hieu, "ngay": ngay,
                               "hint": "Gọi search_flights đúng ngày để lấy mã chuyến hợp lệ"})
        kq = _dinh_dang({"status": "ok", "so_hieu": so_hieu, "ngay": ngay,
                         "con": c["con"], "gia": c["gia"],
                         "con_cho": c["con"] > 0})
        kho.ghi_nhan_check(so_hieu, ngay)  # chỉ tác động đúng chuyến/ngày vừa kiểm
        return kq

    def book_seat(so_hieu: str, ngay: str) -> dict:
        """Giữ ghế trên chuyến đã check_seat NGAY ĐÓ. Trả mã đặt chỗ (held)."""
        c = kho.chuyen(so_hieu, ngay)
        if c is None:
            return _dinh_dang({"status": "error", "error": "flight_not_found_on_date",
                               "so_hieu": so_hieu, "ngay": ngay,
                               "hint": "Gọi search_flights đúng ngày để lấy mã chuyến hợp lệ"})
        if c["con"] <= 0:
            return _dinh_dang({"status": "error", "error": "flight_full",
                               "so_hieu": so_hieu, "ngay": ngay,
                               "hint": "Chọn chuyến khác còn ghế (check_seat để biết)"})
        c["con"] -= 1                    # giữ chỗ làm giảm tồn kho thật
        ve = kho.dat_moi(so_hieu, ngay, c["gio"])
        return _dinh_dang({"status": "ok", **ve})

    def pay(ma_dat: str, the: str = "corp_card") -> dict:
        """Thanh toán mã đặt chỗ đang held."""
        ve = kho.ve(ma_dat)
        if ve is None:
            return _dinh_dang({"status": "error", "error": "booking_not_found",
                               "ma_dat": ma_dat,
                               "hint": "Gọi book_seat trước để có mã đặt chỗ"})
        if ve["trang_thai"] != "held":
            return _dinh_dang({"status": "error", "error": "wrong_state",
                               "ma_dat": ma_dat, "trang_thai": ve["trang_thai"],
                               "hint": "Chỉ thanh toán được đặt chỗ đang held"})
        ve["trang_thai"], ve["paid"] = "paid", True
        return _dinh_dang({"status": "ok", "ma_dat": ma_dat,
                           "trang_thai": "paid", "so_tien": ve["gia"]})

    def get_booking(ma_dat: str) -> dict:
        """Đọc lại đặt chỗ. Sau khi pay thành công, trạng thái chuyển confirmed."""
        ve = kho.ve(ma_dat)
        if ve is None:
            return _dinh_dang({"status": "error", "error": "booking_not_found",
                               "ma_dat": ma_dat,
                               "hint": "Gọi book_seat trước để có mã đặt chỗ"})
        if ve["trang_thai"] == "paid":
            ve["trang_thai"] = "confirmed"          # hệ thống xác nhận sau thanh toán
        return _dinh_dang({"status": "ok", **ve})

    ham = {"search_flights": search_flights, "check_seat": check_seat,
           "book_seat": book_seat, "pay": pay, "get_booking": get_booking}

    from langchain_core.tools import tool
    tools_langchain = [tool(search_flights), tool(check_seat), tool(book_seat),
                       tool(pay), tool(get_booking)]
    return tools_langchain, ham


if __name__ == "__main__":
    from lib.du_lieu import kich_ban_s1
    kho = KhoChuyenBay(kich_ban_s1().chuyen)
    _, td = tao_tools(kho)
    import json as j
    print(j.dumps(td["search_flights"]("SGN", "DAD", "07/10"), ensure_ascii=False))
    print(j.dumps(td["check_seat"]("VN214", "07/10"), ensure_ascii=False))
    print(j.dumps(td["book_seat"]("VN214", "07/10"), ensure_ascii=False))
    print(j.dumps(td["pay"]("4XJ1"), ensure_ascii=False))
    print(j.dumps(td["get_booking"]("4XJ1"), ensure_ascii=False))
