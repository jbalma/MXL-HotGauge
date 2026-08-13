# Resume notes — SimScale integration session

Paused mid-session. Everything below is saved to disk (uncommitted, on NFS).

## Still running on allocation 1154 (node-03-6xv100)

I left these going rather than killing them — they represent real compute already spent, and
they write to files on the node so results survive the disconnect. Kill them if you want the
node back.

| what | command output | writes |
|---|---|---|
| 34-core cliff search, 60/100/140 W @ 88 CFM | `bn4l1llwd` | `/tmp/ss34c.log`, `/tmp/ss34c/sweep.json` |
| **128-core like-for-like**, 200/360 W @ 88 CFM | `bt61sx48d` | `/tmp/ss128.log`, `/tmp/ss128/sweep.json` |

The 128-core one was still queued behind the first (srun runs one step at a time on an
allocation). Both are on node-local `/tmp`, so copy them off before the allocation ends:

    srun --jobid=<id> bash -lc 'cat /tmp/ss128/sweep.json' > ss128.json

## The open question these runs answer

Our 34-core (101 mm²) die showed an on-die resistance of **0.607 K/W against SimScale's
0.20 K/W** — 3× worse, on a die 4× smaller. The 128-core floorplan is **347.55 mm²**, within
13% of SimScale's 400 mm², so it is the first genuinely like-for-like test.

**Prediction to check:** if our on-die resistance drops toward ~0.2 K/W on the 128-core die,
the two independent models agree and the 34-core gap was purely a die-size artifact. If it
stays near 0.6 K/W, the difference is real and comes from floorplan granularity — we resolve
33 functional units per core with LINPACK concentrated in FPU/AVX, versus SimScale's uniform
2 mm cores plus one discrete 200 µm hotspot each. Either answer is informative; they imply
different things about whether our hotspots are physical or meshing artifacts.

## State of play

Done this session:
* `BaffledFinSink` + `simscale_*` in `thermal/sink_models.py` — **corrected** to present the
  convective resistance only; α is end-to-end and double-counts the die if used as a boundary.
* α/β decomposed into conduction floor + convective term (max residual 0.011 K/W).
  **β − α = 1.042 K/W is a pure constriction resistance** — 73 K of the ~165 K rise, immune to
  airflow, and the mechanistic core of the MR argument.
* `examples/simscale_hpc_study.py` — couples the sink to the leakage loop; now separates the
  die-geometry gap from the leakage gap (conflating them produced a false claim earlier).
* `thermal/fan_specs.py` — datasheet fan models, validated against `Sheet5` (η 0.2628/0.1247).
* 128-, 70-, 34-core floorplans generated; aspect-ratio guard added to `grid_for`.
* `replicate_trace_cores` — tiles the 8-core McPAT trace onto N cores.
* 26 new regression tests; full suite 167 passing.

Bugs fixed that produced wrong *results*, not crashes:
1. `NO_POWER_UNITS` hardcoded to 8 cores (`AVXs_0..7`) — capped the whole pipeline at 8 cores.
2. `grid_for` accepted any exact factorisation — 32 cores tiled as a 2×17 "die".
3. Solver/setup failures recorded as thermal runaway — a missing file reported as physics.
4. α used as the 3D-ICE sink boundary — manufactured a runaway at 100 W.
5. `eta_laser` inverted (0.20 vs 5.0) — made laser cooling look 25× too cheap.

## Next steps after the runs land

1. Read `/tmp/ss128/sweep.json` and settle the prediction above.
2. Replace the **digitised** α/β with the fitted values in `docs/SimScale/data/` before
   anything is quoted externally.
3. Re-run the hybrid optimiser against `BaffledFinSink` with the discontinuous fan curve — the
   band jumps at 88 and 133 CFM are what create the COP optimum, and the current optimiser
   models one continuous fan so it cannot see that mechanism.
