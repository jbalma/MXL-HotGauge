import os
import glob
import json
from collections import defaultdict
import functools
import math

from tqdm import tqdm

from HotGauge.power.traces import JSONFilesPowerTrace, JSONFilePowerTrace
from HotGauge.configuration import load_block_powers
from HotGauge.power.mcpat import swap_cores, mcpat_block_powers_to_DICE
from HotGauge.power.hotgauge_models import add_extra_DICE_units

from .metadata import SimpleMetaDataHandler, TypeParser
from .config import LOGGER

#maz
from .ml_config import top_features_wo_sensor
from HotGauge.power.traces import SniperStatsDFTrace

################################################################################
########################### Workload Related Errors ############################
################################################################################

class WorkloadSetError(ValueError): pass
class WorkloadConfError(WorkloadSetError): pass
class WorkloadDirectoryParseError(WorkloadSetError): pass

################################################################################
################################# Type Parsers #################################
################################################################################

class WorkloadParser(TypeParser):
    def make_parse_fn(self):
        def parse(value):
            if value.startswith('wl'): # it's intel
                return {'benchmark': value}
            wl, region = value.split('_')
            wl = wl.replace('_', '-') # linpack_singlethread -> linpack-singlethread
            return {'benchmark' : wl, 'region' :region}
        return parse

class TechNodeParser(TypeParser):
    def make_parse_fn(self):
        def parse(value):
            if isinstance(value, str) and value.endswith('nm'):
                node = int(value[:-2])
            else:
                node = int(value)
            return {'tech_node':node, 'tech_node_nm':'{}nm'.format(node)}
        return parse

# TODO: Can all of the remaining parsers be replaced with SuffixParsers?
#class SuffixParser(TypeParser):
#    def __init__(self, suffix, cast_type=None):
#        self.suffix = suffix
#        self.cast_type = cast_type
#    def make_parse_fn(self):
#        def parse(value):
#            if value.endswith(self.suffix):
#                value = value[:-len(self.suffix)]
#            if cast_type != None:
#                return cast_type(value)
#            return value
#        return parse

class ClockFrequencyParser(TypeParser):
    def make_parse_fn(self):
        def parse(value):
            suffix = '_clockrate'
            if value.endswith(suffix):
                value = value[:-len(suffix)]
            return int(value)
        return parse

class ClockFrequencyParser2(TypeParser):
    def make_parse_fn(self):
        def parse(value):
            suffix = 'GHz'
            if value.endswith(suffix):
                value = value[:-len(suffix)]
            return float(value)
        return parse

class VDDParser(TypeParser):
    def make_parse_fn(self):
        def parse(value):
            suffix = '_vdd'
            if value.endswith(suffix):
                value = value[:-len(suffix)]
            return float(value)
        return parse

class WorkloadHandler(SimpleMetaDataHandler):
    parse_workload = WorkloadParser()
    parse_tech_node = TechNodeParser()
    parse_clk_freq = ClockFrequencyParser()
    parse_frequency = ClockFrequencyParser()
    parse_vdd = VDDParser()


DEFAULT_WL_SET = 'fine-grained'
DEFAULT_BASE_WORKLOAD_DIR = '/r/tcal/work/hotspot_share/perf_power_sims/'
DEFAULT_HANDLER = WorkloadHandler()
def get_workload_set(set_name=DEFAULT_WL_SET, base_dir=DEFAULT_BASE_WORKLOAD_DIR, meta_handler=DEFAULT_HANDLER):
    # Find the workload set
    set_dir = os.path.join(base_dir, set_name)
    if not os.path.isdir(set_dir):
        raise WorkloadSetError('Cannot load {} from {}'.format(set_name, base_dir))

    # Load the simulation metadata file
    set_metadata_file = os.path.join(set_dir, 'simulation_metadata.json')
    try:
        set_metadata = json.load(open(set_metadata_file, 'r'))
    except OSError as e:
        raise WorkloadConfError('Error loading {}... does file exist?'.format(set_metadata_file)) from e

    # Prepare to load simulation details with metadata
    try:
        dir_frmt = set_metadata['directory_format']
    except KeyError as e:
        raise WorkloadConfError('directory_format key required but missing from {}'.format(set_metadata_file))

    default_metadata = set_metadata.pop('defaults', {})
    keys = dir_frmt.split('/')
    sim_pattern = os.path.join(set_dir, '*/' * len(keys))
    sim_dirs = glob.glob(sim_pattern)
    # Directory -> meta_data
    sims = {sim_dir: parse_metadata(keys, os.path.relpath(sim_dir, set_dir).split('/'), default_metadata, meta_handler=meta_handler) for sim_dir in sim_dirs}
    return sims

def parse_metadata(metadata_keys, metadata_fields, base_metadata, meta_handler=DEFAULT_HANDLER):
    metadata = dict(base_metadata)
    metadata.update(meta_handler.parse_all(metadata_keys, metadata_fields))
    return metadata

# TODO: parallelize this...
def cached_traces_for_workload_set(cache_base_dir, wl_set=DEFAULT_WL_SET,
                                   base_wl_dir=DEFAULT_BASE_WORKLOAD_DIR, force=False):
    LOGGER.info('Loading {} from {}'.format(wl_set, base_wl_dir))
    wl_set_dir = os.path.join(base_wl_dir, wl_set)
    base_workloads = get_workload_set(wl_set)
    prepped_workloads = {}
    cache_dir =  os.path.join(cache_base_dir, wl_set)
    for wl_dir, wl_meta in tqdm(base_workloads.items(), desc='Loading sims', unit='sims'):
        prepped_trace_path = wl_dir.replace(wl_set_dir, cache_dir)
        prepped_trace_file = os.path.join(prepped_trace_path, 'power_trace.json')
        prepped_trace_meta = os.path.join(prepped_trace_path, 'simulation_metadata.json')
        # See if we already prepped the trace
        if os.path.exists(prepped_trace_file) and os.path.exists(prepped_trace_meta):
            if not(force):
                LOGGER.info('Using cached copy for {}'.format(wl_dir))
                with open(prepped_trace_meta, 'r') as f:
                    wl_meta = json.load(f)
                    prepped_workloads[prepped_trace_file] = wl_meta
                continue
            else:
                LOGGER.info('Ignoring cached copy for {}. It will be overwritten'.format(wl_dir))

        # Load the trace
        wl_trace = JSONFilesPowerTrace(load_block_powers(wl_dir), float(wl_meta['interval_ns']))
        # Discard empty/not-ready traces
        if len(wl_trace) == 0:
            LOGGER.warn('Failed to load {}'.format(wl_dir))
            continue

        LOGGER.info('Loading and caching trace for {}'.format(wl_dir))
        # Load and cache the trace
        os.makedirs(prepped_trace_path, exist_ok=True)
        with open(prepped_trace_file, 'w') as f:
            powers = {u: list(p) for u, p in wl_trace.powers.items()}
            json.dump(powers, f)
        with open(prepped_trace_meta, 'w') as f:
            json.dump(wl_meta, f)
        prepped_workloads[prepped_trace_file] = wl_meta
    return prepped_workloads

def block_powers_trace_to_DICE(trace, floorplan, tech_node, core_sources=None):
    if core_sources:
        trace = swap_cores(trace, core_sources)
    trace = mcpat_block_powers_to_DICE(trace, 8)
    trace = add_extra_DICE_units(trace, floorplan, tech_node)
    return trace

################################################################################
###################### Workload Splicing and Manipulation ######################
################################################################################
class WorkloadSplicer(object):
    def __init__(self, traces_at_freqs, metadata):
        """ Each splicer should have traces for each available frequency for a given experiment
        traces_at_freqs: {freq_GHz: PowerTrace, ...}
        meta_data: experiment configuration data, e.g. workload

        The splicing assumes constant IPC at each frequency (so 25% completion at 5GHz corresponds
            to 25% completion at 2.5GHz)
        """
        self.traces_at_freqs = traces_at_freqs
        self.metadata = metadata

    def fraction_done_at_idx_for_freq(self, idx, freq):
        total_len = len(self[freq])
        fraction = idx / float(total_len)
        return fraction

    def idx_at_fraction_done_for_freq(self, fraction, freq):
        total_len = len(self[freq])
        idx = math.floor(fraction*total_len)
        return idx

    def splice_trace(self, starting_freq, *durations_and_freqs):
        """ Returns a spliced trace at the given frequencies and durations
        Start of trace is at starting_freq

        durations_and_freq: list of (duration, frequency) tuples

        For each (duration, frequency), the *previous* frequency should be run for duration number
            of steps and the *remainder* of the trace should be run at the next frequency, or for
            the number of time steps specified by the *next* duration value
        """
        # Start with the initial frequency
        trace_segments = [self[starting_freq]]

        last_freq = starting_freq
        fraction_done = 0
        for duration, freq in durations_and_freqs:
            # trim previous freq to duration
            trace_segments[-1] = trace_segments[-1][:duration]
            # Figure out where we are in the overall trace
            fraction_done += self.fraction_done_at_idx_for_freq(duration, last_freq)
            # Find where that corresponds to in the new frequency trace
            start_idx = self.idx_at_fraction_done_for_freq(fraction_done, freq)
            # Start the trace at the new frequency at that location
            rest_of_trace = self[freq][start_idx:]
            last_freq = freq
            trace_segments.append(rest_of_trace)
        # Append all of the traces together
        return functools.reduce(lambda t1,t2: t1<<t2, trace_segments)

    @property
    def frequencies(self):
        return sorted(self.traces_at_freqs.keys())

    def __getitem__(self, frequency):
        return self.traces_at_freqs[frequency]

    def filter_freqs(self, above=None, below=None):
        freqs = self.frequencies
        if above is not None:
            freqs = [f for f in freqs if f > above]
        if below is not None:
            freqs = [f for f in freqs if f < below]
        return freqs

    @staticmethod
    def group_workloads(wl_traces):

        grouped_wl_traces = defaultdict(dict)
        for wl_trace_json, wl_meta in wl_traces.items():
            trimmed_meta = {k:v for k,v in wl_meta.items() if k != 'frequency'}
            meta_key = tuple(sorted(trimmed_meta.items()))
            wl_trace = JSONFilePowerTrace(wl_trace_json, wl_meta['interval_ns'] * 1e-9)
            grouped_wl_traces[meta_key][frequency(wl_meta['frequency'])] = wl_trace
        return [WorkloadSplicer(traces, dict(meta)) for meta, traces in grouped_wl_traces.items()]

    # maz ---------------------------------------------------------------------------------------------------
    @staticmethod
    def df_grouper_helper(df):
        return df[top_features_wo_sensor].values.tolist()

    @staticmethod
    def df_grouper(df):
        df_wl_f_list =  df.groupby(['clockrate']).apply(WorkloadSplicer.df_grouper_helper)
        traces_at_freqs = df_wl_f_list.apply(SniperStatsDFTrace).to_dict()
        return traces_at_freqs

    @staticmethod
    def parse_df_wl(row):
        meta = row[['workload', 'tech_node']].to_dict()
        traces_at_freqs = row[['traces_at_freqs']].values[0]
        return (meta, traces_at_freqs)

    @staticmethod
    def group_workloads_from_df(df):
        df_wl = df.groupby(['workload', 'tech_node']).apply(WorkloadSplicer.df_grouper).reset_index(name='traces_at_freqs')
        grouped_tuples = df_wl.apply(WorkloadSplicer.parse_df_wl, axis=1).tolist()
        return [WorkloadSplicer(traces, meta) for meta, traces in grouped_tuples]
    # maz ---------------------------------------------------------------------------------------------------


def frequency(freq_str):
    return float(freq_str.strip('GHz'))
