"""DRAM power with temperature-dependent refresh -- the memory analogue of leakage feedback.

Why a separate model
--------------------
Logic is delay-limited: it gets slower as it heats, and past a spec point it throttles. DRAM is
**retention-limited**: cells leak their charge faster as they heat, so the part must refresh
more often to keep the data. Refresh costs power, which raises temperature, which shortens
retention -- the same shape of positive feedback as subthreshold leakage, on a different
mechanism and with a limit roughly 15 K *below* the logic's.

That is the whole reason design D is interesting (docs/DESIGN_STUDY_PLAN.md): stacking memory
over logic puts a structure with a lower limit into the hot part's heat path, so the binding
constraint on the *system* may stop being the logic's 100 C and become the memory's 85 C. A
constraint that lives in one identifiable region is exactly what targeted cooling is good at,
whereas the logic's constraint is a 15-block plateau that it is not.

Provenance, stated plainly
--------------------------
**These are conventions, not measurements, and no number from this module should be quoted
until it is pinned to a datasheet.**

* The 85 C breakpoint and the 2x refresh rate above it are the JEDEC extended-temperature-range
  convention for DDR/LPDDR parts. They are in every DRAM datasheet, but not in a datasheet we
  hold; the references in docs/chip_design_lit cover TSV stacking and HBM integration, not
  retention.
* Retention time halving every ~10 K is the standard rule of thumb for the same reason.
* Absolute power terms (background, activate, I/O) are placeholders sized to give a plausible
  W/mm^2 for a stacked die, NOT extracted from a part.

What that means in practice: use this to ask **whether the memory limit binds and where the hot
zone is**, which is a structural question the shape of the model answers. Do not use it to claim
a memory power number.
"""

import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

#: JEDEC extended-temperature breakpoint [K]. Above it the refresh interval halves.
DEFAULT_REFRESH_BREAK_K = 358.15          # 85 C

#: Retention halves per this many K. Standard rule of thumb; see the module note.
DEFAULT_RETENTION_HALVING_K = 10.0

#: The hard limit most DRAM datasheets set for the junction. Beyond it the part is out of spec
#: regardless of refresh rate, so a search must treat it as a wall and not as a cost.
DEFAULT_DRAM_LIMIT_K = 368.15             # 95 C


class DRAMPowerModel(object):
    """Per-bank DRAM power as a function of temperature.

        P(T) = P_background + P_activity + P_refresh(T)

    ``P_refresh`` scales with the refresh rate, which rises as retention falls:

        rate(T) = 2 ** ((T - T_break) / halving_K)     for T > T_break, else 1

    and JEDEC's extended range adds a further factor of 2 at the breakpoint itself, which is why
    a part that crosses 85 C sees a step rather than a smooth rise. Both effects are modelled
    because the step is what makes the limit behave like a cliff.
    """

    def __init__(self, background_W, activity_W, refresh_W,
                 break_K=DEFAULT_REFRESH_BREAK_K,
                 halving_K=DEFAULT_RETENTION_HALVING_K,
                 extended_range_step=2.0, calibrated=False):
        if halving_K <= 0:
            raise ValueError('halving_K must be > 0')
        for name, val in (('background_W', background_W), ('activity_W', activity_W),
                          ('refresh_W', refresh_W)):
            if val < 0:
                raise ValueError('{} must be >= 0'.format(name))
        self.background_W = float(background_W)
        self.activity_W = float(activity_W)
        self.refresh_W = float(refresh_W)
        self.break_K = float(break_K)
        self.halving_K = float(halving_K)
        self.extended_range_step = float(extended_range_step)
        #: False until pinned to a datasheet. Downstream reporting should surface this the way
        #: FMaxModel.calibrated is surfaced, so an uncalibrated number cannot look measured.
        self.calibrated = bool(calibrated)

    def refresh_multiplier(self, T_K):
        """How much more often the part must refresh at ``T_K`` than at the breakpoint."""
        T = np.asarray(T_K, dtype=float)
        over = np.maximum(T - self.break_K, 0.0)
        step = np.where(T > self.break_K, self.extended_range_step, 1.0)
        return step * 2.0 ** (over / self.halving_K)

    def power(self, T_K):
        """Total DRAM power at temperature ``T_K`` [W]."""
        return (self.background_W + self.activity_W
                + self.refresh_W * self.refresh_multiplier(T_K))

    def __repr__(self):
        return ('<DRAMPowerModel bg={:.3g} act={:.3g} refresh={:.3g} W, break {:.1f} K{}>'
                .format(self.background_W, self.activity_W, self.refresh_W, self.break_K,
                        '' if self.calibrated else ' UNCALIBRATED'))


def stacked_dram_model(area_mm2, density_W_per_mm2=0.15, refresh_fraction=0.35,
                       activity_fraction=0.30, **kwargs):
    """A per-bank model sized from die area and an assumed power density.

    ``density_W_per_mm2`` is the *total* memory-die power density at the breakpoint temperature;
    the fractions split it into refresh, activity and background. 0.15 W/mm^2 is a deliberately
    modest figure next to the logic die's ~1.0 W/mm^2 -- stacked memory is not what makes a 3D
    part hot, it is what *suffers* from what makes it hot, and a model that got that backwards
    would answer the wrong question.
    """
    if not 0.0 <= refresh_fraction + activity_fraction <= 1.0:
        raise ValueError('refresh + activity fractions must lie in [0, 1]')
    total = float(area_mm2) * float(density_W_per_mm2)
    return DRAMPowerModel(background_W=total * (1.0 - refresh_fraction - activity_fraction),
                          activity_W=total * activity_fraction,
                          refresh_W=total * refresh_fraction, **kwargs)


def dram_block_powers(block_names, model, temps_K=None, default_T_K=None):
    """Per-block DRAM power, evenly split across banks, at the given temperatures.

    ``temps_K`` maps block -> temperature; blocks without one use ``default_T_K`` (the
    breakpoint if unset). Feeding this the solved memory-layer field and re-solving is the
    memory-side fixed point, and it is coupled to the logic's leakage loop through the shared
    thermal solution rather than through anything in the power model.
    """
    names = list(block_names)
    if not names:
        return {}
    default_T_K = model.break_K if default_T_K is None else float(default_T_K)
    per_bank = 1.0 / len(names)
    out = {}
    for name in names:
        T = float(np.ravel(temps_K[name])[-1]) if temps_K and name in temps_K else default_T_K
        out[name] = per_bank * float(model.power(T))
    return out


def dram_limit_report(temps_K, limit_K=DEFAULT_DRAM_LIMIT_K,
                      break_K=DEFAULT_REFRESH_BREAK_K):
    """Summarise a memory field against its two thresholds.

    Returns the peak, which blocks are past the refresh breakpoint (a power cost) and which are
    past the hard limit (out of spec). They are different failures and conflating them would
    hide the one that matters: a part running at 90 C is expensive, a part at 100 C is broken.
    """
    if not temps_K:
        return {'peak_K': None, 'n_over_break': 0, 'n_over_limit': 0, 'over_limit': []}
    finals = {k: float(np.ravel(v)[-1]) for k, v in temps_K.items()}
    peak = max(finals.values())
    return {'peak_K': peak, 'peak_block': max(finals, key=finals.get),
            'n_over_break': sum(1 for t in finals.values() if t > break_K),
            'n_over_limit': sum(1 for t in finals.values() if t > limit_K),
            'over_limit': sorted([k for k, t in finals.items() if t > limit_K]),
            'break_K': float(break_K), 'limit_K': float(limit_K)}
