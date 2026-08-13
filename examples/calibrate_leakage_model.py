#!/usr/bin/env python
"""Measure McPAT's leakage-vs-temperature response instead of assuming it.

Why
---
The feedback loop scales McPAT's leakage by ``exp(ln2*(T - T_ref)/dT_2x)``. Both parameters
have been *assumptions*:

* ``T_ref`` -- the temperature at which McPAT extracted the baseline leakage. It is the anchor
  of the whole exponential. Our Sniper->McPAT pipeline hardcodes it
  (``snipersim/tools/mcpat.py``: ``<param name="temperature" value="330"/>``), yet the default
  in ``leakage.py`` was 360 K. At ``dT_2x = 15 K`` a 30 K anchor error is a **4x** error in
  leakage at every temperature -- in the optimistic direction (it *underestimates* leakage,
  so it also underestimates runaway risk).
* ``dT_2x`` -- the doubling constant, defaulted to 10-15 K with no measurement behind it.

Both feed the electrothermal loop gain ``G = R * ln2/dT_2x * P_leak(T)``, and runaway is
``G >= 1``, so an exponentially-sensitive stability boundary currently rests on two guesses.

What this does
--------------
Re-runs McPAT on one real XML at a sweep of ``temperature`` values, extracts total and
per-unit leakage at each, and reports:

1. the true ``T_ref`` found in the XML (so nothing has to be assumed downstream),
2. the measured relative-leakage curve, ready for ``LeakageModel.from_table``,
3. the effective doubling constant implied by that curve -- globally and per unit -- so the
   ``exponential(dT_2x)`` shorthand can be checked rather than trusted.

McPAT solves for leakage at the XML temperature, so this is McPAT's own model being
characterized -- it inherits McPAT's accuracy, and is a calibration of *our surrogate to
McPAT*, not to silicon.

Example
-------
    python examples/calibrate_leakage_model.py --trace-dir mcpat_runs/7nm/linpack_3.8GHz \\
        --temps 320 330 340 350 360 370 380
"""
import os
import re
import sys
import json
import shutil
import argparse
import subprocess

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

TEMP_RGX = re.compile(r'(<param\s+name="temperature"\s+value=")([0-9.]+)(")')
#: "  Subthreshold Leakage = 3.05158 W" (ignore the power-gating variant, which is a
#: different quantity -- leakage *with* power gating applied, not the baseline)
LEAK_RGX = re.compile(r'^\s*(Subthreshold Leakage|Gate Leakage)\s*=\s*([0-9.eE+-]+)\s*W\s*$')
SUBTOTAL_RGX = re.compile(r'^\s*Subthreshold Leakage with power gating')


def read_xml_tref(xml_path):
    with open(xml_path) as f:
        m = TEMP_RGX.search(f.read())
    if not m:
        raise RuntimeError('No <param name="temperature"> in {}'.format(xml_path))
    return float(m.group(2))


def write_xml_at_temp(src_xml, temp_K, dst_xml):
    with open(src_xml) as f:
        content = f.read()
    content, n = TEMP_RGX.subn(
        lambda m: '{}{:g}{}'.format(m.group(1), temp_K, m.group(3)), content)
    if n < 1:
        raise RuntimeError('Could not set temperature in {}'.format(src_xml))
    with open(dst_xml, 'w') as f:
        f.write(content)
    return n


def run_mcpat(mcpat_bin, xml_path, out_txt, print_level=5):
    with open(out_txt, 'w') as out:
        proc = subprocess.run([mcpat_bin, '-infile', xml_path,
                               '-print_level', str(print_level)],
                              stdout=out, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError('McPAT failed on {}: {}'.format(
            xml_path, proc.stderr.decode()[:400]))
    return out_txt


def total_leakage(out_txt):
    """Sum Subthreshold + Gate leakage over the top-level Processor block.

    McPAT's print_level 5 output repeats leakage at every hierarchy level, so summing every
    match would multiply-count. The first Processor-level pair is the chip total.
    """
    sub = gate = None
    with open(out_txt) as f:
        for line in f:
            if SUBTOTAL_RGX.match(line):
                continue
            m = LEAK_RGX.match(line)
            if not m:
                continue
            if m.group(1) == 'Subthreshold Leakage' and sub is None:
                sub = float(m.group(2))
            elif m.group(1) == 'Gate Leakage' and gate is None:
                gate = float(m.group(2))
            if sub is not None and gate is not None:
                break
    if sub is None:
        raise RuntimeError('No leakage found in {}'.format(out_txt))
    return sub, (gate or 0.0)


def implied_doubling(temps_K, rel):
    """Effective doubling constant [K] from a relative-leakage curve, by log-linear fit.

    rel = 2**((T - T_ref)/dT_2x)  =>  log2(rel) = (T - T_ref)/dT_2x, so the slope of
    log2(rel) vs T is 1/dT_2x. A single number only if the curve is truly exponential --
    the residual reported alongside says whether that shorthand is defensible.
    """
    t = np.asarray(temps_K, dtype=float)
    y = np.log2(np.asarray(rel, dtype=float))
    slope, intercept = np.polyfit(t, y, 1)
    if slope <= 0:
        return float('nan'), float('nan')
    fit = slope * t + intercept
    resid = float(np.max(np.abs(2.0 ** y - 2.0 ** fit)))
    return float(1.0 / slope), resid


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trace-dir', default=None)
    ap.add_argument('--tech-node', type=int, default=7)
    ap.add_argument('--xml', default=None, help='specific XML; default = first in trace dir')
    ap.add_argument('--temps', type=float, nargs='+',
                    default=[320, 330, 340, 350, 360, 370, 380])
    ap.add_argument('--mcpat-bin', default=os.path.join(_REPO, 'McPAT', 'mcpat'))
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--out-json', default=None)
    args = ap.parse_args()

    args.trace_dir = args.trace_dir or os.path.join(
        _HERE, 'ICE_simulation_from_MCPAT', 'traces', 'example_workload',
        '{}nm'.format(args.tech_node))
    args.out_dir = args.out_dir or os.path.join(os.getcwd(), 'leakage_calibration')
    os.makedirs(args.out_dir, exist_ok=True)

    if args.xml is None:
        xmls = sorted([f for f in os.listdir(args.trace_dir) if f.endswith('.xml')])
        if not xmls:
            raise SystemExit('No .xml in {} -- run the Sniper->McPAT pipeline first'.format(
                args.trace_dir))
        args.xml = os.path.join(args.trace_dir, xmls[0])
    if not os.path.isfile(args.mcpat_bin):
        raise SystemExit('McPAT binary not found at {}'.format(args.mcpat_bin))

    t_ref_xml = read_xml_tref(args.xml)
    print('leakage model calibration')
    print('  xml        : {}'.format(os.path.basename(args.xml)))
    print('  McPAT bin  : {}'.format(args.mcpat_bin))
    print('  T_ref FOUND IN XML : {:.1f} K  ({:.1f} C)  <- the true anchor'.format(
        t_ref_xml, t_ref_xml - 273.15))
    print('  sweeping temperature over: {}'.format(
        ', '.join('{:g}'.format(t) for t in args.temps)))

    rows = []
    failed = []
    for temp in sorted(args.temps):
        tag = 'T{:g}'.format(temp)
        xml_t = os.path.join(args.out_dir, 'mcpat_{}.xml'.format(tag))
        txt_t = os.path.join(args.out_dir, 'mcpat_{}.txt'.format(tag))
        write_xml_at_temp(args.xml, temp, xml_t)
        try:
            run_mcpat(args.mcpat_bin, xml_t, txt_t)
            sub, gate = total_leakage(txt_t)
        except RuntimeError:
            # McPAT gives up above its device-model temperature range: it prints its banner
            # and stops, with no results and no error. Record the ceiling instead of dying --
            # knowing where the power model stops being defined is itself a result.
            failed.append(float(temp))
            print('    T={:6.1f} K : McPAT produced NO RESULTS (outside its valid range)'
                  .format(temp))
            continue
        rows.append({'T_K': float(temp), 'subthreshold_W': sub, 'gate_W': gate,
                     'total_leak_W': sub + gate})
        print('    T={:6.1f} K : subthreshold {:9.4f} W | gate {:8.4f} W | total {:9.4f} W'
              .format(temp, sub, gate, sub + gate))

    if not rows:
        raise SystemExit('McPAT produced no usable results at any requested temperature.')
    if failed:
        print('\n  *** McPAT VALIDITY CEILING: no results at or above {:.1f} K ({:.1f} C). '
              'The leakage\n  model is undefined above this point, so any simulated operating '
              'point hotter than\n  {:.1f} C is outside the power model entirely -- treat it as '
              '"thermally non-viable",\n  not as a quantified result. ***'.format(
                  min(failed), min(failed) - 273.15, max(r['T_K'] for r in rows) - 273.15))

    temps = [r['T_K'] for r in rows]
    totals = np.array([r['total_leak_W'] for r in rows])
    subs = np.array([r['subthreshold_W'] for r in rows])

    # Normalize to the XML's own anchor if it is in the sweep, else to the first point.
    if t_ref_xml in temps:
        anchor_idx = temps.index(t_ref_xml)
    else:
        anchor_idx = 0
        print('\n  NOTE: T_ref {:.1f} K not in the sweep; normalizing at {:.1f} K'.format(
            t_ref_xml, temps[anchor_idx]))
    rel = totals / totals[anchor_idx]

    print('\n  --- measured relative leakage (anchor {:.1f} K = 1.000) ---'.format(
        temps[anchor_idx]))
    print('  {:>8s} {:>12s} {:>14s} {:>14s}'.format('T[K]', 'rel(measured)', 'exp(dT2x=10)',
                                                    'exp(dT2x=15)'))
    for t, r in zip(temps, rel):
        e10 = 2.0 ** ((t - temps[anchor_idx]) / 10.0)
        e15 = 2.0 ** ((t - temps[anchor_idx]) / 15.0)
        print('  {:>8.1f} {:>12.4f} {:>14.4f} {:>14.4f}'.format(t, r, e10, e15))

    d_tot, resid_tot = implied_doubling(temps, rel)
    d_sub, _ = implied_doubling(temps, subs / subs[anchor_idx])
    print('\n  --- implied doubling constant ---')
    if np.isfinite(d_tot):
        print('  total leakage      : dT_2x = {:.2f} K  (max |residual| vs pure exponential '
              '= {:.4f} in relative units)'.format(d_tot, resid_tot))
        print('  subthreshold only  : dT_2x = {:.2f} K'.format(d_sub))
        print('\n  Use in code:')
        print('    LeakageModel.exponential({:.2f})   with T_ref={:.1f}'.format(d_tot, t_ref_xml))
        print('    # or, exactly, without assuming an exponential shape:')
        print('    LeakageModel.from_table({}, {})'.format(
            [float(t) for t in temps], [round(float(r), 6) for r in rel]))
    else:
        print('  *** leakage did NOT increase with temperature in this sweep. Either McPAT is '
              'ignoring the temperature parameter for this configuration, or the XML was not '
              'modified as expected -- inspect {} before using any of this. ***'.format(
                  args.out_dir))

    out = args.out_json or os.path.join(args.out_dir, 'leakage_calibration.json')
    with open(out, 'w') as f:
        json.dump({'xml': args.xml, 't_ref_xml_K': t_ref_xml, 'rows': rows,
                   'anchor_K': temps[anchor_idx], 'rel_leakage': [float(x) for x in rel],
                   'implied_doubling_K': None if not np.isfinite(d_tot) else d_tot}, f, indent=2)
    print('\n  written: {}'.format(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
