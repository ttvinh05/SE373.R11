# -*- coding: utf-8 -*-
"""BTVN#3 · Bốn lớp harness bắt buộc (đề bài yêu cầu 01) + hai lớp phụ trợ.

Bốn lớp yêu cầu — mỗi lớp là code Python thuần, không gọi model, không phụ
thuộc LangChain, cắm được vào cả ba mẫu thiết kế (số 1–4 theo THỨ TỰ ĐỀ BÀI
liệt kê, không phải thứ tự chạy thật):

    1. RangBuoc / check_rang_buoc   ràng buộc là DỮ LIỆU        (S62)
    2. dat_muc_tieu                 tiêu chí hoàn thành kiểm bằng CODE (S43)
    3. canh_bao_quyen / KiemQuyen   kiểm quyền chạy TRƯỚC tool  (S35 check #0, S41)
    4. ban_giao                     bàn giao 4 trường khi dừng bất thường (S48)

THỨ TỰ CHẠY THẬT của mỗi hành động (checklist S35): phát hiện lặp → điều
kiện tiền đề → KIỂM QUYỀN (3, trước tool) → tool thực thi → TIÊU CHÍ HOÀN
THÀNH (2, sau observation); BÀN GIAO (4) khi dừng bất thường; lớp 1 là dữ
liệu mà mọi lớp cùng đọc.

Hai lớp phụ trợ mượn từ kit buổi 03 (lib/harness.py của demo2):
    LoopDetector                    phát hiện lặp + bế tắc     (S45, S46)
    kiem_can_cu / chan_truoc_khi_tra_loi  đối chiếu câu trả lời với quan sát (S58)

Chạy thử:  python3 lib/harness.py
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict


# ================================================== LỚP 1 · RÀNG BUỘC LÀ DỮ LIỆU
@dataclass
class RangBuoc:
    """Yêu cầu người dùng ghi thành dữ liệu, KHÔNG nằm trong prompt (S62).

    Giữ yêu cầu ở một chỗ cố định: mọi bước ("có nên đặt chuyến này không?",
    "đã xong chưa?") đều kiểm tra lại bằng hàm, không dựa vào trí nhớ model.
    """

    di: str
    den: str
    ngay: str            # ngày khách muốn, "07/10"
    ngay_du_phong: str   # ngày được phép dò thêm nếu ngày chính hết lựa chọn
    gio_toi_da: str      # "buổi sáng" ⇒ gio < "12:00"
    tran_gia: int        # trần giá
    han_muc_duyet: int   # đặt/trả vé trên mức này (hoặc vé không hoàn) cần người duyệt
    cho_doi_ngay: bool   # người dùng có cho phép chuyển ngày không

    def hop_le(self, chuyen: dict) -> bool:
        """Lọc giá/giờ của ứng viên; ngày/tuyến kiểm trên record đầy đủ."""
        gia = chuyen.get("gia")
        return (isinstance(gia, (int, float)) and not isinstance(gia, bool)
                and 0 <= gia <= self.tran_gia
                and gio_hop_le(chuyen.get("gio"), self.gio_toi_da))

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def gio_hop_le(gio, gio_toi_da: str) -> bool:
    """Giờ mock dùng HH:MM; dữ liệu sai định dạng phải bị từ chối."""
    if not isinstance(gio, str) or not re.fullmatch(r"\d{2}:\d{2}", gio):
        return False
    try:
        return datetime.strptime(gio, "%H:%M").time() < datetime.strptime(gio_toi_da, "%H:%M").time()
    except (ValueError, TypeError):
        return False


def check_rang_buoc(ve: dict, rb: RangBuoc) -> dict:
    """Kiểm lại đặt chỗ với DỮ LIỆU ràng buộc ngay trước khi trả lời (S62).

    Chỉ kiểm RÀNG BUỘC NHIỆM VỤ: trần giá, ngày được phép, khung giờ, tuyến.
    Quyền tự quyết trên vé không hoàn/vượt hạn mức là việc của LỚP KIỂM QUYỀN
    (lớp 3) — nếu người duyệt đã đồng ý thì đó không phải vi phạm ở đây.
    Ngày được phép = ngày khách hỏi + ngày dự phòng (chỉ khi người dùng cho
    phép đổi ngày trong dữ liệu yêu cầu).
    """
    vi_pham = []
    gia = ve.get("gia")
    if (not isinstance(gia, (int, float)) or isinstance(gia, bool)
            or not 0 <= gia <= rb.tran_gia):
        vi_pham.append(f"giá {gia!r} không hợp lệ hoặc vượt trần {viet_tien_qd(rb.tran_gia)}")
    ngay_duoc_phep = {rb.ngay} | ({rb.ngay_du_phong} if rb.cho_doi_ngay else set())
    if ve.get("ngay") not in ngay_duoc_phep:
        vi_pham.append(f"ngày {ve.get('ngay')!r} không thuộc ngày được phép {sorted(ngay_duoc_phep)}")
    if not gio_hop_le(ve.get("gio"), rb.gio_toi_da):
        vi_pham.append(f"giờ {ve.get('gio')!r} không trước {rb.gio_toi_da}")
    if ve.get("di") != rb.di or ve.get("den") != rb.den:
        vi_pham.append(f"tuyến {ve.get('di')!r}→{ve.get('den')!r} ≠ yêu cầu {rb.di}→{rb.den}")
    return {"dat": not vi_pham, "vi_pham": vi_pham}


def kiem_hanh_dong(tool: str, args: dict, kho, rb: RangBuoc) -> str | None:
    """Chặn vi phạm nhiệm vụ TRƯỚC book/pay, độc lập với model và duyệt chi tiêu."""
    if tool == "book_seat":
        c = kho.chuyen(args.get("so_hieu"), args.get("ngay"))
        ve = ({**c, "ngay": args.get("ngay"), "di": kho.TUYEN[0], "den": kho.TUYEN[1]}
              if c else None)
    elif tool == "pay":
        ve = kho.ve(args.get("ma_dat", ""))
    else:
        return None
    if ve is None:
        return None  # tool trả lỗi lookup có cấu trúc
    kq = check_rang_buoc(ve, rb)
    return "; ".join(kq["vi_pham"]) if not kq["dat"] else None


def trang_thai_ban_giao(kho, **them) -> dict:
    """Lưu record thật kể cả khi exception xảy ra sau một tác dụng phụ."""
    bookings = deepcopy(list(kho.dat_cho.values()))
    cuoi = bookings[-1] if bookings else {}
    return {"ma_dat": cuoi.get("ma_dat"), "trang_thai": cuoi.get("trang_thai"),
            "paid": cuoi.get("paid", False), "dat_cho": bookings, **them}


def viet_tien_qd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"


# ================================== LỚP 2 · TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE
def dat_muc_tieu(ma_dat: str, ham: dict, rb: RangBuoc) -> dict:
    """Quy tắc khách quan độc lập với phán đoán của model (S43 — ĐỦ CÔNG THỨC).

    get_booking(code).status == "confirmed" and paid == True
    and price <= tran_gia and depart_date ∈ ngày được phép and depart_time < "12:00"
    and đúng tuyến

    Ngày được phép = ngày khách hỏi + ngày dự phòng (chỉ khi dữ liệu yêu cầu
    cho phép đổi ngày) — vé ngày khác KHÔNG được tính là đạt. Model TUYÊN BỐ
    "đã xong" không được tin; hàm này chạy bằng code và là điều kiện dừng 1
    (Đạt mục tiêu) duy nhất được phép kết thúc "bình thường".
    """
    kq = ham["get_booking"](ma_dat)
    krc = check_rang_buoc(kq, rb)
    dieu_kien = {
        "status == confirmed": kq.get("trang_thai") == "confirmed",
        "paid == True":        kq.get("paid") is True,
        "tool status == ok": kq.get("status") == "ok",
        "đúng ràng buộc giá/ngày/giờ/tuyến": krc["dat"],
    }
    dat = all(dieu_kien.values())
    return {"dat": dat, "dieu_kien": dieu_kien, "booking": kq}


# ================================================ LỚP 3 · KIỂM QUYỀN (TRƯỚC TOOL)
def canh_bao_quyen(tool: str, args: dict, kho, rb: RangBuoc) -> str | None:
    """Hành động có tác dụng phụ phải qua cổng này TRƯỚC khi thực thi (S35 #0).

    Quy tắc (bám S41): book_seat/pay trên vé KHÔNG HOÀN hoặc giá vượt
    han_muc_duyet thì vượt thẩm quyền — agent phải dừng chờ phê duyệt.
    Trả None nếu được phép, trả chuỗi lý do nếu cần người duyệt.
    """
    if tool not in ("book_seat", "pay"):
        return None
    c = (kho.ve(args.get("ma_dat", "")) if tool == "pay"
         else kho.chuyen(args.get("so_hieu"), args.get("ngay")))
    if c is None:
        return None                          # lỗi tham số — để tool tự trả mã lỗi
    if not c["hoan"]:
        return (f"vé {c['so_hieu']} KHÔNG hoàn, giá {viet_tien_qd(c['gia'])} — "
                f"vượt thẩm quyền tự quyết (hạn mức {viet_tien_qd(rb.han_muc_duyet)}, vé không hoàn)")
    if c["gia"] > rb.han_muc_duyet:
        return (f"giá {viet_tien_qd(c['gia'])} > hạn mức tự quyết "
                f"{viet_tien_qd(rb.han_muc_duyet)}")
    return None


def xin_duyet(hanh_dong: str, ly_do: str, che_do: str) -> bool:
    """Cổng phê duyệt — ba chế độ (S41: agent dừng chờ phê duyệt):

        "tu-dong"  người duyệt đồng ý ngay (cho chạy ma trận đánh giá, xác định)
        "hoi"      hỏi Y/N ngay trên terminal — như demo chọn y/N trên lớp
        "khong"    không ai duyệt → luôn từ chối → dừng + bàn giao chờ người
    """
    if che_do == "tu-dong":
        return True
    if che_do == "hoi":
        print(f"\n⚡ KIỂM QUYỀN — agent định làm: {hanh_dong}")
        print(f"   Lý do vượt thẩm quyền: {ly_do}")
        d = input("   Cho phép thực hiện? [y/N] ").strip().lower()
        return d == "y"
    return False


# =============================================== LỚP 4 · BÀN GIAO CHO CON NGƯỜI
def ban_giao(ly_do: str, da_thu: list, trang_thai: dict, cau_hoi: str) -> dict:
    """Dừng bất thường thì bàn giao đủ 4 trường, không break im lặng (S48).

    "Bàn giao tốt là bàn giao mà người nhận trả lời được trong 30 giây."
    """
    return {"stop_reason": ly_do, "da_thu": da_thu,
            "trang_thai": trang_thai, "cau_hoi_cho_nguoi": cau_hoi}


def in_ban_giao(b: dict) -> str:
    return ("DỪNG BẤT THƯỜNG · " + b["stop_reason"] + "\n"
            "  Đã thử          : " + " → ".join(b["da_thu"]) + "\n"
            "  Trạng thái      : " + str(b["trang_thai"]) + "\n"
            "  Hỏi người dùng  : " + b["cau_hoi_cho_nguoi"])


# ======================================= PHỤ TRỢ · PHÁT HIỆN LẶP (từ kit buổi 03)
def muc_dat_cho(trang_thai: str | None) -> int:
    """Mức tiến trình của đặt chỗ: 0 chưa có · 1 held · 2 paid · 3 confirmed."""
    return {"held": 1, "paid": 2, "confirmed": 3}.get(trang_thai or "", 0)


def do_tien_trien(so_quan_sat_ok: int, stage: int) -> int:
    """Đại lượng TIẾN TRIỂN nghiệp vụ truyền vào LoopDetector.check (S46:
    "progress do bạn truyền vào, là đại lượng của bài toán").

    = số quan sát HỢP LỆ (status ok) đã thu được + 10 × mức tiến trình đặt chỗ.
    Dò thêm ngày, kiểm thêm chuyến (quan sát ok mới) hay đẩy đặt chỗ tiến lên
    thì tăng; gọi mã chuyến không tồn tại (quan sát lỗi) hay bế tắc không thu
    được gì mới thì đứng yên qua N vòng → STALL ("trace bận rộn nhưng vẫn bế
    tắc", S40). Polling get_booking chờ confirmed trả ok mới → không bị nhầm
    là bế tắc — đúng phân biệt polling hợp lệ ở S39.
    """
    return so_quan_sat_ok + 10 * stage


class LoopDetector:
    """Ba tín hiệu (S45): trùng action · trùng observation · không tiến triển."""

    def __init__(self, window=6, repeat_k=3, same_obs_k=4, stall_n=5):
        self.recent = deque(maxlen=window)
        self.obs = deque(maxlen=window)
        self.k, self.k_obs, self.n = repeat_k, same_obs_k, stall_n
        self.last_progress, self.stall = None, 0

    def check(self, tool: str, args: dict, observation=None, progress=None):
        # Đọc lại booking để chờ confirmed là polling hợp lệ. Ngân sách runner
        # vẫn giới hạn tổng số lần thử; không dùng tín hiệu lặp để chặn polling.
        if tool == "get_booking":
            return None
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k:
            return (f"LOOP · '{tool}' gọi {self.recent.count(fp) + 1} lần "
                    f"với cùng tham số trong {self.recent.maxlen} vòng gần nhất")
        self.recent.append(fp)
        return self.observe(tool, observation, progress)

    def observe(self, tool: str, observation=None, progress=None):
        """Nạp mỗi kết quả thực thi đúng một lần; không nạp lại khi replan."""
        if tool == "get_booking":
            return None
        if observation is not None:
            ofp = repr(observation)
            if self.obs.count(ofp) + 1 >= self.k_obs:
                return (f"LOOP · {self.obs.count(ofp) + 1} lời gọi khác tham số "
                        f"nhưng trả về cùng một kết quả")
            self.obs.append(ofp)
        if progress is not None:
            self.stall = self.stall + 1 if progress == self.last_progress else 0
            self.last_progress = progress
            if self.stall >= self.n:
                return f"STALL · tiến triển đứng yên ở {progress!r} qua {self.stall} vòng"
        return None


# ============================== PHỤ TRỢ · KIỂM CĂN CỨ (từ kit buổi 03, S58)
MAU_DU_KIEN = [
    r"\d{1,3}(?:\.\d{3})+(?:đ|\s?VNĐ|\s?đồng)?",   # 1.850.000đ
    r"\d{1,2}:\d{2}",                              # 08:15
    r"\d{1,2}/\d{1,2}",                            # 07/10
    r"\b[A-Z]{2}\d{2,4}\b",                      # VN214
    r"\b4XJ\d+\b",                                # toàn bộ mã đặt chỗ
]


def kiem_can_cu(cau_tra_loi: str, ket_qua_tool: list, nguon_khac: str = "") -> dict:
    """Mọi số/giờ/ngày/mã trong câu trả lời phải truy được về observation.

    Nguồn hợp lệ gồm (S58): kết quả tool đã nhận + dữ liệu ràng buộc người
    dùng cung cấp (nguon_khac, vd. trần giá 2.000.000đ, khung 12:00).
    Số được chuẩn hoá bỏ dấu chấm để "1.480.000đ" khớp "1480000" trong JSON.
    """
    nguon = " ".join(str(x) for x in ket_qua_tool) + " " + nguon_khac
    nguon_goc = nguon.replace(".", "").replace(" ", "")
    du_kien = []
    for mau in MAU_DU_KIEN:
        du_kien += re.findall(mau, cau_tra_loi)
    du_kien = list(dict.fromkeys(du_kien))

    def co_nguon(d: str) -> bool:
        so = re.sub(r"(?:đ|VNĐ|đồng)\s*$", "", d).replace(".", "").strip()
        if so.isdigit():
            return re.search(r"(?<!\d)" + re.escape(so) + r"(?!\d)", nguon_goc) is not None
        return re.search(r"(?<!\w)" + re.escape(d) + r"(?!\w)", nguon) is not None

    thieu = [d for d in du_kien if not co_nguon(d)]
    return {"dat": not thieu, "khong_co_nguon": thieu, "du_kien": du_kien}


def chan_truoc_khi_tra_loi(cau_tra_loi: str, ket_qua_tool: list, nguon_khac: str = "") -> str:
    kq = kiem_can_cu(cau_tra_loi, ket_qua_tool, nguon_khac)
    if kq["dat"]:
        return cau_tra_loi
    return ("Chưa trả lời được đầy đủ. Các dữ kiện sau không truy được về kết quả tool nào: "
            + " · ".join(kq["khong_co_nguon"])
            + ". Cần gọi tool bổ sung, hoặc chuyển cho nhân viên hỗ trợ.")


if __name__ == "__main__":
    """Tour tự kiểm BỐN LỚP đi theo THỨ TỰ CHẠY THẬT của một lượt đặt vé:
    lớp 1 kiểm ràng buộc chuyến → lớp 3 kiểm quyền TRƯỚC khi đặt → tool
    đặt + trả tiền → lớp 2 kiểm tiêu chí hoàn thành trên kết quả → lớp 4
    bàn giao khi dừng bất thường. Số 1–4 là nhãn theo thứ tự ĐỀ BÀI liệt
    kê, không phải thứ tự chạy (thứ tự chạy thật ghi ở docstring đầu file).
    """
    from lib.du_lieu import kich_ban_s1
    from lib.tools_ve import KhoChuyenBay, tao_tools

    kb = kich_ban_s1()
    rb = RangBuoc(**{**kb.muc_tieu, "ngay_du_phong": "08/10"})
    kho = KhoChuyenBay(kb.chuyen)
    _, ham = tao_tools(kho)

    print("── Lớp 1 · ràng buộc là dữ liệu ──")
    vn214 = kho.chuyen("VN214")
    vj210 = kho.chuyen("VJ210")
    print("  VN214 hop_le:", rb.hop_le(vn214), "| VJ210 hop_le:", rb.hop_le(vj210))

    print("── Lớp 3 · kiểm quyền (chạy TRƯỚC tool — S35 check #0) ──")
    print("  book VN214 :", canh_bao_quyen("book_seat", {"so_hieu": "VN214", "ngay": "07/10"}, kho, rb))
    print("  book VJ210 :", canh_bao_quyen("book_seat", {"so_hieu": "VJ210", "ngay": "07/10"}, kho, rb))

    print("── Lớp 2 · tiêu chí hoàn thành (chạy SAU khi có observation — S43) ──")
    ham["book_seat"]("VN214", "07/10")
    kq = dat_muc_tieu("4XJ1", ham, rb)
    print("  held:", kq["dat"], kq["dieu_kien"])
    ham["pay"]("4XJ1")
    kq = dat_muc_tieu("4XJ1", ham, rb)
    print("  sau pay:", kq["dat"], kq["dieu_kien"])

    print("── Lớp 4 · bàn giao ──")
    b = ban_giao("LOOP · check_seat gọi 3 lần với cùng tham số",
                 ["check_seat({'so_hieu': 'VJ604'})"] * 3,
                 {"so_lan_goi_tool": 3, "ket_qua_dung": 0},
                 "Chọn chuyến khác hay bỏ?")
    print("  " + in_ban_giao(b).replace("\n", "\n  "))

    print("── Phụ trợ · kiem_can_cu (S58) ──")
    ket_qua = ['{"status":"ok","so_hieu":"VN214","gia":1480000}']
    cau = "Vé VN214 giá 1.480.000đ, tổng 1.480.000đ, đã gồm 30.000đ phí."
    for line in chan_truoc_khi_tra_loi(cau, ket_qua).splitlines():
        print("  " + line)
