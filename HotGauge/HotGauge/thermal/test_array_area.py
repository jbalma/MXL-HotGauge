"""The photonic array charged its own footprint (§P0.18).

Until now every recorded result solved an array whose tiles filled the cooled surface edge to
edge. The device does not: couplers, waveguides, fibre access and the monolithic-backside LPC
share the pixel layer's footprint with the emitting extractor (v91 Fig. 9.1 / 9.8 / 9.12). These
tests pin three things that would otherwise go wrong silently:

* **coverage is areal.** ``tile_grid``'s ``fill`` is a linear edge fraction, so a "50 % array"
  written straight into it is a 25 % one. The conversion is tested, not assumed.
* **the achieved coverage is reported, not the requested one.** Snapping to the thermal grid
  moves it, and a row stamped with the request would overstate the array.
* **the default is 1.0 in every catalogue driver**, so the recorded catalogue reproduces
  un-flagged -- the same discipline as ``--rbb-policy`` and ``--leakage-curve``.
"""
import os
import re
import tempfile

import pytest

from HotGauge.thermal.mr_array import (tile_grid, fill_for_coverage, array_area_ledger,
                                       tile_flux_report, ArrayWiring, DEFAULT_COVERAGE,
                                       DEFAULT_PITCH_UM, project_plan_to_tiles, gap_blocks,
                                       nearest_tiles)

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


# ---------------------------------------------------------------------------
# coverage -> fill
# ---------------------------------------------------------------------------
def test_coverage_is_areal_so_fill_is_its_square_root():
    assert fill_for_coverage(1.0) == pytest.approx(1.0)
    assert fill_for_coverage(0.25) == pytest.approx(0.5)
    assert fill_for_coverage(0.5) == pytest.approx(0.7071067811865476)


@pytest.mark.parametrize('bad', (0.0, -0.1, 1.01, 2.0))
def test_coverage_outside_the_unit_interval_is_refused(bad):
    with pytest.raises(ValueError):
        fill_for_coverage(bad)


def test_the_default_is_full_coverage_which_is_every_recorded_result():
    assert DEFAULT_COVERAGE == 1.0


# ---------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------
def test_ledger_at_full_coverage_charges_nothing():
    tiles = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0)
    L = array_area_ledger(tiles, 4000.0, 4000.0)
    assert L['n_tiles'] == 64
    assert L['footprint_mm2'] == pytest.approx(16.0)
    assert L['extractor_mm2'] == pytest.approx(16.0)
    assert L['reserved_mm2'] == pytest.approx(0.0, abs=1e-9)
    assert L['coverage_achieved'] == pytest.approx(1.0)


def test_ledger_reports_the_requested_coverage_when_the_grid_can_honour_it():
    """0.25 at 500 um pitch on a 50 um grid is a 250 um tile: exactly representable."""
    tiles = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0,
                      fill=fill_for_coverage(0.25))
    L = array_area_ledger(tiles, 4000.0, 4000.0)
    assert L['n_tiles'] == 64
    assert L['extractor_mm2'] == pytest.approx(4.0)
    assert L['reserved_mm2'] == pytest.approx(12.0)
    assert L['coverage_achieved'] == pytest.approx(0.25)
    assert L['tile_mm2_max'] == pytest.approx(0.0625)


def test_ledger_reports_the_achieved_coverage_when_snapping_moves_it():
    """0.50 asks for a 353.6 um tile; the grid gives 350 um and the ledger must say 0.49, not
    0.50 -- a row stamped with the request overstates the array."""
    tiles = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0,
                      fill=fill_for_coverage(0.5))
    L = array_area_ledger(tiles, 4000.0, 4000.0)
    assert L['coverage_achieved'] == pytest.approx(0.49)
    assert abs(L['coverage_achieved'] - 0.5) < 0.02
    assert L['coverage_achieved'] != pytest.approx(0.5, abs=1e-6)


def test_gapped_tiles_stay_on_the_thermal_grid_and_inside_the_chip():
    w, h = 8800.0, 6100.0
    tiles = tile_grid(w, h, pitch_um=500.0, cell_um=50.0, fill=fill_for_coverage(0.5))
    for t in tiles:
        for v in (t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h']):
            assert v / 50.0 == pytest.approx(round(v / 50.0), abs=1e-9)
        assert t['x'] >= 0.0 and t['y'] >= 0.0
        assert t['x'] + t['w'] <= w + 1e-9 and t['y'] + t['h'] <= h + 1e-9
        assert t['w'] >= 50.0 and t['h'] >= 50.0


def test_gapped_tiles_do_not_overlap():
    tiles = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0, fill=fill_for_coverage(0.5))
    claimed = set()
    for t in tiles:
        for cx in range(int(round(t['x'] / 50.0)), int(round((t['x'] + t['w']) / 50.0))):
            for cy in range(int(round(t['y'] / 50.0)), int(round((t['y'] + t['h']) / 50.0))):
                assert (cx, cy) not in claimed, 'cell claimed twice at coverage 0.5'
                claimed.add((cx, cy))


# ---------------------------------------------------------------------------
# per-tile flux against h_max
# ---------------------------------------------------------------------------
def _four_tiles():
    return tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0)     # 4 x 1 mm^2


def test_flux_report_divides_by_the_tile_area_not_the_pitch_cell():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=100.0, fill=0.5)  # 4 x 0.25 mm^2
    name = tiles[0]['name']
    r = tile_flux_report({name: 5.0}, tiles, h_max_W_per_mm2=1000.0)
    assert r['n_engaged'] == 1
    assert r['max_flux_W_per_mm2'] == pytest.approx(20.0)
    assert r['max_flux_tile'] == name
    assert not r['over_h_max']


def test_flux_report_flags_a_tile_asked_for_more_than_the_extractor_emits():
    tiles = _four_tiles()
    r = tile_flux_report({tiles[0]['name']: 5.0, tiles[1]['name']: 1.0}, tiles,
                         h_max_W_per_mm2=4.0)
    assert r['over_h_max'] and r['n_tiles_over_h_max'] == 1
    assert r['mean_flux_W_per_mm2'] == pytest.approx(3.0)
    assert r['W_total'] == pytest.approx(6.0)


def test_flux_report_on_an_idle_array_is_empty_not_an_error():
    r = tile_flux_report({}, _four_tiles(), 1000.0)
    assert r['n_engaged'] == 0 and r['max_flux_W_per_mm2'] == 0.0 and not r['over_h_max']


# ---------------------------------------------------------------------------
# ArrayWiring carries it through
# ---------------------------------------------------------------------------
def _write_flp(d):
    flp = os.path.join(d, 'die_template.flp')
    with open(flp, 'w') as f:
        f.write('A :\n\tposition 0.0, 0.0 ;\n\tdimension 4000.0, 4000.0 ;\n'
                '\tpower values {powers[A]};\n')
    return flp


def test_wiring_default_coverage_reproduces_the_bare_tile_grid():
    with tempfile.TemporaryDirectory() as d:
        w = ArrayWiring(_write_flp(d), d, pitch_um=500.0, cell_um=50.0)
        bare = tile_grid(4000.0, 4000.0, pitch_um=500.0, cell_um=50.0)
        assert w.coverage == 1.0
        assert [(t['name'], t['x'], t['y'], t['w'], t['h']) for t in w.tiles] == \
            [(t['name'], t['x'], t['y'], t['w'], t['h']) for t in bare]
        f = w.area_fields()
        assert f['array_coverage'] == 1.0 and f['array_coverage_achieved'] == pytest.approx(1.0)
        assert f['array_reserved_mm2'] == pytest.approx(0.0, abs=1e-9)


def test_wiring_stamps_achieved_coverage_and_reserved_area():
    with tempfile.TemporaryDirectory() as d:
        w = ArrayWiring(_write_flp(d), d, pitch_um=500.0, cell_um=50.0, coverage=0.25)
        f = w.area_fields()
        assert f['array_coverage'] == 0.25
        assert f['array_coverage_achieved'] == pytest.approx(0.25)
        assert f['array_extractor_mm2'] == pytest.approx(4.0)
        assert f['array_reserved_mm2'] == pytest.approx(12.0)
        assert 'coverage 0.25' in repr(w)


def test_wiring_flux_report_reads_the_current_plan_in_planner_convention():
    with tempfile.TemporaryDirectory() as d:
        w = ArrayWiring(_write_flp(d), d, pitch_um=1000.0, cell_um=100.0, coverage=0.25)
        # 16 tiles of 500 um -> 0.25 mm^2 each. Stack convention is NEGATIVE.
        first = w.tiles[0]['name']
        w.set_mr_powers({t['name']: (-2.0 if t['name'] == first else 0.0) for t in w.tiles})
        r = w.flux_report(1000.0)
        assert r['n_engaged'] == 1
        assert r['max_flux_W_per_mm2'] == pytest.approx(8.0)
        assert r['W_total'] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# the catalogue drivers default to full coverage
# ---------------------------------------------------------------------------
COVERAGE_DRIVERS = ('mr_comparison.py', 'mr_clipping_study.py', 'clock_headroom.py')


@pytest.mark.parametrize('driver', COVERAGE_DRIVERS)
def test_every_catalogue_driver_defaults_to_full_coverage(driver):
    """`[!]` If this fails, every recorded array result from that driver has silently moved."""
    path = os.path.join(_REPO, 'examples', driver)
    if not os.path.isfile(path):
        pytest.skip('{} not present'.format(driver))
    src = open(path).read()
    m = re.search(r"add_argument\('--array-coverage',[^)]*?default=(\S+?)[,)]", src, re.S)
    assert m is not None, 'the --array-coverage flag is missing from {}'.format(driver)
    assert m.group(1) == 'DEFAULT_COVERAGE'
    # and the wiring actually receives it -- a flag that is parsed and dropped is the silent case
    assert 'coverage=args.array_coverage' in src, \
        '{} parses --array-coverage but never passes it to the wiring'.format(driver)


# ---------------------------------------------------------------------------
# a block under a gap is cooled by the nearest tile -- and that path is unreachable at full coverage
# ---------------------------------------------------------------------------
def _gapped():
    # 2 x 2 tiles of 500 um on a 1000 um pitch: tiles at [250,750] in each axis of each cell
    return tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=50.0, fill=0.5)


def test_full_coverage_has_no_gap_blocks_so_the_recorded_path_is_untouched():
    tiles = tile_grid(2000.0, 2000.0, pitch_um=1000.0, cell_um=50.0)
    blocks = {'A': (10.0, 10.0, 30.0, 30.0), 'B': (990.0, 990.0, 20.0, 20.0),
              'C': (1500.0, 100.0, 400.0, 50.0)}
    assert gap_blocks(blocks, tiles) == []
    tp = project_plan_to_tiles({'A': 1.0, 'B': 2.0, 'C': 3.0}, blocks, tiles)
    assert sum(tp.values()) == pytest.approx(6.0)


def test_a_gap_block_goes_to_its_nearest_tile_and_the_watts_are_conserved():
    tiles = _gapped()
    # the corner of the die is a gap at fill 0.5: nearest tile is the (0, 0) one
    blocks = {'corner': (0.0, 0.0, 50.0, 50.0)}
    assert gap_blocks(blocks, tiles) == ['corner']
    assert nearest_tiles(blocks['corner'], tiles) == ['MR_r00_c00']
    tp = project_plan_to_tiles({'corner': 0.5}, blocks, tiles)
    assert tp['MR_r00_c00'] == pytest.approx(0.5)
    assert sum(tp.values()) == pytest.approx(0.5)


def test_an_equidistant_gap_block_is_split_equally():
    tiles = _gapped()
    # centred on the seam between the two left-column tiles, in the horizontal gap between them
    blocks = {'seam': (490.0, 990.0, 20.0, 20.0)}
    near = nearest_tiles(blocks['seam'], tiles)
    assert sorted(near) == ['MR_r00_c00', 'MR_r01_c00']
    tp = project_plan_to_tiles({'seam': 1.0}, blocks, tiles)
    assert tp['MR_r00_c00'] == pytest.approx(0.5) and tp['MR_r01_c00'] == pytest.approx(0.5)


def test_gap_policy_error_reproduces_the_old_refusal():
    tiles = _gapped()
    blocks = {'corner': (0.0, 0.0, 50.0, 50.0)}
    with pytest.raises(ValueError, match='overlaps no cooling tile'):
        project_plan_to_tiles({'corner': 0.5}, blocks, tiles, gap_policy='error')
    with pytest.raises(ValueError):
        project_plan_to_tiles({'corner': 0.5}, blocks, tiles, gap_policy='sideways')


def test_wiring_counts_its_gap_blocks():
    with tempfile.TemporaryDirectory() as d:
        w = ArrayWiring(_write_flp(d), d, pitch_um=500.0, cell_um=50.0, coverage=0.25)
        # one 4000 x 4000 block cannot sit in a gap; the count is structural, and reported
        assert w.gap_blocks == []
        f = w.area_fields()
        assert f['array_n_gap_blocks'] == 0 and f['array_n_blocks'] == 1


def test_a_block_outside_the_array_footprint_is_still_refused():
    """The gap rule applies inside the footprint only; outside it is a coordinate-frame mistake."""
    tiles = _gapped()
    blocks = {'far': (50000.0, 50000.0, 100.0, 100.0)}
    with pytest.raises(ValueError, match='overlaps no cooling tile'):
        project_plan_to_tiles({'far': 1.0}, blocks, tiles)
