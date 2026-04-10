#! /usr/bin/env python
import random
import sys
from ThermalSideChannelAnalysisTools import GridHeatmap, Floorplan

def usage():
   print ("Usage:\n\t%s floorplan_file grid_heatmap_file" % (sys.argv[0]) )
   exit(1)

def main():
   argv = sys.argv
   if (len (argv) != 3):
      usage()

   flp = Floorplan.from_file(argv[1])
   temps = GridHeatmap.from_file(argv[2])

   masks = flp.get_masks()

   print "Computing core averages from %s using floorplan %s" % (argv[1],argv[2])

   for m in masks:
      t = temps.average_within_mask(m)
      print "%s: %f" % (m.name,t)

if __name__ == "__main__":
   main()
