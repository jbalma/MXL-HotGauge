#!/usr/bin/env python
"""When does a faster solver actually pay? A cost model fitted to measured factorisations.

    python scripts/solver_cost_model.py
    python scripts/solver_cost_model.py --matrices 40 --unknowns 1.41e6 --speedup 3.5

Why a model rather than a rule of thumb
---------------------------------------
The decision to port 3D-ICE's solver to the GPU keeps being argued from anecdotes -- "that run
took ages" -- and the anecdotes have twice turned out to be self-inflicted bugs rather than solver
cost. This prices a study from three numbers that are actually measured, so the trigger can be
checked instead of felt.

The cost of a study
-------------------
    T  =  M * F(N)  +  S * s(N)

    M : distinct SYSTEM MATRICES. This is the number that matters and it is NOT the number of
        runs. The matrix is built from the stack and the floorplan GEOMETRY, so changing airflow,
        R_th, the grid, the floorplan or the die count makes a new one -- while changing die power,
        the kernel, the MR target, dt_max, the COP or the leakage fraction does not.
    F : factorisation time, superlinear in the unknowns N.
    S : total solves. Cheap once the matrix is factorised.

A faster solver scales F only. So it pays in proportion to M -- and M collapses to almost nothing
on a workload sweep, while staying large on a cooling or geometry sweep. That distinction is the
whole answer to "when".

Measurements (node-03, SuperLU 4.3 via 3D-ICE)
----------------------------------------------
    691k unknowns    87.5 s     34-core CPU die, 50 um
    1.41M unknowns  431.3 s     GA100, 100 um
    5.64M unknowns 2849.2 s     GA100, 50 um

A single power law through these is a poor fit -- the local exponent is 2.24 over the first
interval and 1.36 over the second, which is normal for sparse LU as it moves between cache and
memory regimes -- so the model fits log-log least squares over all three and reports the residual
rather than pretending one exponent holds everywhere.
"""
import math
import argparse

#: (unknowns, factorisation seconds). Measured, not projected.
MEASURED = [(691e3, 87.5), (1.41e6, 431.3), (5.64e6, 2849.2)]

#: Per-solve cost once factorised, measured on the 691k system. Scales far more gently than
#: factorisation (triangular solves are roughly linear in the nonzeros of L+U), so it is modelled
#: as linear in N -- which OVERSTATES it at large N and therefore understates the case for a
#: faster factorisation. Deliberate: the model should not flatter the conclusion it exists to test.
SOLVE_REF = (691e3, 0.43)


def fit_power_law(points=None):
    """Least squares in log-log. Returns (coefficient, exponent, max relative residual)."""
    pts = points or MEASURED
    n = len(pts)
    xs = [math.log(N) for N, _ in pts]
    ys = [math.log(t) for _, t in pts]
    xbar, ybar = sum(xs) / n, sum(ys) / n
    num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    den = sum((x - xbar) ** 2 for x in xs)
    b = num / den
    a = math.exp(ybar - b * xbar)
    resid = max(abs(a * (N ** b) - t) / t for N, t in pts)
    return a, b, resid


def factor_s(N, fit=None, prefer_measured=True):
    """Factorisation seconds at ``N`` unknowns.

    Prefers a MEASURED point when one sits within 2% of ``N``. The fit carries a 23% residual --
    one power law does not describe sparse LU across cache and memory regimes -- and using a
    fitted value where a measurement exists would put avoidable error into a decision.
    """
    if prefer_measured:
        for Nm, tm in MEASURED:
            if abs(Nm - N) / Nm < 0.02:
                return tm
    a, b, _ = fit or fit_power_law()
    return a * (N ** b)


def solve_s(N):
    Nref, tref = SOLVE_REF
    return tref * (N / Nref)


def study_cost_s(n_matrices, n_solves, N, speedup=1.0, fit=None):
    return n_matrices * factor_s(N, fit) / speedup + n_solves * solve_s(N)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--unknowns', type=float, default=1.41e6,
                    help='problem size (default: GA100 at 100 um, the working configuration)')
    ap.add_argument('--matrices', type=int, default=None,
                    help='distinct system matrices in the study')
    ap.add_argument('--solves', type=int, default=None)
    ap.add_argument('--speedup', type=float, default=3.5,
                    help='factorisation speedup a GPU solver is assumed to give (GAMEPLAN est.)')
    ap.add_argument('--port-days', type=float, default=2.0,
                    help='engineering days to do the port')
    ap.add_argument('--hours-per-day', type=float, default=6.0,
                    help='hours of solver time actually on the critical path per working day')
    args = ap.parse_args()

    a, b, resid = fit_power_law()
    print('fitted  F(N) = {:.3e} * N^{:.3f}   (max residual {:.1%} over the measured points)'
          .format(a, b, resid))
    print('measured:')
    for N, t in MEASURED:
        print('   {:>8.2f}M unknowns  {:>8.1f} s   model {:>8.1f} s'
              .format(N / 1e6, t, factor_s(N, prefer_measured=False)))
    print()

    N = args.unknowns
    F = factor_s(N)
    print('at {:.2f}M unknowns: one factorisation {:.0f} s ({:.1f} min), one solve {:.2f} s'
          .format(N / 1e6, F, F / 60, solve_s(N)))
    print()

    # --- the shape of the answer: cost against how matrix-diverse the study is -----------
    print('cost of a 200-solve study, by how many DISTINCT MATRICES it needs:')
    print('   {:>9s} {:>12s} {:>12s} {:>10s} {:>12s}'.format(
        'matrices', 'CPU', 'GPU x{:.1f}'.format(args.speedup), 'saved', 'factor frac'))
    for M in (1, 2, 5, 10, 20, 50, 100):
        cpu = study_cost_s(M, 200, N)
        gpu = study_cost_s(M, 200, N, speedup=args.speedup)
        frac = (M * F) / cpu
        print('   {:>9d} {:>10.1f} h {:>10.1f} h {:>8.1f} h {:>11.0%}'.format(
            M, cpu / 3600, gpu / 3600, (cpu - gpu) / 3600, frac))
    print()

    # --- payback -------------------------------------------------------------------------
    budget_s = args.port_days * args.hours_per_day * 3600
    saved_per_matrix = F * (1 - 1 / args.speedup)
    n_break = budget_s / saved_per_matrix
    print('payback: the port costs {:.0f} engineering-hours; each factorisation avoided saves '
          '{:.0f} s'.format(args.port_days * args.hours_per_day, saved_per_matrix))
    print('   -> it pays for itself after {:.0f} distinct matrices at this size'.format(n_break))
    print('   -> at {:.0f} h/day of solver time on the critical path, that is {:.1f} working days'
          .format(args.hours_per_day,
                  n_break * F / (args.hours_per_day * 3600)))
    print()

    if args.matrices is not None:
        S = args.solves if args.solves is not None else 25 * args.matrices
        cpu = study_cost_s(args.matrices, S, N)
        gpu = study_cost_s(args.matrices, S, N, speedup=args.speedup)
        print('this study: {} matrices, {} solves at {:.2f}M unknowns'.format(
            args.matrices, S, N / 1e6))
        print('   CPU {:.2f} h   GPU {:.2f} h   saved {:.2f} h ({:.0%})'.format(
            cpu / 3600, gpu / 3600, (cpu - gpu) / 3600, 1 - gpu / cpu))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
