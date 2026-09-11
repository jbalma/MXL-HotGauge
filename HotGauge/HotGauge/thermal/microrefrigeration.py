"""Goal 3: photonic microrefrigeration (MR) as targeted heat removal in the HotGauge pipeline.

The model
---------
MR is injected as **negative power sources** at floorplan blocks. This is validated behaviour,
not an assumption: removing 0.5 W at ``cALU_0`` in a 35 W steady solve drops that block 10.7 K,
cools its neighbours (``RBB_0`` by 9.5 K), and leaves distant blocks essentially untouched.

**Thermal clipping, not bulk cooling.** MR removes only the heat needed to pull a block down to
a temperature target -- the *excess* -- rather than its whole heat load. That is what makes a
poor cooler COP acceptable: you pay to move a small amount of heat from exactly the place that
limits the clock. Two measured facts make the case:

* McPAT leakage is nearly flat below ~340 K and explodes above ~350 K (see
  ``examples/calibrate_leakage_model.py``), so cooling a cool block buys almost nothing while
  clipping a hot one buys a great deal.
* A core runs at one clock, set by its **hottest** block, so removing one hotspot lifts the
  frequency of the whole core.

Operating envelope (docs/Microrefrigeration_v1.pdf)
--------------------------------------------------
The MR stage is not unlimited. Defaults encode the documented envelope:

* cooling power density ``H`` ~1-10 W/mm^2 -- a block's removal is capped at ``H_max * area``
* temperature lift ``dT`` <~ 10 K
* spatial targeting <~100 um -- blocks narrower than this cannot be addressed individually; a
  spot cools a neighbourhood, which ``spot_limited`` flags rather than silently ignoring
* ``COP`` -- electrical cost is ``Q_removed / COP``. The working assumption is **0.2 (20 %
  efficiency)**, i.e. 5 W electrical per watt of heat removed; the literature range for
  thin-film uTEC practical COP is ~0.1-0.3. MR only wins because ``Q_removed`` is small and
  buys a disproportionate frequency gain; it is trivially a net loss if used as a bulk cooler.

Sensitivity is measured, not assumed
------------------------------------
Converting "this block is 20 K too hot" into "remove q watts" needs dT/dq [K/W] per block.
That is NOT derivable from the block's own thermal resistance -- lateral spreading dominates.
For ``cALU_0`` the naive R_die estimate gives 153 K for 0.5 W; the measured response is 10.7 K,
15x smaller. So ``run_mr_clipping`` measures the sensitivity by secant update across iterations
and never trusts an analytical value.
"""

import re
import logging

import numpy as np

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------
# The MR envelope, and where every number in it comes from
# ---------------------------------------------------------------------------------------------
# Until 26 August 2026 this block read "Documented MR envelope: h_max 10 W/mm^2, dt_max 10 K"
# with no source. It was wrong in both directions at once, and the direction mattered:
#
#   * **pessimistic about CAPABILITY.** Draft_5 s6.4.1 (benchtop, preliminary) reports
#     250 W/mm^2 extracted from a 100 x 100 um area and a 45 C reduction against the
#     conventional baseline. The model was clipping at 10 W/mm^2 and 10 K -- 25x and 4.5x below
#     what the bench had already shown.
#   * **optimistic about EFFICIENCY.** The same bench achieved 3.5 % cooling efficiency
#     (eta_ASF ~ 0.035) where the model assumed 0.20.
#
# That combination silently bounded every MR result in the catalogue: the planner could never
# ask for more than 10 K of lift, so any architectural lever needing more was unreachable **by
# assumption**, not by physics. The threshold-voltage lever is the case that matters -- a 50 mV
# V_t reduction needs ~22 K and a 75 mV one ~33 K (docs/LADDER_GEN0.md). Both are inside the
# demonstrated 45 K and both were outside the assumed 10 K.
#
# The values below are the DEMONSTRATED bench figures for capability and the TARGET figures for
# efficiency. Both are labelled, because they are not the same kind of number and a reader is
# entitled to know which is which.

#: Peak cooling power density [W/mm^2]. **Demonstrated**, Draft_5 s6.4.1: 250 W/mm^2 from a
#: 100 x 100 um area on the bench.
#:
#: Note what that does and does not say. It is a LOCAL extraction density over 0.01 mm^2. Whether
#: a tile-scale array sustains it over a 500 um tile is a separate question about pump delivery
#: and parasitic load, and this model does not answer it -- it applies the figure per tile. If
#: that turns out to be the binding constraint, it will show up as the plan hitting h_max, which
#: run_mr_clipping already reports.
#: `[!]` REFRESHED 30 Aug 2026 against v91 Table 8.2. The previous 250.0 is the Yb:YLF-era figure
#: from Draft_5 s6.4.1 and it understated the current platforms by 4-40x. v91 gives 1e3-1e4 W/mm^2
#: for BOTH current extractor platforms (SMILES-R640-in-polymer and direct-bandgap GaAs/GaInP),
#: which is also where v91 Figure 1.6 puts hot-spot DEMAND -- so supply now meets demand where it
#: previously fell short by that factor.
#:
#: The default is the LOW end of the published range, deliberately: 1e3 vs 1e4 is a 10x lever and
#: picking the top of a range as a default is how an optimistic number becomes load-bearing. Sweep
#: it with --mr-h-max rather than assuming either end.
DEFAULT_H_MAX_W_PER_MM2 = 1000.0
#: v91 Table 8.2, both current platforms. Use as a sweep range, not as a point estimate.
V91_H_MAX_RANGE_W_PER_MM2 = (1.0e3, 1.0e4)
#: The Yb:YLF-era value every result before 30 Aug 2026 was computed with. Retained so those
#: results still reproduce exactly: --mr-h-max 250
LEGACY_H_MAX_W_PER_MM2_DRAFT5 = 250.0
#: Previous value, retained so a pre-26-Aug result can be reproduced: --mr-h-max 10
LEGACY_H_MAX_W_PER_MM2 = 10.0

#: Maximum temperature lift the stage can sustain [K]. **Demonstrated**, Draft_5 s6.4.1:
#: "Temperature reduction: 45 C below conventional cooling baseline".
#:
#: `[!]` UNRESOLVED as of 30 Aug 2026. This is the OTHER Yb:YLF-era envelope figure, and unlike
#: h_max above, **v91 does not supply a replacement** -- a search of the materials and device
#: chapters found no maximum-lift figure. It is left at 45.0 K deliberately rather than scaled by
#: guesswork, because it is load-bearing: the measured 34-core rescue failed on exactly this
#: constraint ("envelope insufficient: dt_max binds ... this is the device's temperature lift, not
#: its cost"), so an invented value would manufacture the result it is meant to test.
#: **This is an open question for the device team, and it is the single blocking input.**
DEFAULT_DT_MAX_K = 45.0
#: Previous value, retained for reproduction: --mr-dt-max 10
LEGACY_DT_MAX_K = 10.0

#: Anti-Stokes fluorescence (ASF) extraction efficiency: heat removed per watt of *optical* pump.
#: **TARGET**, mid-range of Draft_5 s3.5.4's "10-60 % across MVP stages". Bench-demonstrated is
#: 0.035 (s6.4.1); the previous default was 0.20.
#:
#: This is an OPTICAL efficiency. The electrical COP is eta_asf * eta_laser.
#:
#: The usable range is **0.10-0.60** -- Draft_5 s3.5.4's "10-60 % across MVP stages", which is a
#: span of *stages*, not a single platform's tolerance. 0.32 is the middle ground and the default.
#:
#: `[!]` A 3 Sep 2026 revision narrowed this to 0.10-0.30 and moved the default to 0.20 on the
#: reading that the shipping platform's own band was tighter. **That narrowing is withdrawn** --
#: the full MVP-stage range stands and 0.32 is restored, so every recorded MR cost reproduces
#: un-flagged. Sweep it with --mr-eta-asf rather than treating any point in it as settled.
#:
#: What eta_asf does and does not touch, which is worth knowing before sweeping it: it enters only
#: through `cop = eta_asf * eta_laser`, and the planner sizes its removal from the THERMAL problem.
#: So it moves every MR **cost** in proportion and moves **no** thermal result -- not a peak, not a
#: rescue verdict, not a density ceiling.
ETA_ASF_RANGE = (0.10, 0.60)
DEFAULT_ETA_ASF = 0.32
#: Laser diode wall-plug efficiency (electrical -> optical pump). **TARGET**. Draft_5 s3.5.4
#: gives 70-75 % as *demonstrated* at 900-1000 nm, so 0.85 is beyond demonstrated and must be
#: reported as a target.
DEFAULT_LASER_WALLPLUG = 0.85
#: Laser power converter (LPC) cell efficiency, optical -> DC. **TARGET**. Draft_5 s3.5.4 gives
#: "up to 87 % demonstrated in GaAs/SiC", so 0.92 is likewise beyond demonstrated.
DEFAULT_LPC_EFFICIENCY = 0.92

#: What the bench has actually achieved, kept next to the targets so the gap is inspectable
#: rather than remembered. Sources are all Draft_5.
DEMONSTRATED = {
    'h_max_W_per_mm2': 250.0,      # s6.4.1, from a 100 x 100 um area
    'dt_max_K': 45.0,              # s6.4.1, below the conventional baseline
    'eta_asf': 0.035,              # s6.4.1, "7000 W/mm^2 pump for 250 W/mm^2 cooling"
    'laser_wallplug': 0.75,        # s3.5.4, 70-75 % demonstrated at 900-1000 nm
    'lpc_efficiency': 0.87,        # s3.5.4, "up to 87 % demonstrated in GaAs/SiC"
    'source': 'docs/photonic_cooling/Draft_5__Photonic_cooling_of_chips_v12___Provisional_Version.pdf',
}

#: `[!]` SUPERSEDED BY v91 CHAPTER 8. The Yb:YLF numbers above are the old rare-earth platform and
#: are no longer the design target: at 1-10 W/mm^2 they are two to three orders of magnitude below
#: what the current platforms reach. Do NOT quote eta_asf = 0.035 or "0.02 demonstrated" as the
#: state of the art -- both refer to Yb:YLF.
#:
#: Platform table is v91 Table 8.2; the anti-Stokes ladder is v91 Table 8.1. Note the notation:
#: Table 8.1's "eta_c" is the PER-PHOTON anti-Stokes shift, which v91 Table 1.1 renames; the
#: composite is eta_ASF = eta_abs * eta_EQE * (per-photon shift).
#: `[!]` CORRECTED 3 Sep 2026. The shipping platform is **two thin-film extractor options**, and
#: neither is a rare-earth crystal:
#:
#:   * **semiconductor (GaAs) extractor tiles**, and
#:   * **SiN-encapsulated molecular dyes**
#:
#: both reaching **> 1000 W/mm^2** cooling power density, across an eta_ASF range of
#: **0.10-0.60** (Draft_5 s3.5.4, spanning the MVP stages; 0.32 is the working point). Yb:YLF is
#: retained below ONLY as the historical baseline that the pre-30-Aug catalogue was computed
#: against. `[!]` It is **not** the cold-zone material and must not be quoted as one -- an earlier
#: revision of this file said it was "still the right choice for the COLD zone", which was wrong.
#: Both current platforms cover the cold zone: GaAs is tabulated to 77 K and the dye to 250 K.
PLATFORMS_V91 = {
    'sin_encapsulated_dye': {
        'cooling_density_W_per_mm2': (1e3, 1e4),
        'eta_EQE': 0.99,                 # red-tail pump, Nt >= 1e-2 M
        'per_photon_shift': {680: 0.124, 700: 0.157, 720: 0.190, 740: 0.223},
        'eta_asf_tabulated': 0.123,      # 680 nm design point, eta_abs -> 1 via Purcell
        'eta_asf_best_tabulated': 0.221,  # 740 nm
        'T_range_K': (250.0, 400.0),
        'encapsulation': 'SiN',
        'note': 'v91 s8.3.2/8.3.3. SiN-encapsulated molecular dye thin film. Solution-processable, '
                'substrate-agnostic, room temperature; matches direct-bandgap semiconductor '
                'cooling density. The dye chemistry is a SMILES lattice (Small-Molecule Ionic '
                'Isolation Lattices -- NOT the chemical-notation format); the ENCAPSULATION is '
                'SiN, not the polymer host an earlier revision of this table named.',
    },
    'gaas_gainp_epitaxy': {
        'cooling_density_W_per_mm2': (1e3, 1e4),
        'eta_EQE': 0.99,                 # low-temperature; 0.96 at 850 nm room temperature
        'eta_asf_tabulated': None,
        'T_range_K': (77.0, 400.0),
        'form': 'thin-film extractor tiles',
        'note': 'v91 s8.2.1 Table 8.2. Thin-film GaAs extractor tiles, monolithic with a '
                'co-designed multi-junction LPC; cost is MBE/MOCVD lattice-matched growth and a '
                'substrate form-factor constraint. Tabulated to 77 K, so this platform covers the '
                'cold zone on its own.',
    },
    'cr_lisaf': {
        'cooling_density_W_per_mm2': (0.2, 0.8),      # v98 Table 1.1: 20-80 W/mm^3 at 10 um, F_P 30-100
        'cooling_density_W_per_mm3': (20.0, 80.0),
        'eta_EQE': 0.9,                             # demonstrated 0.85-0.95; > 0.94 needed
        'T_range_K': (150.0, 400.0),
        'note': 'v98 §8.1.2 / Table 1.1 / Table 8.4. Cr3+:LiSAF, the STORAGE-ZONE material '
                '(decided 8 Sep 2026). Allowed transition, 67 us lifetime, 1e21 cm^-3, disorder '
                'tail sigma 0.26. A decade above Yb:YLF and two below the dye at the same '
                'Purcell factor; fails the breakeven test at its demonstrated IQE, so every '
                'figure is a ceiling at eta_EQE = 1.',
    },
    'yb_ylf_crystal': {
        'cooling_density_W_per_mm2': (1.0, 10.0),
        'eta_EQE': 0.97,
        'T_range_K': (150.0, 300.0),
        'note': 'v91 Table 8.2. `[!]` HISTORICAL BASELINE ONLY -- 2-3 orders of magnitude below '
                'the two shipping platforms above, and NOT the cold-zone material. It is kept so '
                'the pre-30-Aug catalogue (h_max 250 W/mm^2, eta_asf 0.035) can be reproduced with '
                '--mr-h-max 250 --mr-eta-asf 0.035, and for no other purpose. An earlier revision '
                'of this table recommended it for the cold zone; that recommendation is WITHDRAWN.',
    },
}

#: `[!}` REPLACED 3 Sep 2026. The previous table assigned a different rare-earth crystal to each
#: thermal zone (Yb:YLF cold, Ho/Tm-fluoride hot, SiC:Er above 600 K). **That is not the platform.**
#: The shipping device is a thin film of GaAs *or* SiN-encapsulated molecular dye, and zone
#: selection happens **within** those two options rather than by swapping to a rare-earth.
#:
#: What survives from v91 s8.4 is the *principle* -- a heterogeneous-thermal die does not use one
#: extractor everywhere, because eta_ASF and the achievable lift both depend on the local T_j.
#: What is withdrawn is the rare-earth material list.
#: `[!]` DECIDED 8 Sep 2026 (§P0.21), on v98 Table 10.8 read against the 3 Sep rule: the storage
#: (cold) zone material is **Cr:LiSAF** -- not Yb:YLF, which stays out of every zone -- and the
#: hot zone is the dye extractor. And the DEFAULT cold plate is SINGLE-material (see
#: `thermal.extractor.DEFAULT_ZONE_MODE`): a floorplan-matched dual-material arrangement is a
#: per-architecture product and is a flagged experiment, never the default.
ZONE_EXTRACTORS = {
    'cold_cache': {
        'T_K': (150.0, 320.0),
        'platforms': ('cr_lisaf',),
        'note': 'Storage / control zone. Cr3+:LiSAF (v98 §8.1.2, Table 1.1): 20-80 W/mm^3 at '
                'F_P 30-100, quantum defect 5.9 % at 900 on 850 nm, needs eta_EQE > 0.94. Its '
                'transparency cap collapses on cooling like every anti-Stokes emitter, so it '
                'is a low-density, leakage-suppression tile, not a hot-spot razor.',
    },
    'hot_compute': {
        'T_K': (320.0, 450.0),
        'platforms': ('sin_encapsulated_dye',),
        'note': 'Compute zone. The R640-SMILES film (v98 Table 1.1 row, rung 6 of the ladder) is '
                'intrinsically a hot-die platform: its tail absorption and transparency ceiling '
                'both grow exponentially with T. GaAs/GaInP remains a platform alternative with '
                'a retuned pump (§9.3.2) but is not the zone assignment.',
    },
    'above_tabulated': {
        'T_K': (400.0, None),
        'platforms': (),
        'note': '`[!]` OPEN. Neither shipping platform is tabulated above 400 K in v91. This is an '
                'honest gap, not a material recommendation -- do not fill it with the retired '
                'rare-earth list. It also does not bind today: a die that survives does not reach '
                'it, and CLAUDE.md already says to report >127 C as non-viable rather than as a '
                'number.',
    },
}

#: Kept under the old name so nothing imports a hole, but it is the same corrected table.
ZONE_EXTRACTORS_V91 = ZONE_EXTRACTORS
PLATFORMS = PLATFORMS_V91

#: The previous defaults, as one dict, so a driver can offer --legacy-envelope and a test can
#: assert the old catalogue still reproduces.
LEGACY_ENVELOPE = {
    'h_max': 10.0, 'dt_max_K': 10.0,
    'eta_asf': 0.20, 'laser_wallplug': 0.70, 'lpc_efficiency': 0.90,
}
#: Optical-path collection loss between the cooling element and the LPC. 1.0 reproduces the
#: MXL-Photonic-Cooling-Power-Analysis.xlsx model exactly (it assumes perfect routing).
DEFAULT_COLLECTION_EFFICIENCY = 1.0

#: Smallest feature the cooling stage can be focused onto [um]. The realistic range is
#: **1-10 um**: ~1 um is roughly the diffraction limit at the pump wavelength, ~10 um a
#: conservative practical delivery limit. The default is the cautious end of that range.
#:
#: This was previously 100 um, which is wrong by 10-100x and materially understated what MR can
#: reach. On the 34-core die that excluded 37 of the 57 above-target blocks -- including the two
#: highest power densities on the chip, ``RBB`` (13.4 um) and ``iBuf`` (1.3 um). At 10 um the
#: reachable set is 44 of 57 hot blocks and 99.4% of die power; at 1 um it is all of it.
#:
#: Consequence worth stating plainly: spot size is **not** the binding constraint on photonic
#: cooling here. The block *selection policy* is -- ``run_mr_clipping`` cools only blocks above
#: ``target_K``, and on that die they carry ~10% of total power while 65% sits in a band 10-20 K
#: below the target, untouched.
DEFAULT_SPOT_MIN_UM = 10.0

#: What to do with a block narrower than ``spot_min_um``:
#:
#: * ``'dilute'``  -- illuminate the whole pixel: the block still gets the cooling it needs, but
#:   you pay for the pixel, so the laser cost rises by ``pixel_area / block_area``. This is what
#:   a real tile array does and is the default.
#: * ``'exclude'`` -- the block cannot be targeted at all. A conservative bound.
#: * ``'ideal'``   -- cool it in full at no penalty. This was the *de facto* behaviour before
#:   the policy existed, because ``spot_limited`` was computed and never acted on -- so every
#:   result predating this assumed perfect targeting at any feature size.
DEFAULT_SPOT_POLICY = 'dilute'
#: Maxwell Labs working assumption (2026-08-11): 20% MR efficiency, i.e. 5 W electrical per
#: watt of heat removed. The literature range for thin-film uTEC practical COP is ~0.1-0.3.
DEFAULT_COP = 0.2


class MRParams(object):
    """Microrefrigeration stage capability and cost.

    target_K       : temperature the clipper pulls hot blocks down to.
    h_max          : max cooling power density [W/mm^2] the stage can deliver.
    dt_max_K       : max temperature lift the stage can sustain.
    cop            : coefficient of performance; electrical cost = Q_removed / cop.
    spot_min_um    : spatial targeting limit; narrower blocks are flagged ``spot_limited``.
    max_total_W    : optional cap on total heat removed (a laser power budget).
    """

    def __init__(self, target_K, h_max=DEFAULT_H_MAX_W_PER_MM2, dt_max_K=DEFAULT_DT_MAX_K,
                 eta_asf=DEFAULT_ETA_ASF, spot_min_um=DEFAULT_SPOT_MIN_UM,
                 spot_policy=DEFAULT_SPOT_POLICY, max_total_W=None,
                 laser_wallplug=DEFAULT_LASER_WALLPLUG, lpc_efficiency=DEFAULT_LPC_EFFICIENCY,
                 collection_efficiency=DEFAULT_COLLECTION_EFFICIENCY, recover=True, cop=None,
                 extractor=None, zone_targets=None, objective=None, envelope_shape='seed'):
        if target_K <= 0:
            raise ValueError('target_K must be > 0')
        # §P0.24 (F3): the SHAPE of the envelope the rescue path starts from. 'seed' (every
        # recorded row): each block's cap is dt_max / s with s the 1.0 K/W placeholder, i.e. a
        # uniform 45 W per block, which the conservation cap then scales -- 367 x 45 W = 16.5 kW
        # on the GA100, scaled 45x, so the eight hot SMs of a concentrated kernel got ~1 W each
        # and the "full capability" solve ran away (register §3, the plan-shape item). 'power':
        # each block is additionally capped at its OWN dissipation, so full capability means
        # removing every block's own heat and the conservation cap is met by construction.
        if envelope_shape not in ('seed', 'power'):
            raise ValueError("envelope_shape must be 'seed' or 'power', got {!r}".format(envelope_shape))
        self.envelope_shape = envelope_shape
        # §P0.22 (D3): a PER-ZONE target. ``zone_targets`` is ``[(pattern, T_K), ...]``; a block
        # whose name matches a pattern (regex search, first match wins -- the same rule
        # ``mr_array.tiles_over_blocks`` uses) is planned against that temperature instead of
        # ``target_K``. This is what turns the hot-spot planner into a cache-leakage planner:
        # ``[('^(L2|L3)', 280.0)]`` asks for the caches at 280 K and everything else at the
        # hot-spot target. With no zones every code path is bit-identical to the recorded one --
        # ``target_for`` returns ``target_K`` and ``objective_peak`` is the plain maximum.
        self.zone_targets = []
        for pat, tk in (zone_targets or ()):
            if float(tk) <= 0:
                raise ValueError('zone target must be > 0 K, got {!r} for {!r}'.format(tk, pat))
            self.zone_targets.append((re.compile(pat), float(tk)))
        self.objective = str(objective) if objective else ('zoned' if self.zone_targets else 'peak')
        if h_max <= 0:
            raise ValueError('h_max must be > 0')
        for name, val in (('laser_wallplug', laser_wallplug),
                          ('lpc_efficiency', lpc_efficiency),
                          ('collection_efficiency', collection_efficiency),
                          ('eta_asf', eta_asf)):
            if not 0.0 <= val <= 1.0:
                raise ValueError('{} must be in [0, 1], got {!r}'.format(name, val))
        self.target_K = float(target_K)
        self.h_max = float(h_max)
        # §P0.19: with an extractor model the lift is DERIVED -- the per-block cap becomes the
        # extractor's cooling flux at the temperature of the tile above the block, which falls
        # as the tile cools and crosses zero at T_min -- so dt_max_K may be None (no scalar lift
        # cap). Passing both keeps the scalar as an additional cap.
        self.extractor = extractor
        self.dt_max_K = float('inf') if dt_max_K is None else float(dt_max_K)
        if dt_max_K is None and extractor is None:
            raise ValueError('dt_max_K=None needs an extractor model to bound the lift instead')
        self.spot_min_um = float(spot_min_um)
        if spot_policy not in ('ideal', 'exclude', 'dilute'):
            raise ValueError("spot_policy must be 'ideal', 'exclude' or 'dilute', got {!r}"
                             .format(spot_policy))
        self.spot_policy = spot_policy
        self.max_total_W = None if max_total_W is None else float(max_total_W)
        self.laser_wallplug = float(laser_wallplug)
        self.lpc_efficiency = float(lpc_efficiency)
        self.collection_efficiency = float(collection_efficiency)
        self.recover = bool(recover)
        if cop is not None:
            # Back-compat: an explicit electrical COP pins eta_asf = cop / eta_laser.
            if cop <= 0:
                raise ValueError('cop must be > 0')
            if self.laser_wallplug <= 0:
                raise ValueError('cannot derive eta_asf from cop with zero wall-plug')
            self.eta_asf = float(cop) / self.laser_wallplug
        else:
            self.eta_asf = float(eta_asf)

    @property
    def has_zones(self):
        """True when at least one block is planned against a zone target rather than ``target_K``."""
        return bool(self.zone_targets)

    def target_for(self, block):
        """The temperature this block is planned against: its zone's target, else ``target_K``."""
        if self.zone_targets:
            name = str(block)
            for rx, tk in self.zone_targets:
                if rx.search(name):
                    return tk
        return self.target_K

    @property
    def cop(self):
        """Electrical COP = heat removed per watt of electrical draw, BEFORE recovery.

        The spreadsheet parameterises the cooler by its *optical* efficiency ``eta_asf``
        (heat removed per watt of optical pump), so the electrical figure is
        ``eta_asf * eta_laser``: 20 % ASF at 70 % wall-plug is an electrical COP of 0.14,
        not 0.20. Keeping these distinct matters -- conflating them overstates the cooler
        by 1/eta_laser.
        """
        return self.eta_asf * self.laser_wallplug

    @property
    def breakeven_ratio(self):
        """``eta_LPC * (1 + eta_ASF) * eta_laser`` -- recovered power per watt drawn.

        This is the master design number from MXL-Photonic-Cooling-Power-Analysis.xlsx:

        * ``< 1`` -- MR costs net electrical power (the usual regime)
        * ``= 1`` -- self-sustaining: recovery exactly pays for the pump
        * ``> 1`` -- net-generating: the loop returns more electrical power than it draws,
          with the extracted chip heat as the additional energy source

        Collection loss multiplies it. With eta_LPC 0.90 and eta_laser 0.70, breakeven needs
        ``eta_ASF >= 0.587`` -- i.e. **the extractor, not the LPC, is the binding constraint**.

        `[!]` **This is a FIRST-LAW ledger and it is an upper bound, not an operating point.**
        It credits the whole fluorescence stream ``(1 + eta_ASF)`` as convertible to electricity
        at ``eta_LPC``, with no Carnot penalty on the heat-derived part. The second-law form is
        equation (1.15) in ``HotGauge.thermal.exergy``::

            loop_gain = eta_L * eta_c * (1 + eta_AS * phi)      phi = 1 - T_0/T_h

        and ``eta_AS`` there is this same ``eta_asf``. The two expressions differ by exactly the
        factor ``phi`` multiplying ``eta_ASF``, so **this property is the phi -> 1 limit**, which
        requires ``T_h -> infinity``. At any finite die temperature it overstates recovery, and at
        the shipped defaults it overstates it enough to flip the verdict: this returns 1.032
        ("net-generating") where the second-law value at 350 K is 0.821 and does not reach 1.0 at
        any temperature reachable by silicon.

        Use :meth:`breakeven_ratio_at` for a physical number. This property is kept because every
        result recorded before 30 August 2026 was computed with it.
        """
        return (self.lpc_efficiency * self.collection_efficiency
                * (1.0 + self.eta_asf) * self.laser_wallplug)

    def breakeven_ratio_at(self, T_h_K, T_0_K=295.0):
        """Second-law-bounded recovered power per watt drawn, at source temperature ``T_h_K``.

        Equation (1.15): ``eta_L * eta_c * (1 + eta_AS * phi)``. Identical to
        :attr:`breakeven_ratio` except that the anti-Stokes term is weighted by the Carnot factor
        of the heat actually being lifted, which is the physics :attr:`breakeven_ratio` omits.

        ``T_h_K`` is the temperature the heat is lifted FROM -- the junction, not the ambient.
        """
        T_h = float(T_h_K)
        if T_h <= 0.0:
            raise ValueError('T_h_K must be positive, got {}'.format(T_h_K))
        phi = 1.0 - float(T_0_K) / T_h
        return (self.lpc_efficiency * self.collection_efficiency
                * (1.0 + self.eta_asf * phi) * self.laser_wallplug)

    def __repr__(self):
        rec = ('eta_LPC={:.2f}, eta_ASF={:.2f}, eta_laser={:.2f} -> breakeven ratio {:.3f}'
               .format(self.lpc_efficiency, self.eta_asf, self.laser_wallplug,
                       self.breakeven_ratio)
               if self.recover else 'no recovery (eta_ASF={:.2f})'.format(self.eta_asf))
        return (('MRParams(target={:.1f} K, H<={:.1f} W/mm^2, dT<={} K, COP_elec={:.3f}, '
                'spot>={:.0f} um, {}{}{})'.format(
                    self.target_K, self.h_max,
                    'inf' if self.dt_max_K == float('inf') else '{:.1f}'.format(self.dt_max_K),
                    self.cop, self.spot_min_um, rec,
                    '' if self.max_total_W is None else
                    ', budget<={:.2f} W'.format(self.max_total_W),
                    '' if self.extractor is None else
                    ', extractor={}'.format(getattr(self.extractor, 'label', 'yes'))))
                + ('' if not self.zone_targets else
                   ' zones=[{}]'.format(', '.join('{}->{:.0f} K'.format(rx.pattern, tk)
                                                  for rx, tk in self.zone_targets))))


#: Prefix marking a Tflp key that is BOOKKEEPING, not a floorplan block.
#: ``thermal.leakage_feedback`` injects ``__agg__L3`` (see ``BRIDGEABLE_AGGREGATES``) so a bridged
#: aggregate's leakage has a temperature to feed back against. Such a key has a real temperature
#: and no real surface, so it must never reach a cooling plan.
SYNTHETIC_TEMP_PREFIX = '__agg__'


def is_synthetic_temp_key(name):
    """True for a Tflp key that stands for an aggregate rather than a floorplan block.

    Matched on the prefix rather than imported from ``leakage_feedback`` so the planner carries no
    dependency on the feedback layer, and so a future bridged aggregate is excluded automatically
    instead of having to be remembered here.
    """
    return str(name).startswith(SYNTHETIC_TEMP_PREFIX)


def _last_K(t):
    return float(np.ravel(t)[-1]) if np.ndim(t) else float(t)


def objective_peak(temps, params, t_floor_K=200.0):
    """The temperature the planner's convergence and hold tests are read against (§P0.22, D3).

    Under the default objective (no zone targets) this is the plain peak over the die, computed
    by exactly the expression every descent used before -- so the recorded rows reproduce
    bit-for-bit. With zone targets it is ``target_K + max_b (T_b - target_for(b))``: the block
    that is furthest above ITS OWN target, expressed on the hot-spot target's scale, so that
    every existing ``peak > target_K + tol`` test becomes "some block is above its target by more
    than tol" without touching the tests themselves. Synthetic bookkeeping keys are skipped in
    the zoned form (they have no target); in the plain form they are harmless (a mean of blocks
    is never the maximum).
    """
    if not getattr(params, 'has_zones', False):
        return max((float(np.ravel(t)[-1]) for t in temps.values()
                    if float(np.ravel(t)[-1]) > t_floor_K), default=float('nan'))
    worst = None
    for blk, t in temps.items():
        if is_synthetic_temp_key(blk):
            continue
        T = _last_K(t)
        if T <= t_floor_K:
            continue
        ex = T - params.target_for(blk)
        worst = ex if worst is None else max(worst, ex)
    return float('nan') if worst is None else params.target_K + worst


def zone_report(temps, params, t_floor_K=200.0):
    """Per-zone summary of a solved field: how far each zone sits from its own target.

    Returns ``{'<pattern>': {...}, 'rest': {...}}`` with block count, max / mean temperature (a
    plain mean over blocks, not area-weighted -- stated so nobody reads it as a die average),
    the target, the count above target and the worst excess. ``rest`` is every block no zone
    pattern matches, against ``target_K``.
    """
    zones = [(rx.pattern, rx, tk) for rx, tk in getattr(params, 'zone_targets', [])]
    buckets = {label: [] for label, _, _ in zones}
    buckets['rest'] = []
    for blk, t in temps.items():
        if is_synthetic_temp_key(blk):
            continue
        T = _last_K(t)
        if T <= t_floor_K:
            continue
        for label, rx, _ in zones:
            if rx.search(str(blk)):
                buckets[label].append(T)
                break
        else:
            buckets['rest'].append(T)
    out = {}
    for label, _, tk in zones + [('rest', None, params.target_K)]:
        vals = buckets[label]
        out[label] = {'target_K': float(tk), 'n_blocks': len(vals),
                      'max_K': (max(vals) if vals else None),
                      'mean_K': (float(np.mean(vals)) if vals else None),
                      'n_above_target': int(sum(1 for v in vals if v > tk)),
                      'worst_excess_K': ((max(vals) - tk) if vals else None)}
    return out


def clipping_plan(block_temps_K, block_geom, params, sensitivity_K_per_W, t_floor_K=200.0,
                  die_power_W=None, h_max_by_block=None, q_cap_by_block=None):
    """Heat to remove per block [W] to clip everything above ``params.target_K``.

    block_temps_K       : {block: T_K}
    block_geom          : {block: {'area_mm2': .., 'min_dim_um': ..}}
    sensitivity_K_per_W : {block: dT/dq} -- how much this block cools per watt removed.
                          Measured, never assumed (see module docstring).

    Each block's removal is the smallest of what the excess needs and what the stage can do:

        q_need = (T - target) / sensitivity        (what would clip it)
        q_H    = h_max * area                      (cooling-density ceiling)
        q_dT   = dt_max / sensitivity              (temperature-lift ceiling)

    ``h_max_by_block`` (§P0.19) replaces ``params.h_max`` per block with the extractor's cooling
    flux at the temperature of the tile above it (see :func:`extractor_caps`); a block whose
    extractor can no longer cool (flux <= 0, the tile at or below ``T_min``) is skipped with
    ``limit='extractor_exhausted'``. That is how the lift stops being a scalar.

    All three of those are **device** limits. ``die_power_W`` adds the one **physical** limit:
    in steady state the array cannot remove more heat than the die generates without driving it
    below the coolant, which is a refrigeration regime this model does not claim. Passing it is
    strongly recommended -- see the note on the cap below for what it prevents.

    Returns ``(plan, detail)`` where plan is ``{block: q_W}`` (positive = heat removed) and
    detail records, per block, which limit bound it -- so a disappointing result can be traced
    to the physical constraint responsible rather than guessed at.
    """
    plan, detail = {}, {}
    for blk, T in block_temps_K.items():
        if is_synthetic_temp_key(blk):
            # `[!]` Bookkeeping keys are not coolable surfaces (§P0.17). `bridge_aggregates=True`
            # injects `__agg__L3` so the L3's leakage can feed back against the mean of the real
            # L3_* blocks -- it is a temperature with no floorplan block behind it. Planning a
            # tile onto it produced
            #     KeyError: "plan names block '__agg__L3', which is not in the floorplan"
            # at placement time, killing ~10 points per arm of the §P0.16 catalogue re-run.
            # `[!]` The trigger is the MR TARGET being low enough that the key is above it, and
            # since the key's temperature moves with the leakage curve and the core_other policy,
            # it is arm-dependent -- point 16 raised in arm B and completed in arm D. There is no
            # target threshold that expresses it, which is why the filter is on the key itself.
            continue
        T = float(np.ravel(T)[-1]) if np.ndim(T) else float(T)
        target = params.target_for(blk)          # §P0.22: the block's OWN target (zone or die)
        if T <= t_floor_K or T <= target:
            continue
        geom = block_geom.get(blk)
        if geom is None:
            continue
        s = float(sensitivity_K_per_W.get(blk, 0.0))
        if s <= 0:
            # Without a positive measured sensitivity we cannot size the removal; skipping is
            # the honest choice (removing a guessed amount would be untraceable).
            detail[blk] = {'limit': 'no_sensitivity', 'q_W': 0.0, 'excess_K': T - target}
            continue
        excess = T - target
        q_need = excess / s
        h_cap = params.h_max
        capped_by_extractor = False
        if h_max_by_block is not None and blk in h_max_by_block:
            h_cap = float(h_max_by_block[blk])
            capped_by_extractor = True
            if h_cap <= 0.0:
                detail[blk] = {'limit': 'extractor_exhausted', 'q_W': 0.0, 'excess_K': excess,
                               'q_need_W': q_need, 'q_h_max_W': 0.0,
                               'q_dt_max_W': params.dt_max_K / s}
                continue
        q_H = h_cap * geom['area_mm2']
        q_dT = params.dt_max_K / s
        q = min(q_need, q_H, q_dT)
        limit = ('need' if q == q_need else
                 (('extractor' if capped_by_extractor else 'h_max') if q == q_H else 'dt_max'))
        if q_cap_by_block is not None and blk in q_cap_by_block:
            # §P0.24: an explicit per-block ceiling (the block's own dissipation under the
            # 'power' envelope shape). A block with no power to remove is skipped.
            q_own = float(q_cap_by_block[blk])
            if q_own <= 0.0:
                continue
            if q_own < q:
                q, limit = q_own, 'own_power'
        if q <= 0:
            continue

        # A block narrower than the pixel pitch cannot be illuminated on its own. What happens
        # then is set by spot_policy -- see MRParams. Until this was added the flag below was
        # computed and never read, so every result silently assumed ideal targeting at any
        # feature size (i.e. the 1 um array), and changing spot_min_um did nothing at all.
        spot_limited = geom['min_dim_um'] < params.spot_min_um
        cost_mult = 1.0
        if spot_limited:
            if params.spot_policy == 'exclude':
                detail[blk] = {'limit': 'spot_limited', 'q_W': 0.0, 'excess_K': excess,
                               'q_need_W': q_need, 'q_h_max_W': q_H, 'q_dt_max_W': q_dT,
                               'spot_limited': True, 'achievable_dT_K': 0.0,
                               'cost_multiplier': float('inf')}
                continue
            if params.spot_policy == 'dilute':
                # The pixel is illuminated in full but only the block's area fraction of the
                # cooling lands on the block. Delivered q is unchanged; the laser bill is not.
                pixel_mm2 = (params.spot_min_um ** 2) / 1.0e6
                cost_mult = pixel_mm2 / max(geom['area_mm2'], 1e-12)
                limit = limit + '+spot_dilute'

        plan[blk] = q
        detail[blk] = {'limit': limit, 'q_W': q, 'excess_K': excess,
                       'q_need_W': q_need, 'q_h_max_W': q_H, 'q_dt_max_W': q_dT,
                       'spot_limited': spot_limited, 'cost_multiplier': cost_mult,
                       'achievable_dT_K': q * s}

    # A laser budget is spent on the blocks with the largest excess first: the hottest block
    # sets the clock, so the marginal watt is worth most there.
    #
    # TWO different caps can bind here and they mean opposite things:
    #
    #   max_total_W -- a BUDGET the caller chose. Hitting it is a result: the plan wanted more
    #                  than it was allowed.
    #   die_power_W -- CONSERVATION, and hitting it is a BUG SIGNAL. In steady state the array
    #                  cannot remove more heat than the die generates without driving the die
    #                  below the coolant temperature, which is a refrigeration regime this model
    #                  does not claim and cannot price.
    #
    # Why the conservation cap exists (added 27 Aug 2026). The first iteration of the descent
    # sizes its plan from an ASSUMED sensitivity of 1.0 K/W, because nothing has been measured
    # yet. Under the legacy envelope (h_max 10 W/mm^2, dt_max 10 K) the device caps quietly
    # restrained that first plan -- h_max bound 396 of 400 blocks on a representative near-cliff
    # field. Correcting the envelope to its demonstrated values (250 W/mm^2, 45 K) removed that
    # restraint: on the same field the first plan went from 841 W to **9405 W**, sized by
    # `excess / s` with `s` a guess, against a die dissipating 79 W. Applied to the trace it
    # produced blocks at 3838 K and a coupled solve with no damping-independent answer, which is
    # what zeroed the MR arm of every clock study (docs/evidence/clock_search_mr_arm_defect.json).
    #
    # The cap is GLOBAL, not per block. A per-block bound of q <= p_block is the wrong physics:
    # the array sits above the silicon, so a tile cools a thermal NEIGHBOURHOOD and legitimately
    # removes more than the block underneath dissipates -- measured, the working margin plans
    # remove 0.108 W per engaged block against a 0.070 W mean block power. Only the total is
    # conserved.
    # CONSERVATION first, and it SCALES rather than reallocating. The two caps need different
    # arithmetic because they answer different questions. A budget is a spending decision, so
    # "hottest block first" is right: the marginal watt is worth most where the peak is. A
    # conservation violation is not a spending decision -- the plan's SHAPE came from the physics
    # and only its total is impossible, so the honest correction is to scale the whole plan and
    # leave the shape alone. Reallocating greedily under a conservation cap would concentrate the
    # entire die's power onto the two hottest blocks, which is a second pathology replacing the
    # first: on the field above that put 39.5 W on a single block.
    if die_power_W is not None and plan:
        total = sum(plan.values())
        if total > die_power_W:
            scale = die_power_W / total
            plan = {b: q * scale for b, q in plan.items()}
            for blk in plan:
                detail[blk]['limit'] = detail[blk]['limit'] + '+die_power_scaled'
                detail[blk]['q_W'] = plan[blk]
                detail[blk]['die_power_scale'] = scale
            LOGGER.warning(
                'MR plan wanted %.1f W from a die dissipating %.1f W (%.0fx) and was scaled by '
                '%.3g to conserve energy. This is NOT a budget being hit: a plan that large means '
                'it was sized from an untrustworthy sensitivity, so treat the result as suspect '
                'rather than merely trimmed.', total, die_power_W, total / max(die_power_W, 1e-9),
                scale)

    # A laser BUDGET is then spent on the blocks with the largest excess first: the hottest block
    # sets the clock, so the marginal watt is worth most there.
    if params.max_total_W is not None and plan:
        total = sum(plan.values())
        if total > params.max_total_W:
            order = sorted(plan, key=lambda b: -detail[b]['excess_K'])
            remaining, trimmed = params.max_total_W, {}
            for blk in order:
                if remaining <= 0:
                    detail[blk]['limit'] = 'budget_exhausted'
                    detail[blk]['q_W'] = 0.0
                    continue
                take = min(plan[blk], remaining)
                trimmed[blk] = take
                remaining -= take
                if take < plan[blk]:
                    detail[blk]['limit'] = 'budget'
                    detail[blk]['q_W'] = take
            plan = trimmed
    return plan, detail


def apply_cooling_to_trace(trace, plan, name_map):
    """Return a new trace with MR heat removal applied as negative power at mapped units.

    ``plan`` is keyed by floorplan block; the power trace is keyed by McPAT unit, so
    ``name_map`` bridges them. If several McPAT units map to one block, the removal is split
    between them in proportion to their power -- removing it all from one would distort the
    within-block distribution that 3D-ICE sees.
    """
    from HotGauge.power.traces import BasicPowerTrace

    by_block = {}
    for unit in trace.powers:
        blk = name_map(unit)
        if blk in plan:
            by_block.setdefault(blk, []).append(unit)

    powers = {u: np.array(v, dtype=float).copy() for u, v in trace.powers.items()}
    for blk, units in by_block.items():
        weights = np.array([max(float(np.sum(powers[u])), 0.0) for u in units], dtype=float)
        total = weights.sum()
        share = (weights / total) if total > 0 else np.full(len(units), 1.0 / len(units))
        for u, frac in zip(units, share):
            # plan is a steady removal rate in W, so it applies at every timestep.
            powers[u] = powers[u] - plan[blk] * frac
    return BasicPowerTrace(powers, trace.time_step)


def mr_accounting(plan, params, compute_power_W=None, detail=None, T_h_K=None,
                  T_0_K=295.0):
    """Laser power, LPC recovery, and net cost -- the MXL-Photonic-Cooling-Power-Analysis model.

    Implements the spreadsheet's formulation exactly (validated against its MVP-1/2/3 cases)::

        P_laser    = Q / (eta_ASF * eta_laser)                  electrical draw
        P_removed  = eta_ASF * eta_laser * P_laser              = Q, by construction
        P_recovered= eta_LPC * collection * (1 + eta_ASF) * eta_laser * P_laser
        P_used     = P_laser - P_recovered = (1 - breakeven_ratio) * P_laser

    The ``(1 + eta_ASF)`` term is the physics that makes this interesting: the light reaching
    the LPC is the pump *plus* the heat that was up-converted into it, so the recoverable
    optical power exceeds what the laser emitted.

    **Net-generating operation is a regime, not an error.** When
    ``breakeven_ratio = eta_LPC * collection * (1 + eta_ASF) * eta_laser`` exceeds 1, the loop
    returns more electrical power than it draws and ``P_used`` goes negative -- the extracted
    chip heat is the additional source. The spreadsheet's own MVP-3 sits there
    (eta 0.85/0.92/0.62 -> ratio 1.267, P_used = -50.7 W on 190 W of laser), and it is a
    target regime, so it is reported plainly rather than flagged.

    What *is* checked is the **first law**: energy out must not exceed energy in
    (``P_recovered <= P_laser + Q``). That catches genuine bookkeeping bugs without
    editorialising about which efficiency combinations are achievable -- that judgement belongs
    to the device model, not here.

    With eta_laser 0.70 / eta_LPC 0.90 / eta_ASF 0.20 the ratio is 0.756, so MR still costs
    net power; breakeven at that laser and LPC needs eta_ASF >= 0.587, which makes the
    **extractor the binding constraint**.
    """
    q_total = float(sum(plan.values())) if plan else 0.0
    cop_elec = params.cop

    # Blocks narrower than the pixel are illuminated pixel-wide, so the laser is billed for the
    # whole pixel while only the block's share does useful work. ``detail`` carries that
    # multiplier from clipping_plan; without it we would silently price a diluted spot as if it
    # were perfectly focused -- which is exactly the bug the spot_policy work fixed.
    if detail:
        q_billed = float(sum(q * float(detail.get(b, {}).get('cost_multiplier', 1.0))
                             for b, q in plan.items()))
    else:
        q_billed = q_total
    gross = (q_billed / cop_elec) if cop_elec > 0 else 0.0

    if params.recover:
        # `[!]` params.breakeven_ratio is the phi -> 1 (infinite-T_h) limit. Passing T_h_K uses
        # the second-law form, eq. (1.15). The default is unchanged so that every result recorded
        # before 30 August 2026 still reproduces exactly -- but it is flagged in the output.
        ratio = (params.breakeven_ratio if T_h_K is None
                 else params.breakeven_ratio_at(T_h_K, T_0_K))
        recovered = ratio * gross
        optical_in = params.laser_wallplug * gross
        # Heat carried out is what was actually removed from the die, not what was billed.
        optical_out = optical_in + q_total
    else:
        ratio = 0.0
        recovered = optical_in = optical_out = 0.0
    net = gross - recovered

    # First law: what leaves as recovered electricity cannot exceed pump-in plus heat-in.
    first_law_ok = recovered <= gross + q_total + 1e-9
    if not first_law_ok:
        LOGGER.error(
            'MR accounting violates energy conservation: recovered %.4f W > laser %.4f W + '
            'heat %.4f W. Check eta_LPC/collection/eta_laser/eta_ASF.', recovered, gross, q_total)

    out = {'heat_removed_W': q_total, 'heat_billed_W': q_billed,
           'spot_dilution_overhead': (q_billed / q_total) if q_total > 0 else 1.0,
           'cop': cop_elec, 'eta_asf': params.eta_asf,
           'n_blocks_cooled': len(plan),
           'electrical_gross_W': gross, 'optical_in_W': optical_in,
           'optical_to_lpc_W': optical_out, 'recovered_W': recovered,
           'electrical_power_W': net,
           'breakeven_ratio': ratio,
           'net_generating': bool(q_total > 0 and net < 0),
           'self_sustaining': bool(ratio >= 1.0),
           'recovery_fraction': (recovered / gross) if gross > 0 else 0.0,
           'effective_cop': (q_total / net) if net > 0 else float('inf'),
           'first_law_ok': bool(first_law_ok),
           # Whether the recovery term respects the second law, or is the phi -> 1 upper bound.
           'second_law_bounded': bool(T_h_K is not None),
           'T_h_K': (float(T_h_K) if T_h_K is not None else None),
           'phi': (1.0 - float(T_0_K) / float(T_h_K)) if T_h_K is not None else None,
           'breakeven_ratio_first_law_limit': params.breakeven_ratio if params.recover else 0.0}
    if compute_power_W is not None:
        out['compute_power_W'] = float(compute_power_W)
        out['total_power_W'] = float(compute_power_W) + net
        out['mr_overhead_frac'] = net / float(compute_power_W) if compute_power_W else float('nan')
    return out


def estimate_sensitivity(temps_before_K, temps_after_K, plan, floor=1e-6):
    """Secant estimate of dT/dq [K/W] per block from one applied cooling step.

    Positive means the block got cooler when heat was removed, which is the physical sign.
    A non-positive result (block warmed despite cooling, e.g. because leakage feedback moved
    more than the removal did) is dropped rather than fed back as a negative gain, which would
    make the controller push heat the wrong way.
    """
    out = {}
    for blk, q in plan.items():
        if q <= floor:
            continue
        t0 = float(np.ravel(temps_before_K.get(blk, np.nan))[-1])
        t1 = float(np.ravel(temps_after_K.get(blk, np.nan))[-1])
        if not (np.isfinite(t0) and np.isfinite(t1)):
            continue
        s = (t0 - t1) / q
        if s > 0:
            out[blk] = s
    return out


def envelope_plan(block_geom, params, sensitivity_K_per_W, blocks=None, t_floor_K=200.0,
                  die_power_W=None, h_max_by_block=None, q_cap_by_block=None):
    """The most cooling the device can apply to each block, ignoring how much is needed.

    Obtained by asking ``clipping_plan`` about an unboundedly hot die, so ``q_need`` never binds
    and every block is capped by ``h_max * area`` or ``dt_max / sensitivity`` -- which also
    means the spot pitch and policy are applied by exactly the same code path as a normal plan.

    This is the anchor for the rescue regime: it is the most-cooled state the device can reach,
    so if the coupled system has no steady state even here, MR cannot rescue that operating
    point at all. That is a statement about the device, where the old path gave one about the
    solver.
    """
    names = list(blocks if blocks is not None else block_geom)
    hot = {b: params.target_K + 1.0e6 for b in names}
    return clipping_plan(hot, block_geom, params, sensitivity_K_per_W, t_floor_K=t_floor_K,
                         die_power_W=die_power_W, h_max_by_block=h_max_by_block,
                         q_cap_by_block=q_cap_by_block)


def extractor_caps(params, tile_temps_K, tiles, tile_blocks, block_geom=None,
                   base_tile_temps_K=None, last_plan_W=None):
    """Per-block cooling-flux caps from the extractor model (§P0.19), SELF-CONSISTENT with the
    tile's response to the cooling.

    The extractor's flux depends on its own temperature, and its temperature depends on how
    much it is asked to remove. Evaluating the curve at the last solve's tile temperature and
    planning from that oscillates whenever the tile cools by more than a degree per watt (it
    over-pulls, freezes the tile out, plans zero, warms up, over-pulls again). So each block's
    cap is the root of

        phi = h( T_tile_now + s_t (phi_last - phi) ),     s_t = (T_tile_base - T_tile_now) / phi_last

    -- the flux at which the extractor's curve meets the tile temperature that flux itself
    produces, using the tile's measured response ``s_t`` [K per W/mm^2] from the baseline
    (zero-plan) solve to the current one. Before any plan has been applied there is no
    measured response and the cap is the curve at the current (baseline) tile temperature.

    Returns ``{block: h_W_per_mm2}`` or ``None`` when there is no extractor, no array, or no tile
    temperatures yet. A block whose tile cannot cool even at its baseline temperature gets 0.
    """
    if params.extractor is None or not tile_temps_K or not tiles or not tile_blocks:
        return None
    from HotGauge.thermal.mr_array import block_tile_temps
    bt_now = block_tile_temps(tile_temps_K, tile_blocks, tiles)
    bt_base = (block_tile_temps(base_tile_temps_K, tile_blocks, tiles)
               if base_tile_temps_K else {})
    last_plan_W = last_plan_W or {}
    h = params.extractor.cooling_density_W_per_mm2
    out = {}
    for blk, T_now in bt_now.items():
        T_now = float(T_now)
        area = float((block_geom or {}).get(blk, {}).get('area_mm2', 0.0) or 0.0)
        q_last = float(last_plan_W.get(blk, 0.0))
        T_base = float(bt_base.get(blk, T_now))
        if q_last <= 0.0 or area <= 0.0 or T_base <= T_now + 1e-9:
            out[blk] = max(float(h(T_now)), 0.0) if T_now >= T_base - 1e-9 else max(float(h(T_base)), 0.0)
            continue
        phi_last = q_last / area
        s_t = (T_base - T_now) / phi_last                       # K per (W/mm^2), > 0
        h_base = float(h(T_base))
        if h_base <= 0.0:
            out[blk] = 0.0
            continue
        # f(phi) = phi - h(T_now + s_t (phi_last - phi)) is increasing in phi (h falls as the
        # tile cools); bracket [0, phi_hi] with f(0) < 0 and bisect.
        def f(phi):
            return phi - float(h(T_now + s_t * (phi_last - phi)))
        lo, hi = 0.0, max(h_base, phi_last, 1e-9)
        if f(lo) >= 0.0:
            out[blk] = 0.0
            continue
        for _ in range(40):
            if f(hi) > 0.0:
                break
            hi *= 2.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0.0:
                hi = mid
            else:
                lo = mid
        out[blk] = 0.5 * (lo + hi)
    return out


def extractor_tile_caps(params, tile_temps_K, tiles, base_tile_temps_K=None,
                        last_tile_plan_W=None):
    """Per-TILE removal caps [W] from the extractor curve, self-consistent with each tile's own
    measured response (§P0.19). The tile is where the extractor is, so this is the physical
    site of the cap; the block-level plan keeps its recorded shape and is scaled back at
    delivery where a tile cannot follow (:func:`~HotGauge.thermal.mr_array.deliver_capped`).

    Same fixed point as :func:`extractor_caps`, per tile: ``phi = h(T_now + s_t (phi_last - phi))``
    with ``s_t = (T_base - T_now) / phi_last``. A tile whose baseline temperature is already
    outside the curve's cooling range gets 0.
    """
    if params.extractor is None or not tile_temps_K or not tiles:
        return None
    zoned = bool(getattr(params.extractor, 'zoned', False))
    last_tile_plan_W = last_tile_plan_W or {}
    base = base_tile_temps_K or {}
    out = {}
    for t in tiles:
        name = t['name']
        if name not in tile_temps_K:
            continue
        # §P0.21: a dual-zone array hands each tile its own zone's curve.
        h = ((lambda T, _n=name: params.extractor.cooling_density_W_per_mm2(T, tile=_n))
             if zoned else params.extractor.cooling_density_W_per_mm2)
        T_now = float(tile_temps_K[name])
        area = t['w'] * t['h'] / 1.0e6
        if area <= 0.0 or not (T_now > 50.0):
            out[name] = 0.0
            continue
        T_base = float(base.get(name, T_now))
        q_last = float(last_tile_plan_W.get(name, 0.0))
        if q_last <= 0.0 or T_base <= T_now + 1e-9:
            T_eval = T_now if T_now >= T_base - 1e-9 else T_base
            out[name] = max(float(h(T_eval)), 0.0) * area
            continue
        phi_last = q_last / area
        s_t = (T_base - T_now) / phi_last
        h_base = float(h(T_base))
        if h_base <= 0.0:
            out[name] = 0.0
            continue

        def f(phi):
            return phi - float(h(T_now + s_t * (phi_last - phi)))
        lo, hi = 0.0, max(h_base, phi_last, 1e-9)
        if f(lo) >= 0.0:
            out[name] = 0.0
            continue
        for _ in range(40):
            if f(hi) > 0.0:
                break
            hi *= 2.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0.0:
                hi = mid
            else:
                lo = mid
        out[name] = 0.5 * (lo + hi) * area
    return out


def _energy_capped(plan, cap_W):
    """Scale a plan down so its total does not exceed ``cap_W`` (None = no cap)."""
    if not plan or cap_W is None:
        return plan
    tot = float(sum(plan.values()))
    if tot <= float(cap_W) or tot <= 0.0:
        return plan
    f = float(cap_W) / tot
    return {b: q * f for b, q in plan.items() if q * f > 0.0}


def _delivered(apply_plan, plan):
    """The plan as applied after any tile cap; ``plan`` itself for appliers without caps."""
    fn = getattr(apply_plan, 'delivered', None)
    return fn(plan) if callable(fn) else plan


def _cap_plan(plan, caps_plan):
    """Clip a plan block-wise to another plan's values (the current envelope)."""
    if not caps_plan:
        return plan
    return {b: q for b, q in ((b, min(q, caps_plan.get(b, 0.0))) for b, q in plan.items())
            if q > 0.0}


def _relax_plan_toward_target(plan, envelope, temps, params, sens, relax, t_floor_K):
    """One Newton step on the plan, from the cooled state: cool more where hot, less where cold.

    Symmetric by construction -- a block below target has its cooling *reduced* -- so an initial
    over-cool is corrected rather than locked in, which is the property the baseline-anchored
    scheme was written to get and only got when the baseline existed.
    """
    new = {}
    for blk, q_env in envelope.items():
        t = temps.get(blk)
        if t is None:
            continue
        t = float(np.ravel(t)[-1])
        if t <= t_floor_K:
            continue
        s = float(sens.get(blk, 0.0))
        if s <= 0:
            new[blk] = plan.get(blk, 0.0)
            continue
        step = (t - params.target_for(blk)) / s   # >0 wants more cooling, <0 wants less (own target)
        q = plan.get(blk, 0.0) + relax * step
        new[blk] = min(max(q, 0.0), q_env)
    return {b: q for b, q in new.items() if q > 0.0}


class CoolingApplication(object):
    """How a plan expressed over processor blocks reaches the solver.

    Two placements exist and they are not interchangeable.

    ``in_source_layer`` (legacy) subtracts the plan from the processor trace, so the removal
    lands in the die's own source layer -- the same 20 um of silicon the transistors are in.
    Cooling and heating are then co-located with zero transport distance, the burial depth is
    inert by construction, and every number so computed is an upper bound. **This is not the
    device**; it is retained only so results predating the fix stay reproducible.

    ``array_above`` projects the plan onto the tiles of the photonic array, a second powered die
    directly above the silicon, and hands those tile powers to the solver. The extracted watt
    then has to cross ``source_depth_um`` of silicon to be taken away, which is what the part
    actually does.

    Callers get a ``placement`` string to stamp into their output. Two generations of results
    now exist and ``mr: true/false`` no longer identifies which one a row came from.
    """

    def __init__(self, trace, name_map, tiles=None, blocks=None, set_mr_powers=None):
        self.trace = trace
        self.name_map = name_map
        self.tiles = tiles
        self.blocks = blocks
        self._set_mr_powers = set_mr_powers
        if tiles is None:
            if blocks is not None or set_mr_powers is not None:
                raise ValueError('blocks/set_mr_powers are meaningless without tiles')
            self.placement = 'in_source_layer'
        else:
            if blocks is None or set_mr_powers is None:
                raise ValueError('the array placement needs tiles, blocks and set_mr_powers '
                                 'together: without the callback the plan would be computed '
                                 'and then silently never applied')
            self.placement = 'array_above'
        self.last_tile_plan = None
        # §P0.19: optional per-tile cap [W], evaluated at delivery. When set, a tile asked for
        # more than its extractor can remove delivers the cap and the blocks' requests are
        # scaled back in proportion (last_delivered_plan), so the planner reasons about what
        # was applied.
        self.tile_caps_fn = None
        self.last_delivered_plan = None
        self.last_shortfall_W = 0.0
        self.last_n_capped = 0

    def __call__(self, plan):
        """Apply ``plan`` and return the trace to solve.

        For the array the processor trace is returned unchanged -- the cooling is not in it. The
        tile powers are pushed into the solver as a side effect, which is what makes them a
        property of the *other* die rather than of the workload.
        """
        if self.tiles is None:
            return apply_cooling_to_trace(self.trace, plan, self.name_map)
        from HotGauge.thermal.mr_array import (project_plan_to_tiles, tile_powers_for_stack,
                                               deliver_capped)
        caps = self.tile_caps_fn() if self.tile_caps_fn is not None else None
        if caps:
            tile_plan, delivered, short, n_capped = deliver_capped(plan, self.blocks, self.tiles,
                                                                   caps)
            self.last_delivered_plan = delivered
            self.last_shortfall_W = short
            self.last_n_capped = n_capped
        else:
            tile_plan = project_plan_to_tiles(plan, self.blocks, self.tiles)
            self.last_delivered_plan = None
            self.last_shortfall_W = 0.0
            self.last_n_capped = 0
            requested, projected = sum(plan.values()), sum(tile_plan.values())
            if abs(requested - projected) > 1e-6 * max(1.0, abs(requested)):
                raise ValueError('projection lost power: {:.6f} W planned, {:.6f} W landed on '
                                 'tiles'.format(requested, projected))
        self.last_tile_plan = tile_plan
        self._set_mr_powers(tile_powers_for_stack(tile_plan, self.tiles))
        return self.trace

    def preview_shortfall(self, plan):
        """What the tile caps would take off ``plan`` -- WITHOUT applying it.

        `[!]` Applying a plan advances the wiring's plan generation, and the wiring refuses the
        next plan unless a solver read this one (`ArrayWiring._assert_last_plan_was_solved`).
        The §P0.20 first-plan re-cap applied the plan to learn the shortfall and only solved
        when it was non-zero, so every UNCAPPED run (the target device on this die) died on
        the next application. Found by the §P0.21 regression point; ask here first.
        """
        if self.tiles is None or self.tile_caps_fn is None:
            return 0.0
        caps = self.tile_caps_fn()
        if not caps:
            return 0.0
        from HotGauge.thermal.mr_array import deliver_capped
        return float(deliver_capped(plan, self.blocks, self.tiles, caps)[2])

    def delivered(self, plan):
        """The plan as applied after the tile caps -- ``plan`` itself when no cap bound."""
        return self.last_delivered_plan if self.last_delivered_plan is not None else plan


def run_mr_clipping(trace, thermal_solve_fn, block_geom, params, name_map,
                    initial_sensitivity=None, max_iter=6, tol_K=1.0, relax=0.7,
                    t_floor_K=200.0, status_fn=None, plan_mode='auto',
                    tiles=None, tile_blocks=None, set_mr_powers=None, die_power_W=None,
                    calibrate=True, calibration_fraction=0.02,
                    recovery_at_junction=False, T_0_K=295.0,
                    tile_temps_fn=None, die_power_fn=None):
    """Plan MR cooling against the solver. See :func:`_run_mr_clipping_dispatch` for the loop.

    §P0.19: ``tile_temps_fn`` returns the array die's solved tile temperatures (``{tile: K}``)
    from the most recent solve; with ``params.extractor`` set it turns the per-block flux cap
    into the extractor's own cooling curve at the tile above the block. ``die_power_fn``
    returns the CONVERGED die power after the most recent solve, so the energy-conservation
    cap tracks the die the cooling actually produced rather than the injected trace (the
    12 W over-pull of §P0.18.2). Both optional; both default to the recorded behaviour.

    This wrapper exists to do one thing the loop must not be trusted to remember at each of its
    thirteen exits: **stamp where the cooling was applied**. Two generations of results now
    exist -- ``in_source_layer`` (legacy, an upper bound) and ``array_above`` (the device) --
    and ``mr: true/false`` no longer tells them apart. An unstamped row is unusable, so the
    stamp is applied here where there is exactly one exit rather than thirteen.

    Pass ``tiles``, ``tile_blocks`` and ``set_mr_powers`` together for the array; omit all three
    for the legacy placement. See :class:`CoolingApplication`.
    """
    apply_plan = CoolingApplication(trace, name_map, tiles=tiles, blocks=tile_blocks,
                                    set_mr_powers=set_mr_powers)
    # §P0.19: snapshot the array die's tile temperatures per solve, keyed by the identity of the
    # temperature field the solve returned, so the stamp below describes the REPORTED field and
    # not the last probe executed (which the bisections deliberately leave on a failing trial).
    snapshots = {}
    base_tiles = {'temps': None}
    latest = {'temps': None, 'tile_plan': None}
    if tile_temps_fn is not None and params.extractor is not None and tiles:
        _inner_solve = thermal_solve_fn

        def thermal_solve_fn(tr):                     # noqa: F811 - deliberate wrap
            t = _inner_solve(tr)
            try:
                snap = tile_temps_fn()
            except Exception:                         # noqa: BLE001
                snap = None
            snapshots[id(t)] = dict(snap) if snap else None
            try:
                diverged = bool((status_fn() or {}).get('diverged')) if status_fn else False
            except Exception:                         # noqa: BLE001
                diverged = False
            # The field this solve produced, and the tile plan it was solved under: the pair the
            # next cap is made self-consistent against. `[!]` A DIVERGED field is a runaway, not
            # a state the array is ever in: its tile temperatures (hundreds of kelvin high) sit
            # past every curve's hot-side limit and would cap the hottest tiles to zero -- which
            # is how the first GaAs pass read "envelope insufficient" at every rung. So caps are
            # made from CONVERGED fields only -- and the last converged field PERSISTS across a
            # diverged solve. Clearing it let a solve that diverged *because* the cap starved
            # the tiles reset the cap, so the next application went out uncapped, held, and the
            # bisection reported that uncapped hold (the v98 first pass: a 0.04 W-per-tile film
            # "holding" 2.00 W/mm^2). Only the very first application, before any converged
            # field exists, is uncapped.
            if snap and not diverged:
                latest['temps'] = dict(snap)
                latest['tile_plan'] = dict(apply_plan.last_tile_plan or {})
            if base_tiles['temps'] is None and snap and not diverged and \
                    not any(q > 0 for q in (apply_plan.last_tile_plan or {}).values()):
                base_tiles['temps'] = dict(snap)
            return t

        def _tile_caps():
            if not latest['temps']:
                return None
            return extractor_tile_caps(params, latest['temps'], tiles, base_tiles['temps'],
                                       latest['tile_plan'])
        apply_plan.tile_caps_fn = _tile_caps
    block_power_W = None
    if getattr(params, 'envelope_shape', 'seed') == 'power':
        # Every geometry block starts at zero: a block the trace gives no power has nothing to
        # remove, and leaving it out would hand it the 45 W seed instead (found by the test).
        block_power_W = {b: 0.0 for b in block_geom if not is_synthetic_temp_key(b)}
        for unit, series in trace.powers.items():
            blk = name_map(unit)
            if blk is None or blk not in block_geom or is_synthetic_temp_key(blk):
                continue
            block_power_W[blk] = block_power_W.get(blk, 0.0) + float(np.ravel(series)[-1])
    result = _run_mr_clipping_dispatch(
        trace, thermal_solve_fn, block_geom, params, name_map,
        initial_sensitivity=initial_sensitivity, max_iter=max_iter, tol_K=tol_K, relax=relax,
        t_floor_K=t_floor_K, status_fn=status_fn, plan_mode=plan_mode, apply_plan=apply_plan,
        die_power_W=die_power_W, calibrate=calibrate,
        calibration_fraction=calibration_fraction,
        tile_temps_fn=tile_temps_fn, die_power_fn=die_power_fn,
        tile_geom=(tiles, tile_blocks), block_power_W=block_power_W)
    result['envelope_shape'] = getattr(params, 'envelope_shape', 'seed')
    result['placement'] = apply_plan.placement
    result['tile_plan'] = apply_plan.last_tile_plan
    # §P0.22 (D3): which objective the plan was built against, and where each zone landed. The
    # plain 'peak' objective stamps the label only, so the recorded rows gain one key and lose
    # nothing.
    result['objective'] = params.objective
    if params.has_zones and result.get('temp_trace'):
        result['zones'] = zone_report(result['temp_trace'], params, t_floor_K)
    if params.extractor is not None:
        # What the extractor model did, stamped once at the single exit, from the REPORTED
        # solve's tile snapshot: the coldest engaged tile, the curve's flux there, T_min, and how
        # many tiles were capped at delivery (with the shortfall).
        tt = snapshots.get(id(result.get('temp_trace'))) or {}
        tp = result.get('tile_plan') or {}
        engaged = {t for t, q in tp.items() if q > 0}
        cold = (min((float(v) for t, v in tt.items() if t in engaged), default=None) if engaged
                else (min((float(v) for v in tt.values()), default=None) if tt else None))
        physical = cold is not None and cold > 50.0
        result['extractor'] = {
            'label': getattr(params.extractor, 'label', None),
            'platform': getattr(params.extractor, 'platform', None),
            'T_min_K': params.extractor.t_min_K(),
            'h_300K_W_per_mm2': float(params.extractor.cooling_density_W_per_mm2(300.0)),
            'min_engaged_tile_K': cold,
            'h_at_min_tile_W_per_mm2': (float(params.extractor.cooling_density_W_per_mm2(cold))
                                        if physical else None),
            'eta_asf_at_min_tile': (float(params.extractor.eta_asf(cold)) if physical else None),
            'n_tiles_capped': int(apply_plan.last_n_capped),
            'shortfall_W': float(apply_plan.last_shortfall_W),
            'reported_field_has_tiles': bool(tt),
            'dt_max_scalar_K': (None if params.dt_max_K == float('inf') else params.dt_max_K)}
    if recovery_at_junction:
        # `[!]` The LPC recovery term is Carnot-limited by the temperature the heat is lifted
        # FROM, and that temperature is an OUTPUT of the solve rather than an input to the
        # planner -- so it is applied here, once, rather than at each of the dispatch's return
        # sites. Without it the accounting uses MRParams.breakeven_ratio, which is the phi -> 1
        # (infinite-T_h) limit and can report a net-generating loop the second law forbids.
        # See docs/evidence/loop_model_reconciliation.json.
        # Computed inline rather than importing leakage_feedback.peak_temp_K: this module is
        # imported BY that one, and the cycle is not worth a four-line helper.
        _vals = []
        for _v in (result.get('temp_trace') or {}).values():
            _a = np.ravel(_v)
            if _a.size:
                _m = float(np.max(_a))
                if _m > t_floor_K:
                    _vals.append(_m)
        T_h = max(_vals) if _vals else float('nan')
        if np.isfinite(T_h) and T_h > 0.0 and result.get('plan'):
            result['accounting'] = mr_accounting(result['plan'], params,
                                                 detail=result.get('detail'),
                                                 T_h_K=float(T_h), T_0_K=T_0_K)
    # NOTE: this deliberately does NOT re-apply the reported plan on the way out.
    #
    # An earlier version of this fix did, reasoning that the array should be left in the state the
    # accounting describes. ArrayWiring's own guard refused it, and the guard was right: applying
    # a plan that no solver will ever read is a no-op that only sets up the *next* caller to be
    # confused ("plan generation 2, last read 1"). The invariant is enforced at ENTRY instead --
    # every planning call zeroes the array before solving its baseline -- which is both sufficient
    # and honest: the last plan applied is always the one that was solved to produce the
    # temp_trace being returned.
    return result


def _run_mr_clipping_dispatch(trace, thermal_solve_fn, block_geom, params, name_map,
                              die_power_W=None, calibrate=True, calibration_fraction=0.02,
                              initial_sensitivity=None, max_iter=6, tol_K=1.0, relax=0.7,
                              t_floor_K=200.0, status_fn=None, plan_mode='auto',
                              apply_plan=None, tile_temps_fn=None, die_power_fn=None,
                              tile_geom=(None, None), block_power_W=None):
    """Iterate MR cooling against the thermal solver until hot blocks reach the target.

    Structurally the same fixed point as the leakage loop: the plan changes the temperatures,
    which change the plan. Sensitivities start from ``initial_sensitivity`` (or a small
    positive seed) and are refined by secant update each iteration, so the controller learns
    the real dT/dq including lateral spreading instead of assuming it.

    Two ways to size the plan
    -------------------------
    ``plan_mode='baseline'`` (the original) sizes every plan from the UNCOOLED solve. Correct
    and cheap when the bare die has a steady state.

    **It is invalid in the rescue regime, which is the regime MR exists for.** There the
    uncooled solve diverges, so the field it plans from is whichever one the iteration happened
    to be passing through when a runaway guard fired. Measured on the 34-core die at 88 CFM:
    the baseline peak used to size the plan was 138.7 C at 1.12 W/mm^2 and 142.8 C at 1.15,
    giving plans of 0.561 W and 1.979 W -- a 3.5x difference between two points 3% apart in
    density. The small plan failed to arrest the runaway and the large one succeeded, so
    "does MR rescue this die" was decided by where a divergent sequence stopped. The rescue was
    correspondingly non-monotone: 1.10 yes, 1.12 no, 1.15 yes, 1.16 no.

    ``plan_mode='envelope'`` starts from the other side instead. It applies the full device
    envelope and relaxes the cooling *down* toward the target, so it never reads a divergent
    field:

      * if the fully-cooled system still has no steady state, MR cannot rescue this point --
        reported as ``reason='envelope insufficient'``;
      * otherwise the loop reduces cooling where blocks sit below target and adds it back where
        they sit above, converging on the *minimum* plan that holds the target.

    ``plan_mode='auto'`` (default) picks 'baseline' when the uncooled solve converged and
    'envelope' when it did not. That keeps previously-validated convergent-regime results
    unchanged while making the rescue regime mean something.

    ``status_fn`` is an optional zero-argument callable returning the status of the most recent
    solve (``{'diverged': ..., 'unconverged': ...}``) -- ``run_leakage_feedback`` callers can
    supply it directly. Without it 'auto' cannot tell the two cases apart and falls back to
    'baseline', so a caller that needs the rescue regime handled correctly must pass it.

    Returns a dict with the final plan, temperature trace, accounting, per-iteration history
    and a ``converged`` flag. Not converging is a real answer -- it means the envelope cannot
    clip this workload -- so it is reported, not raised.
    """
    if plan_mode not in ('auto', 'baseline', 'envelope'):
        raise ValueError("plan_mode must be 'auto', 'baseline' or 'envelope', got {!r}"
                         .format(plan_mode))
    apply_plan = apply_plan or CoolingApplication(trace, name_map)
    sens = dict(initial_sensitivity or {})
    tiles, tile_blocks = tile_geom

    base_tiles = {'temps': None}

    def _caps(last_plan=None):
        # §P0.19: the extractor cap is applied per TILE at delivery (CoolingApplication /
        # extractor_tile_caps), so the block-level plan keeps its recorded shape. The block-level
        # cap (extractor_caps) exists for callers that want it and is not used in this loop.
        return None

    def _die_power():
        if die_power_fn is None:
            return die_power_W
        try:
            v = die_power_fn()
            return float(v) if v else die_power_W
        except Exception:                  # noqa: BLE001
            return die_power_W

    def _status():
        try:
            return dict(status_fn() or {}) if status_fn is not None else {}
        except Exception:                      # noqa: BLE001 - a broken probe must not decide physics
            LOGGER.warning('status_fn raised; treating the solve status as unknown')
            return {}

    # The plan is always recomputed against the UNCOOLED baseline using the latest measured
    # sensitivity. Planning against the already-cooled temperatures instead would let a first
    # overshoot stand forever: the loop would see nothing above target, declare success, and
    # report a laser budget several times larger than needed. Overspending must be corrected,
    # not just under-spending.
    # START FROM ZERO COOLING. The exit hook below leaves the array matching the plan this call
    # REPORTS, which is right for the caller -- but it means the next call inherits that plan, and
    # a baseline solved with the previous call's cooling still applied is not a baseline.
    #
    # In clock_headroom the wiring is built once per ARM and reused across every step of the clock
    # bisection, so this is exactly the path taken. Symptom, measured 27 Aug 2026 at r_th 0.3
    # AFTER the exit hook was added: array_on reported 4.7188 GHz at 71.0 C on 167.6 W with
    # 0.000 W removed, while array_idle -- same stack, lower clock, 61.7 W -- sat at 85.0 C. A
    # baseline cannot be cooler than the same die at lower power unless something is cooling it.
    #
    # Zeroing at entry and re-applying at exit are the two halves of one invariant: the array's
    # state is always the plan the accounting describes, and every planning call measures from
    # the unpowered array.
    apply_plan({})
    base_temps = thermal_solve_fn(trace)
    base_status = _status()
    if tile_temps_fn is not None and params.extractor is not None:
        try:
            base_tiles['temps'] = dict(tile_temps_fn() or {})
        except Exception:                  # noqa: BLE001
            base_tiles['temps'] = None
    # Status of the solve that produced the field we would REPORT, as distinct from "any solve
    # in this loop". The searches deliberately visit unstable states to bracket an answer, so
    # conflating the two flags a good result because an exploratory probe behaved as intended.
    result_status = dict(base_status)
    history = []

    mode = plan_mode
    if mode == 'auto':
        mode = 'envelope' if base_status.get('diverged') else 'baseline'
    if mode == 'envelope':
        return _run_mr_clipping_envelope(
            trace, thermal_solve_fn, block_geom, params, name_map, sens,
            max_iter=max_iter, tol_K=tol_K, relax=relax, t_floor_K=t_floor_K,
            status_fn=_status, base_temps=base_temps, base_status=base_status,
            apply_plan=apply_plan, die_power_W=die_power_W, caps_fn=_caps,
            die_power_fn=(_die_power if die_power_fn is not None else None),
            block_power_W=block_power_W)

    # `[!]` The synthetic-key filter is needed HERE as well as in `clipping_plan` (§P0.17).
    # `base_hot` feeds the sensitivity-calibration PROBE below, which builds its own plan and hands
    # it straight to `apply_plan` -> `project_plan_to_tiles` without passing through
    # `clipping_plan` at all. Filtering only the planner left the probe raising the identical
    # KeyError from a different stack, which is how a "fixed" re-run failed 10 of 11 points.
    base_hot = {b: float(np.ravel(t)[-1]) for b, t in base_temps.items()
                if not is_synthetic_temp_key(b)
                and float(np.ravel(t)[-1]) > max(t_floor_K, params.target_for(b))}

    # MEASURE the sensitivity before sizing anything from it.
    #
    # The descent used to start from `sens.setdefault(b, 1.0)` -- an assumed 1.0 K/W -- and size
    # its first plan from that guess. Under the legacy envelope the device caps hid the problem:
    # h_max bound 396 of 400 blocks on a near-cliff field, so the first plan was restrained by
    # the device rather than by the guess. With the envelope corrected to its demonstrated values
    # that restraint is gone and `q_need = excess / s` binds instead, so the guess sets the plan
    # directly. The conservation cap above stops it running to kilowatts; this stops it being a
    # guess at all.
    #
    # The probe is a small, PROPORTIONAL removal over the hot blocks -- proportional because the
    # secant estimate is per block and a uniform probe would over-drive the small ones. Its size
    # is a fraction of die power, which is the only scale available that is a property of the
    # workload rather than of the device. One extra solve per planning call.
    if base_hot and calibrate and die_power_W and thermal_solve_fn is not None:
        excess = {b: base_hot[b] - params.target_for(b) for b in base_hot}
        tot_excess = sum(excess.values())
        if tot_excess > 0:
            probe_W = calibration_fraction * float(die_power_W)
            probe = {b: probe_W * excess[b] / tot_excess for b in base_hot}
            probe_temps = thermal_solve_fn(apply_plan(probe))
            probe_status = _status()
            measured = estimate_sensitivity(base_temps, probe_temps, probe)
            if measured and not probe_status.get('diverged'):
                sens.update(measured)
                LOGGER.info('sensitivity calibrated on %d of %d hot blocks with a %.3f W probe '
                            '(%.1f%% of die power); median %.4g K/W',
                            len(measured), len(base_hot), probe_W,
                            100.0 * calibration_fraction,
                            float(np.median(list(measured.values()))))
            else:
                # A probe that diverges says the operating point is already unstable, which is
                # information -- but it is not a sensitivity, so nothing is learned and the
                # fallback below applies. Saying so beats silently reverting to the guess.
                LOGGER.warning('sensitivity calibration probe failed (%s); falling back to the '
                               'assumed 1.0 K/W for %d blocks, so this plan is sized from a '
                               'guess and the conservation cap is the only thing bounding it',
                               'diverged' if probe_status.get('diverged') else 'no positive dT/dq',
                               len(base_hot))

    if not base_hot:
        return {'plan': {}, 'detail': {}, 'temp_trace': base_temps, 'sensitivity': sens,
                'result_unconverged': bool(result_status.get('unconverged')),
                'converged': True, 'iterations': 0, 'history': history,
                'accounting': mr_accounting({}, params),
                'reason': 'nothing above target; no cooling needed'}

    # Whatever the calibration probe could not measure falls back to the assumed 1.0 K/W. That
    # fallback is now BOUNDED rather than load-bearing: the conservation cap in clipping_plan
    # stops a guessed sensitivity producing an impossible plan.
    for b in base_hot:
        sens.setdefault(b, 1.0)

    plan, detail, temps = {}, {}, base_temps
    for it in range(max_iter):
        new_plan, detail = clipping_plan(base_hot, block_geom, params, sens,
                                         t_floor_K=t_floor_K, die_power_W=_die_power(),
                                         h_max_by_block=_caps(plan))
        if not new_plan:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'converged': False, 'iterations': it, 'history': history,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'reason': 'envelope allows no further cooling'}

        blended = ({b: relax * new_plan[b] + (1 - relax) * plan.get(b, 0.0) for b in new_plan}
                   if plan else dict(new_plan))
        cooled_trace = apply_plan(blended)
        blended = _delivered(apply_plan, blended)         # what the tiles could actually remove
        temps = thermal_solve_fn(cooled_trace)
        result_status = _status()

        # Refine dT/dq against the baseline, which is what the plan is sized from.
        sens.update(estimate_sensitivity(base_temps, temps, blended))

        peak = objective_peak(temps, params, t_floor_K)
        delta_plan = max((abs(blended[b] - plan.get(b, 0.0)) for b in blended), default=0.0)
        total = float(sum(blended.values()))
        history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': total,
                        'max_plan_change_W': delta_plan})
        plan = blended

        # Converged when the plan has stopped moving AND the peak is at target (within tol).
        # Requiring both is what distinguishes "clipped efficiently" from "overcooled".
        if delta_plan <= max(1e-3, 0.01 * total) and abs(peak - params.target_K) <= tol_K:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'converged': True, 'iterations': it + 1, 'history': history,
                    'temp_trace_diverged': False, 'plan_is_minimum': False,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'reason': 'descent converged on the target; this plan holds the target but '
                              'the stability boundary was never probed, so it is not known to '
                              'be the smallest plan that keeps a steady state'}

    # The baseline path used to return NO verdict here, while the envelope path's equivalent
    # return sets one. A missing plan_holds_target reads downstream as "unknown" and printed as
    # None, which is indistinguishable from a key that was never populated -- so a partial descent
    # looked the same as a converged one that forgot to say so. It gets an explicit verdict now,
    # and on a truncated descent that verdict is almost always False.
    peak_now = objective_peak(temps, params, t_floor_K)
    holds = bool(peak_now == peak_now and peak_now <= params.target_K + tol_K)

    # Distinguish "ran out of iterations" from "ran out of DEVICE", because they are opposite
    # engineering conclusions and they arrive at the same exit. The stage can lift a block by at
    # most dt_max_K, so if the achieved peak has come down by dt_max and is still above target,
    # more iterations cannot help and neither can a better COP -- the device's lift is the binding
    # constraint. Every truncated accelerator run at 700 W turned out to be this: exactly 10.00 K
    # of lift against a 12.6-37 K requirement, reported as an iteration budget problem.
    base_peak = None
    if base_temps:
        _bp = objective_peak(base_temps, params, t_floor_K)
        base_peak = _bp if _bp == _bp else None
    dt_bound = bool(base_peak is not None and peak_now == peak_now and not holds
                    and peak_now <= base_peak - params.dt_max_K + 0.05)

    if dt_bound:
        reason = ('envelope insufficient: dt_max binds. The stage lifted the peak the full '
                  '{:.1f} K it is capable of ({:.1f} -> {:.1f} C) and the target needs {:.1f} K. '
                  'More iterations cannot help and neither can a better COP -- this is the '
                  'device\'s temperature lift, not its cost.'
                  .format(params.dt_max_K, base_peak - 273.15, peak_now - 273.15,
                          base_peak - params.target_K))
    else:
        reason = ('max_iter reached: the descent was still building the plan, so this cost is a '
                  'LOWER BOUND on what holding the target actually needs (peak {:.1f} C against a '
                  '{:.1f} C target)'.format(peak_now - 273.15, params.target_K - 273.15))

    return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
            'result_unconverged': bool(result_status.get('unconverged')),
            'converged': False, 'iterations': max_iter, 'history': history,
            'plan_is_minimum': False, 'plan_holds_target': holds,
            'dt_max_bound': dt_bound,
            'lift_achieved_K': None if base_peak is None else base_peak - peak_now,
            'lift_needed_K': None if base_peak is None else base_peak - params.target_K,
            'accounting': mr_accounting(plan, params, detail=detail),
            'reason': reason}


def _run_mr_clipping_envelope(trace, thermal_solve_fn, block_geom, params, name_map, sens,
                              max_iter=6, tol_K=1.0, relax=0.7, t_floor_K=200.0,
                              status_fn=None, base_temps=None, base_status=None,
                              bisect_iters=8, apply_plan=None, die_power_W=None,
                              caps_fn=None, die_power_fn=None, block_power_W=None):
    """MR sizing anchored on the device envelope rather than on an uncooled baseline.

    Used when the bare die has no steady state, where the baseline the original scheme plans
    from does not exist. See ``run_mr_clipping`` for why that matters.

    Strategy: start at the most-cooled state the device can produce and walk *down* toward the
    target. The first solve then answers the question that actually matters -- can MR hold this
    die at all? -- and everything after it is a descent from a known-feasible point, so the
    answer never depends on where a divergent sequence stopped.
    """
    status_fn = status_fn or (lambda: {})
    apply_plan = apply_plan or CoolingApplication(trace, name_map)
    history = []
    caps_fn = caps_fn or (lambda: None)
    _die_power_for_envelope = die_power_fn or (lambda: die_power_W)

    def _envelope(last_plan=None):
        # Re-derived against the tiles' current temperatures when an extractor cap is live: the
        # most the device can do, self-consistent with how far the cooling has pulled the tiles.
        return envelope_plan(block_geom, params, sens, t_floor_K=t_floor_K,
                             die_power_W=_die_power_for_envelope(),
                             h_max_by_block=caps_fn(last_plan),
                             q_cap_by_block=block_power_W)

    # Seed sensitivities for every block we might cool. 1.0 K/W is a placeholder that the
    # secant update replaces after the first cooled solve; it only sets the first step.
    for b in block_geom:
        sens.setdefault(b, 1.0)

    envelope, detail = _envelope()
    if not envelope:
        return {'plan': {}, 'detail': detail, 'temp_trace': base_temps, 'sensitivity': sens,
                'result_unconverged': bool(result_status.get('unconverged')),
                'converged': False, 'iterations': 0, 'history': history,
                'plan_is_minimum': False, 'plan_holds_target': False,
                'temp_trace_diverged': bool((base_status or {}).get('diverged')),
                'accounting': mr_accounting({}, params, detail=detail),
                'reason': 'device envelope allows no cooling on any block'}

    plan = dict(envelope)
    prev_peak = None
    result_status, prev_status = {}, {}
    _tr = apply_plan(plan)
    plan = _delivered(apply_plan, plan)
    temps = thermal_solve_fn(_tr)
    st = status_fn()
    # The status of the solve that produced the field we would REPORT. Exploratory probes below
    # deliberately visit unstable states, so "some solve was unverified" is not a statement about
    # the answer; this is.
    result_status = dict(st)
    peak = objective_peak(temps, params, t_floor_K)
    history.append({'iter': 0, 'peak_K': peak, 'heat_removed_W': float(sum(plan.values())),
                    'max_plan_change_W': float('inf'), 'stage': 'full envelope'})

    # ``peak != peak`` is a NaN test: the solve returned no block above the floor, so the field is
    # unusable. That is a FAILED solve, not a cool die -- and it must be caught here, because
    # _relax_plan_toward_target skips every block it cannot read a temperature for and so returns
    # an empty plan, which the descent would then interpret as "no cooling wanted".
    if st.get('diverged') or peak != peak:
        # The strongest statement this model can make about MR at an operating point: even at
        # full device capability the coupled system has no steady state.
        return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                'result_unconverged': bool(result_status.get('unconverged')),
                'converged': False, 'iterations': 1, 'history': history,
                'temp_trace_diverged': True,
                'plan_is_minimum': False, 'plan_holds_target': False,
                'accounting': mr_accounting(plan, params, detail=detail),
                'reason': ('envelope insufficient: no steady state even at full MR capability'
                           if st.get('diverged') else
                           'envelope insufficient: the solve at full MR capability returned no '
                           'usable temperature field')}

    if base_temps is not None:
        sens.update(estimate_sensitivity(base_temps, temps, plan))

    # §P0.19: the first plan was sized against the INJECTED die power (the baseline diverged, so
    # no converged power existed yet). Under a converged-power cap that plan may remove more
    # than the cooled die dissipates; it must be re-capped and re-solved before it can stand as
    # a holding state, or the over-pull leaks through the bisection as the reported answer.
    if die_power_fn is not None and die_power_fn() is not None \
            and float(sum(plan.values())) > float(die_power_fn()) + 1e-9:
        cap_W = float(die_power_fn())
        capped = _energy_capped(plan, cap_W)
        _tr = apply_plan(capped)
        capped = _delivered(apply_plan, capped)
        temps_c = thermal_solve_fn(_tr)
        st_c = status_fn()
        peak_c = objective_peak(temps_c, params, t_floor_K)
        history.append({'iter': 0, 'peak_K': peak_c, 'heat_removed_W': float(sum(capped.values())),
                        'max_plan_change_W': float(sum(plan.values())) - float(sum(capped.values())),
                        'stage': 'conservation cap at the converged die power'})
        if st_c.get('diverged') or not (peak_c == peak_c) or peak_c > params.target_K + tol_K:
            return {'plan': capped, 'detail': detail, 'temp_trace': temps_c, 'sensitivity': sens,
                    'result_unconverged': bool(st_c.get('unconverged')),
                    'converged': not st_c.get('diverged'), 'iterations': 2, 'history': history,
                    'temp_trace_diverged': bool(st_c.get('diverged')),
                    'plan_is_minimum': False, 'plan_holds_target': False,
                    'conservation_bound': True,
                    'accounting': mr_accounting(capped, params, detail=detail),
                    'reason': ('conservation binds: holding the target needs more heat removed '
                               '({:.1f} W) than the cooled die dissipates ({:.1f} W); the array '
                               'would be refrigerating the heat sink. Reported at the cap: peak '
                               '{}'.format(float(sum(plan.values())), cap_W,
                                           'runaway' if st_c.get('diverged') else
                                           '{:.1f} C'.format(peak_c - 273.15)))}
        plan, temps, st, peak = capped, temps_c, st_c, peak_c
        result_status = dict(st)
        # (_remember is defined just below and records this state as the first holding plan.)

    # §P0.20: the first plan went out UNCAPPED (no converged field existed to cap it against).
    # Now one does. If the extractor cannot deliver that plan at the tile temperatures it
    # produced, re-apply it under the cap and re-solve before it can stand as a holding state;
    # otherwise the uncapped hold leaks through the bisection as the answer.
    # `[!]` Preview the shortfall; do not apply the plan unless it will be solved (P0.21 fix).
    _preview = getattr(apply_plan, 'preview_shortfall', None)
    if callable(_preview) and getattr(apply_plan, 'tile_caps_fn', None) is not None:
        short = float(_preview(plan))
        if short > 1e-6 * max(1.0, float(sum(plan.values()))):
            asked = float(sum(plan.values()))
            _tr = apply_plan(plan)
            short = float(getattr(apply_plan, 'last_shortfall_W', short) or short)
            plan = _delivered(apply_plan, plan)
            temps_x = thermal_solve_fn(_tr)
            st_x = status_fn()
            peak_x = objective_peak(temps_x, params, t_floor_K)
            history.append({'iter': 0, 'peak_K': peak_x, 'heat_removed_W': float(sum(plan.values())),
                            'max_plan_change_W': short, 'stage': 'extractor cap on the first plan'})
            if st_x.get('diverged') or not (peak_x == peak_x) or peak_x > params.target_K + tol_K:
                return {'plan': plan, 'detail': detail, 'temp_trace': temps_x, 'sensitivity': sens,
                        'result_unconverged': bool(st_x.get('unconverged')),
                        'converged': not st_x.get('diverged'), 'iterations': 2, 'history': history,
                        'temp_trace_diverged': bool(st_x.get('diverged')),
                        'plan_is_minimum': False, 'plan_holds_target': False,
                        'extractor_bound': True, 'extractor_shortfall_W': short,
                        'accounting': mr_accounting(plan, params, detail=detail),
                        'reason': ('extractor binds: the film cannot deliver the plan at the tile '
                                   'temperatures it produces -- {:.1f} W asked, {:.1f} W deliverable '
                                   '({} tiles capped). Reported at the cap: peak {}'
                                   .format(asked, float(sum(plan.values())),
                                           int(getattr(apply_plan, 'last_n_capped', 0)),
                                           'runaway' if st_x.get('diverged') else
                                           '{:.1f} C'.format(peak_x - 273.15)))}
            temps, st, peak = temps_x, st_x, peak_x
            result_status = dict(st)

    # The last plan whose solve BOTH converged and held the target. "The previous iterate" is not
    # the same thing: the descent deliberately walks past the feasible boundary to bracket the
    # minimum, so the previous iterate can be a diverged field full of NaN. Restoring that as an
    # answer produced "No block temperatures above the 200 K floor" downstream.
    last_holding = None

    def _remember(pl, tp, stt, pk):
        if stt.get('diverged'):
            return
        if not (pk == pk) or pk > params.target_K + tol_K:
            return
        return {'plan': dict(pl), 'temps': tp, 'status': dict(stt), 'peak_K': pk}

    last_holding = _remember(plan, temps, st, peak) or last_holding

    # Descend: reduce cooling where blocks sit below target, restore it where they sit above.
    for it in range(1, max_iter):
        prev_temps, prev_plan, prev_peak = temps, plan, peak
        prev_status = dict(result_status)
        plan = _relax_plan_toward_target(plan, envelope, temps, params, sens, relax, t_floor_K)
        # §P0.19: with a converged-power energy cap, the conservation limit follows the die the
        # cooling actually produced, every iteration (the P0.18.2 over-pull at 2.60 W/mm^2).
        if die_power_fn is not None and die_power_fn() is not None:
            plan = _energy_capped(plan, die_power_fn())
        if not plan:
            # The relaxation has taken the plan to zero. That is only the answer if the die
            # actually holds with no cooling, so it has to be TESTED -- and on a die that has no
            # steady state uncooled, it does not.
            temps = thermal_solve_fn(trace)
            st = status_fn()
            peak = objective_peak(temps, params, t_floor_K)
            history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': 0.0,
                            'max_plan_change_W': float(sum(prev_plan.values())),
                            'stage': 'relaxed to zero'})
            zero_holds = (not st.get('diverged')
                          and not (peak == peak and peak > params.target_K + tol_K))
            if zero_holds:
                result_status = dict(st)
                return {'plan': {}, 'detail': detail, 'temp_trace': temps,
                        'sensitivity': sens,
                        'result_unconverged': bool(result_status.get('unconverged')),
                        'converged': True, 'iterations': it + 1,
                        'history': history, 'temp_trace_diverged': False,
                        'plan_is_minimum': True, 'plan_holds_target': True,
                        'accounting': mr_accounting({}, params),
                        'reason': 'no cooling needed to hold the target'}
            # It does not hold. The relaxation overshot, so the answer is the last plan whose
            # solve actually held -- reporting the zero plan here claimed "MR not needed" on a die
            # with no steady state at all, which is the exact opposite of the finding.
            why = ('runaway' if st.get('diverged')
                   else 'peak {:.1f} C over target'.format(peak - 273.15))
            if last_holding is None:
                # Nothing in this descent ever held. That is a real answer and a strong one, but
                # it is NOT a plan.
                return {'plan': {}, 'detail': detail, 'temp_trace': temps,
                        'sensitivity': sens,
                        'result_unconverged': bool(dict(st).get('unconverged')),
                        'converged': False, 'iterations': it + 1, 'history': history,
                        'temp_trace_diverged': bool(st.get('diverged')),
                        'plan_is_minimum': False, 'plan_holds_target': False,
                        'accounting': mr_accounting({}, params),
                        'reason': ('relaxation reached zero and no plan in the descent held the '
                                   'target ({})'.format(why))}
            result_status = dict(last_holding['status'])
            history.append({'iter': it, 'peak_K': last_holding['peak_K'],
                            'heat_removed_W': float(sum(last_holding['plan'].values())),
                            'max_plan_change_W': 0.0,
                            'stage': 'relaxation overshot to zero; restored last holding plan'})
            return {'plan': last_holding['plan'], 'detail': detail,
                    'temp_trace': last_holding['temps'], 'sensitivity': sens,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'converged': True, 'iterations': it + 1, 'history': history,
                    'temp_trace_diverged': False,
                    # NOT minimal: the interval between that plan and zero was never bisected, so
                    # the true minimum lies somewhere inside it.
                    'plan_is_minimum': False, 'plan_holds_target': True,
                    'accounting': mr_accounting(last_holding['plan'], params, detail=detail),
                    'reason': ('relaxation reached zero but the die has no steady state '
                               'uncooled ({}); reporting the last plan that held'.format(why))}

        _tr = apply_plan(plan)
        plan = _delivered(apply_plan, plan)
        temps = thermal_solve_fn(_tr)
        st = status_fn()
        result_status = dict(st)
        sens.update(estimate_sensitivity(prev_temps, temps,
                                         {b: plan.get(b, 0.0) - prev_plan.get(b, 0.0)
                                          for b in set(plan) | set(prev_plan)}))
        peak = objective_peak(temps, params, t_floor_K)
        total = float(sum(plan.values()))
        delta_plan = max((abs(plan.get(b, 0.0) - prev_plan.get(b, 0.0))
                          for b in set(plan) | set(prev_plan)), default=0.0)
        history.append({'iter': it, 'peak_K': peak, 'heat_removed_W': total,
                        'max_plan_change_W': delta_plan, 'stage': 'descent'})
        last_holding = _remember(plan, temps, st, peak) or last_holding

        if st.get('diverged') or peak != peak:
            # Walked past the feasible boundary. Do NOT stop here: "the last plan that held"
            # depends on the step size that got us here, which is exactly the iteration-count
            # dependence this rewrite exists to remove (the plan drifted 0.615 -> 0.335 W at
            # 1.10 W/mm^2 between 6 and 20 iterations). Bisect the plan scale between the
            # smallest plan known to hold and the largest known to fail, which converges on the
            # true minimum instead of wherever the descent happened to overshoot.
            bad = plan
            plan, temps = prev_plan, prev_temps
            result_status = dict(prev_status or {})
            for _ in range(bisect_iters):
                trial = {b: 0.5 * (plan.get(b, 0.0) + bad.get(b, 0.0))
                         for b in set(plan) | set(bad)}
                trial = {b: q for b, q in trial.items() if q > 0.0}
                if die_power_fn is not None and die_power_fn() is not None:
                    trial = _energy_capped(trial, die_power_fn())
                _tr = apply_plan(trial)
                trial = _delivered(apply_plan, trial)
                t_trial = thermal_solve_fn(_tr)
                st_trial = status_fn()
                pk = objective_peak(t_trial, params, t_floor_K)
                history.append({'iter': len(history), 'peak_K': pk,
                                'heat_removed_W': float(sum(trial.values())),
                                'max_plan_change_W': float('nan'),
                                'stage': 'boundary bisection'})
                # A trial "fails" if it diverges OR if it lands on the HOT BRANCH. This
                # system is bistable: a leakage-limited die has a cool solution near the target
                # and a second stable solution far above it, with an unstable region between,
                # so reducing MR does not slide the peak up smoothly -- it snaps. Measured at
                # 1.15 W/mm^2: 42.05 W of cooling holds 90.6 C, while 0.71 W also "converges",
                # at 133.2 C. Accepting any convergence made the cheap hot-branch solution look
                # like the answer, which is how a 133 C die got reported as a rescue.
                if st_trial.get('diverged') or pk > params.target_K + tol_K:
                    bad = trial
                else:
                    plan, temps = trial, t_trial
                    result_status = dict(st_trial)
                lo, hi = float(sum(plan.values())), float(sum(bad.values()))
                if lo <= 0 or (lo - hi) <= 0.01 * lo:
                    break
            final_peak = objective_peak(temps or {}, params, t_floor_K)
            on_cool_branch = bool(final_peak <= params.target_K + tol_K)
            return {'plan': plan, 'detail': detail, 'temp_trace': temps,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'sensitivity': sens, 'converged': True,
                    'iterations': it + 1, 'history': history, 'temp_trace_diverged': False,
                    'accounting': mr_accounting(plan, params, detail=detail),
                    'plan_is_minimum': True, 'plan_holds_target': on_cool_branch,
                    'minimum_plan_W': float(sum(plan.values())),
                    'largest_failing_plan_W': float(sum(bad.values())),
                    'reason': ('minimum plan that keeps the die on the cool branch, bracketed '
                               'by bisection' if on_cool_branch else
                               'no plan in the bracket keeps the die on the cool branch: this '
                               'system is BISTABLE and the hot-branch solution is what is '
                               'reported. Stable, but read the peak before calling it a '
                               'rescue')}

        # Crossing the TARGET on the way down is the product-relevant answer, and it has to be
        # caught here rather than waiting for the plan to go stationary too: descending from the
        # envelope the peak RISES, so it sails past the target while the plan is still moving
        # fast. Without this the loop carries on to the stability boundary and reports a plan
        # whose steady state sits at 133 C -- stable, past McPAT's 127 C validity ceiling, and
        # not an operating point anyone would ship. Bisect to land ON the target instead.
        if peak > params.target_K + tol_K and prev_peak is not None \
                and prev_peak <= params.target_K + tol_K:
            too_little, enough, temps_ok = plan, prev_plan, prev_temps
            result_status = dict(prev_status or {})
            for _ in range(bisect_iters):
                trial = {b: 0.5 * (enough.get(b, 0.0) + too_little.get(b, 0.0))
                         for b in set(enough) | set(too_little)}
                trial = {b: q for b, q in trial.items() if q > 0.0}
                if die_power_fn is not None and die_power_fn() is not None:
                    trial = _energy_capped(trial, die_power_fn())
                _tr = apply_plan(trial)
                trial = _delivered(apply_plan, trial)
                t_trial = thermal_solve_fn(_tr)
                st_trial = status_fn()
                pk = objective_peak(t_trial, params, t_floor_K)
                history.append({'iter': len(history), 'peak_K': pk,
                                'heat_removed_W': float(sum(trial.values())),
                                'max_plan_change_W': float('nan'),
                                'stage': 'target bisection'})
                if st_trial.get('diverged') or pk > params.target_K + tol_K:
                    too_little = trial
                else:
                    enough, temps_ok = trial, t_trial
                    result_status = dict(st_trial)
                    if abs(pk - params.target_K) <= tol_K:
                        break
            return {'plan': enough, 'detail': detail, 'temp_trace': temps_ok,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'sensitivity': sens, 'converged': True, 'iterations': it + 1,
                    'history': history, 'temp_trace_diverged': False,
                    'plan_is_minimum': True, 'plan_holds_target': True,
                    'minimum_plan_W': float(sum(enough.values())),
                    'accounting': mr_accounting(enough, params, detail=detail),
                    'reason': 'minimum plan that holds the target, bracketed by bisection'}

        if delta_plan <= max(1e-3, 0.01 * total) and abs(peak - params.target_K) <= tol_K:
            return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
                    'result_unconverged': bool(result_status.get('unconverged')),
                    'converged': True, 'iterations': it + 1, 'history': history,
                    'temp_trace_diverged': False,
                    # Landed on the target smoothly. It holds the target; whether it is also the
                    # smallest plan that keeps a steady state is a different question and was
                    # not probed, so that flag stays False.
                    'plan_is_minimum': False, 'plan_holds_target': True,
                    'accounting': mr_accounting(plan, params, detail=detail)}

    return {'plan': plan, 'detail': detail, 'temp_trace': temps, 'sensitivity': sens,
            'result_unconverged': bool(result_status.get('unconverged')),
            'converged': not st.get('diverged'), 'iterations': max_iter, 'history': history,
            'temp_trace_diverged': bool(st.get('diverged')), 'plan_is_minimum': False,
            'plan_holds_target': bool(peak <= params.target_K + tol_K),
            'accounting': mr_accounting(plan, params, detail=detail),
            'reason': 'max_iter reached during envelope descent: the descent never reached the '
                      'stability boundary, so this plan is an UPPER BOUND on what MR needs, not '
                      'the minimum. Raise max_iter to bracket the boundary.'}


def distributed_plan(block_geom, params, total_W, weight='area', t_floor_K=200.0):
    """Spread a fixed cooling budget over the whole die instead of clipping hotspots.

    Design E in docs/DESIGN_STUDY_PLAN.md: the control arm. Every MR result in this project
    assumes MR is a *hotspot* tool, and that assumption is load-bearing -- it is why a poor
    cooler COP is tolerable, because ``Q_removed`` is small and buys a disproportionate
    frequency gain. If spreading the same watts over the die did as well, the framing would be
    wrong and the comparison should be against a better heat sink rather than against nothing.

    It is included because it is the strongest argument against the hotspot framing, and an
    argument you have not measured is an argument you have not answered. The expectation is that
    it loses badly on wall-plug grounds -- an electrical COP of 0.14 against a cold plate that
    moves heat for the cost of a pump -- but it can only be *reported* as a loss if it is run.

    weight : 'area' spreads the budget by block area (uniform cooling flux, which is what a
             tile array with no targeting would do), 'uniform' splits it evenly per block
             (which over-cools small blocks and is mostly a sanity contrast).

    Blocks are still capped by the device envelope, so a budget larger than the device can
    deliver is silently truncated -- the returned plan's total is the honest deliverable amount
    and callers should compare against that rather than against what they asked for.
    """
    if total_W <= 0:
        raise ValueError('total_W must be > 0, got {!r}'.format(total_W))
    if weight not in ('area', 'uniform'):
        raise ValueError("weight must be 'area' or 'uniform', got {!r}".format(weight))

    names = [b for b, g in block_geom.items() if g and g.get('area_mm2', 0.0) > 0]
    if not names:
        return {}, {}
    if weight == 'area':
        tot_area = sum(block_geom[b]['area_mm2'] for b in names)
        share = {b: block_geom[b]['area_mm2'] / tot_area for b in names}
    else:
        share = {b: 1.0 / len(names) for b in names}

    plan, detail = {}, {}
    for b in names:
        want = total_W * share[b]
        cap = params.h_max * block_geom[b]['area_mm2']      # the device's flux ceiling
        q = min(want, cap)
        if q <= 0:
            continue
        plan[b] = q
        detail[b] = {'limit': 'h_max' if q < want else 'budget', 'q_W': q,
                     'requested_W': want, 'q_h_max_W': cap}
    delivered = float(sum(plan.values()))
    if delivered < 0.999 * total_W:
        LOGGER.warning('distributed plan could only deliver %.3f W of the requested %.3f W: the '
                       'per-block h_max ceiling binds. Compare against the delivered figure.',
                       delivered, total_W)
    return plan, detail
