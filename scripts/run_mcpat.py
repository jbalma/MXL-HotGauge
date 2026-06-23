#!/usr/bin/env python
import os
import shutil
import sys
import glob
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("rundir")
parser.add_argument("--jobs", type=int, default=8)
args = parser.parse_args()

rundir = args.rundir

if rundir[-1] != '/':
    rundir += '/'

txtfiles = glob.glob(rundir + 'energystats-temp*.txt')
pyfiles = glob.glob(rundir + 'energystats-temp*.py')
cfgfiles = glob.glob(rundir + 'energystats-temp*.cfg')
files_to_delete = txtfiles + pyfiles + cfgfiles

for filePath in files_to_delete:
    try:
        os.remove(filePath)
    except:
        print("Error while deleting file : ", filePath)

fp_commands_file = os.path.join(rundir, "mcpat_commands.txt")
if os.path.exists(fp_commands_file):
    fp_commands_file_bak = os.path.join(rundir, "mcpat_commands_old.txt")
    shutil.move(fp_commands_file, fp_commands_file_bak)

with open(fp_commands_file, "w") as f:
    for fname in os.listdir(rundir):
        if fname.endswith(".xml"):
            time_step = fname.split('-')[2].split('.')[0]
            command = (
                "../McPAT/mcpat "
                + "-infile " + rundir + fname
                + " -print_level 5 > "
                + rundir + "mcpat_output_" + time_step + ".txt\n"
            )
            f.write(command)

subprocess.run(
    ["parallel", "-j", str(args.jobs)],
    stdin=open(fp_commands_file, "r"),
    check=True
)
