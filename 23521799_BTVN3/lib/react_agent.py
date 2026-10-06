# -*- coding: utf-8 -*-
"""BTVN#3 · MẪU 1 · ReAct (S18–S21, S29).

Cài bằng create_agent của LangChain 1.x: model (giả) suy luận MỖI VÒNG,
harness gọi tool, quan sát nạp lại vào lịch sử, model lại suy luận —
suy luận → hành động → quan sát → suy luận tiếp.

Harness cắm vào vòng lặp qua middleware (framework không làm hộ phần sau):
    KiemQuyenMiddleware    chạy SAU model TRƯỚC tool — điều kiện dừng 5 (S35 #0)
    PhatHienLapMiddleware  chạy SAU model — điều kiện dừng 3/4 (S39, S45, S46)
    ModelCallLimitMiddleware (framework) — điều kiện dừng 2: ngân sách
Điều kiện dừng 1 (đạt mục tiêu) nằm ở model thôi gọi tool + được KIỂM CHỨNG
bằng code ở runner (dat_muc_tieu, đủ công thức S43 gồm ngày/giờ/tuyến).
"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware, hook_config
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from lib.du_lieu import KichBan
from lib import harness as harness_mod
from lib.harness import (RangBuoc, LoopDetector, ban_giao, in_ban_giao,
                         canh_bao_quyen, xin_duyet,
                         dat_muc_tieu, kiem_can_cu, chan_truoc_khi_tra_loi,
                         do_tien_trien, muc_dat_cho, kiem_hanh_dong, trang_thai_ban_giao)
from lib.ket_qua import KetQua
from lib.model_gia import ModelVeGia, doc_quan_sat, quan_sat_tu_messages, cau_tra_loi_cuoi
from lib.tools_ve import KhoChuyenBay, tao_tools


def _da_thu_tu_messages(messages) -> list[str]:
    return [f"{c['name']}({c['args']})"
            for m in messages if getattr(m, "tool_calls", None)
            for c in m.tool_calls]


def _tien_trien_tu_messages(messages) -> tuple[int, int, dict | None]:
    """(số quan sát ok, mức đặt chỗ, quan sát gần nhất) — tính từ lịch sử."""
    quan_sat = quan_sat_tu_messages(messages)
    st = doc_quan_sat(quan_sat)
    so_ok = sum(1 for q in quan_sat if isinstance(q["kq"], dict) and q["kq"].get("status") == "ok")
    return so_ok, muc_dat_cho((st["booking"] or {}).get("trang_thai")), \
        (quan_sat[-1]["kq"] if quan_sat else None)


# =============================================== lớp harness tự viết · kiểm quyền
class KiemQuyenMiddleware(AgentMiddleware):
    """Chạy sau model, TRƯỚC khi tool thực thi (S35 check #0).

    Kiểm TẤT CẢ các tool_call trong cùng một lượt model đề xuất — duyệt tool
    này không đồng nghĩa bỏ qua tool kế tiếp.

    che_do_duyet:
        "tu-dong" — người duyệt đồng ý ngay (ma trận đánh giá cần xác định)
        "hoi"     — hỏi y/N trên terminal, như demo chọn y/N trên lớp
        "khong"   — không ai duyệt → dừng graph + bàn giao chờ phê duyệt
    """

    def __init__(self, rb: RangBuoc, kho: KhoChuyenBay, che_do_duyet: str = "tu-dong"):
        super().__init__()
        self.rb, self.kho, self.che_do = rb, kho, che_do_duyet
        self.su_kien: list[str] = []
        self.handoff: dict | None = None
        self.da_duyet: set[str] = set()
        self.stop_type = "can_nguoi"

    def _kiem_tra(self, c, messages):
        vi_pham = kiem_hanh_dong(c["name"], c["args"], self.kho, self.rb)
        ly_do = vi_pham or canh_bao_quyen(c["name"], c["args"], self.kho, self.rb)
        if ly_do is None:
            return True
        hanh_dong = f"{c['name']}({c['args']})"
        if vi_pham is None:
            if c["id"] in self.da_duyet:
                return True
            duyet = xin_duyet(hanh_dong, ly_do, self.che_do)
            self.su_kien.append(f"{hanh_dong} — {ly_do}" +
                                 (" → ĐỒNG Ý" if duyet else " → DỪNG chờ người duyệt"))
            if duyet:
                self.da_duyet.add(c["id"])
                return True
        self.stop_type = "vi_pham_rang_buoc" if vi_pham else "can_nguoi"
        self.handoff = ban_giao(
            ("VI PHẠM RÀNG BUỘC · " if vi_pham else "CẦN NGƯỜI DUYỆT · ") + ly_do,
            _da_thu_tu_messages(messages),
            trang_thai_ban_giao(self.kho, hanh_dong_bi_chan=hanh_dong),
            "Điều chỉnh yêu cầu?" if vi_pham else "Cho phép thực hiện hành động này không?")
        return False

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        for c in getattr(state["messages"][-1], "tool_calls", None) or []:
            if not self._kiem_tra(c, state["messages"]):
                return {"jump_to": "end", "messages": [AIMessage(content=in_ban_giao(self.handoff))]}
        return None

    def wrap_tool_call(self, request, handler):
        # Kiểm lại ngay tại ranh giới thực thi: pay trong cùng lượt với book
        # có thể mới có record đặt chỗ sau khi after_model chạy.
        if not self._kiem_tra(request.tool_call, request.state["messages"]):
            raise DungHarness("Hành động bị harness chặn")
        return handler(request)


# ============================================== lớp harness tự viết · phát hiện lặp
class PhatHienLapMiddleware(AgentMiddleware):
    """LoopDetector tự viết — cả 3 tín hiệu S45 đều được nối vào luồng:
    trùng action, trùng observation (mỗi quan sát thực thi được nạp đúng một lần),
    không tiến triển (do_tien_trien = quan sát ok + mức đặt chỗ)."""

    def __init__(self):
        super().__init__()
        self.det = LoopDetector(window=6, repeat_k=3, stall_n=5)
        self.da_doc: set[str] = set()
        self.handoff: dict | None = None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        cuoi = state["messages"][-1]
        if not getattr(cuoi, "tool_calls", None):
            return None
        da_thu = _da_thu_tu_messages(state["messages"])
        so_ok, stage, _ = _tien_trien_tu_messages(state["messages"])
        canh_bao = None
        for i, m in enumerate(state["messages"]):
            if m.type != "tool" or m.tool_call_id in self.da_doc:
                continue
            self.da_doc.add(m.tool_call_id)
            ok, muc, obs = _tien_trien_tu_messages(state["messages"][:i + 1])
            canh_bao = self.det.observe(m.name, obs, do_tien_trien(ok, muc))
            if canh_bao:
                break
        if canh_bao is None:
            for c in cuoi.tool_calls:
                canh_bao = self.det.check(c["name"], c["args"])
                if canh_bao:
                    break
        if canh_bao:
            self.handoff = ban_giao(
                canh_bao, da_thu, {"so_quan_sat_ok": so_ok},
                "Agent đang lặp vô ích — tiếp tục, đổi chiến lược hay dừng?")
            return {"jump_to": "end", "messages": [AIMessage(content=in_ban_giao(self.handoff))]}
        return None


class DungHarness(Exception):
    """Lệnh dừng có bàn giao, khác lỗi runtime của tool/model."""


class DemLoiGoiMiddleware(AgentMiddleware):
    """Đếm tại ranh giới invoke; AIMessage do harness sinh không phải model call."""
    def __init__(self, kq):
        self.kq = kq
        self.da_thu: list[str] = []

    def wrap_model_call(self, request, handler):
        self.kq.model_calls += 1
        return handler(request)

    def wrap_tool_call(self, request, handler):
        self.kq.tool_calls += 1
        c = request.tool_call
        self.da_thu.append(f"{c['name']}({c['args']})")
        return handler(request)


def _ghi_trace(kq, messages):
    vong = 0
    for m in messages:
        if m.type == "ai" and getattr(m, "tool_calls", None):
            vong += 1
            for c in m.tool_calls:
                kq.trace.append(f"[V{vong}] AI     {c['name']}({c['args']})")
        elif m.type == "tool":
            kq.trace.append(f"[V{vong}] Tool   {m.content}")
        elif m.type == "ai" and str(m.content).strip():
            kq.trace.extend(f"[V{vong}] AI     {d}" for d in str(m.content).splitlines())


# ==================================================================== runner
def chay_react(kb: KichBan, che_do_duyet: str = "tu-dong", run_limit: int = 12) -> KetQua:
    rb = RangBuoc(**{**kb.muc_tieu, "ngay_du_phong": "08/10"})
    kho = KhoChuyenBay(kb.chuyen, mat_ghze_sau_check=kb.mat_ghze_sau_check)
    tools, ham = tao_tools(kho)
    kq = KetQua(kich_ban=kb.ten, mau="react")
    gate = KiemQuyenMiddleware(rb, kho, che_do_duyet)
    lap = PhatHienLapMiddleware()
    counter = DemLoiGoiMiddleware(kq)
    messages = []

    def dung(stop, ly_do, cau_hoi, bao=None):
        kq.stop_type = stop
        kq.ban_giao = bao or ban_giao(ly_do, _da_thu_tu_messages(messages), {}, cau_hoi)
        kq.ban_giao["da_thu"] = list(counter.da_thu)
        kq.ban_giao["trang_thai"] = {
            **kq.ban_giao["trang_thai"], **trang_thai_ban_giao(kho),
            "so_lan_goi_tool": kq.tool_calls, "so_lan_goi_model": kq.model_calls}
        kq.cau_tra_loi = in_ban_giao(kq.ban_giao)
        return kq

    try:
        agent = create_agent(
            model=ModelVeGia(rb={**kb.muc_tieu, "ngay_du_phong": "08/10"}, tinh_cach=kb.tinh_cach),
            tools=tools,
            middleware=[gate, lap, ModelCallLimitMiddleware(run_limit=run_limit, exit_behavior="end"), counter],
        )
        cau_hoi = "Đặt vé máy bay. Ràng buộc: " + rb.to_json()
        # Giữ state sau từng node để có thể bàn giao khi node kế tiếp ném lỗi.
        for state in agent.stream({"messages": [{"role": "user", "content": cau_hoi}]},
                                  stream_mode="values"):
            messages = state["messages"]
        _ghi_trace(kq, messages)
        if lap.handoff is not None:
            return dung("lap", "", "", lap.handoff)
        if gate.handoff is not None:
            return dung(gate.stop_type, "", "", gate.handoff)

        st = doc_quan_sat(quan_sat_tu_messages(messages))
        booking = st["booking"]
        final = str(messages[-1].content)
        verdict = None
        if booking and booking.get("ma_dat"):
            kq.tool_calls += 1  # đọc lại booking, kể cả khi verdict thất bại
            verdict = dat_muc_tieu(booking["ma_dat"], ham, rb)
            krc = harness_mod.check_rang_buoc(verdict["booking"], rb)
            kq.rang_buoc = ("ĐẠT (không vi phạm ràng buộc dữ liệu)" if krc["dat"]
                            else "VI PHẠM: " + "; ".join(krc["vi_pham"]))
            if verdict["dat"] and krc["dat"]:
                kq.dat, kq.stop_type = True, "dat_muc_tieu"
                contents = [m.content for m in messages if m.type == "tool"] + [verdict["booking"]]
                kq.cau_tra_loi = chan_truoc_khi_tra_loi(
                    cau_tra_loi_cuoi(verdict["booking"], rb), contents, rb.to_json())
                return kq
        if final.startswith("Model call limits exceeded"):
            return dung("ngan_sach", f"HẾT NGÂN SÁCH · trần {run_limit} lần gọi model",
                        "Tăng ngân sách hoặc xử lý đặt chỗ dở dang?")
        ly_do = ("; ".join(d for d, ok in verdict["dieu_kien"].items() if not ok)
                 if verdict else "model dừng khi chưa có đặt chỗ")
        return dung("be_tac", "BẾ TẮC · " + ly_do, "Nới ràng buộc hay xử lý đặt chỗ dở dang?")
    except DungHarness:
        _ghi_trace(kq, messages)
        return dung(gate.stop_type, "", "", gate.handoff)
    except Exception as e:
        _ghi_trace(kq, messages)
        kq.trace.append(f"[LỖI] {type(e).__name__}: {e}")
        stop = "tran_cung" if isinstance(e, GraphRecursionError) else "loi_runtime"
        return dung(stop, f"{stop.upper()} · {type(e).__name__}: {e}",
                    "Kiểm tra lỗi và đặt chỗ dở dang trước khi chạy lại?")
    finally:
        kq.kiem_quyen = gate.su_kien
