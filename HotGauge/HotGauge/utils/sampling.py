import math
import numpy as np

def resample(signal, factor):
    # new number of time-steps is factor * len(signal)
    if factor > 1:
        up_factor = math.ceil(factor)
        signal = upsample(signal, up_factor)
        factor /= up_factor
    signal = downsample(signal, 1.0/factor)
    return signal

def upsample(signal, n):
    assert int(n) == n, 'Upsamping can only be done via integer values.. try resample'
    return np.repeat(signal, n)

def downsample(signal, factor):
    if factor == 1:
        return np.array(signal)
    assert factor > 1.0, 'Factor must be greater than 1'
    current_x = 0.0
    out_sig = []
    while math.ceil(current_x + factor) <= len(signal):
        total_len = 0.0
        out_sig.append(0.0)
        sig_idx = math.floor(current_x)
        while total_len < factor:
           # See if we can use a full sample...
           next_end_pt = math.floor(current_x + total_len + 1)
           this_len = next_end_pt - (current_x + total_len)
           
           # See if the next end point is actually too far
           if total_len + this_len > factor:
               # Backtrack to end of window
               this_len = factor - total_len
           
           out_sig[-1] += this_len / factor * signal[sig_idx]

           total_len += this_len
           sig_idx += 1
        current_x += total_len
    return out_sig
