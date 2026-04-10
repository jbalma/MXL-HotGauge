#! /usr/bin/env python
import sys
import argparse
import random
from ThermalSideChannelAnalysisTools import GridHeatmap

def parse_args():
   p = argparse.ArgumentParser(description='Add NETD noise to grid thermal map data')
   p.add_argument('input_grid_file', help = 'path to the grid temperatures file [eg: sample.t]')
   p.add_argument('width', type=int, help='width of heatmap')
   p.add_argument('height', type=int, help='height of heatmap')
   p.add_argument('-o', '--out_file', help = 'path to the output grid temperatures file [eg: sample_noise.t]')
   p.add_argument('--NETD', type=float, default=0, help='(std deviation of white noise')
   p.add_argument('--seed', type=float, default=None, help='Seed for rng')

   return p.parse_args()

def main():
    args = parse_args()
    grid = GridHeatmap.from_file(args.input_grid_file, width=args.width, height=args.height)
    if args.seed is not None:
        random.seed(args.seed)
    noise = GridHeatmap.gaussian_noise(args.NETD, grid.width, grid.height)
    grid_noise = grid + noise
    print args.out_file
    if args.out_file:
        grid_noise.write_heatmap_file(args.out_file)
    else:
        grid_noise.write_heatmap_file()

if __name__ == "__main__":
   main()
