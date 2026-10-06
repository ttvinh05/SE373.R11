# -*- coding: utf-8 -*-
"""BTVN#3 · MẪU 2 · Plan-then-Execute (S22–S23).

Gọi model MỘT LẦN để sinh trọn kế hoạch (lap_ke_hoach), rồi executor thực
thi tuần tự từng bước theo kế hoạch đó. Executor KHÔNG tự suy luận lại:
mỗi bước chỉ được
    · giải ký hiệu $best$/$ma_dat$ tại thời điểm chạy — ứng viên CHỐT MỘT
      LẦN cho cả kế hoạch (book dùng đúng chuyến đã check),
    · qua bộ phát hiện lặp (đủ 3 tín hiệu: action/observation/tiến triển),
    · kiểm ĐIỀU KIỆN TIỀN ĐỀ bằng code (vd. check_seat(...).con > 0),
    · qua lớp kiểm quyền TRƯỚC khi thực thi,
    · kiểm tiêu chí hoàn thành (S43 đủ công thức) + lớp 1 khi chốt.

Điều kiện tiền đề của một bước bị phá vỡ ⇒ kế hoạch lỗi thời ⇒ mẫu này
KHÔNG lập lại kế hoạch: dừng và bàn giao (đúng điểm yếu "Kế hoạch lỗi thời"
trong bảng chọn mẫu S26 và "lỗi ở bước đầu làm hỏng toàn bộ sau" S23).
"""
from __future__ import annotations

import json

from lib.du_lieu import KichBan
from lib import harness as harness_mod
from lib.harness import (RangBuoc, LoopDetector, ban_giao, in_ban_giao,
                         canh_bao_quyen, xin_duyet,
                         dat_muc_tieu, chan_truoc_khi_tra_loi,
                         do_tien_trien, muc_dat_cho, kiem_hanh_dong, trang_thai_ban_giao)
from lib.ket_qua import KetQua
from lib.model_gia import lap_ke_hoach, giai_ky_hieu, doc_quan_sat, cau_tra_loi_cuoi
from lib.tools_ve import KhoChuyenBay, tao_tools



def _tien_trien(quan_sat: list[dict]) -> tuple[int, int, dict | None]:
    so_ok = sum(1 for q in quan_sat if isinstance(q["kq"], dict) and q["kq"].get("status") == "ok")
    st = doc_quan_sat(quan_sat)
    return so_ok, muc_dat_cho((st["booking"] or {}).get("trang_thai")), \
        (quan_sat[-1]["kq"] if quan_sat else None)


def chay_plan(kb: KichBan, che_do_duyet: str = "tu-dong", tool_limit: int = 24) -> KetQua:
    rb = RangBuoc(**{**kb.muc_tieu, "ngay_du_phong": "08/10"})
    kho = KhoChuyenBay(kb.chuyen, mat_ghze_sau_check=kb.mat_ghze_sau_check)
    _, ham = tao_tools(kho)
    kq = KetQua(kich_ban=kb.ten, mau="plan")

    quan_sat: list[dict] = []
    da_thu: list[str] = []
    det = LoopDetector(window=6, repeat_k=3, stall_n=5)
    model_calls = 0
    verification_calls = 0
    try:
        model_calls += 1                       # một lần gọi model để sinh kế hoạch
        ke_hoach = lap_ke_hoach(rb, quan_sat)
        kq.trace.append("[KẾ HOẠCH] " + " → ".join(f"{b['tool']}" for b in ke_hoach))

        if not ke_hoach:
            bao = ban_giao("BẾ TẮC · planner không sinh được kế hoạch từ quan sát hiện có",
                           [], {"quan_sat": len(quan_sat)},
                           "Nới ràng buộc ngày/giờ/giá?")
            kq.stop_type, kq.ban_giao, kq.model_calls = "be_tac", bao, model_calls
            kq.cau_tra_loi = in_ban_giao(bao)
            return kq

        chon_ke_hoach: str | None = None      # ứng viên CHỐT cho cả kế hoạch
        for buoc in ke_hoach:
            ten, args = buoc["tool"], buoc["args"]
            st = doc_quan_sat(quan_sat)
            args, chon_ke_hoach = giai_ky_hieu(args, rb, st, chon_ke_hoach)

            # ── bộ phát hiện lặp — đủ 3 tín hiệu (điều kiện dừng 3/4) ──────────
            canh = det.check(ten, args)
            if canh:
                bao = ban_giao(canh, da_thu, {"so_lan_goi_tool": len(da_thu)},
                               "Tiếp tục, đổi chiến lược hay dừng?")
                return _ket_thuc(kq, "lap", bao, model_calls, quan_sat, da_thu)

            # ── điều kiện tiền đề kiểm bằng code (kế hoạch còn đáng tin không?) ─
            vi_pham = _ktra_tien_de(ten, args, st)
            if vi_pham is not None:
                bao = ban_giao("KẾ HOẠCH LỖI THỜI · " + vi_pham, da_thu,
                               {"buoc": ten, "args": args},
                               "Lập lại kế hoạch hay dừng? (mẫu Plan-then-Execute không tự lập lại)")
                return _ket_thuc(kq, "ke_hoach_loi_thoi", bao, model_calls, quan_sat, da_thu)

            vi_pham_rb = kiem_hanh_dong(ten, args, kho, rb)
            if vi_pham_rb or len(da_thu) >= tool_limit:
                stop = "vi_pham_rang_buoc" if vi_pham_rb else "ngan_sach"
                bao = ban_giao("VI PHẠM RÀNG BUỘC · " + vi_pham_rb if vi_pham_rb
                               else "HẾT NGÂN SÁCH TOOL", da_thu,
                               {"hanh_dong_bi_chan": f"{ten}({args})"},
                               "Điều chỉnh yêu cầu hoặc ngân sách rồi chạy lại?")
                return _ket_thuc(kq, stop, bao, model_calls, quan_sat, da_thu)

            # ── kiểm quyền chạy TRƯỚC khi thực thi (điều kiện dừng 5) ─────────
            ly_do_quyen = canh_bao_quyen(ten, args, kho, rb)
            if ly_do_quyen is not None:
                hanh_dong = f"{ten}({args})"
                duyet = xin_duyet(hanh_dong, ly_do_quyen, che_do_duyet)
                kq.kiem_quyen.append(f"{hanh_dong} — {ly_do_quyen}"
                                     + (" → ĐỒNG Ý" if duyet else " → DỪNG chờ người duyệt"))
                if not duyet:
                    bao = ban_giao("CẦN NGƯỜI DUYỆT · " + ly_do_quyen, da_thu,
                                   {"hanh_dong_cho_duyet": hanh_dong},
                                   "Cho phép thực hiện hành động này không?")
                    return _ket_thuc(kq, "can_nguoi", bao, model_calls, quan_sat, da_thu)

            kq.trace.append(f"[BƯỚC {len(da_thu) + 1}] {ten}({json.dumps(args, ensure_ascii=False)})")
            da_thu.append(f"{ten}({args})")
            kq_exec = ham[ten](**args)
            quan_sat.append({"tool": ten, "args": args, "kq": kq_exec})
            kq.trace.append(f"[BƯỚC {len(da_thu)}] Tool   {json.dumps(kq_exec, ensure_ascii=False)}")

            # ── tiêu chí hoàn thành kiểm bằng code (điều kiện dừng 1, S43) ─────
            if ten == "get_booking" and kq_exec.get("status") == "ok" \
                    and kq_exec.get("trang_thai") == "confirmed":
                if len(da_thu) + verification_calls >= tool_limit:
                    bao = ban_giao("HẾT NGÂN SÁCH TOOL · chưa thể xác minh độc lập",
                                   da_thu, {}, "Tăng ngân sách để xác minh đặt chỗ đã thanh toán?")
                    return _ket_thuc(kq, "ngan_sach", bao, model_calls, quan_sat, da_thu)
                verification_calls += 1
                verdict = dat_muc_tieu(args["ma_dat"], ham, rb)
                krc = harness_mod.check_rang_buoc(verdict["booking"], rb)   # lớp 1: kiểm lại trước khi trả lời
                kq.rang_buoc = ("ĐẠT (không vi phạm ràng buộc dữ liệu)" if krc["dat"]
                                else "VI PHẠM: " + "; ".join(krc["vi_pham"]))
                # tool_calls bao gồm cả thao tác xác minh của harness (dat_muc_tieu → get_booking)
                kq.dat = verdict["dat"] and krc["dat"]
                kq.stop_type = "dat_muc_tieu" if kq.dat else "be_tac"
                if kq.dat:
                    kq.cau_tra_loi = chan_truoc_khi_tra_loi(
                        cau_tra_loi_cuoi(verdict["booking"], rb),
                        [json.dumps(q_["kq"], ensure_ascii=False) for q_ in quan_sat],
                        nguon_khac=rb.to_json())
                else:
                    ly_do = ("chưa thoả tiêu chí: " +
                             "; ".join(d for d, ok in verdict["dieu_kien"].items() if not ok)) \
                        if not verdict["dat"] else "vi phạm ràng buộc dữ liệu: " + "; ".join(krc["vi_pham"])
                    bao = ban_giao("BẾ TẮC · đặt chỗ " + ly_do, da_thu,
                                   {"ma_dat": args["ma_dat"],
                                    "trang_thai": verdict["booking"].get("trang_thai")},
                                   "Xử lý đặt chỗ dở dang thế nào?")
                    kq.ban_giao = bao
                    kq.cau_tra_loi = in_ban_giao(bao)
                # +1: thao tác xác minh của harness (dat_muc_tieu → get_booking)
                kq.model_calls, kq.tool_calls = model_calls, len(da_thu) + 1
                return kq

            so_ok, stage, _ = _tien_trien(quan_sat)
            canh = det.observe(ten, kq_exec, do_tien_trien(so_ok, stage))
            if canh or kq_exec.get("status") == "error":
                bao = ban_giao(canh or f"KẾ HOẠCH LỖI THỜI · {ten}: {kq_exec.get('error')}",
                               da_thu, {}, "Lập lại kế hoạch hay dừng?")
                return _ket_thuc(kq, "lap" if canh else "ke_hoach_loi_thoi", bao,
                                 model_calls, quan_sat, da_thu)

        # kế hoạch chạy hết mà chưa đạt tiêu chí
        bao = ban_giao("BẾ TẮC · kế hoạch đã chạy hết nhưng chưa đạt tiêu chí hoàn thành",
                       da_thu, {"so_buoc": len(da_thu)},
                       "Lập lại kế hoạch hay dừng?")
        return _ket_thuc(kq, "be_tac", bao, model_calls, quan_sat, da_thu)
    except Exception as e:
        kq.trace.append(f"[LỖI RUNTIME] {type(e).__name__}: {e}")
        bao = ban_giao(f"LỖI RUNTIME · {type(e).__name__}: {e}", da_thu,
                       {"loi": type(e).__name__}, "Kiểm tra lỗi và đặt chỗ dở dang trước khi chạy lại?")
        return _ket_thuc(kq, "loi_runtime", bao, model_calls, quan_sat, da_thu)
    finally:
        kq.model_calls = model_calls
        kq.tool_calls = len(da_thu) + verification_calls
        kq.lap_ke_hoach = max(0, model_calls - 1) if kq.mau == "lai" else 0
        if kq.ban_giao is not None:
            kq.ban_giao["trang_thai"] = {**kq.ban_giao["trang_thai"], **trang_thai_ban_giao(kho),
                                         "so_lan_goi_tool": kq.tool_calls,
                                         "so_lan_goi_model": kq.model_calls}
            kq.cau_tra_loi = in_ban_giao(kq.ban_giao)


def _ktra_tien_de(ten: str, args: dict, st: dict) -> str | None:
    """Điều kiện tiền đề của một bước — kiểm bằng code, không dựa vào model."""
    if ten == "book_seat":
        ks = st["check_seat"].get((args.get("ngay"), args.get("so_hieu")))
        if ks is None:
            return f"chưa từng check_seat({args.get('so_hieu')}) — bước đặt ghế không có căn cứ"
        if ks.get("con", 0) <= 0:
            return f"check_seat({args.get('so_hieu')}) cho thấy HẾT GHẾ nhưng kế hoạch vẫn định đặt"
    if ten == "pay" and (st["booking"] or {}).get("trang_thai") != "held":
        return "không có đặt chỗ đang held để thanh toán"
    if ten == "get_booking" and st["booking"] is None:
        return "chưa có mã đặt chỗ nào để đọc lại"
    return None


def _ket_thuc(kq: KetQua, stop_type: str, bao: dict, model_calls: int,
              quan_sat: list[dict], da_thu: list[str]) -> KetQua:
    kq.stop_type, kq.ban_giao = stop_type, bao
    kq.model_calls, kq.tool_calls = model_calls, len(da_thu)
    kq.cau_tra_loi = in_ban_giao(bao)
    return kq
