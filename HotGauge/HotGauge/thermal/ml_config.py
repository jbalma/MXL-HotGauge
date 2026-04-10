
root_folder = "/r/tcal/work/maziar/work/hotspot"
csvs_folder = "{}/csvs".format(root_folder)
pkls_folder = "{}/pkls".format(root_folder)

workload_names = [
    'GemsFDTD', 'astar', 'bwaves', 'bzip2', 'cactusADM', 'calculix',
    'gamess', 'gcc', 'gobmk', 'gromacs', 'h264ref', 'hmmer', 'lbm',
    'leslie3d', 'libquantum', 'mcf', 'milc', 'namd', 'omnetpp',
    'perlbench', 'povray', 'sjeng', 'soplex', 'sphinx3', 'tonto',
    'wrf', 'zeusmp'
    ]

feature_columns = [
    'ALU_cdb_duty_cycle', 'ALU_duty_cycle', 'BTB_read_accesses',
    'BTB_write_accesses', 'FPU_cdb_duty_cycle', 'FPU_duty_cycle',
    'IFU_duty_cycle', 'LSU_duty_cycle', 'MUL_cdb_duty_cycle',
    'MUL_duty_cycle', 'MemManU_D_duty_cycle', 'MemManU_I_duty_cycle',
    'PBT_chooser_predictor_bits', 'PBT_chooser_predictor_entries',
    'PBT_global_predictor_bits', 'PBT_global_predictor_entries',
    'PBT_local_predictor_entries', 'ROB_reads', 'ROB_writes',
    'branch_instructions', 'branch_mispredictions', 'busy_cycles',
    'cdb_alu_accesses', 'cdb_fpu_accesses', 'cdb_mul_accesses',
    'committed_fp_instructions', 'committed_instructions',
    'committed_int_instructions', 'context_switches', 'dcache_conflicts',
    'dcache_read_accesses', 'dcache_read_misses', 'dcache_write_accesses',
    'dcache_write_misses', 'dtlb_conflicts', 'dtlb_number_entries',
    'dtlb_total_accesses', 'dtlb_total_misses', 'float_regfile_reads',
    'float_regfile_writes', 'fp_inst_window_reads',
    'fp_inst_window_wakeup_accesses', 'fp_inst_window_writes',
    'fp_instructions', 'fp_rename_reads', 'fp_rename_writes',
    'fpu_accesses', 'function_calls', 'ialu_accesses', 'icache_conflicts',
    'icache_read_accesses', 'icache_read_misses', 'idle_cycles',
    'inst_window_reads', 'inst_window_wakeup_accesses',
    'inst_window_writes', 'int_instructions', 'int_regfile_reads',
    'int_regfile_writes', 'itlb_conflicts', 'itlb_number_entries',
    'itlb_total_accesses', 'itlb_total_misses', 'load_instructions',
    'mul_accesses', 'rename_reads', 'rename_writes', 'store_instructions',
    'total_cycles', 'total_instructions',
    't_sens_0_0', 't_sens_0_1', 't_sens_0_2',
    't_sens_0_3', 't_sens_0_4', 't_sens_0_5', 't_sens_0_6',
    'clockrate'
    ]

fc = [
    'ALU_cdb_duty_cycle', 'ALU_duty_cycle', 'BTB_read_accesses',
    'BTB_write_accesses', 'FPU_cdb_duty_cycle', 'FPU_duty_cycle',
    'IFU_duty_cycle', 'LSU_duty_cycle', 'MUL_cdb_duty_cycle',
    'MUL_duty_cycle', 'MemManU_D_duty_cycle', 'MemManU_I_duty_cycle',
    'PBT_chooser_predictor_bits', 'PBT_chooser_predictor_entries',
    'PBT_global_predictor_bits', 'PBT_global_predictor_entries',
    'PBT_local_predictor_entries', 'ROB_reads', 'ROB_writes',
    'branch_instructions', 'branch_mispredictions', 'busy_cycles',
    'cdb_alu_accesses', 'cdb_fpu_accesses', 'cdb_mul_accesses',
    'committed_fp_instructions', 'committed_instructions',
    'committed_int_instructions', 'context_switches', 'dcache_conflicts',
    'dcache_read_accesses', 'dcache_read_misses', 'dcache_write_accesses',
    'dcache_write_misses', 'dtlb_conflicts', 'dtlb_number_entries',
    'dtlb_total_accesses', 'dtlb_total_misses', 'float_regfile_reads',
    'float_regfile_writes', 'fp_inst_window_reads',
    'fp_inst_window_wakeup_accesses', 'fp_inst_window_writes',
    'fp_instructions', 'fp_rename_reads', 'fp_rename_writes',
    'fpu_accesses', 'function_calls', 'ialu_accesses', 'icache_conflicts',
    'icache_read_accesses', 'icache_read_misses', 'idle_cycles',
    'inst_window_reads', 'inst_window_wakeup_accesses',
    'inst_window_writes', 'int_instructions', 'int_regfile_reads',
    'int_regfile_writes', 'itlb_conflicts', 'itlb_number_entries',
    'itlb_total_accesses', 'itlb_total_misses', 'load_instructions',
    'mul_accesses', 'rename_reads', 'rename_writes', 'store_instructions',
    'total_cycles', 'total_instructions'
    ]

non_feature_columns = [
    'workload', 'time_step', 'tech_node', 'start_condition', 
    'current_step_severity', 'current_step_hotspot', 
    'next_step_hotspot', 'next_step_severity', 'is_hotspot'
    ]

dataset_parameters = [
    'workload', 'time_step', 'tech_node', 'start_condition', 'clockrate'
    ]

label_column = 'next_step_severity'

top_features = [
        'FPU_cdb_duty_cycle', 'dcache_write_accesses', 'LSU_duty_cycle',
        'IFU_duty_cycle', 'MUL_cdb_duty_cycle', 'branch_mispredictions',
        'BTB_read_accesses', 'dcache_read_misses', 'itlb_total_misses',
        'cdb_fpu_accesses', 'committed_int_instructions',
        'icache_read_accesses', 'dtlb_total_accesses', 'ROB_reads',
        'busy_cycles', 'dcache_read_accesses', 'committed_instructions',
        'cdb_alu_accesses', 'total_cycles', 'tsens03'
        ]

top_features_wo_sensor = [
        'FPU_cdb_duty_cycle', 'dcache_write_accesses', 'LSU_duty_cycle',
        'IFU_duty_cycle', 'MUL_cdb_duty_cycle', 'branch_mispredictions',
        'BTB_read_accesses', 'dcache_read_misses', 'itlb_total_misses',
        'cdb_fpu_accesses', 'committed_int_instructions',
        'icache_read_accesses', 'dtlb_total_accesses', 'ROB_reads',
        'busy_cycles', 'dcache_read_accesses', 'committed_instructions',
        'cdb_alu_accesses', 'total_cycles'
        ]

#top_features = [
#    'dtlb_total_accesses', 'cdb_alu_accesses',
#    'committed_instructions', 'sum_busy_cycles', 'BTB_read_accesses',
#    'committed_int_instructions', 'busy_cycles',
#    'dcache_read_accesses', 'ROB_reads', 'tsens03'
#    ]

def predict(clf, X_inp, y_inp, mt):
    y_pred = clf.predict(X_inp)
    scr = mean_squared_error(y_inp, y_pred)
    return y_pred, scr
