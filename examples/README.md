# HotGauge example scripts
The `ICE_simulation_from_MCPAT.py` and `custom_simulation_with_warmup.py` scripts demonstrate one how the 3D-ICE portion
of HotGauge can be run. Both run two simulations, one warmup sim, and one ICE sim. These simulations are split into two
steps in the newest release of HotGauge, and those seperate scripts can be found in `examples/template`. These two scripts
remain the repository for two reasons. First, `custom_simulation_with_warmup.py` is a useful test script to see if 3D-ice
is working on your system. Second, for users looking to modify HotGauge, these scripts provide useful examples of how
HotGauge can be run.

# HotGauge template directory
Each HotGauge run will require copying this template directory. The copied template directory will
hold the simulation metadata and outputs. Within this directory are three scripts, the warmup script,
the sim from warmup script, and a script that generates power trace and metadata files. There are also
two directories inside of the template directory. The `floorplan` directory contains floorplan template
files, and the `analysis_scripts` directory that contains the scripts that identify and visualize 
hotspots. When you complete a HotGauge run, the outputs will be in that directories `outputs` directory
in a long chain of sub-directories named to contain metadata about the run.

## HotGauge Python Package Requirment
Note that these scripts rely on the **HotGauge** python package, and thus, you must be using a
python environment with **HotGauge** installed. If you created a virtual-environment as suggested in
the README, you can run `source ../env/bin/activate` or the appropriate version for your shell with
an extension of either `.csh` or `.fish`.
