"""Real fan specifications from the Maxwell Labs datasheets, for cooling-power budgeting.

Why this matters more than it looks
-----------------------------------
Until now ``PumpedSink``'s *thermal* curve was calibrated against the HS483 FMU but its
*power* coefficients were placeholders -- and the optimal P_fan : P_MR split depends directly
on what a watt of fan buys. These are the measured numbers.

The headline consequence: **a real server fan is expensive**. A Delta PFB0412EN-E draws
31.2 W nominal (42 W max) where the MR stage in our 23 W study cost 0.4 W net. Optimiser
sweeps run with 1-4 W cooling budgets were exploring a regime a 1U server fan cannot even
enter -- its minimum operating draw is ~28 W. Realistic server thermals put the fan at a
large, coarsely-quantised cost and MR as the cheap marginal lever.

Operating point vs free air
---------------------------
Datasheets quote maximum airflow at *zero* static pressure and maximum pressure at *zero*
airflow; a fan never runs at either. ``cfm``/``pressure_mmH2O`` here are the loaded operating
points from ``docs/Data_sheets/fan_efficiency_curve_RM.xlsx`` where available (e.g. the
PFB0412EN-E delivers 22.2 CFM at 96.6 mmH2O, not its 38 CFM free-air rating), with the
free-air figures kept separately for reference.

Scaling
-------
``at_rpm`` applies the standard fan affinity laws -- Q ~ N, dP ~ N^2, P_elec ~ N^3 -- which
hold *within* one fan design. They are NOT valid between models: the PFB0412EN-E and
PFB0412EHN-TP06 differ by 2.03x in speed but 6.4x in static pressure, because they are
different blade designs, not one fan at two speeds.
"""

import math


class FanSpec(object):
    """A fan's datasheet operating point, with affinity-law scaling.

    ``power_W`` is electrical input at ``rpm``. ``cfm`` and ``pressure_mmH2O`` are the loaded
    operating point unless only free-air data was available (``operating_point=False``).
    """

    def __init__(self, model, size_mm, rpm, cfm, pressure_mmH2O, power_W,
                 free_air_cfm=None, max_pressure_mmH2O=None, max_power_W=None,
                 voltage_V=12.0, noise_dBA=None, notes='', operating_point=True):
        self.model = model
        self.size_mm = size_mm
        self.rpm = float(rpm)
        self.cfm = float(cfm)
        self.pressure_mmH2O = float(pressure_mmH2O)
        self.power_W = float(power_W)
        self.free_air_cfm = free_air_cfm
        self.max_pressure_mmH2O = max_pressure_mmH2O
        self.max_power_W = max_power_W
        self.voltage_V = voltage_V
        self.noise_dBA = noise_dBA
        self.notes = notes
        self.operating_point = bool(operating_point)

    @property
    def air_power_W(self):
        """Useful pneumatic power at the operating point [W]: Q * dP in SI.

        1 CFM = 4.71947e-4 m^3/s, 1 mmH2O = 9.80665 Pa.
        """
        return (self.cfm * 4.71947e-4) * (self.pressure_mmH2O * 9.80665)

    @property
    def efficiency(self):
        """Pneumatic power / electrical power at the operating point."""
        return self.air_power_W / self.power_W if self.power_W > 0 else float('nan')

    def at_rpm(self, rpm):
        """This fan scaled to another speed by the affinity laws (same design only)."""
        if rpm < 0:
            raise ValueError('rpm must be >= 0')
        r = rpm / self.rpm if self.rpm else 0.0
        return FanSpec(self.model + '@{:.0f}rpm'.format(rpm), self.size_mm, rpm,
                       self.cfm * r, self.pressure_mmH2O * r ** 2, self.power_W * r ** 3,
                       voltage_V=self.voltage_V, notes='affinity-scaled from ' + self.model,
                       operating_point=self.operating_point)

    def rpm_for_power(self, power_W):
        """Speed whose electrical draw is ``power_W`` (affinity: P ~ N^3)."""
        if power_W <= 0:
            return 0.0
        return self.rpm * (power_W / self.power_W) ** (1.0 / 3.0)

    def __repr__(self):
        return ('FanSpec({} {}mm, {:.0f} RPM, {:.1f} CFM @ {:.1f} mmH2O, {:.1f} W, '
                'eta={:.3f})'.format(self.model, self.size_mm, self.rpm, self.cfm,
                                     self.pressure_mmH2O, self.power_W, self.efficiency))


#: Delta 40 mm, 32,500 RPM. **The server-class archetype.** Very high static pressure
#: (188.7 mmH2O free) is what a 1U/2U CPU heatsink's dense fin stack requires; 40 mm
#: high-RPM fans in banks are the standard 1U solution. 70.5 dB-A -- a server part, not a
#: workstation one. Operating point from the efficiency spreadsheet.
PFB0412EN_E = FanSpec('PFB0412EN-E', 40, 32500, cfm=22.24, pressure_mmH2O=96.57,
                      power_W=37.82, free_air_cfm=38.00, max_pressure_mmH2O=188.72,
                      max_power_W=42.0, noise_dBA=70.5,
                      notes='1U/2U server archetype; 31.2 W nominal, 37.8 W at this '
                            'operating point, 42 W max')

#: Delta 40 mm, 16,000 RPM low-power variant. Same footprint, ~6x less power and ~6x less
#: static pressure -- a workstation/2U-quiet part rather than a dense-server one.
PFB0412EHN_TP06 = FanSpec('PFB0412EHN-TP06', 40, 16000, cfm=11.67, pressure_mmH2O=15.14,
                          power_W=6.56, noise_dBA=None,
                          notes='low-power 40 mm variant; too little static pressure for a '
                                'dense 1U heatsink')

#: Delta 40 mm, 23,000 RPM. Between the two PFB parts. Its datasheet spec table is a scanned
#: image and is not in the efficiency spreadsheet, so these numbers are interpolated.
FFB0412EN_00Y2E = FanSpec('FFB0412EN-00Y2E', 40, 23000, cfm=16.0, pressure_mmH2O=48.0,
                          power_W=18.0, operating_point=False,
                          notes='ESTIMATED between the two PFB points -- the datasheet table '
                                'is image-only; measure before relying on it')

#: 172 mm chassis fan, 1330-2500 RPM, from the digitised fan/power curves in this directory.
#: The *other* server-class archetype: 315 CFM free-air but only 17.8 mmH2O -- eight times the
#: flow of a PFB0412EN-E at a tenth of its pressure. This is the bulk air mover for a 2U/4U
#: chassis or rack door, not the fan that pushes through a CPU fin stack. A real HPC node has
#: both stages, and they are not interchangeable.
EFP172 = FanSpec('EFP172', 172, 2500, cfm=150.0, pressure_mmH2O=6.73, power_W=21.0,
                 free_air_cfm=315.0, max_pressure_mmH2O=17.78, max_power_W=30.0,
                 notes='chassis/rack bulk airflow at 2500 RPM; operating point read off the '
                       'digitised curves (Data_sheet_fan.png / Data_sheet_power.png)')

#: Sanyo Denki San Ace 80 (80x80x15 mm), from the P-Q curve in PQ_123.png. Peak static
#: pressure ~36 Pa (3.7 mmH2O) at 13.8 V -- fifty times less than a PFB0412EN-E. A case fan.
SAN_ACE_80 = FanSpec('San Ace 80 (9P)', 80, 3000, cfm=20.0, pressure_mmH2O=2.0, power_W=2.5,
                     free_air_cfm=35.3, max_pressure_mmH2O=3.67, operating_point=False,
                     notes='ESTIMATED from PQ_123.png; case/chassis fan, far too little '
                           'static pressure for any server heatsink')

#: The HS483's own fan (P14752-ND), for reference: this is what our FMU calibration measured.
#: 40 mm class but far lower speed and power than a server part.
P14752 = FanSpec('P14752-ND (HS483)', 40, 6000, cfm=10.0, pressure_mmH2O=8.0, power_W=2.0,
                 operating_point=False,
                 notes='ESTIMATED; the fan in the calibrated HS483 FMU. Desktop-class -- the '
                       'reason our R_th calibration tops out near 0.69 K/W')

CATALOG = {f.model: f for f in (PFB0412EN_E, PFB0412EHN_TP06, FFB0412EN_00Y2E, EFP172,
                                SAN_ACE_80, P14752)}

#: Recommended archetype for the *die-level* heatsink when scaling power and core count --
#: that is a static-pressure problem, and this is the only part in the set built for it.
SERVER_CLASS = PFB0412EN_E

#: Recommended archetype for the *chassis* stage of the same node.
CHASSIS_CLASS = EFP172


def fan_bank(spec, n):
    """``n`` identical fans in parallel: n x the flow and n x the power, same pressure.

    Real 1U nodes use banks of 4-8 40 mm fans, which is how they reach the airflow a
    300-700 W part needs. Pressure does not add in parallel -- that is what limits how far
    this scales without moving to liquid.
    """
    if n < 1:
        raise ValueError('n must be >= 1')
    return FanSpec('{} x{}'.format(spec.model, n), spec.size_mm, spec.rpm,
                   cfm=spec.cfm * n, pressure_mmH2O=spec.pressure_mmH2O,
                   power_W=spec.power_W * n, voltage_V=spec.voltage_V,
                   notes='bank of {} in parallel'.format(n),
                   operating_point=spec.operating_point)
