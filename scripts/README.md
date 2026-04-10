These are the scripts that take snipersim output and feed it into McPAT. The bash
script `14_perf_sims_to_7_10_14_power_sims.sh` runs the three python scripts on the
snipersim output in this order:

1) `run_mcpat.py`
2) `mcpat_txt_to_json.py`
3) `mcpat_to_blk_lvl_power_dict.py`
  
