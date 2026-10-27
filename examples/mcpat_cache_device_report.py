#!/usr/bin/env python
"""§P0.40: McPAT A/B on the caches' DEVICE CLASS -- is the cache-leakage prize a device choice?

    bash spice_toolchain/tmp/mcpat_cache_device_ab.sh     # on the node: three McPAT runs
    python examples/mcpat_cache_device_report.py          # -> docs/evidence/mcpat_cache_device.json

The recorded trace's McPAT XML gives every L2 and the L3 ``device_type = 0`` (HP), the core logic's
class. This reads the same steady slice re-run with the caches at 0 (HP, as recorded), 1 (LSTP)
and 2 (LOP): subthreshold + gate leakage of the L3, of one L2 and of the processor, at McPAT's
330 K. Real cache arrays use low-leakage bitcells, so the truth sits between the HP and LSTP
columns and far nearer LSTP; LOP at this fork's 7 nm tables is not credible (it RAISES leakage
23x) and is recorded, not used.
"""
import os
import re
import sys
import json

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(_REPO, 'results', 'mcpat_cache_device')
KEYS = ('Area', 'Peak Dynamic', 'Subthreshold Leakage', 'Gate Leakage', 'Runtime Dynamic')
NAMES = ('Processor', 'Total Cores', 'Total L3s', 'Core', 'L2', 'L3')


def parse(path):
    t = open(path).read().split('\n')
    out = {}
    for i, l in enumerate(t):
        # `[!]` McPAT's per-core L2 header has NO trailing colon (CLAUDE.md, the raw-McPAT traps)
        m = re.match(r'^\s*(Processor|Total Cores|Total L3s|Core|L2|L3)\b[^=]*$', l)
        if not m or m.group(1) in out:
            continue
        d = {}
        for k in t[i + 1:i + 12]:
            mm = re.match(r'\s*(%s)\s*=\s*([0-9.eE+-]+)' % '|'.join(KEYS), k)
            if mm and mm.group(1) not in d:
                d[mm.group(1)] = float(mm.group(2))
        out[m.group(1)] = d
    return out


def main():
    R = {dt: parse(os.path.join(BASE, 'caches_dt%d.txt' % dt)) for dt in (0, 1, 2)}
    leak = lambda d: d.get('Subthreshold Leakage', 0.0) + d.get('Gate Leakage', 0.0)
    n_l2 = 8
    rows = {}
    for dt, lab in ((0, 'HP (recorded)'), (1, 'LSTP'), (2, 'LOP')):
        r = R[dt]
        cache = leak(r['Total L3s']) + n_l2 * leak(r['L2'])
        proc = leak(r['Processor'])
        rows[lab] = {'device_type': dt, 'L3_leak_W': leak(r['Total L3s']), 'L2_leak_W_each': leak(r['L2']),
                     'cache_leak_W': cache, 'processor_leak_W': proc, 'cache_share_of_leak': cache / proc,
                     'processor_dynamic_W': r['Processor'].get('Runtime Dynamic'),
                     'static_fraction': proc / (proc + r['Processor'].get('Runtime Dynamic', 0.0)),
                     'L3_area_mm2': r['Total L3s'].get('Area'), 'L2_area_mm2_each': r['L2'].get('Area')}
        print('%-14s L3 %.4f W  L2 %.4f W each  caches %.4f W = %.1f %% of processor leakage %.3f W; static fraction %.1f %%' % (
            lab, rows[lab]['L3_leak_W'], rows[lab]['L2_leak_W_each'], cache, 100 * cache / proc, proc, 100 * rows[lab]['static_fraction']))
    hp, ls = rows['HP (recorded)'], rows['LSTP']
    sc = {'P1_prize_is_the_device_choice': {'measured': {'cache_leak_ratio_HP_over_LSTP': hp['cache_leak_W'] / ls['cache_leak_W'],
                                                           'LOP_over_HP': rows['LOP']['cache_leak_W'] / hp['cache_leak_W']},
                                            'verdict': 'confirmed' if hp['cache_leak_W'] / ls['cache_leak_W'] >= 10 else 'FALSIFIED'},
          'P2_static_fraction': {'measured': {'HP': hp['static_fraction'], 'LSTP': ls['static_fraction'],
                                              'cache_share_HP': hp['cache_share_of_leak'], 'cache_share_LSTP': ls['cache_share_of_leak']},
                                 'verdict': 'see the checklist: McPAT-native scope (8 cores, raw), not the floorplan ledger'},
          'P3_mcpat_accepts_the_classes': {'measured': {'ran': True, 'LOP_credible': False}, 'verdict': 'not as predicted: all three ran; LOP is not credible at 7 nm'}}
    out = {'note': __doc__.strip(), 'source_xml': 'mcpat_runs/7nm/linpack_3.8GHz/energystats-temp-2000000000000.xml',
           'T_K': 330, 'n_L2': n_l2, 'rows': rows, 'raw': {str(k): v for k, v in R.items()}, 'scorecard': sc}
    p = os.path.join(_REPO, 'docs', 'evidence', 'mcpat_cache_device.json')
    json.dump(out, open(p, 'w'), indent=1)
    print('written:', os.path.relpath(p, _REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
