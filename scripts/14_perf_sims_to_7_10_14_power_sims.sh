#!/bin/bash

# Usage: ./14_perf_sims_to_7_10_14_power_sims.sh sim_dir [num_cores] [max_jobs]
[ $# -lt 1 -o $# -gt 3 ] && { echo "Usage: $0 sim_dir [num_cores] [max_jobs]"; exit 1; }

SIM_ROOT="$1"
NUM_CORES="${2:-1}"
MAX_JOBS="${3:-8}"

[ ! -d "$SIM_ROOT" ] && { echo "$SIM_ROOT doesn't exist"; exit 1; }

BASE_SIM_DIR_14nm="$SIM_ROOT/14nm"
SIM_DIRS_14nm=$(ls -1d "${BASE_SIM_DIR_14nm}"/*/ 2>/dev/null)
[ -z "$SIM_DIRS_14nm" ] && { echo "$BASE_SIM_DIR_14nm has no sub-directories.. sims missing..."; exit 1; }

for sim_dir_14nm in $SIM_DIRS_14nm; do
    echo "$sim_dir_14nm"
    for node in 7 10; do
        sim_dir_other_nm=${sim_dir_14nm/14nm/${node}nm}
        mkdir -p "${sim_dir_other_nm}"
        cp "${sim_dir_14nm}"/energystats-temp-* "${sim_dir_other_nm}"
        sed -i "s/\"core_tech_node\" value=\"14\"/\"core_tech_node\" value=\"${node}\"/" "${sim_dir_other_nm}"/energystats-temp-*
    done
done

for node in 7 10 14; do
    echo "Running ${node}nm sims..."
    SIM_DIRS=$(ls -1d "$SIM_ROOT/${node}nm"/*)

    for sim_dir in $SIM_DIRS; do
        python run_mcpat.py "$sim_dir" --jobs "$MAX_JOBS"
    done
    echo "MCPAT done"

    # Keep this sequential unless it is truly slow.
    # It is safer because the expensive parallelism is already inside other stages.
    for sim_dir in $SIM_DIRS; do
        python mcpat_txt_to_json.py "$sim_dir"
    done
    echo "MCPAT txt to json done"

    for sim_dir in $SIM_DIRS; do
        python mcpat_to_blk_lvl_power_dict.py "$sim_dir" --num-cores "$NUM_CORES" --jobs "$MAX_JOBS"
    done
    echo "MCPAT json blk_lvl_power_dict done"
done

exit 0
