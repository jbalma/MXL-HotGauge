#!/usr/bin/env python
"""Regenerate the checked-in stack templates from HotGauge.thermal.die_stack.

The templates are committed so that ``--stack direct_die_mr`` works from every driver without
each of them growing a stack-building flag. They are generated rather than hand-written so the
die geometry has exactly one definition; edit ``die_stack.py`` and re-run this.

    python scripts/generate_stacks.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, 'HotGauge'))

from HotGauge.thermal.die_stack import StackSpec, write_stack, compare_packages
from HotGauge.thermal.ICE import ICE_STK_DIR

#: name -> spec. ``skylake.stk`` is deliberately absent: it is the historical file every published
#: result came through, and it stays checked in as-is rather than being regenerated underneath
#: the back catalogue.
TEMPLATES = {
    'direct_die': StackSpec(package='direct_die', cell_um=50.0),
    'direct_die_mr': StackSpec(package='direct_die', mr_layer=True, mr_material='GAAS',
                               cell_um=50.0),
    'direct_die_mr_sin': StackSpec(package='direct_die', mr_layer=True, mr_material='SI3N4',
                                   cell_um=50.0),
    # The lidded rebuild. Not used by any study -- it exists so that the equivalence with
    # skylake.stk can be inspected by eye, not only asserted in a test.
    'lidded_rebuilt': StackSpec(package='lidded', cell_um=50.0),
}


def main():
    for name, spec in sorted(TEMPLATES.items()):
        path = write_stack(spec, os.path.join(ICE_STK_DIR, name + '.stk'))
        b826 = spec.resistance_budget(826.0)['total_K_per_W']
        b91 = spec.resistance_budget(91.0)['total_K_per_W']
        print('{:<20s} {:>10.5f} K/W @826mm2  {:>9.5f} @91mm2   coolant path {:>5.0f} um   {}'
              .format(name, b826, b91, spec.path_to_coolant_um()['total_um'],
                      os.path.basename(path)))
    print()
    for area in (826.0, 91.0):
        c = compare_packages(area)
        print('at {:>4.0f} mm2:  lidded {:.5f} -> direct-die+MR {:.5f} K/W  ({:.0f}% lower)'
              .format(area, c['lidded_K_per_W'], c['direct_die_K_per_W'], 100 * c['reduction']))


if __name__ == '__main__':
    main()
