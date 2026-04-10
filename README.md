# HotGauge
A framework for characterizing hotspots in next-generation processors

[[_TOC_]]

# Local Machine Setup
This codebase requires python 3 and was developed using python 3.9

# System Dependencies (RHEL 9)

The following packages must be installed before using HotGauge.

| Package            | Required Version        | Notes |
|--------------------|------------------------|------|
| python3            | ≥ 3.9                  | Newer Scripts developed using Python 3.9, older ones with 3.4 |
| python3-devel      | Matching Python3       | Needed for building Sniper |
| gcc                | ≥ 7.4 (tested 11.5)    | Required for Sniper + 3D-ICE |
| make / cmake       | Any recent             | Build tools |
| bison              | ≥ 3.0 (tested 3.7.4)   | Required for 3D-ICE |
| flex               | ≥ 2.6                  | Required for 3D-ICE |
| pkg-config         | Any recent             | Used in builds |
| boost-devel        | Any recent             | Sniper dependency |
| sqlite-devel       | Any recent             | Sniper dependency |
| zlib-devel         | Any recent             | Sniper dependency |
| openblas-devel     | ≥ 0.3 expected to work | BLAS backend |
| openblas-openmp    | Any compatible         | Parallel BLAS |
| bzip2-devel        | Any recent             | Build dependency |
| xz                 | Any recent             | Needed for archive extraction |
| wget / unzip / zip | Any recent             | Utility tools |
| csh                | Any recent             | Required by Sniper scripts |
| parallel           | Any recent             | Used in workflows |
| pugixml            | ≥ 1.8                  | Required for 3D-ICE plugin |
| pugixml-devel      | ≥ 1.8                  | Headers |
| OpenModelica       | ≥ 1.16                 | Required for heat-sink model |
| ffmpeg             | Any Recent             | Required for analyis script |

### Special Case: McPAT (32-bit dependencies)

| Package              | Version |
|----------------------|--------|
| glibc-devel.i686     | Any compatible |
| libstdc++.i686       | Any compatible |
| libgcc.i686          | Any compatible |


# Version Compatibility Notes

HotGauge integrates several external tools (Sniper, McPAT, 3D-ICE) that were originally developed with older dependencies.

- 3D-ICE was originally built with:
  - gcc 7.4.0
  - bison 3.0.4
  - flex 2.6.4
  - BLAS 3.7.1

- This repository has been successfully tested on:
  - gcc 11.5.0
  - bison 3.7.4
  - flex 2.6.4
  - OpenBLAS 0.3.26

In general:
- Newer versions of these dependencies work correctly
- No strict version pinning is required
- If build issues occur, they are most likely due to missing packages rather than version incompatibility

# System Depency Installation Help

These commands install dependencies that are not available through the default `dnf` repositories.

### Install McPAT 32-bit Dependencies

1) `sudo dnf upgrade -y libstdc++.x86_64`
1) `sudo dnf install -y glibc-devel.i686 libstdc++.i686 libgcc.i686`

### Install pugixml and pugixml-devel

1) `sudo subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms`
1) `sudo dnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm`
1) `sudo dnf install pugixml pugixml-devel`

### Install open-modelica
1) `sudo dnf config-manager --add-repo https://build.openmodelica.org/rpm/el9/omc.repo`
1) `sudo dnf install openmodelica-nightly`
1) `sudo chmod -R a+rX /opt/openmodelica-nightly/share/omc/runtime/c/fmi/buildproject/`


## Initial Setup
1. Clone this repository and enter it
2. Set up a virtual-environment
   1. Create the virtual-environment: `python3 -m venv env`
   2. Activate the virtual-environment
      * `source env/bin/activate` if using `bash`
      * `source env/bin/activate.csh` if using `csh`
      * `source env/bin/activate.fish` if using `fish`
   3. Update pip `python -m pip install --upgrade pip`
   4. Install required modules: `pip install -r requirements.txt`
3. Set up Sniper (the performance simulator)
   1. Go to https://github.com/snipersim/snipersim and clone the repository.
   2. Set the `SNIPER_ROOT` environment variable using: `export SNIPER_ROOT="$PWD"`
   3. Enter the new directory
   4. Apply the patch: `patch -p1 < ~/HotGauge/RHEL9_patches/sniper_rhel9_delta.patch`
   5. Run: `make`
4. Set up McPAT (the power simulator)
   1. Re-enter the HotGauge root directory and download and patch McPAT using: `get_and_patch_McPAT.sh`
   2. Change into the HotGauge/McPAT directory and run: `make`
   3. Make the McPAT Binary executable: `chmod u+x ~/HotGauge/McPAT/mcpat`
      * If you make clean and then make again it will likely not work. In the event that you run make clean, just delete the McPAT directory entirely and start over at the beginning of this step
5. Set up 3D-ICE (the thermal simulator)
   1. Return to the HotGauge root directory and download and patch 3d-ice using: `get_and_patch_3DICE.sh`
   2. Enter the 3d-ice directory and run: `./install-superlu.sh`
      * At the end of the installation there will be a bunch of small tests that superlu runs and they may fail due to segmentation faults. Do not worry about this, the build was successful.
   3. Enter into the `SuperLU_4.3` directory and apply the patch: `patch -p1 < ~/HotGauge/RHEL9_patches/supLU_rhel9_delta.patch`
   4. Compile the heatsink plugin using `make` in `/3d-ice/heatsink_plugin/`
   5. Compile 3D-ICE executables using `make` in `./3d-ice/`
   6. Test by navigating to `~/HotGauge/examples` and running: `Python custom_simulation_with_warmup.py`
      * You may need to go into the python file and then uncomment and adjust the sys path insert line
      * Note: This script can take 2 days to run
6. Utilize **HotGauge** as you see fit!
    
## Subsequent Use
1) Activate the environment: `source env/bin/activate`
2) Refer to `use_instructions.pdf` in this directory for a description of how to use HotGauge


# Repository Contents
The following directories contain the code developed for use with this project. Each directory has a
different purpose, as described below.

## Examples
This directory holds HotGauge outputs, scripts to run the 3D-ICE and analysis parts of HotGauge, 
and sample sniper configuration and 3D-ICE warmup files.

## Scripts
This is where the scripts that feed Sniper Output into McPAT live.

## End to End
This directory holds a script that runs HotGauge from sniper all the way through 3D-ice. It also holds
a template configuration file that the end to end script takes as input.

## HotGauge
The python package for HotGauge. This includes scripts to run simulations and process the outputs.

## RHEL9 patches
The patch files that modify the tools in HotGauge such that they can run on RHEL9.

## ThermalSideChannelAnalysisTools
Python scripts that help with visualizing hotspots
