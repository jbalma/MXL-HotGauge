"""Tests for leakage-benefit allocation. Pure Python, no toolchain.

The policy this module implements is a candidate replacement for half of a decision recorded as
settled, so the tests pin both what it does and how small the lever turns out to be -- the second
being the part that decides whether it should replace anything.
"""
import math
import pytest

from HotGauge.thermal import leakage_targeting as LT


class _Model:
    """Stand-in carrying the real curve's SHAPE, which is the thing under test.

    A single exponential will not do here, and getting that wrong is how the first draft of these
    tests passed vacuously: with a constant doubling constant every block has identical
    benefit-per-watt and the policy degenerates to even splitting. The measured curve's local
    doubling constant runs from ~274 K at 310 K down to ~10 K at 350 K, and it is precisely that
    variation the allocator exists to exploit. These are the measured relative-leakage values from
    ``leakage_calibration/``, interpolated log-linearly and clamped below the floor as the real
    model clamps.
    """
    _T = (310., 320., 330., 340., 350., 360., 370., 380., 390., 400.)
    _R = (0.9231, 0.9467, 1.0000, 1.1302, 1.5976, 3.1538, 6.0412, 9.5914, 16.1592, 36.0993)

    def scale(self, T):
        T = max(float(T), LT.MIN_TRUSTWORTHY_T_K)
        if T >= self._T[-1]:
            return self._R[-1]
        for a, b, ra, rb in zip(self._T, self._T[1:], self._R, self._R[1:]):
            if a <= T <= b:
                f = (T - a) / (b - a)
                return math.exp(math.log(ra) + f * (math.log(rb) - math.log(ra)))
        return self._R[0]


class _Params:
    def __init__(self, h_max=0.5, dt_max_K=45.0, target_K=350.0):
        self.h_max = h_max
        self.dt_max_K = dt_max_K
        self.target_K = target_K
        self.spot_min_um = 10.0
        self.spot_policy = 'dilute'


def _geom(area=1.0, mind=50.0):
    return {'area_mm2': area, 'min_dim_um': mind}


class TestTheFigureOfMerit:
    def test_benefit_combines_sensitivity_and_leakage_response(self):
        m = _Model()
        b1 = LT.benefit_per_watt(370, 0.1, 1.0, m)
        b2 = LT.benefit_per_watt(370, 0.1, 2.0, m)
        assert b2 == pytest.approx(2 * b1)        # twice as easy to cool -> twice the benefit

    def test_a_hotter_block_is_worth_more_to_cool_than_a_cold_one(self):
        """The whole point: temperature excess cannot see this, benefit can."""
        m = _Model()
        assert LT.benefit_per_watt(370, 0.1, 1.0, m) > 5 * LT.benefit_per_watt(315, 0.1, 1.0, m)

    def test_a_block_that_cannot_be_cooled_is_worth_nothing(self):
        assert LT.benefit_per_watt(370, 0.1, 0.0, _Model()) == 0.0

    def test_the_lever_is_small_and_the_module_says_so(self):
        """~1.5% return at best on the real curve. If this ever exceeds 1.0 the claim that
        leakage payback cannot justify cooling on its own would need revisiting."""
        m = _Model()
        best = max(LT.benefit_per_watt(T, 0.23, 0.9, m) for T in range(310, 401, 5))
        assert best < 0.10, 'leakage payback alone would justify cooling -- recheck the claim'
        assert LT.MIN_BENEFIT_W_PER_W < best


class TestAllocation:
    def _setup(self):
        temps = {'hot': 380.0, 'warm': 360.0, 'cold': 315.0}
        geom = {b: _geom() for b in temps}
        sens = {b: 0.9 for b in temps}
        leak = {b: 0.1 for b in temps}
        return temps, geom, sens, leak

    def test_it_spends_where_the_curve_is_STEEPEST_which_is_not_the_hottest_block(self):
        """A result worth pinning, because the obvious intuition is wrong.

        At equal leakage the allocator prefers 360 K over 380 K, because the measured curve's
        local doubling constant is 10.7 K at 360 K and 13.3 K at 380 K -- the relative response
        peaks in the middle of the range, not at the top. "Cool the hottest block" is the
        clipping policy's rule; it is not the leakage-optimal one.
        """
        temps, geom, sens, leak = self._setup()
        plan, det = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 0.5)
        assert plan.get('warm', 0) > plan.get('cold', 0)
        assert plan.get('warm', 0) >= plan.get('hot', 0)

    def test_and_a_cold_block_is_always_last(self):
        """The one direction that is unambiguous: the flat end of the curve is worth nothing."""
        temps, geom, sens, leak = self._setup()
        plan, _ = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 0.5)
        assert plan.get('cold', 0.0) == 0.0 or plan['cold'] < plan.get('warm', 0)

    def test_a_block_below_the_trustworthy_floor_is_skipped_not_guessed(self):
        temps, geom, sens, leak = self._setup()
        temps['cold'] = 300.0
        _, det = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 0.5)
        assert det['skipped']['cold'] == 'already_below_trustworthy_floor'

    def test_blocks_with_no_leakage_are_skipped(self):
        temps, geom, sens, leak = self._setup()
        leak['hot'] = 0.0
        _, det = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 0.5)
        assert det['skipped']['hot'] == 'no_leakage'

    def test_device_caps_bind_the_same_way_clipping_plan_applies_them(self):
        temps, geom, sens, leak = self._setup()
        geom['hot'] = _geom(area=0.02)                 # h_max * area = 0.01 W
        plan, _ = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 5.0)
        assert plan['hot'] <= 0.01 + 1e-9

    def test_no_block_is_cooled_below_the_trustworthy_floor(self):
        temps, geom, sens, leak = self._setup()
        plan, det = LT.leakage_benefit_plan(temps, geom, _Params(h_max=100.0, dt_max_K=500.0),
                                            sens, leak, _Model(), 200.0)
        for b, d in det['per_block'].items():
            assert d['T_to_K'] >= LT.MIN_TRUSTWORTHY_T_K - 1e-6

    def test_unspent_budget_is_reported_rather_than_forced_out(self):
        """Leftover budget means nothing remaining is worth cooling. That is a result."""
        temps, geom, sens, leak = self._setup()
        _, det = LT.leakage_benefit_plan(temps, geom, _Params(h_max=0.001), sens, leak,
                                         _Model(), 10.0)
        assert det['unspent_W'] > 0
        assert 'not a failure' in det['note']

    def test_zero_budget_is_a_no_op(self):
        temps, geom, sens, leak = self._setup()
        plan, _ = LT.leakage_benefit_plan(temps, geom, _Params(), sens, leak, _Model(), 0.0)
        assert plan == {}


class TestScoringIsPolicyAgnostic:
    """The clipping plan was never built to maximise leakage, so scoring it fairly is what makes
    the comparison mean anything."""

    def test_any_plan_can_be_scored(self):
        temps = {'a': 380.0, 'b': 360.0}
        sens = {'a': 0.9, 'b': 0.9}
        leak = {'a': 0.1, 'b': 0.1}
        saved = LT.leakage_saved_by_plan({'a': 0.5}, temps, sens, leak, _Model())
        assert saved > 0

    def test_cooling_a_hotter_block_saves_more_at_equal_watts(self):
        temps = {'a': 380.0, 'b': 320.0}
        sens = {'a': 0.9, 'b': 0.9}
        leak = {'a': 0.1, 'b': 0.1}
        m = _Model()
        assert (LT.leakage_saved_by_plan({'a': 0.5}, temps, sens, leak, m) >
                LT.leakage_saved_by_plan({'b': 0.5}, temps, sens, leak, m))

    def test_scoring_respects_the_same_floor_as_allocation(self):
        """A huge plan cannot claim savings from cooling below where the model can see."""
        temps = {'a': 380.0}
        s = LT.leakage_saved_by_plan({'a': 1e6}, temps, {'a': 0.9}, {'a': 0.1}, _Model())
        capped = 0.1 * (1.0 - _Model().scale(LT.MIN_TRUSTWORTHY_T_K) / _Model().scale(380.0))
        assert s == pytest.approx(capped)
