import os
import re
import math
import copy
import logging
LOGGER = logging.getLogger(__name__)

import numpy as np

from HotGauge import HOT_GAUGE_ROOT_DIR
from HotGauge.script_runner import ExecutableJob
from HotGauge.script_runner.tool_scripts import write_or_update_file, populate_template
from HotGauge.utils import Floorplan
from HotGauge.thermal.utils import K_to_C

################################################################################
##################### # Utilities for parsing 3D-ICE files #####################
################################################################################

# Regular Expressions for parsing the stack files
CELL_SIZE_REGEX = re.compile(r'cell\s+length\s+(\S+)\s*,\s+width\s+(\S+)\s*;')
OUTPUT_START_REGEX = re.compile('^\s*output\s*:\s*$')
OUTPUT_REGEX = re.compile(r'^(\w*)\s*\((\s*\w*\s*,)?\s*"(.*)"\s*(,\s*\w*\s*)+\)\s*;$')
COMMENT_REGEX = r'("[^\n]*"(?!\\))|(//[^\n]*$|/(?!\\)\*[\s\S]*?\*(?!\\)/)'
PLUGIN_REGEX = re.compile(r'\s*plugin\s*".*"\s*,\s*"(\S+)\s.*"\s*;\s*')

# Methods for selecting and parsing 3D-ICE stack files

def get_stack_template(template_name):
    template_fname = template_name.replace('.stk','') + '.stk'
    stack_file = os.path.join(ICE_STK_DIR, template_fname)
    return stack_file

def strip_stack_file(stack_file):
    """" Reads stack file and removes contents and blank lines """
    contents = open(stack_file, 'r').read()
    # Remove C style comments
    for x in re.findall(COMMENT_REGEX, contents, 8):
        contents = contents.replace(x[1], '')
    # Remove blank lines and strip others
    return [l.strip() for l in contents.split('\n') if len(l.strip())>0]

def parse_file_name_from_output_line(output_line):
    return OUTPUT_REGEX.match(output_line).group(3)

def parse_cell_size_from_stack_file(stack_file):
    cell_size = None
    try:
        lines = strip_stack_file(stack_file)
        for line in lines:
            match = CELL_SIZE_REGEX.match(line)
            if match:
                assert cell_size == None
                length, width = match.groups((0,1))
                cell_size = (float(length), float(width))
        return cell_size
    except:
        pass
    return (None, None)

def parse_output_files_from_stack_file(stack_file):
    line_iter = iter(strip_stack_file(stack_file))
    # Go until we reach the start of the output list
    for line in line_iter:
        if OUTPUT_START_REGEX.match(line):
            break
    # Each of the remaining lines is an ouput, so parse the files
    return [OUTPUT_REGEX.match(l).group(3) for l in line_iter]

def parse_pluggable_heatsink_from_stack_file(stack_file):
    contents = strip_stack_file(stack_file)
    for line in contents:
        match = PLUGIN_REGEX.match(line)
        if match:
            return match.group(1)
    return None

def parse_step_slot_from_stack_file(stack_file):
    """ Get time-step and time slot from stack file

    Can only be used on stack files with transient sim type """
    contents = strip_stack_file(stack_file)
    step_slot = None
    for line in contents:
        match = TRANSIENT_STEP_REGEX.match(line)
        if not(match):
            continue
        if step_slot != None:
            LOGGER.warn('Multiple step/slot lines encountered.. returning the last one')
        step, slot = match.groups((0,1))
        step_slot = (float(step), float(slot))
    return step_slot

################################################################################
########################## 3D-ICE Simulation Wrappers ##########################
################################################################################

# Location of ICE executables
ICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '3d-ice'))
# Location of HotGauge stack files
ICE_STK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), 'stack_templates'))

class ICESimConfig(object):
    """ Contains details used to fill in the 3D-ICE templates """
    def __init__(self, initial_temp = 300, plugin_args=None, output_list=None):
        self.initial_temp = initial_temp
        self.plugin_args = plugin_args

        if output_list == None:
            self.output_list = []
        elif isinstance(output_list, str):
            self.output_list = [output_list]
        elif isinstance(output_list, list):
            self.output_list = output_list

    @property
    def initial_temp_lines(self):
        lines = []
        initial_temp = self.initial_temp
        # (val0, val1)
        if isinstance(initial_temp, tuple):
            if len(initial_temp) != 2:
                msg = '{}.initial_temp should be length 2'.format(self.__class__.__name__) + \
                      ' but was {}'.format(len(initial_temp))
                raise ValueError(msg)

            # (temp_stack, temp_sink)
            if isinstance(initial_temp[0], (int, float)) and \
               isinstance(initial_temp[1], (int, float)):
                temp_stack, temp_sink = initial_temp
                lines.append('initial temperature {} ;'.format(temp_stack))
                lines.append('initial sink temperature {} ;'.format(temp_sink))
            # (tstack_file, temp_sink):
            elif isinstance(initial_temp[0], str) and \
                 isinstance(initial_temp[1], (int, float)):
                initial_temp_file = initial_temp[0]
                initial_temp = initial_temp[1]
                lines.append('initial temperature "{}" ;'.format(initial_temp_file))
                lines.append('initial sink temperature {} ;'.format(initial_temp))
            else:
                types = type(initial_temp[0]), type(initial_temp[1])
                msg = 'Cannot understand tuple {}'.format(initial_temp) + \
                      'of types {} as initial temperature'.format(types)
                raise ValueError(msg)

        # temp_stack
        elif isinstance(initial_temp, (int, float)):
            temp_stack = initial_temp
            lines.append('initial temperature {} ;'.format(temp_stack))
        elif isinstance(initial_temp, str):
            initial_temp_file = initial_temp
            initial_temp = 300
            lines.append('initial temperature "{}" ;'.format(initial_temp_file))
            lines.append('initial sink temperature {} ;'.format(initial_temp))
        else:
            msg = 'Cannot understand {}'.format(initial_temp) + \
                  'of type {} as initial temperature'.format(type(initial_temp))
            raise ValueError(msg)
        return lines

    @property
    def initial_temp_file(self):
        initial_temp = self.initial_temp
        # (val0, val1)
        if isinstance(initial_temp, tuple):
            candidate = initial_temp[0]
        else:
            candidate = initial_temp
        if isinstance(candidate, str):
            return candidate
        return None

class ICESim(ExecutableJob):
    EMULATOR_EXECUTABLE = os.path.join(ICE_DIR, 'bin', '3D-ICE-Emulator')
    OUTPUT_TSTACK_FINAL = 'Tstack ("final.tstack", final ) ;'
    parallel_options = copy.deepcopy(ExecutableJob.parallel_options)

    def __init__(self, stack_template, flp_template, power_trace, sim_config, *args, **kwargs):
        self.stack_template = stack_template
        self.flp_template = flp_template
        self.power_trace = power_trace
        self.sim_config = sim_config
        self._output_files_cache = None
        super().__init__(*args, **kwargs)

    @property
    def solver_config(self):
        lines = [self.sim_type_str] + self.sim_config.initial_temp_lines
        return '\n'.join('   '+ l for l in lines)

    # Pre-defined locations for input files
    @property
    def flp_file(self):
        return os.path.join(self.run_path, 'IC.flp')
    
    @property
    def stack_file(self):
        return os.path.join(self.run_path, 'IC.stk')

    @property
    def expected_output_length(self):
        return len(self.power_trace)

    def output_files(self):
        if self._output_files_cache is not None:
            return self._output_files_cache
        output_list = parse_output_files_from_stack_file(self.stack_file)
        output_list = list(map(lambda f: os.path.join(self.run_path, f), output_list))
        self._output_files_cache = output_list
        return self._output_files_cache

    def input_files(self):
        files = [self.stack_file, self.flp_file, self.__class__.EMULATOR_EXECUTABLE]
        initial_temp_file = self.sim_config.initial_temp_file
        if initial_temp_file != None:
            files.append(initial_temp_file)
        return files

    def job_args(self):
        """ runs {3D-ICE_Emulator} {stack_file} """
        return '{} {} {}'.format(self.run_path,
                                 self.__class__.EMULATOR_EXECUTABLE,
                                 os.path.basename(self.stack_file))

    @classmethod
    def job_cmd(cls):
        # TODO: make this it's own *template.sh script
        """The command to run with job_args from each instance"""
        return os.path.join(HOT_GAUGE_ROOT_DIR, 'script_runner', 'run_executable_instance')

    def prep_for_run(self):
        self.fill_flp_template()
        self.fill_stk_template()

    def fill_flp_template(self):
        # Copy the powers
        power_dict = dict(self.power_trace.powers)
        self.power_trace.validate()

        # Convert raw numbers to 3DICE format: [p0, p1, ..., pn]
        for k,v in power_dict.items():
            power_dict[k] = ', '.join(map(str, v))

        contents = populate_template(self.flp_template, powers=power_dict)
        return write_or_update_file(self.flp_file, contents)


    def fill_stk_template(self):
        flp = Floorplan.from_file(self.flp_file)
        stk_width, stk_height = flp.width + 1e-3, flp.height + 1e-3

        # Make sure there are an integer number of pixels
        #   (actualy make it even too, so heatspreader border is even too)
        #   Cell is 50 um, so 2 cells are 100um. Spreader is 30,000um
        # TODO: use parse_cell_size_from_stack_file instead of assuming 50um
        stk_width = math.ceil(stk_width/100)*100
        stk_height = math.ceil(stk_height/100)*100

        output_list_str = '\n'.join('   ' + o for o in self.sim_config.output_list)

        rel_flp_file = os.path.abspath(self.flp_file)
        contents = populate_template(self.stack_template, flp_file=rel_flp_file,
                                     flp_width=stk_width,
                                     flp_height=stk_height,
                                     solver_config=self.solver_config,
                                     ICE_DIR=ICE_DIR,
                                     plugin_args=self.sim_config.plugin_args,
                                     output_list=output_list_str)

        status = write_or_update_file(self.stack_file, contents)
        pluggable_heatsink = parse_pluggable_heatsink_from_stack_file(self.stack_file)
        if pluggable_heatsink:
            base_heatsink_dir = os.path.join(ICE_DIR, 'heatsink_plugin', 'heatsinks')
            basename = pluggable_heatsink.split('_')[0]
            basename = {'Cuplex':'cuplex_kryos_21606'}.get(basename, basename)
            heatsink_model_dir = os.path.join(base_heatsink_dir, basename, pluggable_heatsink)
            dst_link = os.path.join(self.run_path, pluggable_heatsink)
            tmp_link = os.path.join(self.run_path, "_" + pluggable_heatsink)
            os.symlink(heatsink_model_dir, tmp_link)
            os.rename(tmp_link, dst_link)
        return status

    def output_status(self):
        num_outputs = self.expected_output_length
        msgs = []
        for output in self.output_files():
            if os.path.splitext(output)[1] == '.tstack':
                # TODO: Check number of lines in this files based on flp size, resolution and length?
                pass
            else: # Other files have number of outputs equal to simulation steps
                regexes = [
                           re.compile('^$'), # Grid files are seperated by empty lines
                           re.compile('^\s*[^%]') # Element files have 1 entry per line (plus comments)
                          ]
                counts = [0] *  len(regexes)
                with open(output, 'r') as f:
                    for line in f:
                        for reg_idx, regex in enumerate(regexes):
                            if regex.match(line)!=None:
                                counts[reg_idx] += 1
                if num_outputs not in counts:
                    # None of the known file formats have been validated
                    lens = ', '.join(['{1} for {0}'.format(r,c) for r,c in zip(regexes, counts)])
                    msgs.append('Output length using python for {} not correct. Expected {} but got {}'.format(os.path.basename(output), num_outputs, lens))
        if len(msgs)==0:
            return True, None
        return False, "\n".join(msgs)

class ICETransientSim(ICESim):
    TRANSIENT_STEP_REGEX = re.compile(r'transient\s*step\s*(\S+)\s*,\s*slot\s*(\S+)\s*;')
    CELL_SIZE_REGEX = re.compile(r'cell\s+length\s*(\S+)\s*,\s*width\s*(\S+)\s*;')
    DIE_TMAP_OUTPUT = 'Tmap (PROCESSOR_DIE, "die_grid.temps", slot ) ;'
    DIE_PMAP_OUTPUT = 'Pmap (PROCESSOR_DIE, "die_grid.pows", slot ) ;'
    DIE_TFLP_OUTPUT = 'Tflp (PROCESSOR_DIE, "die_elements.temps", average, slot) ;'
    def __init__(self, *args, steps_per_slot=10, **kwargs):
        if steps_per_slot == None:
            self.steps_per_slot = 10
        else:
            self.steps_per_slot = steps_per_slot
        assert self.steps_per_slot > 1, 'Each time slot must be broken up into 1 or more step'
        super().__init__(*args, **kwargs)

    @property
    def time_slot(self):
        return self.power_trace.time_step

    @property
    def time_step(self):
        return self.time_slot / self.steps_per_slot

    @property
    def sim_type_str(self):
        step =  DICE_float_to_string(self.time_step, 10)
        slot =  DICE_float_to_string(self.time_slot, 10)
        return 'transient step {}, slot {} ;'.format(step, slot)
    
    @classmethod
    def get_step_slot(cls, stk_file):
        
        from pathlib import Path

        stk_path = Path(stk_file)

        in_solver_block = False

        with stk_path.open() as f:
            for line in f:
                stripped = line.strip()

                # Enter solver block when we see 'solver :'
                if stripped.startswith("solver"):
                    in_solver_block = True
                    continue

                #look for the transient line
                if in_solver_block:
                    # Skip comments or empty lines
                    if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                        continue

                    m = cls.TRANSIENT_STEP_REGEX.search(line)
                    if m:
                        step_str, slot_str = m.groups()
                        step = float(step_str)
                        slot = float(slot_str)
                        return step, slot

                    # If we hit another header, we can stop looking
                    if stripped.endswith(":") and not stripped.startswith("solver"):
                        break

        raise ValueError(
            f"No 'transient step ..., slot ... ;' line found in solver block of stack file: {stk_file}"
        )

    @classmethod
    def get_cell_size(cls, stk_file):
        
        from pathlib import Path

        stk_path = Path(stk_file)
        in_dimensions_block = False

        with stk_path.open() as f:
            for line in f:
                stripped = line.strip()

                if stripped.startswith("dimensions"):
                    in_dimensions_block = True
                    continue

                if in_dimensions_block:
                    # Skip comments / empty lines
                    if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                        continue

                    m = cls.CELL_SIZE_REGEX.search(line)
                    if m:
                        length_str, width_str = m.groups()
                        length = float(length_str)
                        width = float(width_str)
                        return length, width


class ICESteadySim(ICESim):
    DIE_TMAP_OUTPUT = 'Tmap (PROCESSOR_DIE, "die_grid.temps", final ) ;'
    DIE_PMAP_OUTPUT = 'Pmap (PROCESSOR_DIE, "die_grid.pows", final ) ;'
    DIE_TFLP_OUTPUT = 'Tflp (PROCESSOR_DIE, "die_elements.temps", average, final ) ;'
    @property
    def sim_type_str(self):
        return 'steady ;'

    @property
    def expected_output_length(self):
      return 1

def DICE_float_to_string(number, precision=20):
    return '{0:.{prec}f}'.format(
            number, prec=precision,
            ).rstrip('0').rstrip('.') or '0'

################################################################################
################### Methods for loading 3D-ICE output files ####################
################################################################################
def load_3DICE_grid_file(fname, convert_K_to_C=True):
    def load_step(rows):
        data = []
        for row in rows:
            vals = list(float(val) for val in row.split())
            if len(vals) > 0:
                data.append(vals)
        return data

    f = open(fname, 'r')
    l = f.readline() # skip first line
    assert l[0] == '%'

    grids = []
    current_lines = []
    for line in f:
        if line != '\n':
            current_lines.append(line)
            continue
        # current line is blank, end of current_lines chunk
        vals = load_step(current_lines)
        if len(vals) > 0:
            grids.append(vals)
        current_lines = []

    ttrace = np.flip(np.asarray(grids, dtype=float), 1)
    if convert_K_to_C:
        ttrace = K_to_C(ttrace)
    return ttrace

def load_3DICE_block_file(fname, convert_K_to_C=False, to_dict=True):
    # TODO: make this more readable so that convert_K_to_C can be implemented
    if convert_K_to_C:
        raise NotImplementedError()
    f = open(fname, 'r')
    l1 = f.readline() # skip first line
    assert l1[0] == '%'
    l2 = f.readline() # The second line is the header
    assert l2[0] == '%'

    header = [t[:-4].strip() for t in l2[1:].split('\t')]
    data = [[]]*len(header)
    content = f.read()
    lines = content.split('\n')
    values = [list(map(float, line.split('\t')[:-1])) for line in lines][:-1]
    if to_dict:
        return dict(zip(header,map(np.array, zip(*values))))
    return header, values
