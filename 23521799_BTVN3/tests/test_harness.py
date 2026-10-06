"""Regression checks: no network, uses in-memory scenarios and mock policies.
Run BTVN3_ROOT=/path/to/submission python -B this_file.py
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.environ.get('BTVN3_ROOT', str(Path(__file__).resolve().parents[1])))
from lib.du_lieu import kich_ban_s1, kich_ban_s2, kich_ban_s5, KichBan, muc_tieu_goc
from lib.harness import RangBuoc, canh_bao_quyen, dat_muc_tieu, check_rang_buoc, LoopDetector, kiem_can_cu
from lib.tools_ve import KhoChuyenBay, tao_tools
from lib.react_agent import chay_react
from lib.plan_agent import chay_plan
from lib.hybrid_agent import chay_hybrid
from lib.model_gia import ModelVeGia
import lib.react_agent as react
import lib.plan_agent as plan
import lib.hybrid_agent as hybrid


class HarnessRegression(unittest.TestCase):
    def test_tool_budget_includes_completion_verification(self):
        for run in (chay_plan, chay_hybrid):
            with self.subTest(run=run.__name__):
                q = run(kich_ban_s1(), tool_limit=5)
                self.assertEqual(q.stop_type, 'ngan_sach')
                self.assertFalse(q.dat)
                self.assertEqual(q.tool_calls, 5)
                self.assertTrue(q.ban_giao['trang_thai']['paid'])

    def rb(self):
        return RangBuoc(**{**muc_tieu_goc(), 'ngay_du_phong': '08/10'})

    def test_standard_scenarios(self):
        for run in (chay_react, chay_plan, chay_hybrid):
            with self.subTest(run=run.__name__):
                self.assertTrue(run(kich_ban_s1()).dat)
                denied = run(kich_ban_s2(), che_do_duyet='khong')
                self.assertEqual(denied.stop_type, 'ke_hoach_loi_thoi' if run is chay_plan else 'can_nguoi')
                self.assertIsNotNone(denied.ban_giao)
        for run in (chay_react, chay_hybrid):
            self.assertTrue(run(kich_ban_s5()).dat)

    def test_backup_date_does_not_inherit_primary_full_status(self):
        base = dict(so_hieu='VN214', gio='08:15', gia=1_480_000, hoan=True, con=0)
        kb = KichBan('same_code_two_dates', '', {'07/10': [base], '08/10': [{**base, 'con': 4}]}, muc_tieu_goc())
        for run in (chay_react, chay_hybrid):
            with self.subTest(run=run.__name__):
                q = run(kb)
                self.assertTrue(q.dat, 'Backup date has four valid seats on same flight code')

    def test_budget_counts_actual_invocations(self):
        actual = []
        generate = ModelVeGia._generate
        def counted(self, *args, **kw):
            actual.append(1)
            return generate(self, *args, **kw)
        with patch.object(ModelVeGia, '_generate', counted):
            q = chay_react(kich_ban_s1(), run_limit=1)
        self.assertEqual(q.stop_type, 'ngan_sach')
        self.assertEqual(q.model_calls, len(actual))

    def two_dates(self):
        base = dict(so_hieu='VN214', gio='08:15', gia=1_480_000, hoan=True, con=2)
        return KhoChuyenBay({'07/10': [base], '08/10': [{**base, 'gia': 1_980_000, 'hoan': False}]})

    def test_permission_uses_booking_date(self):
        kho = self.two_dates()
        self.assertIsNotNone(canh_bao_quyen('book_seat', {'so_hieu': 'VN214', 'ngay': '08/10'}, kho, self.rb()))

    def test_permission_pay_uses_held_booking(self):
        kho = self.two_dates()
        _, ham = tao_tools(kho)
        b = ham['book_seat']('VN214', '08/10')
        self.assertIsNotNone(canh_bao_quyen('pay', {'ma_dat': b['ma_dat']}, kho, self.rb()))

    def test_runtime_handoff_retains_held_booking(self):
        count = []
        generate = ModelVeGia._generate
        def fails_after_hold(self, *args, **kw):
            count.append(1)
            if len(count) == 4:
                raise RuntimeError('Injected failure after holding seat')
            return generate(self, *args, **kw)
        with patch.object(ModelVeGia, '_generate', fails_after_hold):
            q = chay_react(kich_ban_s1())
        self.assertEqual(q.stop_type, 'loi_runtime')
        self.assertEqual(q.ban_giao['trang_thai'].get('ma_dat'), '4XJ1')
        self.assertGreaterEqual(q.tool_calls, 3)
        self.assertTrue(q.ban_giao['da_thu'])

    def test_plan_and_hybrid_tool_runtime_handoff(self):
        real_tools = tao_tools
        def faulty_tools(kho):
            wrapped, ham = real_tools(kho)
            def fail(**kwargs):
                raise RuntimeError('Injected search service failure')
            ham['search_flights'] = fail
            return wrapped, ham
        for module, run in ((plan, chay_plan), (hybrid, chay_hybrid)):
            with self.subTest(run=run.__name__), patch.object(module, 'tao_tools', faulty_tools):
                q = run(kich_ban_s1())
                self.assertEqual(q.stop_type, 'loi_runtime')
                self.assertIsNotNone(q.ban_giao)

    def test_constraint_rejected_before_pay(self):
        forbidden_plan = [
            {'tool': 'search_flights', 'args': {'di':'SGN','den':'DAD','ngay':'07/10'}},
            {'tool': 'check_seat', 'args': {'so_hieu':'VN122','ngay':'07/10'}},
            {'tool': 'book_seat', 'args': {'so_hieu':'VN122','ngay':'07/10'}},
            {'tool': 'pay', 'args': {'ma_dat':'$ma_dat$'}},
            {'tool': 'get_booking', 'args': {'ma_dat':'$ma_dat$'}},
        ]
        real_tools = tao_tools
        for module, run in ((plan, chay_plan), (hybrid, chay_hybrid)):
            stores = []
            def observe_store(kho):
                stores.append(kho)
                return real_tools(kho)
            with self.subTest(run=run.__name__), patch.object(module, 'lap_ke_hoach', return_value=forbidden_plan), patch.object(module, 'tao_tools', observe_store):
                q = run(kich_ban_s1())
                self.assertFalse(q.dat)
                self.assertFalse(any(b.get('paid') for b in stores[0].dat_cho.values()), 'Agent paid flight above hard price ceiling before final constraint rejection')

    def test_completion_rejects_error_status(self):
        b = {'status':'error', 'error':'provider_failure', 'ma_dat':'4XJ1', 'trang_thai':'confirmed', 'paid':True, 'gia':1_480_000, 'ngay':'07/10', 'gio':'08:15', 'di':'SGN', 'den':'DAD'}
        self.assertFalse(dat_muc_tieu('4XJ1', {'get_booking':lambda _:b}, self.rb())['dat'])

    def test_constraint_missing_or_invalid_fields_fail_closed(self):
        valid = {'gia': 1480000, 'ngay': '07/10', 'gio': '08:15', 'di': 'SGN', 'den': 'DAD'}
        for field, bad in [('gia', None), ('gia', True), ('gia', -1), ('gio', None),
                           ('gio', '00:99'), ('gio', '8:15'), ('ngay', '09/10'), ('den', 'HAN')]:
            with self.subTest(field=field, bad=bad):
                self.assertFalse(check_rang_buoc({**valid, field: bad}, self.rb())['dat'])
        self.assertFalse(check_rang_buoc({}, self.rb())['dat'])

    def test_backup_requires_user_permission(self):
        rb = self.rb()
        rb.cho_doi_ngay = False
        b = {'gia': 1480000, 'ngay': '08/10', 'gio': '08:15', 'di': 'SGN', 'den': 'DAD'}
        self.assertFalse(check_rang_buoc(b, rb)['dat'])

    def test_inventory_and_date_isolation(self):
        kho = self.two_dates()
        _, ham = tao_tools(kho)
        self.assertEqual(ham['book_seat']('VN214', '09/10')['status'], 'error')
        ham['book_seat']('VN214', '07/10')
        ham['book_seat']('VN214', '07/10')
        self.assertEqual(ham['book_seat']('VN214', '07/10')['error'], 'flight_full')
        self.assertEqual(ham['check_seat']('VN214', '08/10')['con'], 2)

    def test_react_refuses_forbidden_model_action_before_hold(self):
        stores = []
        def capture(kho):
            stores.append(kho)
            return tao_tools(kho)
        with patch.object(react, 'tao_tools', capture), patch('lib.model_gia.hanh_dong_tiep_theo',
                return_value=('GOI', 'book_seat', {'so_hieu':'VN122', 'ngay':'07/10'})):
            r = chay_react(kich_ban_s1())
        self.assertEqual(r.stop_type, 'vi_pham_rang_buoc')
        self.assertEqual(stores[0].dat_cho, {})
        self.assertEqual(r.tool_calls, 0)
        self.assertEqual(r.ban_giao['da_thu'], [])

    def test_react_checks_all_actions_in_one_batch(self):
        from langchain_core.messages import AIMessage
        gate = react.KiemQuyenMiddleware(self.rb(), KhoChuyenBay(kich_ban_s1().chuyen), 'hoi')
        calls = [dict(name='book_seat', args={'so_hieu':'VJ210', 'ngay':'07/10'},
                      id=f'call{i}', type='tool_call') for i in range(2)]
        with patch.object(react, 'xin_duyet', side_effect=[True, False]) as approval:
            result = gate.after_model({'messages':[AIMessage(content='', tool_calls=calls)]}, None)
        self.assertEqual(approval.call_count, 2)
        self.assertEqual(result['jump_to'], 'end')

    def test_refused_payment_preserves_hold_in_all_runners(self):
        for module, run in [(react, chay_react), (plan, chay_plan), (hybrid, chay_hybrid)]:
            with self.subTest(run=run.__name__), patch.object(module, 'xin_duyet', side_effect=[True, False]):
                r = run(kich_ban_s2(), che_do_duyet='hoi')
                if run is chay_plan:
                    continue  # stale plan before approval is this pattern's expected outcome
                self.assertEqual(r.stop_type, 'can_nguoi')
                self.assertEqual(r.ban_giao['trang_thai']['trang_thai'], 'held')
                self.assertFalse(r.ban_giao['trang_thai']['paid'])
                self.assertEqual(r.ban_giao['trang_thai']['ma_dat'], '4XJ1')

    def test_tool_failure_after_payment_retains_actual_paid_state(self):
        for module, run in [(react, chay_react), (plan, chay_plan), (hybrid, chay_hybrid)]:
            def faulty(kho):
                tools, ham = tao_tools(kho)
                original = ham['pay']
                def fails(ma_dat, the='corp_card'):
                    original(ma_dat, the)
                    raise RuntimeError('lost response after payment')
                ham['pay'] = fails
                # Keep the actual LangChain tool calling the modified payment callable.
                next(t for t in tools if t.name == 'pay').func = fails
                return tools, ham
            with self.subTest(run=run.__name__), patch.object(module, 'tao_tools', faulty):
                r = run(kich_ban_s1())
                self.assertEqual(r.stop_type, 'loi_runtime')
                self.assertTrue(r.ban_giao['trang_thai']['paid'])
                self.assertEqual(r.ban_giao['trang_thai']['ma_dat'], '4XJ1')

    def test_tool_budget_has_handoff(self):
        for run in (chay_plan, chay_hybrid):
            with self.subTest(run=run.__name__):
                r = run(kich_ban_s1(), tool_limit=1)
                self.assertEqual(r.stop_type, 'ngan_sach')
                self.assertEqual(r.tool_calls, 1)
                self.assertIsNotNone(r.ban_giao)

    def test_polling_not_misclassified_as_action_loop(self):
        det = LoopDetector()
        for _ in range(8):
            self.assertIsNone(det.check('get_booking', {'ma_dat': '4XJ1'},
                observation={'status': 'ok', 'trang_thai': 'pending'}, progress=0))

    def test_unknown_actions_stall_with_no_progress(self):
        det = LoopDetector()
        warnings = [det.check('check_seat', {'so_hieu':f'ZZ{i}'},
            observation={'error': f'unknown-{i}'}, progress=0) for i in range(7)]
        self.assertTrue(any(w and 'STALL' in w for w in warnings))

    def test_grounding_checks_entire_booking_id_and_amount(self):
        self.assertFalse(kiem_can_cu('Mã đặt chỗ 4XJ12', [{'ma_dat':'4XJ1'}])['dat'])
        self.assertFalse(kiem_can_cu('Giá 480.000đ', [{'gia':1480000}])['dat'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
