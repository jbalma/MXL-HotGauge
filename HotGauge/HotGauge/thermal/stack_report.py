"""Read a 3D-ICE stack file back and say what it actually models.

Why this exists
---------------
The thermal stack is where several of this project's wrong answers came from, and every one of
them was invisible in the ``.stk`` text: a material constant that looks small until you notice
3D-ICE quotes conductivity in W/(um K), a layer whose resistance is negligible on one die and
dominant on another, a heat spreader with no overhang because its ``spread area`` line is
commented out.

None of that is hard to see once the file is turned into a resistance budget for a specific die.
This does that: parse the stack, compute what each layer contributes at a given die area, and rank
them. A layer that is 1% of the budget on an 826 mm^2 die and 25% of it on a 91 mm^2 one is the
kind of thing that should be obvious at a glance, and until now was not.

Units, which are the first trap
-------------------------------
3D-ICE works in micrometres. Conductivity is **W/(um K)**, so silicon's ``1.20e-4`` is 120 W/(m K)
and thermal grease's ``0.04e-4`` is 4 W/(m K). Read as SI those look like 1.2e-4 and 4e-6, which
would make every material an insulator -- an easy and consequential misreading.

The overhang the stack does not model
-------------------------------------
Every layer here spans exactly the die footprint, because 3D-ICE takes ``chip length`` from the
floorplan and this template's ``spread height / area`` lines are commented out. A real integrated
heat spreader is far larger than the die and carries heat sideways before handing it up. Without
that, a small die pays full vertical resistance through every package layer with no lateral relief,
which is why the model reproduces an 826 mm^2 part and fails a 91 mm^2 one.
"""

import re
import logging

LOGGER = logging.getLogger(__name__)

#: 3D-ICE conductivity is W/(um K); multiply by 1e6 for W/(m K).
UM_TO_M = 1.0e6

_MATERIAL_RE = re.compile(r'material\s+(\w+)\s*:(.*?)(?=material\s+\w+\s*:|/\*|\Z)', re.S)
_COND_RE = re.compile(r'thermal\s+conductivity\s+([0-9.eE+-]+)')
_CAP_RE = re.compile(r'volumetric\s+heat\s+capacity\s+([0-9.eE+-]+)')
_LAYERDEF_RE = re.compile(r'layer\s+(\w+)\s*:\s*height\s+([0-9.eE+-]+)\s*;\s*material\s+(\w+)', re.S)
_STACK_RE = re.compile(r'^\s*(layer|die)\s+(\w+)\s+(\w+)', re.M)
_DIELAYER_RE = re.compile(r'^\s*(layer|source)\s+([0-9.]+)\s+(\w+)\s*;', re.M)
_HTC_RE = re.compile(r'heat\s+transfer\s+coefficient\s+([0-9.eE+-]+)')


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def parse_stack(stack_file):
    """Materials, layer definitions and the assembled stack, from a ``.stk``.

    Comments are stripped first, which matters: this template's heat-spreader geometry sits inside
    a ``/* REMOVED BECAUSE THEY LIE */`` block, so a parser that ignored comments would report a
    spreader the solver never sees.
    """
    with open(stack_file) as f:
        raw = f.read()
    text = _strip_comments(raw)

    materials = {}
    for name, body in _MATERIAL_RE.findall(text):
        c, cap = _COND_RE.search(body), _CAP_RE.search(body)
        if not c:
            continue
        materials[name] = {'k_um': float(c.group(1)),
                           'k_si': float(c.group(1)) * UM_TO_M,
                           'cap': float(cap.group(1)) if cap else None}

    layer_defs = {n: {'height_um': float(h), 'material': m}
                  for n, h, m in _LAYERDEF_RE.findall(text)}

    die_layers = [{'kind': k, 'height_um': float(h), 'material': m}
                  for k, h, m in _DIELAYER_RE.findall(text)]

    stack_entries = []
    m = re.search(r'\bstack\s*:(.*?)(?:solver\s*:|output\s*:|\Z)', text, re.S)
    if m:
        for kind, inst, kind2 in _STACK_RE.findall(m.group(1)):
            stack_entries.append({'kind': kind, 'instance': inst, 'type': kind2})

    htc = _HTC_RE.search(text)
    spreader_commented = 'spread height' in raw and 'spread height' not in text

    return {'file': stack_file, 'materials': materials, 'layer_defs': layer_defs,
            'die_layers': die_layers, 'stack': stack_entries,
            'htc_3dice': float(htc.group(1)) if htc else None,
            'spreader_geometry_commented_out': spreader_commented}


def resistance_budget(stack_file, die_area_mm2):
    """Per-layer vertical resistance [K/W] at this die area, ranked.

    Every layer is taken at the die footprint, because that is what the solver does. The point of
    ranking them is that the ORDER changes with die size, and the layer that dominates a small die
    is invisible on a large one.
    """
    p = parse_stack(stack_file)
    area_m2 = float(die_area_mm2) / 1e6
    rows = []

    for e in p['stack']:
        if e['kind'] == 'die':
            for i, dl in enumerate(p['die_layers']):
                mat = p['materials'].get(dl['material'])
                if not mat:
                    continue
                r = (dl['height_um'] * 1e-6) / (mat['k_si'] * area_m2)
                rows.append({'name': 'die[{}]{}'.format(i, '*' if dl['kind'] == 'source' else ''),
                             'material': dl['material'], 'height_um': dl['height_um'],
                             'k_si': mat['k_si'], 'r_K_per_W': r})
            continue
        ld = p['layer_defs'].get(e['type'])
        if not ld:
            continue
        mat = p['materials'].get(ld['material'])
        if not mat:
            continue
        r = (ld['height_um'] * 1e-6) / (mat['k_si'] * area_m2)
        rows.append({'name': e['instance'], 'material': ld['material'],
                     'height_um': ld['height_um'], 'k_si': mat['k_si'], 'r_K_per_W': r})

    total = sum(x['r_K_per_W'] for x in rows)
    for x in rows:
        x['share'] = (x['r_K_per_W'] / total) if total else 0.0
    return {'die_area_mm2': float(die_area_mm2), 'rows': rows, 'total_K_per_W': total,
            'spreader_geometry_commented_out': p['spreader_geometry_commented_out'],
            'htc_3dice': p['htc_3dice'], 'parsed': p}


def format_budget(budget, top=None):
    """A readable resistance budget, in stack order, with each layer's share."""
    out = []
    out.append('stack resistance at {:.0f} mm^2 (every layer at the die footprint)'
               .format(budget['die_area_mm2']))
    out.append('{:<12s} {:<14s} {:>9s} {:>10s} {:>11s} {:>7s}'.format(
        'layer', 'material', 'height um', 'k W/(m K)', 'R K/W', 'share'))
    for r in budget['rows'][:top] if top else budget['rows']:
        out.append('{:<12s} {:<14s} {:>9.0f} {:>10.1f} {:>11.5f} {:>6.1f}%'.format(
            r['name'], r['material'], r['height_um'], r['k_si'], r['r_K_per_W'],
            100.0 * r['share']))
    out.append('{:<12s} {:<14s} {:>9s} {:>10s} {:>11.5f}'.format(
        'TOTAL', '', '', '', budget['total_K_per_W']))
    if budget['spreader_geometry_commented_out']:
        out.append('')
        out.append('NOTE: the heat-spreader geometry (spread height / area) is COMMENTED OUT in '
                   'this template,')
        out.append('      so every layer above spans exactly the die footprint and none of them '
                   'spreads heat')
        out.append('      sideways. That is survivable on a large die and dominant on a small one.')
    return '\n'.join(out)
