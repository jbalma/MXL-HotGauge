import json
from collections import defaultdict
from abc import  ABC, abstractmethod
import itertools

import numpy as np

from HotGauge.utils.sampling import resample

class PowerTraceValidationError(ValueError):
    pass

class PowerTraceImmutableError(TypeError):
    pass

class PowerTraceCompatabilityError(ValueError):
    pass

class PowerTrace(ABC):
    """ Abstract base class for defining power traces """

    # The default value of whether the trace is lazily loaded or not
    LAZY_LOAD = False

    # Specifies whether this specific power trace is mutable in memory
    #   e.g. if it is read from a file, it should probably not be mutable
    MUTABLE = False

    def __init__(self, lazy_load = None, auto_validation=True):
        self.auto_validation = auto_validation
        if lazy_load == None:
            lazy_load = self.__class__.LAZY_LOAD
        if lazy_load == False:
            self._prepare()
            self._auto_validate()

    ################################################################################
    ############################### Required methods ###############################
    ################################################################################
    @abstractmethod
    def _prepare(self):
        """ Prepare the trace, e.g. load from file
            Set self._powers dictionary in the form {'unit_name': [p0, p1, p2], ...}
            Set self._time_step value
        """
        pass

    ################################################################################
    ######################## Baseline Functionality Methods ########################
    ################################################################################
    def _auto_validate(self):
        if self.auto_validation:
            self.validate()

    def validate(self):
        # Make sure the required values were set by the call to _prepare()
        set_fail_msg = '{}._prepare() failed to set {{}}'.format(type(self).__name__)
        if not(hasattr(self, '_powers')):
            raise PowerTraceValidationError(set_fail_msg.format('self._powers dictionary'))
        if not(hasattr(self, '_time_step')):
            raise PowerTraceValidationError(set_fail_msg.format('self._time_step'))

        # Make sure the values set by _prepare() are of the expected type
        set_type_msg = '{}.{{}} should be type {{}} but was {{}}'.format(type(self).__name__)
        cast_type_msg = '{}.{{}} was "{{}}" ({{}}) and could not be cast as type {{}}'.format(type(self).__name__)
        def _check_type(attr, expected_type):
            val = getattr(self, attr)
            if not isinstance(val, expected_type):
                raise PowerTraceValidationError(set_type_msg.format(attr, expected_type, type(val)))
        try:
            _check_type('time_step', float)
        except PowerTraceValidationError as e:
            try:
                self._time_step = float(self._time_step)
            except ValueError as e:
                raise PowerTraceValidationError(cast_type_msg.format('time_step',
                                                self._time_step, type(self._time_step), float))
        _check_type('_powers', dict)

        powers = self._powers

        # Make sure the length of the power trace is at least 1
        if len(powers) == 0:
            msg = 'Power dict (self._powers) was empty...'
            raise PowerTraceValidationError(msg)

        for unit in powers.keys():
            if isinstance(powers[unit], list):
                powers[unit] = np.array(powers[unit])

        # Make sure the lengths of powere trace for each unit is the same
        lens = set(len(ps) for ps in powers.values())
        if len(lens) != 1:
            msg = 'Power traces must be the same length for all units, but they were in the set {}'
            raise PowerTraceValidationError(msg.format(lens))

    ############################## Power trace values ##############################
    @property
    def powers(self):
        """ Returns the power dictionary

        Editiing this dictionary may result in invalid traces

        To edit a trace, use the recommended`trace[unit] = new_powers` instead
        """
        # Check if the trace is already loaded
        if hasattr(self, '_powers'):
            # Check to make sure power dictionary wasn't modified directly...
            self._auto_validate()
            return self._powers

        # Actually load and validate the trace
        self._prepare()
        self._auto_validate()
        return self._powers

    @powers.setter
    def powers(self, powers):
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place'.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        self._powers = powers
        self._auto_validate()

    def __len__(self):
        return len(list(self.powers.items())[0][1])

    ################################## Time step ###################################
    @property
    def time_step(self):
        if hasattr(self, '_time_step'):
            return self._time_step
        self._prepare()
        self._auto_validate()
        return self._time_step

    @time_step.setter
    def time_step(self, time_step):
        """ Manually reset the time-step without resampling in time
            use self.resample(new_time_step) to change the time-resolution of the trace
        """
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place'.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        self._time_step = time_step

    ##################### Common patterns for utility methods ######################
    @staticmethod
    def _apply_fn_to_unit_names(trace, fn):
        """ Applies fn(unit) to each unit name

        Return value of fn :
            if 'unit_in' is removed...
                fn should return None

            if 'unit_in' is mapped to a single unit...
                fn should return "unit_out" or ["unit_out"]

            if 'unit_in' is mapped to a multiple units...
                fn should return ['unit_out_0', ... , 'unit_out_n']
        """
        # Check the types
        if not(isinstance(trace, PowerTrace)):
            msg = 'Scalar functions can only be applied to PowerTraces, not {}'
            raise TypeError(msg.format(type(trace)))
        pnew = {}
        for unit, powers in trace.powers.items():
            mapped = fn(unit)
            # The unit is unmapped, drop it
            if mapped == None:
                continue
            # This unit is mapped to a single unit
            elif isinstance(mapped, str):
                pnew[mapped] = powers
            # The unit is mapped to multiple units
            elif isinstance(mapped, list):
                for mapped_unit in mapped:
                    pnew[mapped_unit] = powers
            else:
                msg = 'Unit renaming function must return either string or list but ' + \
                      'instead returned {}'.format(type(mapped))
                raise TypeError(msg)
        return pnew

    @staticmethod
    def _apply_fn_to_trace_powers(trace0, trace1, op):
        """ Applies op(p1_n_i, p2_n_i) to each timestep and each unit
            where p0_n_i is trace0[unit_n][index_i]
            where p1_n_i is trace1[unit_n][index_i]
        """
        # Check the types
        if not(isinstance(trace0, PowerTrace)) or not(isinstance(trace1, PowerTrace)):
            msg = 'Functions can only be applies to two PowerTraces, not {} and {}'
            raise TypeError(msg.format(type(trace0), type(trace1)))

        # Prepare the variables and check that the keys match
        p0, p1, pnew = trace0.powers, trace1.powers, {}
        k0, k1 = set(p0.keys()), set(p1.keys())
        if k0 != k1:
            raise PowerTraceCompatabilityError('PowerTraces must have same units (keys)')

        # Iterate over each each unit...
        for k in k0:
            p0k, p1k = p0[k], p1[k]
            # Make sure the lengths for each unit matches
            if len(p0k) != len(p1k):
                msg = 'PowerTraces for unit {} were not same length'
                raise PowerTraceCompatabilityError(msg.format(k))
            # Apply op(p0k, p1k) for each time-step
            pnew[k] = [op(a, b) for a,b in zip(p0k, p1k)]
        return pnew

    @staticmethod
    def _apply_fn_to_traces(trace0, trace1, op):
        """ Applies op(p0_n, p1_n) to each unit
            where p0_n is trace0[unit_n]
            where p1_n is trace1[unit_n]
        """
        # Check the types
        if not(isinstance(trace0, PowerTrace)) or not(isinstance(trace1, PowerTrace)):
            msg = 'Functions can only be applies to two PowerTraces, not {} and {}'
            raise TypeError(msg.format(type(trace0), type(trace1)))

        # Prepare the variables and check that the keys match
        p0, p1, pnew = trace0.powers, trace1.powers, {}
        k0, k1 = set(p0.keys()), set(p1.keys())
        if k0 != k1:
            raise PowerTraceCompatabilityError('PowerTraces must have same units (keys)')

        # Iterate over each each unit...
        for k in k0:
            # Apply the function to each power trace
            pnew[k] = op(p0[k], p1[k])
        return pnew

    @staticmethod
    def _apply_scalar_fn_to_trace_powers(trace, scalar, op):
        """ Applies op(p_n_i, scalar) to each timestep and each unit
            where p_n_i is trace0[unit_n][index_i]
        """
        # Check the type
        if not(isinstance(trace, PowerTrace)):
            msg = 'Scalar functions can only be applied to PowerTraces, not {}'
            raise TypeError(msg.format(type(trace)))

        pnew = {}
        for unit, pows in trace.powers.items():
            pnew[unit] = [op(p, scalar) for p in pows]
        return pnew

    @staticmethod
    def _apply_scalar_fn_to_trace(trace, scalar, op):
        """ Applies op(p0_n, scalar) to each unit
            where p0_n is trace0[unit_n]
        """
        # Check the types
        if not(isinstance(trace, PowerTrace)):
            msg = 'Scalar functions can only be applied to PowerTraces, not {}'
            raise TypeError(msg.format(type(trace)))

        pnew = {}
        for unit, pows in trace.powers.items():
            pnew[unit] = op(pows, scalar)
        return pnew

    @staticmethod
    def _apply_fn_to_trace(trace, fn):
        """ Applies fn(p0_n) to each unit
            where p0_n is trace0[unit_n]
        """
        # Check the types
        if not(isinstance(trace, PowerTrace)):
            msg = 'Scalar functions can only be applied to PowerTraces, not {}'
            raise TypeError(msg.format(type(trace)))

        pnew = {}
        for unit, pows in trace.powers.items():
            pnew[unit] = fn(pows)
        return pnew

    ########################## Two Trace Utility Methods ###########################
    #  Each return a new BasicPowerTrace

    # Trace addition
    def __add__(self, other):
        """ Return sum of power traces (e.g. leakage + dynamic) """
        op = lambda a,b : a + b
        return BasicPowerTrace._from_applied_fn_to_others_powers(self, other, op)

    def __iadd__(self, other):
        """ Add other power trace in-place (e.g. total += leakage) """
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place. Use + instead of +='.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        op = lambda a,b : a + b
        self.powers = PowerTrace._apply_fn_to_trace_powers(self, other, op)
        return self

    # Trace subtraction
    def __sub__(self, other):
        """ Return difference between power traces (e.g. total - savings) """
        op = lambda a,b : a - b
        return BasicPowerTrace._from_applied_fn_to_others_powers(self, other, op)

    def __isub__(self, other):
        """ Subtract other power trace in-place (e.g. total -= savings) """
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place. Use - instead of -='.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        op = lambda a,b : a - b
        self.powers = PowerTrace._apply_fn_to_trace_powers(self, other, op)
        return self

    # Trace appending
    def __lshift__(self, other):
        """ Creates a new trace where other is appended to self
            If self is a and other is b, returns [a0,...,an,b0,...,bm] for each unit
        """
        op = lambda a,b : list(itertools.chain(a,b))
        return BasicPowerTrace._from_applied_fn_to_other_trace(self, other, op)

    def __pow__(self, n_repeat):
        if not(isinstance(n_repeat, int)):
            msg = 'trace ** n_repeat must be integer number of repetitions but was {}'
            raise TypeError(msg.format(type(n_repeat)))

        shifted_trace = self
        repeated_trace = None
        while n_repeat > 0:
            if n_repeat % 2:
                if repeated_trace is None:
                    repeated_trace = shifted_trace
                else:
                    repeated_trace = repeated_trace << shifted_trace
            n_repeat //= 2
            shifted_trace = shifted_trace << shifted_trace
        return repeated_trace

    # TODO evaluate the following operations
    #   a | b -> union of two power dictionaries
    # These are less likely to be useful or intiutive...
    #   a & b -> intersection of two power dictionaries?
    #   a ^ b -> difference of two power dictionaries?

    ####################### Trace and Scalar Utility Methods #######################
    #  Each return a new BasicPowerTrace

    # Trace multiplication / division
    def __mul__(self, scalar):
        """ Multiply power trace values by scalar """
        op = lambda a,b : a * b
        return BasicPowerTrace._from_applied_scalar_fn_to_others_powers(self, scalar, op)

    def __truediv__(self, scalar):
        """ Divide power trace values by scalar """
        op = lambda a,b : a / b
        return BasicPowerTrace._from_applied_scalar_fn_to_others_powers(self, scalar, op)

    def __imul__(self, scalar):
        """ Multiply power trace in-place by scalar (e.g. total *= 2 ) """
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place. Use * instead of *='.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        op = lambda a,b : a * b
        self.powers = PowerTrace._apply_scalar_fn_to_trace_powers(self, scalar, op)
        return self

    def __idiv__(self, scalar):
        """ Divide power trace in-place by scalar (e.g. total /= 2 ) """
        if not self.__class__.MUTABLE:
            msg = 'Cannot mutate {} in place. Use / instead of /='.format(type(self).__name__)
            raise PowerTraceImmutableError(msg)
        op = lambda a,b : a / b
        self.powers = PowerTrace._apply_scalar_fn_to_trace_powers(self, scalar, op)
        return self

    def resample(self, new_time_step):
        """ resamples the trace to be at the new time-step """
        new_time_step = float(new_time_step)
        factor = self.time_step / new_time_step
        op = lambda powers, factor : resample(powers, factor)
        return BasicPowerTrace._from_applied_scalar_fn_to_other(self, factor, op, new_time_step)

    def __mod__(self, new_time_step):
        """ resamples the trace to be at the new time-step using trace % new_timestep """
        return self.resample(new_time_step)

    def __getitem__(self, key):
        """ Get powers for a certain unit, for a time-step, or for a slice

            trace['unit'] = [...]

            trace[17] = trace of only 17th timestep

            trace[1:] = trace of second timestep to end
        """
        # Get powers for a specific unit
        if isinstance(key, str):
            return self.powers[key]
        elif isinstance(key, int):
            fn = lambda p: [p[key]]
        else:
            fn = lambda p: p[key]
        return BasicPowerTrace._from_applied_fn_to_other(self, fn)

    def __setitem__(self, unit, value):
        assert isinstance(unit, str), 'Trace[unit] requires unit to be a string'
        old_value = self.powers.get(unit, None)
        self.powers[unit] = value
        try:
            self._auto_validate()
        except PowerTraceValidationError as e:
            if old_value:
                self.powers[unit] = old_value
            raise e

    def rename_units(self, rename_fn):
        """ Renames units using rename function """
        return BasicPowerTrace._from_applied_fn_to_unit_names(self, rename_fn)

class BasicPowerTrace(PowerTrace):
    """ A power trace stored entirely in memory """
    MUTABLE = True
    def __init__(self, powers, time_step, *args, **kwargs):
        self._powers = powers
        self._time_step = time_step
        super(BasicPowerTrace, self).__init__(*args, **kwargs)

    @staticmethod
    def from_other(other, *args, **kwargs):
        powers, time_step = other.powers, other.time_step
        return BasicPowerTrace(powers, time_step, *args, **kwargs)

    def _prepare(self):
        pass # Power and time_step are already known

    ########### Methods for creating a BasicPowerTrace from other traces
    @staticmethod
    def _from_applied_fn_to_unit_names(trace, unit_name_fn, time_step=None):
        if time_step is None:
            time_step = trace.time_step
        new_powers = PowerTrace._apply_fn_to_unit_names(trace, unit_name_fn)
        return BasicPowerTrace(new_powers, time_step)

    @staticmethod
    def _from_applied_fn_to_others_powers(trace0, trace1, op, time_step=None):
        if time_step is None:
            t0, t1 = trace0.time_step, trace1.time_step
            if t0 != t1:
                msg = 'Cannot apply function to PowerTraces with different time steps'
                raise PowerTraceCompatabilityError(msg)
            time_step = t0
        new_powers = PowerTrace._apply_fn_to_trace_powers(trace0, trace1, op)
        return BasicPowerTrace(new_powers, time_step)

    @staticmethod
    def _from_applied_fn_to_other_trace(trace0, trace1, op, time_step=None):
        if time_step is None:
            t0, t1 = trace0.time_step, trace1.time_step
            if t0 != t1:
                msg = 'Cannot apply function to PowerTraces with different time steps'
                raise PowerTraceCompatabilityError(msg)
            time_step = t0
        new_powers = PowerTrace._apply_fn_to_traces(trace0, trace1, op)
        return BasicPowerTrace(new_powers, time_step)

    @staticmethod
    def _from_applied_scalar_fn_to_others_powers(trace, scalar, op, time_step=None):
        if time_step is None:
            time_step = trace.time_step
        new_powers = PowerTrace._apply_scalar_fn_to_trace_powers(trace, scalar, op)
        return BasicPowerTrace(new_powers, time_step)

    @staticmethod
    def _from_applied_scalar_fn_to_other(trace, scalar, op, time_step=None):
        if time_step is None:
            time_step = trace.time_step
        new_powers = PowerTrace._apply_scalar_fn_to_trace(trace, scalar, op)
        return BasicPowerTrace(new_powers, time_step)

    @staticmethod
    def _from_applied_fn_to_other(trace, fn, time_step=None):
        if time_step is None:
            time_step = trace.time_step
        new_powers = PowerTrace._apply_fn_to_trace(trace, fn)
        return BasicPowerTrace(new_powers, time_step)

class JSONFilesPowerTrace(PowerTrace):
    """ A trace comprised of a sequence of json power files """
    LAZY_LOAD = True
    def __init__(self, trace_files, time_step, *args, **kwargs):
        self.trace_files = trace_files
        self._time_step = time_step
        super(JSONFilesPowerTrace, self).__init__(*args, **kwargs)

    def __len__(self):
        return len(self.trace_files)

    def _prepare(self):
        self._powers = defaultdict(list)
        for trace_file in self.trace_files:
            powers = json.load(open(trace_file, 'r'))
            for unit, power in powers.items():
                self._powers[unit].append(power)

class JSONFilePowerTrace(PowerTrace):
    """ A trace comprised of a single json file with the entire trace """
    LAZY_LOAD = True
    def __init__(self, trace_file, time_step, *args, **kwargs):
        self.trace_file = trace_file
        self._time_step = time_step
        super(JSONFilePowerTrace, self).__init__(*args, **kwargs)

    def _prepare(self):
        self._powers = json.load(open(self.trace_file, 'r'))

class SniperStatsDFTrace(object):
    def __init__(self, list_of_sniper_stats_dfs):
        self.list_of_sniper_stats_dfs = np.array(list_of_sniper_stats_dfs)

    def __getitem__(self, idx):
        # This supports [int], [int:], [:int], and [int:int] just like nump arrays
        if isinstance(idx, int): 
            return SniperStatsDFTrace(self.list_of_sniper_stats_dfs[idx:idx+1])
        else:
            return SniperStatsDFTrace(self.list_of_sniper_stats_dfs[idx])

    def __lshift__(self, other):
        first = self.list_of_sniper_stats_dfs
        second = other.list_of_sniper_stats_dfs
        new_trace_list_of_sniper_stats_dfs = np.concatenate((first, second))
        return SniperStatsDFTrace(new_trace_list_of_sniper_stats_dfs)
    
    def __len__(self):
        return len(self.list_of_sniper_stats_dfs)

    def get_stats(self):
        return self.list_of_sniper_stats_dfs
