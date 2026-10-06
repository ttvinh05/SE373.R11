# -*- coding: utf-8 -*-
"""BTVN#3 · Dữ liệu chuyến bay và năm kịch bản đánh giá.

Dữ liệu tĩnh, không gọi mạng, để mỗi lần chạy ra cùng một kết quả — điều
kiện cần để so sánh ba mẫu thiết kế một cách khách quan.

Năm kịch bản (ten, mô tả, biến kiểm soát):

    s1  thuận lợi        dò là thấy, đặt là được            — cả ba mẫu phải đạt
    s2  rào cản tĩnh     chuyến rẻ nhất đã hết ghế từ trước  — Plan giòn, hai mẫu kia thích nghi
    s3  đổi hướng        ngày 07/10 không còn lựa chọn nào  — phải dò thêm ngày 08/10
    s4  model cứng đầu   model lặp lại cùng một hành động   — bẫy để chứng minh lớp phát hiện lặp
    s5  mất ghế          ghế bị lấy sau check, trước book   — kho thay đổi trong lúc chạy

Tình huống s4 chỉ dành cho mẫu ReAct (nơi vòng lặp model → tool lặp tự nhiên).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------- bộ đếm ghế gốc
# "con" là số ghế trống, tool search_flights KHÔNG trả field này — phải check_seat
# mới biết (như slide S37: search trả 12 chuyến, check_seat trả "3 ghế · giá").
CHUYEN_7_10 = [
    dict(so_hieu="VN122", gio="08:00", gia=2_310_000, hoan=False, con=3),
    dict(so_hieu="VJ604", gio="09:30", gia=1_850_000, hoan=False, con=2),
    dict(so_hieu="QH118", gio="10:15", gia=1_980_000, hoan=True,  con=5),
    dict(so_hieu="VN214", gio="08:15", gia=1_480_000, hoan=True,  con=4),
    dict(so_hieu="VJ210", gio="11:40", gia=1_690_000, hoan=False, con=6),
]

CHUYEN_8_10 = [
    dict(so_hieu="VN808", gio="08:00", gia=1_490_000, hoan=True,  con=7),
    dict(so_hieu="VJ809", gio="13:05", gia=1_200_000, hoan=False, con=9),
]


# ---------------------------------------------------------------- mục tiêu
def muc_tieu_goc() -> dict:
    """Ràng buộc là dữ liệu (S62): một dict duy nhất, mọi lớp harness đọc từ đây.

    han_muc_duyet: đặt/trả vé trên mức này hoặc vé không hoàn thì phải xin người duyệt (S41).
    cho_doi_ngay : người dùng cho phép dò thêm 08/10 nếu 07/10 hết lựa chọn.
    """
    return {
        "di": "SGN", "den": "DAD", "ngay": "07/10", "gio_toi_da": "12:00",
        "tran_gia": 2_000_000, "han_muc_duyet": 1_500_000, "cho_doi_ngay": True,
    }


def viet_tien(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"


# ---------------------------------------------------------------- kịch bản
@dataclass
class KichBan:
    ten: str
    mo_ta: str
    chuyen: dict          # {"07/10": [...], "08/10": [...]}
    muc_tieu: dict
    mau_cho_phep: tuple = ("react", "plan", "lai")   # s4 chỉ chạy react
    tinh_cach: str = "chuan"                          # "chuan" | "cung_dau"
    mat_ghze_sau_check: dict | None = None            # s5: sự kiện mất ghế giữa chừng


def _cat_base(het_ghze: tuple = (), sua: dict = None) -> list:
    sua = sua or {}
    ra = []
    for c in CHUYEN_7_10:
        c = replace_dataclass(c, **sua.get(c["so_hieu"], {}))
        if c["so_hieu"] in het_ghze:
            c = replace_dataclass(c, con=0)
        ra.append(c)
    return ra


def replace_dataclass(d: dict, **kw) -> dict:
    return {**d, **kw}


def kich_ban_s1() -> KichBan:
    return KichBan(
        ten="s1_thuan_loi",
        mo_ta="Dò là thấy: VN214 1.480.000đ hoàn được, còn ghế — đặt thẳng.",
        chuyen={"07/10": _cat_base(), "08/10": CHUYEN_8_10},
        muc_tieu=muc_tieu_goc(),
    )


def kich_ban_s2() -> KichBan:
    return KichBan(
        ten="s2_rao_can",
        mo_ta=("VN214 (rẻ nhất thoả ràng buộc) ĐÃ HẾT GHẾ từ trước (mock: bất khả dụng tĩnh) "
               "→ phải chuyển sang VJ210 1.690.000đ KHÔNG hoàn → kích hoạt lớp kiểm quyền (S41)."),
        chuyen={"07/10": _cat_base(het_ghze=("VN214",)), "08/10": CHUYEN_8_10},
        muc_tieu=muc_tieu_goc(),
    )


def kich_ban_s3() -> KichBan:
    return KichBan(
        ten="s3_doi_huong",
        mo_ta=("07/10 hết mọi lựa chọn thoả (rẻ nhất còn ghế là VN214... hết, còn lại "
               "> 2 triệu hoặc hết ghế) → bắt buộc dò thêm ngày 08/10."),
        chuyen={
            "07/10": _cat_base(het_ghze=("VN214", "VJ210", "VJ604"),
                               sua={"QH118": {"gia": 2_050_000}}),
            "08/10": CHUYEN_8_10,
        },
        muc_tieu=muc_tieu_goc(),
    )


def kich_ban_s4() -> KichBan:
    return KichBan(
        ten="s4_cung_dau",
        mo_ta=("Model 'cứng đầu': mỗi lượt vẫn gọi check_seat('VJ604') bất kể quan sát "
               "→ bộ phát hiện lặp phải báo động và bàn giao (S39, S46)."),
        chuyen={"07/10": _cat_base(), "08/10": CHUYEN_8_10},
        muc_tieu=muc_tieu_goc(),
        mau_cho_phep=("react",),
        tinh_cach="cung_dau",
    )


def kich_ban_s5() -> KichBan:
    return KichBan(
        ten="s5_mat_ghze_sau_kiem",
        mo_ta=("Ghế biến mất THẬT giữa chừng — thay đổi kho duy nhất trong bộ kịch bản: "
               "check_seat(VN214) còn 1 ghế, đến lượt đặt thì khách khác đã lấy "
               "(book_seat trả flight_full) → agent phải chuyển sang ứng viên khác."),
        chuyen={"07/10": _cat_base(sua={"VN214": {"con": 1}}), "08/10": CHUYEN_8_10},
        muc_tieu=muc_tieu_goc(),
        mat_ghze_sau_check={"so_hieu": "VN214", "ngay": "07/10", "sau_lan": 1},
    )


KICH_BANS = {
    "s1": kich_ban_s1, "s2": kich_ban_s2, "s3": kich_ban_s3,
    "s4": kich_ban_s4, "s5": kich_ban_s5,
}
