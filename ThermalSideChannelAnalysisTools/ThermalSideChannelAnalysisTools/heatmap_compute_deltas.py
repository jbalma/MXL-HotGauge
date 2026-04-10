#! /usr/bin/env python
import random
import sys
from ThermalSideChannelAnalysisTools import GridHeatmap

def usage():
   print ("Usage:\n\t%s infile1 infile2 outfile" % (sys.argv[0]) )
   exit(1)

def main():
   argv = sys.argv
   if (len (argv) != 4):
      usage()
   ifname1 = argv[1]
   ifname2 = argv[2]
   ofname = argv[3]
   t1 = GridHeatmap.from_file(ifname1)
   t2 = GridHeatmap.from_file(ifname2)
   delta = t1 - t2
   delta.normalize_to_avg()
   delta.write_heatmap_file(ofname)

if __name__ == "__main__":
   main()
