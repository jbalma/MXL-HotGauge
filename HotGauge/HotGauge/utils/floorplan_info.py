#!/usr/bin/env python
import math
import numpy as np
import sys
import click
from collections.abc import Iterable
from collections import OrderedDict

import pint
ureg = pint.UnitRegistry()

from HotGauge.utils.floorplan import Floorplan

def get_stats(flp):
    # Save the old format
    old_frmt = flp.frmt
    # make sure it's hotspot format, which is m^2
    flp.frmt = 'hotspot'
    flp_area = flp.area*ureg['m^2']
    sizes = np.array([unit.area for unit in flp.elements]) * ureg['m^2']

    stats = {'floorplan': OrderedDict([
                ('Floorplan Size', flp_area),
                ('Floorplan Height', flp.height*ureg['m']),
                ('Floorplan Width', flp.width*ureg['m']),
                ('Floorplan Utilization', 100*flp_area / sizes.sum()),
                ]),
             'elements': OrderedDict(
                           (el.name, size) for el,size in zip(flp.elements, sizes)
                         ),
             'element-stats': OrderedDict([
                ('Min Size', sizes.min()),
                ('Max Size', sizes.max()),
                ('Avg Size', sizes.mean()),
             ])
          }
    flp.frmt = old_frmt
    return stats

def format_stats(stats, labels=None, unit=None, val_frmt=None):
    if not isinstance(stats, Iterable):
        stats = [stats]
    if labels == None:
        labels = range(len(stats))
    elif not isinstance(labels, Iterable):
        labels = [labels]
    assert len(labels) == len(stats)

    if unit==None:
        unit_frmt = lambda s: s.to_compact()
    else:
        unit = ureg[unit]
        assert unit.dimensionality == ureg['m'].dimensionality, 'Unit must be length unit'
        unit_sq = unit**2
        def unit_frmt(val):
            try:
                return val.to(unit)
            except:
                pass
            try:
                return val.to(unit_sq)
            except:
                pass
            return val
    if val_frmt is None:
        val_frmt = '{}'

    rows = [['stat'] + [str(label) for label in labels]]
    def add_output(stat_type, last=False):
        all_keys = [one_stats[stat_type].keys() for one_stats in stats]
        unique_keys = []
        for one_keys in all_keys:
            for key in one_keys:
                if key not in unique_keys:
                    unique_keys.append(key)
        for key in unique_keys:
            rows.append([key])
            for idx, one_stats in enumerate(stats):
                value = one_stats[stat_type].get(key, None)
                value = val_frmt.format(unit_frmt(value)) if value is not None else ''
                rows[-1].append(value)
        if not last:
            rows.append(['']*len(rows))
    add_output('floorplan')
    add_output('element-stats')
    add_output('elements', last=True)
    widths = [max(map(len, col)) for col in zip(*rows)]
    for row in rows:
        print("  ".join((val.ljust(width) for val, width in zip(row, widths))))



# CLI Interface
@click.group()
def cli():
    pass

@cli.command()
@click.argument('flp_files', nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.option('--unit', type=str)
@click.option('--val_frmt', type=str, default='{:0.3f~P}')
def stats(flp_files, unit=None, val_frmt=None):
    """Analyse flp_file(s)"""
    stats = [get_stats(Floorplan.from_file(flp_file)) for flp_file in flp_files]
    labels = [f.replace('.flp','') for f in flp_files]
    output = format_stats(stats, labels=labels, unit=unit, val_frmt=val_frmt)

def get_bbox_fn(flp_file, units):
    flp = Floorplan.from_file(flp_file)
    units = [flp[unit] for unit in units]
    bbox_xmin = min(u.minx for u in units)
    bbox_ymin = min(u.miny for u in units)
    bbox_xmax = max(u.maxx for u in units)
    bbox_ymax = max(u.maxy for u in units)
    bbox = (bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax)
    return bbox

def _bbox_str(bbox, sep=' '):
    return sep.join(map(str, bbox))

@cli.command()
@click.argument('flp_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('units', nargs=-1)
def get_bbox(flp_file, units):
    """Get rectangular boudning box around all units in a given floorplan"""
    bbox =  get_bbox_fn(flp_file, units)
    print(_bbox_str(bbox))

@cli.command()
@click.argument('flp_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('px_size', type=float)
@click.argument('units', nargs=-1)
def get_bbox_px(flp_file, px_size, units):
    """Get rectangular boudning box around all units in a given floorplan with a given pixel resolution"""
    bbox = tuple(v/px_size for v in get_bbox_fn(flp_file, units))
    strictly_internal = True
    if strictly_internal:
        bbox = (math.ceil(bbox[0]), math.ceil(bbox[1]), math.floor(bbox[2]),  math.floor(bbox[3]))
    elif strictly_external:
        bbox = (math.floor(bbox[0]), math.floor(bbox[1]), math.ceil(bbox[2]),  math.ceil(bbox[3]))
    elif rounded:
        bbox = (math.round(bbox[0]), math.round(bbox[1]), math.round(bbox[2]),  math.round(bbox[3]))

    print(_bbox_str(bbox))

if __name__ == "__main__":
    cli()
