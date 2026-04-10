import scipy.interpolate

VF_PAIRS = [(0.6, 1.7),
            (0.8, 3.2),
            (1.0, 4.1),
            (1.19, 4.6),
            (1.23, 4.7),
            (1.28, 4.8),
            (1.34, 4.9),
            (1.4, 5.0),
           ]

_VF_fn_of_V = scipy.interpolate.interp1d(*zip(*VF_PAIRS))
_VF_fn_of_F = scipy.interpolate.interp1d(*zip(*([(VF[1], VF[0]) for VF in VF_PAIRS])))

def get_VF_pair(*, V=None, F=None):
    """ Determine either voltage or frequency from one-another
    using 2D interpolation between known VF points

    Arguments:
        V (optional): Voltage at which frequency should be determined
        F (optional): Frequency in GHz at which voltage should be determined

    returns: tuple -> (Voltage, Frequency)
    """
    if V == F == None:
        raise ValueError('V or F must be supplied')
    if (V is not None) and (F is not None):
        raise ValueError('One of V or F must be supplied, not both')
    if V is not None:
        return _VF_fn_of_V(V)
    return _VF_fn_of_F(F)
