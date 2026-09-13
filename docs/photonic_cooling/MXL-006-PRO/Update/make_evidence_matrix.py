#!/usr/bin/env python
"""MXL-006 update memo: the evidence matrix -- every claim-relevant statement, its status
(MEASURED / ARGUED / WITHDRAWN), the number, and the evidence file. Rendered as a figure so the
attorney can drop it into the update without transcribing. Source of truth: docs/RESULTS_REGISTER.md.
"""
import os
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figures')
ROWS = [
    # (theme, statement, status, figure, evidence)
    ('Rescue', 'The laser holds a die that has no steady state; an unpowered array of the same film does not', 'MEASURED', '35/35 points, 3 leakage curves; 1.20 → 3.50 W/mm² under the per-block planner (2.40 under the seed shape)', 'mr_catalogue_curve_compare, array_coverage_armD, rescue_ladder_power'),
    ('Rescue', 'The top rung ends on conservation, not on the extractor: 0 tiles capped; the seed shape\'s "s = 1 at 2.40" was the planner\'s waste', 'MEASURED', 's = 0.99 at 3.50 (per-block, conservation); 4.00 bistable; hottest tile 23 W/mm² vs 813', 'rescue_ladder_power, extractor_armD'),
    ('Clock', 'The laser converts thermal headroom into clock until the transistor V/F ends it', 'MEASURED', '+14 % (1.00), +26 % (1.20) to the 4.17 GHz SPICE ceiling; +34 % on the table', 'clock_f1c_density'),
    ('Clock', '>10 GHz from cooling', 'WITHDRAWN', 'the ceiling is the device (4.17 / 5.0 GHz model ceilings); cooling does not move it', 'clock_f1c'),
    ('Density', 'Dark-silicon recovery: all 34 cores lit at 1.2 W/mm² per core where the package lights none', 'MEASURED', '11.6 W at 1.2 (seed-shape 17.3 withdrawn as a cost); 44 W at 1.5; the recorded 25 % "runaway" was an unfinished descent, holds for 0.8 W', 'dark_silicon'),
    ('Density', 'A 2× / 4× denser execution cluster is held at matched watts', 'MEASURED', 'to 202 / 162 W; plan 1.2–6.9× the reference; at 70 % utilisation 1.22× denser, every rung held', 'd1_exec_density_family_result, x3_utilisation'),
    ('Density', '>1000 W/mm² functional units / >10¹¹ transistors/cm² enabled by cooling', 'NOT MEASURED', 'no simulated die asks more than 5.3 W/mm² of a tile; 1000 W/mm² is the film\'s capability, not a die\'s need', 'register §4'),
    ('Non-thermal end', 'Every rung above ~1.3 W/mm² runs the rails at 1.5–3× the native current; the dense cluster 2× / 4× that', 'MEASURED (J); ARGUED (limit)', 'die current 1.29 → 2.88× from 1.00 to 2.40; EM 12–50× vs native at n = 2, 0.9 eV', 'pdn_em_skew'),
    ('Non-thermal end', 'Thermal clock skew grows with every rung; uniformity is not a clock lever', 'MEASURED (K); ARGUED (%)', '24 K → 60 K core gradient; 3.2 → 7.9 % of the period at 150 ps', 'pdn_em_skew'),
    ('Bursts', 'A modulated array absorbs a 2× burst the package throttles on', 'MEASURED', 'overshoot 0.51–0.67 K/W package → 0.17–0.20 modulated (2.5–3.3×); 2× held under target at 0.80', 'burst_absorption'),
    ('Bursts', 'Branch-prediction-driven laser modulation', 'NOT MEASURED', 'what is simulated is feed-forward from the power monitor (the burst\'s added watts removed at source)', '—'),
    ('Cache', 'Cooling the cache cuts its leakage 2.23× more than first thought; the knee is 280 K', 'MEASURED', 'cache leakage 2.7× (300 K) / 3.6× (280 K) down; ~14 % of die power (accounting-dependent)', 'cold_zone_prize_*, d3_cache_objective'),
    ('Cache', 'A monolithic die can be zoned hot / cold', 'WITHDRAWN', '1.24 K of gradient per 40 W; 280 K on the compute die costs the whole die', 'thermal_zone_separability, d3_cache_objective'),
    ('Cache', 'A storage die between the compute die and the sink collects the prize cheaply', 'WITHDRAWN (X4)', '99.3 W at every bond conductivity; an isolating bond removes the compute die\'s sink', 'gen3_stack'),
    ('Cache', 'The storage die off the compute die\'s heat path (2.5D or two sinks)', 'ARGUED', 'the 1.35 W cold-leakage argument applies only there', 'ladder §4.3'),
    ('Accelerator', 'The array holds a GA100-class die 700 → 2600 W on a microchannel plate where the control has none', 'MEASURED (assumed leakage split)', 'occ8 kernel at 700 W for 32 W; max tile 5.3 W/mm²', 'accel_f3_power_tol1'),
    ('Energy', '> 10× COP vs conventional cooling', 'MEASURED vs air; CONTRADICTED vs liquid below 2.4', 'system COP air 1.65 / 0.52 / – / –, liquid 17.3 / 3.9 / 3.0 / 0.97, photonic 2.6 / 1.9 / 1.6 / 1.3 at 1.20–2.40 W/mm²; air has no solution above 1.60', 'cooling_system_ledger'),
    ('Energy', '>30 % waste-heat recovery / net export on this die', 'WITHDRAWN', 'export crossing 614 K (90 % laser preset); on this die recovery is a cost reduction (effective COP 1.64 at the top rung)', 'recovery_at_temperature'),
    ('Energy', 'Efficiency claim that survives: performance per package watt at fixed cooling infrastructure', 'MEASURED', 'GFLOP/s per package watt FALLS with clock on every arm', 'clock_f1c_density'),
    ('Device', 'Yb:YLF as a zone material; η_ASF 0.02 as the state of the art', 'WITHDRAWN', 'GaAs / dye films > 1000 W/mm², η_ASF 0.10–0.60; Cr:LiSAF storage zone (η_EQE = 1 ceilings)', 'extractor_cooling_curves'),
    ('Device', 'Optics requirement: 200 µm pitch buys what 50 µm buys; 26 % coverage holds the same ceiling', 'MEASURED', 'costs 19.476 / 19.476 / 19.470 W across 813× in tile count', 'mr_catalogue_curve_compare, array_coverage_armD'),
]
COL = {'MEASURED': '#1b5e20', 'ARGUED': '#7a4b00', 'WITHDRAWN': '#a11d1d', 'NOT MEASURED': '#a11d1d'}


def status_col(s):
    for k, c in COL.items():
        if s.startswith(k):
            return c
    return '#333'


def main():
    fig, ax = plt.subplots(figsize=(18, 0.62 * len(ROWS) + 1.4))
    ax.set_axis_off()
    ax.set_xlim(0, 18); ax.set_ylim(-0.5, len(ROWS) + 1)
    ax.text(0.05, len(ROWS) + 0.4, 'Theme', fontweight='bold'); ax.text(1.4, len(ROWS) + 0.4, 'Statement', fontweight='bold')
    ax.text(8.2, len(ROWS) + 0.4, 'Status', fontweight='bold'); ax.text(10.7, len(ROWS) + 0.4, 'Figure / evidence (docs/evidence/*.json)', fontweight='bold')
    for i, (theme, stmt, status, fig_, ev) in enumerate(ROWS):
        y = len(ROWS) - 1 - i
        if i % 2 == 0:
            ax.add_patch(plt.Rectangle((0, y - 0.48), 18, 0.96, facecolor='#f0efec', edgecolor='none'))
        ax.text(0.05, y, theme, va='center', fontsize=8)
        ax.text(1.4, y, textwrap.fill(stmt, 78), va='center', fontsize=7.4)
        ax.text(8.2, y, textwrap.fill(status, 24), va='center', fontsize=7.4, color=status_col(status), fontweight='bold')
        ax.text(10.7, y + 0.17, textwrap.fill(fig_, 88), va='center', fontsize=6.9)
        ax.text(10.7, y - 0.25, ev, va='center', fontsize=6.4, color='#52514e')
    ax.set_title('MXL-006 update — evidence matrix from the HotGauge register (12 Sep 2026); 34-core 7 nm reference die unless stated', loc='left', fontsize=10, fontweight='bold')
    fig.savefig(os.path.join(OUT, 'fig_evidence_matrix.png'), dpi=170, bbox_inches='tight'); plt.close(fig)
    print('written fig_evidence_matrix.png')


if __name__ == '__main__':
    main()
