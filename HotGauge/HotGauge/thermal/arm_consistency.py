"""Does the cooled arm's temperature agree with the cooling it says it applied?

Why this exists
---------------
``CoolingApplication`` pushes tile powers into the solver as a **side effect**, and for most of
this project's history nothing rewound them. A planner exit that reported a different plan than
the last one applied -- ``'nothing above target; no cooling needed'`` reports ``{}`` -- therefore
left the array carrying the previous call's cooling, and the caller solved a die being cooled by a
plan its own accounting said did not exist.

That is invisible in every field the pipeline records. It surfaced only as an arithmetic
impossibility, and only because someone happened to look at three numbers together
(27 August 2026, ``clock_headroom`` at r_th 0.3):

    arm         clock       peak     die power   removed
    control     3.313 GHz   84.0 C    55.4 W       --
    array_idle  3.453 GHz   85.0 C    61.7 W      0.000 W
    array_on    4.813 GHz   62.6 C   183.9 W      0.000 W

Three times the power at a 22 K *lower* peak, with nothing removed. The wrapper now re-applies the
reported plan at every exit so state and accounting agree by construction -- but "fixed once" is
not the same as "cannot recur", and this class of defect is silent by nature. So the arithmetic
that caught it becomes a check the drivers run every time.

What is and is not asserted
---------------------------
* **Zero removal must mean zero cooling.** If the powered arm removed no heat, its peak must equal
  the idle arm's. This is exact, it is the failure actually observed, and it cannot false-positive.
* **A gain per watt far beyond anything measured is flagged, not raised.** The most efficient
  strategy ever measured here is 1.119 K/W (top-5 blocks at a 3 W budget,
  ``docs/evidence/die_average_strategies.json``), so the default ceiling of 10 K/W is an order of
  magnitude of headroom. It is a smoke alarm for unaccounted cooling, not a physical law, and it
  says so when it fires.
"""
import logging

LOGGER = logging.getLogger(__name__)

#: Best peak-reduction-per-watt measured on a UNIFORM die (die_average_strategies.json, top-5
#: strategy at a 3 W budget). Kept because the contrast is the point: concentrated workloads are
#: an order of magnitude more efficient, and a ceiling set from uniform data alone is too tight.
BEST_MEASURED_UNIFORM_K_PER_W = 1.119
BEST_MEASURED_K_PER_W = BEST_MEASURED_UNIFORM_K_PER_W        # back-compatible alias

#: Highest efficiency measured across the eleven workload shapes at 3-8 K of demanded margin
#: (docs/evidence/metric_regression_gen0.json). Concentrated shapes -- one saturated core with
#: its power pushed into the FPUs -- reach here legitimately, because a single small isolated
#: block has a large dT/dq and cooling it scales linearly.
BEST_MEASURED_CONCENTRATED_K_PER_W = 10.77

#: Raised from 10.0 to 25.0 on 27 Aug 2026. The old value was derived from uniform-workload data
#: only and fired on the very first concentrated shape measured (g4_turbo, 10.7 K/W) -- a real
#: result, not unaccounted cooling. It is re-derived here as ~2.3x the highest value now
#: observed across eleven shapes, rather than tuned downward until the warnings stopped, which is
#: the failure this project's acceptance gate exists to prevent.
DEFAULT_MAX_K_PER_W = 25.0

#: Solver noise floor on a peak temperature [K]. The two-die server agrees with the one-shot
#: emulator to 5.1e-4 K, so 0.05 K is generous.
PEAK_TOL_K = 0.05


class ArmConsistencyError(AssertionError):
    """The powered arm's temperature cannot be explained by the cooling it reports."""


def check_arm_consistency(idle_peak_C, powered_peak_C, heat_removed_W,
                          max_K_per_W=DEFAULT_MAX_K_PER_W, tol_K=PEAK_TOL_K, label=''):
    """Compare a powered arm against its own idle baseline.

    ``idle_peak_C``   : peak of the unpowered array arm (``array_idle``) -- the same stack with
                        the laser off. NOT the control, which is a different stack.
    ``powered_peak_C``: peak of the powered arm (``array_on``).
    ``heat_removed_W``: what that arm's accounting says it removed.

    Returns a dict describing the comparison. Raises :class:`ArmConsistencyError` on the exact
    case; logs a warning on the implausible one.
    """
    if idle_peak_C is None or powered_peak_C is None:
        return {'checked': False, 'reason': 'an arm has no peak (diverged or not run)'}

    delta_K = float(idle_peak_C) - float(powered_peak_C)      # positive = powered arm is cooler
    q = float(heat_removed_W or 0.0)
    out = {'checked': True, 'idle_peak_C': float(idle_peak_C),
           'powered_peak_C': float(powered_peak_C), 'delta_K': delta_K,
           'heat_removed_W': q, 'label': label}

    if q <= 0.0:
        if delta_K > tol_K:
            raise ArmConsistencyError(
                '{}the powered arm is {:.2f} K cooler than the idle arm while reporting ZERO heat '
                'removed ({:.2f} C against {:.2f} C). Cooling is being applied that the accounting '
                'does not know about -- see HotGauge/thermal/arm_consistency.py for the defect '
                'this check exists to catch. The result must not be quoted.'
                .format(label and label + ': ', delta_K, powered_peak_C, idle_peak_C))
        out['verdict'] = 'ok: no removal, no cooling'
        return out

    k_per_W = delta_K / q
    out['K_per_W'] = k_per_W
    if k_per_W > max_K_per_W:
        LOGGER.warning(
            '%sthe powered arm gained %.2f K for %.4f W removed (%.1f K/W). The most efficient '
            'strategy ever measured in this project is %.3f K/W, so this is %.0fx beyond it and '
            'is more likely unaccounted cooling than a result. Not fatal -- this ceiling is a '
            'smoke alarm, not a physical law -- but do not quote it without explaining it.',
            label and label + ': ', delta_K, q, k_per_W, BEST_MEASURED_K_PER_W,
            k_per_W / BEST_MEASURED_K_PER_W)
        out['verdict'] = 'suspicious: gain per watt far beyond anything measured'
    else:
        out['verdict'] = 'ok'
    return out
