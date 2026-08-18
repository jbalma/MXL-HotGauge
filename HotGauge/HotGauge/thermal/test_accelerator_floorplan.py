"""Tests for the die-shot-derived GA100 accelerator floorplan.

The point of these is that a floorplan is easy to get subtly wrong in ways a thermal solve will
happily accept -- overlapping blocks, a die that does not close, a tile count that silently drifts
-- and every such error shows up as a temperature, not as an exception. So the geometry is checked
against the measurement rather than against itself, and the assumed inputs are checked for being
labelled as assumed.
"""
import pytest

from HotGauge.thermal.accelerator_floorplan import (
    GA100_AREAS, GA100_COUNTS, GA100_POWER_SPLIT, SM_SRAM_FRACTION,
    ga100_geometry, ga100_consistency, ga100_floorplan, ga100_block_powers,
    block_areas_mm2, power_density_by_class, power_split_sensitivity)


def _blocks(path):
    """(name, x, y, w, h) for every block, in mm."""
    out, name, pos = [], None, None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.endswith(':'):
                name = s[:-1].strip()
            elif s.startswith('position'):
                pos = [float(v) / 1000.0 for v in s[len('position'):].strip(' ;').split(',')]
            elif s.startswith('dimension'):
                d = [float(v) / 1000.0 for v in s[len('dimension'):].strip(' ;').split(',')]
                out.append((name, pos[0], pos[1], d[0], d[1]))
    return out


# ---------------------------------------------------------------------------
# Geometry against the measurement
# ---------------------------------------------------------------------------
def test_die_outline_reproduces_the_measured_area():
    g = ga100_geometry()
    assert g['w_die'] * g['h_die'] == pytest.approx(GA100_AREAS['die_mm2'], rel=1e-9)
    # A100 is a reticle-limit part: ~32 x 25 mm. Anything far from that means the aspect is wrong.
    assert 30.0 < g['w_die'] < 34.0
    assert 24.0 < g['h_die'] < 27.0


def test_compute_tile_has_a_plausible_shape():
    """An SM 10 mm wide and 0.3 mm tall would have the right area and be nonsense thermally --
    lateral spreading is what the whole study turns on."""
    g = ga100_geometry()
    assert g['w_sm'] * g['h_sm'] == pytest.approx(GA100_AREAS['sm_mm2'], rel=1e-9)
    assert 1.0 < g['w_sm'] / g['h_sm'] < 3.0


def test_the_arrangement_leaves_a_plausible_remainder():
    """SM + L2 are the measured blocks; everything else is lumped. If the arrangement were wrong
    the remainder would be absurd -- negative, or nearly the whole die."""
    c = ga100_consistency()
    assert c['closure_err_mm2'] == pytest.approx(0.0, abs=1e-6)
    assert 0.45 < c['sm_frac'] < 0.60          # 128 SM x 3.43 mm^2 is about half the die
    assert 0.10 < c['l2_frac'] < 0.20          # 48 MB of L2
    assert 0.25 < c['lumped_frac'] < 0.40      # PHY, MC, NVLINK, routing, control


def test_every_block_edge_lands_on_the_thermal_grid():
    """The bug this pins actually happened. 3D-ICE quantises every block edge to its own grid, so
    two blocks exactly adjacent in floating point can come back OVERLAPPING after quantisation --
    it reports "Intersection between ..." and aborts. A non-overlap check on the unquantised
    geometry passes happily and catches none of it, which is what it did."""
    import os
    import tempfile
    for cell in (50.0, 100.0):
        path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
        ga100_floorplan(path, cell_um=cell)
        for name, x, y, w, h in _blocks(path):
            for label, v in (('x', x), ('y', y), ('x+w', x + w), ('y+h', y + h)):
                # values are in mm here, the grid in um
                assert abs((v * 1000.0 / cell) - round(v * 1000.0 / cell)) < 1e-6, \
                    '{} {} off the {:g} um grid'.format(name, label, cell)


def test_coarse_grid_that_would_distort_the_areas_is_rejected():
    """Snapping a 667 um L2 tile to a 1 mm grid would silently rewrite the density accounting the
    whole study reads off. Better to refuse than to return a plausible wrong number."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    with pytest.raises(ValueError):
        ga100_floorplan(path, cell_um=1000.0)


def test_blocks_tile_the_die_without_overlapping():
    """3D-ICE will not complain about overlapping blocks; it will just double-count their power."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    ga100_floorplan(path, cell_um=100.0)
    g = ga100_geometry()
    blocks = _blocks(path)
    # The die 3D-ICE sees is the floorplan's own bounding box, so bounds are checked against that
    # rather than the pre-snap outline; that it stays within a cell of the measured die is the
    # separate area check.
    w_box = max(x + w for _, x, _, w, _ in blocks)
    h_box = max(y + h for _, _, y, _, h in blocks)
    assert w_box == pytest.approx(g['w_die'], abs=0.11)
    assert h_box == pytest.approx(g['h_die'], abs=0.11)
    for name, x, y, w, h in blocks:
        assert x >= -1e-6 and y >= -1e-6, name
        assert x + w <= w_box + 1e-6, name
        assert y + h <= h_box + 1e-6, name
        assert w > 0 and h > 0, name
    # Pairwise overlap on a sample grid of probe points: an exact O(n^2) rectangle intersection
    # over 367 blocks, which is cheap enough to just do properly.
    for i in range(len(blocks)):
        n1, x1, y1, w1, h1 = blocks[i]
        for j in range(i + 1, len(blocks)):
            n2, x2, y2, w2, h2 = blocks[j]
            overlap_x = min(x1 + w1, x2 + w2) - max(x1, x2)
            overlap_y = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert overlap_x <= 1e-6 or overlap_y <= 1e-6, '{} overlaps {}'.format(n1, n2)


def test_written_block_areas_sum_to_the_die():
    """No gaps either: unpopulated silicon would spread heat the model then gets for free."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    ga100_floorplan(path)
    total = sum(block_areas_mm2(path).values())
    # Snapping moves the outer edges by up to a cell, so this is a close-not-exact check.
    assert total == pytest.approx(GA100_AREAS['die_mm2'], rel=2e-3)


def test_block_counts_match_the_die_shot():
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    _, classes = ga100_floorplan(path, split_sm=True)
    counts = {}
    for cls in classes.values():
        counts[cls] = counts.get(cls, 0) + 1
    assert counts['sm_dp'] == GA100_COUNTS['n_sm']
    assert counts['sm_l1'] == GA100_COUNTS['n_sm']
    assert counts['l2'] == GA100_COUNTS['n_l2_tiles']
    assert counts['hbm_phy'] == GA100_COUNTS['n_hbm_phy']
    assert counts['mem_ctrl'] == GA100_COUNTS['n_mem_ctrl']
    assert counts['nvlink'] == GA100_COUNTS['n_nvlink_phy']


def test_unsplit_tiles_give_one_block_per_sm():
    import os
    import tempfile
    d = tempfile.mkdtemp()
    _, classes = ga100_floorplan(os.path.join(d, 'a.flp'), split_sm=False)
    counts = {}
    for cls in classes.values():
        counts[cls] = counts.get(cls, 0) + 1
    assert counts['sm'] == GA100_COUNTS['n_sm']
    assert 'sm_dp' not in counts


def test_split_tile_uses_the_measured_sram_fraction():
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    ga100_floorplan(path, split_sm=True)
    areas = block_areas_mm2(path)
    dp, l1 = areas['SM0_DP'], areas['SM0_L1']
    # Grid snapping perturbs a single tile by up to a cell on each edge; the class TOTAL is what
    # ga100_floorplan itself checks against the measurement.
    assert l1 / (dp + l1) == pytest.approx(SM_SRAM_FRACTION, rel=0.10)
    assert dp + l1 == pytest.approx(GA100_AREAS['sm_mm2'], rel=0.10)


# ---------------------------------------------------------------------------
# Power, and the fact that it is assumed
# ---------------------------------------------------------------------------
def test_power_split_conserves_the_budget():
    import os
    import tempfile
    _, classes = ga100_floorplan(os.path.join(tempfile.mkdtemp(), 'a.flp'))
    powers, meta = ga100_block_powers(400.0, classes)
    assert sum(powers.values()) == pytest.approx(400.0, rel=1e-9)
    assert meta['calibrated'] is False
    assert 'ASSUMED' in meta['note']


def test_power_split_must_sum_to_one():
    import os
    import tempfile
    _, classes = ga100_floorplan(os.path.join(tempfile.mkdtemp(), 'a.flp'))
    bad = dict(GA100_POWER_SPLIT)
    bad['sm'] = 0.9
    with pytest.raises(ValueError):
        ga100_block_powers(400.0, classes, split=bad)


def test_tiles_of_a_class_are_uniform_so_any_hotspot_is_geometric():
    """The uniform-activity choice is load-bearing: it means a hotspot in the solve came from
    where a block SITS, not from an activity imbalance assumed into the input."""
    import os
    import tempfile
    _, classes = ga100_floorplan(os.path.join(tempfile.mkdtemp(), 'a.flp'))
    powers, _ = ga100_block_powers(400.0, classes)
    dp = [p for n, p in powers.items() if classes[n] == 'sm_dp']
    assert len(set('{:.9f}'.format(p) for p in dp)) == 1


def test_datapath_is_denser_than_its_own_sram():
    """If the array came out hotter than the tensor datapath the split would be wrong."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'a.flp')
    _, classes = ga100_floorplan(path)
    powers, _ = ga100_block_powers(400.0, classes)
    d = power_density_by_class(classes, powers, block_areas_mm2(path))
    assert d['sm_dp']['W_per_mm2'] > 2.0 * d['sm_l1']['W_per_mm2']


def test_sensitivity_renormalises_instead_of_breaking_the_sum():
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'a.flp')
    _, classes = ga100_floorplan(path)
    areas = block_areas_mm2(path)
    s = power_split_sensitivity(400.0, classes, areas, vary='hbm_phy', factors=(0.5, 1.0, 1.5))
    assert s[0.5]['hbm_phy']['W_per_mm2'] < s[1.0]['hbm_phy']['W_per_mm2']
    assert s[1.0]['hbm_phy']['W_per_mm2'] < s[1.5]['hbm_phy']['W_per_mm2']
    # halving one share must RAISE the others, not lose the power
    assert s[0.5]['sm_dp']['W_per_mm2'] > s[1.0]['sm_dp']['W_per_mm2']
    for fac in s:
        total = sum(v['W'] for v in s[fac].values())
        assert total == pytest.approx(400.0, rel=1e-6)


def test_density_spread_is_narrow_which_is_the_whole_point():
    """The prediction this floorplan exists to test: an accelerator's blocks are far closer in
    density than a CPU's, so the die should be highly degenerate. Pinned as a property of the
    input, NOT as a thermal result -- the solve is what tests the consequence."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'a.flp')
    _, classes = ga100_floorplan(path)
    powers, _ = ga100_block_powers(400.0, classes)
    d = power_density_by_class(classes, powers, block_areas_mm2(path))
    dens = [v['W_per_mm2'] for v in d.values()]
    assert max(dens) / min(dens) < 6.0


# ---------------------------------------------------------------------------
# Kernel activity -- the falsification test for the uniform result
# ---------------------------------------------------------------------------
def _classes():
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'ga100.flp')
    return ga100_floorplan(path)[1]


def test_the_irds_curve_refuses_to_supply_the_boost_ratio():
    """The obvious move -- read the boost cost off the IRDS V/F curve -- is wrong here, and the
    code has to say so rather than quietly returning the number.

    That curve is anchored on the node's 3.86 GHz wireloaded logic path. Asked for a 1.4 GHz GPU
    clock it extrapolates to about 0.30 V against a 0.70 V nominal, which is not what A100 silicon
    does: a GPU's low clock is a wide, wire-dominated design choice, not a logic path coasting near
    threshold. Same limitation as docs/CLOCK_HEADROOM.md records, in a new place.
    """
    from HotGauge.thermal.accelerator_floorplan import sm_boost_power_ratio
    ratio, meta = sm_boost_power_ratio()
    assert meta['extrapolated'] is True
    assert meta['usable'] is False
    assert meta['V_base'] < 0.6 * meta['vdd']
    assert 'extrapolat' in meta['why'] or 'anchored' in meta['why']
    assert ratio > 1.0                       # it does return a number; it just cannot be trusted


def test_occupancy_uses_the_stated_assumption_not_the_extrapolation():
    from HotGauge.thermal.accelerator_floorplan import (kernel_activity,
                                                        DEFAULT_BOOST_POWER_RATIO)
    _, meta = kernel_activity(_classes(), kernel='occupancy', n_active=8)
    assert meta['boost_ratio'] == pytest.approx(DEFAULT_BOOST_POWER_RATIO)
    assert 'ASSUMED' in meta['boost']['source']
    assert meta['boost']['irds_diagnostic']['usable'] is False


def test_uniform_kernel_is_the_identity():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    classes = _classes()
    act, _ = kernel_activity(classes, kernel='uniform')
    assert set(act) == set(classes)
    assert all(v == 1.0 for v in act.values())


def test_occupancy_boosts_the_active_tiles_and_idles_the_rest():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    classes = _classes()
    act, meta = kernel_activity(classes, kernel='occupancy', n_active=8,
                                placement='contiguous', idle_fraction=0.1, boost_ratio=1.9)
    assert act['SM0_DP'] == pytest.approx(1.9)
    assert act['SM7_DP'] == pytest.approx(1.9)
    assert act['SM8_DP'] == pytest.approx(0.1)
    assert act['SM127_DP'] == pytest.approx(0.1)
    # non-SM classes are untouched: the uncore does not idle because the SMs did
    assert act['L2_0'] == pytest.approx(1.0)
    assert act['HBM_PHY_B0'] == pytest.approx(1.0)
    assert meta['n_active'] == 8


def test_placement_changes_which_tiles_run_and_is_recorded():
    """A hotspot from 8 adjacent tiles and a non-hotspot from 8 scattered ones are different
    results, so the placement has to travel with the number."""
    from HotGauge.thermal.accelerator_floorplan import active_sm_set
    contig = active_sm_set(8, 128, 'contiguous')
    scatter = active_sm_set(8, 128, 'scattered')
    assert contig == set(range(8))
    assert len(scatter) == 8
    assert max(scatter) - min(scatter) > 100        # spread across the die, not bunched
    assert contig != scatter


def test_cluster_placement_fills_whole_groups_before_the_next():
    from HotGauge.thermal.accelerator_floorplan import active_sm_set
    a = active_sm_set(40, 128, 'cluster')
    assert set(range(32)) <= a                       # first cluster full
    assert len(a) == 40
    assert max(a) < 32 + 32                          # spilled into the second only


def test_low_occupancy_lowers_die_power_rather_than_concentrating_a_fixed_budget():
    """The physically honest choice, and it cuts AGAINST finding a hotspot. A real part cannot
    exceed its own V/F envelope however much thermal headroom the idle tiles free up, so the die
    total falls. Renormalising back to the TDP would turn a low-occupancy kernel into a power
    virus and manufacture the very hotspot this study is testing for."""
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    classes = _classes()
    act, _ = kernel_activity(classes, kernel='occupancy', n_active=8, boost_ratio=1.9)
    _, meta = ga100_block_powers(400.0, classes, activity=act)
    assert meta['realised_W'] < 400.0
    assert meta['activity_applied'] is True


def test_tensor_kernel_moves_power_without_adding_any():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    classes = _classes()
    act, meta = kernel_activity(classes, kernel='tensor')
    base, _ = ga100_block_powers(400.0, classes)
    hot, m2 = ga100_block_powers(400.0, classes, activity=act)
    assert m2['realised_W'] == pytest.approx(400.0, rel=1e-9)      # pure redistribution
    assert hot['SM0_DP'] > base['SM0_DP']
    assert hot['SM0_L1'] < base['SM0_L1']
    assert hot['L2_0'] == pytest.approx(base['L2_0'])


def test_memory_bound_kernel_idles_compute_and_keeps_the_interface_hot():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    classes = _classes()
    act, _ = kernel_activity(classes, kernel='memory_bound', idle_fraction=0.1)
    assert act['SM0_DP'] == pytest.approx(0.1)
    assert act['HBM_PHY_B0'] == pytest.approx(1.0)
    assert act['MEMCTRL_B0'] == pytest.approx(1.0)
    _, meta = ga100_block_powers(400.0, classes, activity=act)
    assert meta['realised_W'] < 400.0      # a memory-bound kernel is not a power virus


def test_tensor_kernel_needs_split_tiles():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity
    import os
    import tempfile
    _, classes = ga100_floorplan(os.path.join(tempfile.mkdtemp(), 'a.flp'), split_sm=False)
    with pytest.raises(ValueError):
        kernel_activity(classes, kernel='tensor')


def test_bad_kernel_inputs_are_rejected():
    from HotGauge.thermal.accelerator_floorplan import kernel_activity, active_sm_set
    classes = _classes()
    with pytest.raises(ValueError):
        kernel_activity(classes, kernel='not_a_kernel')
    with pytest.raises(ValueError):
        kernel_activity(classes, kernel='occupancy')          # n_active missing
    with pytest.raises(ValueError):
        active_sm_set(0, 128, 'contiguous')
    with pytest.raises(ValueError):
        active_sm_set(200, 128, 'contiguous')
    with pytest.raises(ValueError):
        active_sm_set(8, 128, 'diagonally')
