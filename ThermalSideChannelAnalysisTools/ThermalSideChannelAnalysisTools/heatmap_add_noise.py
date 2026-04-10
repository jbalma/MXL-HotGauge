#! /usr/bin/env python
import sys
import argparse
from ThermalSideChannelAnalysisTools import GridHeatmap, Floorplan

def get_parser():
   p = argparse.ArgumentParser(description='Add noise to grid thermal map data')
   p.add_argument('grid_temp_file', help = 'path to the grid temperatures file [eg: sample.t]')
   p.add_argument('output_file', nargs='?',\
                  help = '[optional] output file [eg: out.t]')
   p.add_argument('--dist', type=str, default="gaussian",
                  help='Distribution of added noise:[gaussian or uniform]')
   p.add_argument('--delta', type=float, default=0.15,
                  help='(sigma for gauss or x in [-number,number] for uniform')
   return p

def parse_args():
   args = get_parser().parse_args()
   return args

def main():
    args = parse_args()
    grid = GridHeatmap.from_file(args.grid_temp_file)
    if args.dist == "gaussian":
        noise = GridHeatmap.gaussian_noise(args.delta,grid.width,grid.height)
    elif args.dist == "uniform":
        noise = GridHeatmap.uniform_noise(args.delta,grid.width,grid.height)
    else:
        print "Unrecognized argument for --dist: {}".format(args.dist)

    grid_noise = grid + noise
    grid_noise.write_heatmap_file(args.output_file)

if __name__ == "__main__":
   main()
