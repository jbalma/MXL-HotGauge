"""Read a BSIM-CMG (HSPICE ``.pm``) model card -- the device parameters, from the vendor's file.

Why parse rather than transcribe
--------------------------------
The point of bringing in a published model card is that the numbers come from someone else's
measured/calibrated process, not from this project's memory of what a 7 nm FinFET is like.
Transcribing a handful of them into a Python constant would throw that away at the first typo, and
the typo would be invisible -- a plausible-looking bandgap coefficient produces a plausible-looking
curve. So the card is vendored verbatim and read.

The card
--------
``spice_leakage/models/asap7_7nm_TT.pm`` -- ASAP7, the 7 nm FinFET predictive PDK from Arizona
State (Clark, Vashishtha et al., *Microelectronics Journal* 2016), BSD-3-Clause, from
``The-OpenROAD-Project/asap7_pdk_r1p7``. It is BSIM-CMG version 107, typical-typical, with eight
device flavours (n/p x lvt/rvt/slvt/sram).

`[!]` ASAP7 rather than PTM proper: ``ptm.asu.edu`` no longer resolves, and ASAP7 is the same
group's successor 7 nm work, published, peer-reviewed and openly licensed. The only local edit to
the vendored file is the HSPICE ``level = 72`` -> ngspice ``level = 17`` renumbering, recorded in
``spice_leakage/PROVENANCE.md``.

Format
------
HSPICE model cards are ``.model <name> <type> level = N`` followed by continuation lines starting
``+`` carrying ``key = value`` pairs, with ``*`` comments and section banners in between.
"""
import os
import re

#: Where the vendored cards live, relative to the repo root.
CARD_DIR = os.path.join('spice_leakage', 'models')
DEFAULT_CARD = 'asap7_7nm_TT.pm'

_MODEL_RE = re.compile(r'^\.model\s+(?P<name>\S+)\s+(?P<type>nmos|pmos)\s+level\s*=\s*(?P<level>\d+)',
                       re.I)
_PAIR_RE = re.compile(r'([A-Za-z_]\w*)\s*=\s*([-+0-9.eE]+)')


def repo_root():
    """The repository root, from this file's location."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def card_path(name=DEFAULT_CARD):
    return os.path.join(repo_root(), CARD_DIR, name)


def parse_card(path=None):
    """``{device_name: {param: float}}`` for every ``.model`` in an HSPICE-style card.

    Values are floats; keys are lower-cased. ``level`` and the device type are stored under the
    reserved keys ``__level__`` and ``__type__`` so a caller can tell an nmos from a pmos without
    a naming convention.
    """
    path = path or card_path()
    devices, current = {}, None
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('*'):
                continue
            m = _MODEL_RE.match(line)
            if m:
                current = {'__type__': m.group('type').lower(),
                           '__level__': int(m.group('level'))}
                devices[m.group('name').lower()] = current
                # a .model line can carry parameters after the level
                line = line[m.end():]
            elif line.startswith('+'):
                line = line[1:]
            else:
                continue
            if current is not None:
                for k, v in _PAIR_RE.findall(line):
                    if k.lower() == 'level':
                        continue
                    current[k.lower()] = float(v)
    if not devices:
        raise ValueError('no .model cards found in {}'.format(path))
    return devices


def require(device, *names):
    """Fetch parameters, raising with the device's name if one is missing.

    A missing parameter must not silently become a default: the whole reason for reading the card
    is that the numbers are the vendor's, and a default substituted for a bandgap coefficient
    would be this project's own guess wearing ASAP7's name.
    """
    out = []
    for n in names:
        if n not in device:
            raise KeyError('model card has no {!r} (have {} ...)'
                           .format(n, sorted(k for k in device if not k.startswith('__'))[:8]))
        out.append(device[n])
    return out[0] if len(out) == 1 else tuple(out)
