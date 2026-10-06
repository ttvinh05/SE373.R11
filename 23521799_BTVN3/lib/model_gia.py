# -*- coding: utf-8 -*-
"""BTVN#3 · "Bộ não" của model giả lập — chính sách quyết định dùng chung.

Đây là chính sách Python cố định, không phải LLM. Hai hàm dưới đây dùng
chung dữ liệu và bộ đọc quan sát, nhưng quyết định theo từng mẫu. Số liệu
chỉ minh họa triển khai này, không chứng minh một mẫu tốt hơn với mọi LLM.

    hanh_dong_tiep_theo(rb, quan_sat)   suy luận MỘT BƯỚC — dùng cho ReAct
    lap_ke_hoach(rb, quan_sat)          sinh TRỌN KẾ HOẠCH — dùng cho Plan/Lai

ModelVeGia bọc hanh_dong_tiep_theo thành BaseChatModel tương thích
LangChain để create_agent chạy được mà không cần API key (mượn cách của
lib/model_gia.py trong kit buổi 03).

quan_sat: list các dict {"tool", "args", "kq"} — mọi quyết định đều rút ra
từ quan sát, không có trí nhớ riêng ngoài dữ liệu đó.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from lib.du_lieu import viet_tien
from lib.harness import RangBuoc


# ============================================================ đọc quan sát
def doc_quan_sat(quan_sat: list[dict]) -> dict:
    """Chưng cất quan sát thô thành trạng thái bài toán.

    da_search : ngày đã dò → danh sách chuyến (search trả giá, KHÔNG trả số ghế)
    check_seat: (ngày, mã chuyến) → kết quả kiểm ghế
    booking   : đặt chỗ mới nhất (held/paid/confirmed)
    het_ghe   : các chuyến đã biết hết ghế
    """
    st = {"da_search": {}, "check_seat": {}, "booking": None, "het_ghe": set()}
    for q in quan_sat:
        ten, kq = q["tool"], q.get("kq") or {}
        if not isinstance(kq, dict):
            continue
        if ten == "search_flights" and kq.get("status") == "ok":
            st["da_search"][kq["ngay"]] = kq.get("flights", [])
        elif ten == "check_seat" and kq.get("status") == "ok":
            key = (kq["ngay"], kq["so_hieu"])
            st["check_seat"][key] = kq
            if kq.get("con", 0) <= 0:
                st["het_ghe"].add(key)
            else:
                st["het_ghe"].discard(key)
        elif ten == "book_seat" and kq.get("status") == "error" and kq.get("error") == "flight_full":
            # kho biến động: ghế vừa có ở check_seat có thể đã bị lấy trước khi đặt
            key = (kq.get("ngay"), kq.get("so_hieu"))
            st["het_ghe"].add(key)
            st["check_seat"].pop(key, None)
        elif ten in ("book_seat", "pay", "get_booking") and kq.get("status") == "ok":
            st["booking"] = {**(st["booking"] or {}), **kq}
    return st


def ung_vien_list(rb: RangBuoc, st: dict) -> list[tuple[str, dict]]:
    """Danh sách ứng viên: thoả ràng buộc giá/giờ, chưa biết hết ghế,
    ngày chính trước ngày dự phòng, trong mỗi ngày RẺ TRƯỚC (S62: ràng buộc là dữ liệu)."""
    ra = []
    ngays = [rb.ngay] + ([rb.ngay_du_phong] if rb.cho_doi_ngay else [])
    for do_uu_tien, ngay in enumerate(ngays):
        for f in st["da_search"].get(ngay, []):
            if (ngay, f["so_hieu"]) in st["het_ghe"]:
                continue
            if rb.hop_le(f):
                ra.append((do_uu_tien, f["gia"], ngay, f))
    ra.sort(key=lambda x: (x[0], x[1]))
    return [(ngay, f) for _, _, ngay, f in ra]


# ============================================================ ReAct · 1 bước
def hanh_dong_tiep_theo(rb: RangBuoc, quan_sat: list[dict], tinh_cach: str = "chuan"):
    """Trả ("GOI", ten_tool, args) hoặc ("TRA_LOI", văn bản)."""
    if tinh_cach == "cung_dau":
        # Tính cách để tái hiện Trace C (S39): bỏ qua mọi quan sát, cứ gọi lại.
        return ("GOI", "check_seat", {"so_hieu": "VJ604", "ngay": rb.ngay})

    st = doc_quan_sat(quan_sat)

    # 1 · đang giữa dòng đặt chỗ: giữ ghế → trả tiền → kiểm chứng
    b = st["booking"]
    if b is not None:
        t = b.get("trang_thai")
        if t == "held":
            return ("GOI", "pay", {"ma_dat": b["ma_dat"], "the": "corp_card"})
        if t == "paid":
            return ("GOI", "get_booking", {"ma_dat": b["ma_dat"]})
        if t == "confirmed":
            return ("TRA_LOI", cau_tra_loi_cuoi(b, rb))

    # 2 · ứng viên thoả ràng buộc: kiểm ghế lần lượt, còn ghế thì đặt
    for ngay, f in ung_vien_list(rb, st):
        ks = st["check_seat"].get((ngay, f["so_hieu"]))
        if ks is None:
            return ("GOI", "check_seat", {"so_hieu": f["so_hieu"], "ngay": ngay})
        if ks.get("con", 0) > 0:
            return ("GOI", "book_seat", {"so_hieu": f["so_hieu"], "ngay": ngay})

    # 3 · chưa dò ngày chính → dò
    if rb.ngay not in st["da_search"]:
        return ("GOI", "search_flights", {"di": rb.di, "den": rb.den, "ngay": rb.ngay})

    # 4 · ngày chính hết lựa chọn → dò ngày dự phòng (đổi hướng)
    if rb.cho_doi_ngay and rb.ngay_du_phong not in st["da_search"]:
        return ("GOI", "search_flights",
                {"di": rb.di, "den": rb.den, "ngay": rb.ngay_du_phong})

    # 5 · hết đường
    return ("TRA_LOI", "Không tìm được vé nào thoả ràng buộc. "
                       "Cần người dùng nới ràng buộc (ngày/giờ/trần giá).")


# ================================================== Plan / Lai · trọn kế hoạch
def _b(tool: str, args: dict, pre: str | None = None) -> dict:
    """Một bước kế hoạch. pre = điều kiện tiền đề executor kiểm bằng code."""
    return {"tool": tool, "args": args, "pre": pre}


_SYM_BEST = "$best$"     # chuyến rẻ nhất thoả ràng buộc từ kết quả search gần nhất
_SYM_MA = "$ma_dat$"     # mã đặt chỗ từ kết quả book_seat gần nhất


def lap_ke_hoach(rb: RangBuoc, quan_sat: list[dict]) -> list[dict]:
    """Gọi model MỘT LẦN để sinh kế hoạch (S22). Biết đến đâu kế hoạch đến đó."""
    st = doc_quan_sat(quan_sat)

    # đang giữa dòng đặt chỗ → đóng nốt
    b = st["booking"]
    if b is not None:
        t = b.get("trang_thai")
        if t == "held":
            return [_b("pay", {"ma_dat": b["ma_dat"], "the": "corp_card"}),
                    _b("get_booking", {"ma_dat": b["ma_dat"]})]
        if t == "paid":
            return [_b("get_booking", {"ma_dat": b["ma_dat"]})]
        if t == "confirmed":
            return []                       # xong — executor chốt tiêu chí

    # ứng viên đã biết còn ghế → đặt luôn
    for ngay, f in ung_vien_list(rb, st):
        ks = st["check_seat"].get((ngay, f["so_hieu"]))
        if ks is not None and ks.get("con", 0) > 0:
            return [_b("book_seat", {"so_hieu": f["so_hieu"], "ngay": ngay},
                       pre=f"check_seat({f['so_hieu']}).con > 0"),
                    _b("pay", {"ma_dat": _SYM_MA, "the": "corp_card"}),
                    _b("get_booking", {"ma_dat": _SYM_MA})]

    # chưa dò ngày chính → kế hoạch mở đầu bằng search, $best$ giải khi chạy
    if rb.ngay not in st["da_search"]:
        return [_b("search_flights", {"di": rb.di, "den": rb.den, "ngay": rb.ngay}),
                _b("check_seat", {"so_hieu": _SYM_BEST, "ngay": rb.ngay}),
                _b("book_seat", {"so_hieu": _SYM_BEST, "ngay": rb.ngay},
                   pre="check_seat($best$).con > 0"),
                _b("pay", {"ma_dat": _SYM_MA, "the": "corp_card"}),
                _b("get_booking", {"ma_dat": _SYM_MA})]

    # ngày chính đã dò — còn ứng viên chưa kiểm → kiểm rồi đặt
    uv = ung_vien_list(rb, st)
    if uv:
        ngay, f = uv[0]
        return [_b("check_seat", {"so_hieu": f["so_hieu"], "ngay": ngay}),
                _b("book_seat", {"so_hieu": f["so_hieu"], "ngay": ngay},
                   pre=f"check_seat({f['so_hieu']}).con > 0"),
                _b("pay", {"ma_dat": _SYM_MA, "the": "corp_card"}),
                _b("get_booking", {"ma_dat": _SYM_MA})]

    # ngày chính hết lựa chọn → đổi hướng sang ngày dự phòng
    if rb.cho_doi_ngay and rb.ngay_du_phong not in st["da_search"]:
        return [_b("search_flights", {"di": rb.di, "den": rb.den, "ngay": rb.ngay_du_phong}),
                _b("check_seat", {"so_hieu": _SYM_BEST, "ngay": rb.ngay_du_phong}),
                _b("book_seat", {"so_hieu": _SYM_BEST, "ngay": rb.ngay_du_phong},
                   pre="check_seat($best$).con > 0"),
                _b("pay", {"ma_dat": _SYM_MA, "the": "corp_card"}),
                _b("get_booking", {"ma_dat": _SYM_MA})]

    return []                           # planner bế tắc


def giai_ky_hieu(args: dict, rb: RangBuoc, st: dict, chon_dan: str | None = None) -> tuple[dict, str | None]:
    """Executor giải ký hiệu $best$/$ma_dat$ tại thời điểm thực thi.

    $best$ = chuyến RẺ NHẤT thoả ràng buộc từ kết quả search của ĐÚNG NGÀY
    mà bước kế hoạch khai báo (loại các chuyến đã biết hết ghế).

    Ứng viên được CHỐT MỘT LẦN cho cả kế hoạch (chọn ở bước đầu cần $best$,
    các bước sau của cùng kế hoạch dùng lại đúng ứng viên đó — book dùng đúng
    chuyến đã check, không tự đổi giữa chừng). Trả (args_đã_giải, ứng_viên_đã_chốt).
    """
    args = dict(args)
    if args.get("so_hieu") == _SYM_BEST:
        if chon_dan:
            args["so_hieu"] = chon_dan
        else:
            ngay = args.get("ngay") or rb.ngay
            ok = [f for f in st["da_search"].get(ngay, [])
                  if rb.hop_le(f) and (ngay, f["so_hieu"]) not in st["het_ghe"]]
            if ok:
                chon_dan = min(ok, key=lambda f: f["gia"])["so_hieu"]
                args["so_hieu"] = chon_dan
    if args.get("ma_dat") == _SYM_MA:
        b = st["booking"]
        args["ma_dat"] = b["ma_dat"] if b else ""
    return args, chon_dan


def cau_tra_loi_cuoi(b: dict, rb: RangBuoc) -> str:
    """Câu trả lời cuối — model chỉ được nhắc dữ kiện có trong quan sát (S58).

    Ngày/giờ lấy từ record đặt chỗ thật (b["ngay"], b["gio"]) — trường hợp đổi
    hướng thì vé nằm ở ngày dự phòng, không phải ngày khách hỏi ban đầu.
    """
    return (f"Đã đặt vé {b['so_hieu']} mã {b['ma_dat']}, trạng thái {b['trang_thai']}, "
            f"giá {viet_tien(b['gia'])} — thoả ràng buộc "
            f"({rb.di}→{rb.den}, trước {rb.gio_toi_da}, trần {viet_tien(rb.tran_gia)}); "
            f"chuyến bay ngày {b.get('ngay', rb.ngay)} lúc {b.get('gio', '?')}.")


# ================================================= Model giả cho create_agent
class ModelVeGia(BaseChatModel):
    """BaseChatModel trả tool_calls theo chính sách — mượn kiến trúc kit buổi 03.

    rb        : RangBuoc dạng dict (ràng buộc là dữ liệu, model đọc từ đây)
    tinh_cach : "chuan" | "cung_dau" (S39)
    """

    rb: dict = {}
    tinh_cach: str = "chuan"
    _luot: int = 0

    @property
    def _llm_type(self) -> str:
        return "btvn3-model-gia"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ModelVeGia":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._luot += 1
        rb = RangBuoc(**self.rb)
        quan_sat = quan_sat_tu_messages(messages)
        quyet_dinh = hanh_dong_tiep_theo(rb, quan_sat, self.tinh_cach)
        if quyet_dinh[0] == "TRA_LOI":
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=quyet_dinh[1]))])
        _, ten_tool, args_tool = quyet_dinh
        ai = AIMessage(content="", tool_calls=[{
            # id DUY NHẤT mỗi lượt: LangGraph nối ToolMessage về tool_call qua id,
            # id trùng sẽ làm toàn bộ quan sát bị ghi nhầm về lời gọi cuối.
            "name": ten_tool, "args": args_tool, "id": f"call_{self._luot}", "type": "tool_call",
        }])
        return ChatResult(generations=[ChatGeneration(message=ai)])


def quan_sat_tu_messages(messages: list[BaseMessage]) -> list[dict]:
    """Ghép mỗi ToolMessage với (tool, args) của nó qua tool_call_id."""
    call_map = {}
    ra = []
    for m in messages:
        if m.type == "ai":
            for c in getattr(m, "tool_calls", None) or []:
                call_map[c["id"]] = (c["name"], c["args"])
        elif m.type == "tool":
            ten, args = call_map.get(getattr(m, "tool_call_id", None), (getattr(m, "name", ""), {}))
            try:
                kq = json.loads(m.content)
            except Exception:
                kq = m.content
            ra.append({"tool": ten, "args": args, "kq": kq})
    return ra
