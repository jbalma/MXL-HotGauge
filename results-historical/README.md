# results-historical

**Evidence behind claims that have been withdrawn.** Kept deliberately.

A withdrawn number that leaves no trace comes back — from an older draft, an earlier slide, or the
memory of anyone who read the repository a fortnight ago. Several of these were *already* corrected
once and resurfaced. So each directory carries a `WHY_RETIRED.md` naming the claim, **what to say
instead**, why it failed, and — importantly — **what still survives inside the files**.

`[!]` **Several items are MIXED**, not wholly wrong: a table whose numbers survive but whose
mechanism does not, a harvest file where one field carries a defect and the rest are fine. Those are
filed here rather than in `results-quotable/` so that a proposal writer browsing for citations never
picks one up by accident. Read `WHY_RETIRED.md` before reaching in.

| directory | withdrawn claim | say instead |
|---|---|---|
| `01-cold-zone-prize-30-percent/` | "The cold-zone prize is 30 % of die power." | ~6 % (recorded accounting) or ~14 % (corrected); better, the 2.23x ratio |
| `02-clock-runaway-mechanism/` | "Above 0.1 K/W the part does not reach its 100 C spec limit -- it runs away first." | the part reaches spec at EVERY cooling point tested |
| `03-fan-affinity-law/` | "Fan power scales as R^-5; localized cooling is worth 22-35 % of system power through fan displacement." | fan power is LINEAR in heat carried; at today's extractor the optimum is baseline airflow |
| `04-density-ceiling-pre-correction/` | "The flat-die ceiling is 1.0-1.2 W/mm^2." Also: "the simulated curve makes the ceiling higher because its hot tail is gentler." | 0.85-0.90 W/mm^2, measured under corrected accounting (see quotable/03) |
| `05-first-law-recovery/` | Every `p_mr_net_W` computed with the first-law recovery term -- 36 rows report a NET-GENERATING cooler. | the second-law form, `breakeven_ratio_at(T_h)`; corrected values in quotable/05 |
| `06-legacy-envelope-and-materials/` | "Yb:YLF is the cold-zone material." "eta_ASF ~ 0.02 is the demonstrated state of the art." The pre-30-Aug device envelope (h_max 250 W/mm^2). | thin-film GaAs tiles or SiN-encapsulated molecular dye; > 1000 W/mm^2; eta_ASF 0.10-0.60 with 0.32 the working point |

Nothing here should appear in a proposal, a slide, or a paper without first reading
`docs/RESULTS_REGISTER.md` §2.

Rebuild or check with `python scripts/build_results_registers.py [--verify]`.
