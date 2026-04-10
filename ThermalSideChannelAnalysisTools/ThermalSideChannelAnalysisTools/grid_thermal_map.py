#!/usr/bin/env/python
#This script generates an SVG figure
#(More informaiton about SVG can be found at http://www.w3.org/TR/SVG/).
#
#Use IE or SVG Viewer to open "<filename>.svg". May need to enable XML
#in your IE.
#Use eog in Linux (there's a package for many Linux distros)
#Also, in Linux, ImageMagick 'convert' could be used to convert
#it to other file formats
#(eg `convert -font Helvetica <filename>.svg <filename>.pdf`).
#
#Run python grid_thermal_map.py --help for usage information
#
#Minimal inputs:
#	(1) A floorplan file with the same format as the other HotSpot .flp files.
#	(2) A list of grid temperatures, with the format of each line:
#      <grid_number>	<grid_temperature>
#	Example floorplan file (example.flp) and the corresponding grid
#	temperature file (example.t) are inlcuded in this release. The resulting
#	SVG figure (example.svg) is also included.
#
#Acknowledgement: The HotSpot developers would like to thank Joshua Rosenbluh
#at Grinnell College, Iowa, for his information and help on the SVG figures.
import argparse
import sys

from math import floor, log10, ceil

from ThermalSideChannelAnalysisTools import GridHeatmap, Floorplan
from ThermalSideChannelAnalysisTools.color_utils import get_color_scheme

def get_parser():
   p = argparse.ArgumentParser(description='generare SVG figure for heatmap')
   p.add_argument('flp_file', help = 'path to the file containing the floorplan [eg: ev6.flp]')
   p.add_argument('input_file', help = 'input grid temps or power trace file  [eg: sample.t, p.ptrace]')
   p.add_argument('output_file', nargs='?',\
                  help = '[optional] output file [eg: out.svg | default: stdout]')
   p.add_argument('--input_type', help='Input file type: grid(default), power_trace, avgerage_power, floorplan',
                  choices=['grid', 'power_trace', 'average_power', 'floorplan'], default='grid')
   p.add_argument('--image_width', type=int, default=None,
                  help='width of svg image[defaut: 1920, auto-computed (if height is specified)]')
   p.add_argument('--image_height', type=int, default=None,
                  help='height of svg image [default: auto computed]')
   p.add_argument('--heatmap_width', type=float, default=80.0,\
                  help='Percent of image width dedicated to the heatmap')
   p.add_argument('--heatmap_height', type=float, default=90.0,\
                  help='Percent of image height dedicated to the heatmap')
   p.add_argument('--legend_gap', type=float, default=0.5,\
                  help='Percent of image between floorplan and legend/scale')
   p.add_argument('--scale_labels', action='store_true', help='Label sub-ticks on size scale')
   p.add_argument('--scale_width', type=float, default=30,\
                  help='Percent of legend dedicated to scale (not labels) [default: 30]')
   p.add_argument('--scale_height', type=float, default=95.0,\
                  help='Percent of image height that the scale occupies [default: 95]')
   p.add_argument('-r', '--rows', type=int, default=128, \
                  help = 'no. of rows in the grid [default: 128]')
   p.add_argument('-c', '--cols', type=int, default=128,
                  help = 'no. of columns in the grid [default: 128]')
   p.add_argument('--layer_width', type=float, default=None, help='[DEPRECATED] Width of heatmap layer')
   p.add_argument('--layer_height', type=float, default=None, help='[DEPRECATED] Height of heatmap layer')
   p.add_argument('--min_t', type=float,\
                  help = 'min. temperature of the scale [defaults to min. from <input_file>]')
   p.add_argument('--max_t', type=float, \
                  help = 'max. temperature of the scale [defaults to max. from <input_file>]')
   p.add_argument('--num_levels', type=int, default=50, help = 'number of color levels[default: 50]')
   p.add_argument('--num_labels', type=int, default=10,\
                  help = 'number of labels on scale[default: 10]')
   p.add_argument('--font_size', type=float, default=None,
                  help = 'Desried font size in px[default: image_height / 15 ]')
   p.add_argument('--font_size_min', type=float, default=None,
                  help = 'Minimum font size in px[default: image_height / 150 ]')
   p.add_argument('--line_width', type=float, default=None, help = 'Line width in px')
   p.add_argument('--title', type=str, default='Temperature Map For HotSpot Grid Model',\
                  help='Title placed in svg file')
   p.add_argument('--color_scheme', type=int, action='store', default=0,\
                  help='0: default(RGB), 1: red-yl, 2: black-red-yl, 3: grayscale')
   return p

def parse_args():
   global wr
   args = get_parser().parse_args()
   # Select stdout or specified file
   if(args.output_file == None):
      args.output_file = sys.stdout
   else:
      args.output_file = open(args.output_file, 'w')
   wr = args.output_file.write

   if args.num_levels < args.num_labels:
      args.num_labels = args.num_levels
   return args

def update_layer_size(flp):
   if args.layer_width or args.layer_height:
       sys.stderr.write("[W] layer_width and layer_height are deprecated and should no longer be"\
                        " used for hotspot grid outputs; the grid maps to an area the same size as"\
                        " the floorplan and extra nodes exist outside the grid on the perihpiary "\
                        "that account for the larger layer sizes of the heatspreader and heatsink\n")

   if args.layer_width:
       assert args.layer_width >= flp.width, "Layer is not as wide as floorplan"
       offsetx = (args.layer_width - flp.width)/2.0
       args.flp_offsetx = offsetx
   else:
       args.layer_width = flp.width
       args.flp_offsetx = 0

   if args.layer_height:
       assert args.layer_height >= flp.height, "Layer is not as tall as floorplan"
       offsety = (args.layer_height - flp.height)/2.0
       args.flp_offsety = offsety
   else:
       args.layer_height = flp.height
       args.flp_offsety = 0

   global scale_factor
   scale_factor = 10**(4 - floor(log10(flp.min_element_size)))

def set_image_sizes():
   """sets image height/width and font sizes"""
   layer_aspect_ratio = (args.layer_width)/(args.layer_height)
   # If neither is given, default width is 1920, then compute the appropriate height
   if args.image_width == None and args.image_height == None:
      args.image_width = 1920

   # Compute what the height should be given the width
   if args.image_height == None:
      heatmap_pixel_width = args.image_width*(args.heatmap_width/100.0)
      # Make the heatmap aspect ratio equal to the layer_aspect ratio
      heatmap_pixel_height = heatmap_pixel_width / layer_aspect_ratio
      args.image_height = heatmap_pixel_height / (args.heatmap_height/100.0)

   # Only height was specified, compute the appropriate width
   if args.image_width == None:
      heatmap_pixel_height = args.image_height * (args.heatmap_height/100.0)
      heatmap_pixel_width = layer_aspect_ratio*heatmap_pixel_height
      args.image_width = heatmap_pixel_width / (args.heatmap_width/100.0)

   default_font_size = args.image_height / 15.0
   if args.font_size == None:
      args.font_size = default_font_size

   if args.font_size_min == None:
      args.font_size_min = default_font_size / 10.0

   if args.line_width is None:
      # by default, make the line width approx 3 px wide on 1920by1080 screen in wider direction
      if args.image_width < args.image_height:
          screen_size = 1920
      else:
          screen_size = 1080
      args.line_width = 3.0 / screen_size * min(args.image_width, args.image_height)

def update_temp_range(temps):
   # Leave the user defaults if they exist
   if (args.min_t == None):
      args.min_t = min(temps)
   if (args.max_t == None):
      args.max_t = max(temps)

def write_svg_header():
   wr('<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.0//EN"\n'
      '"http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">\n')
   wr('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{}px" height="{}px">\n'.format(args.image_width, args.image_height))
   wr('<title>{}</title>\n'.format(args.title))
   wr("<style>\n")
   for idx,p in enumerate(palette):
       color = ("rgb%s" % (p,)).replace(" ","")
       wr("\t.%s{fill:%s}\n"%(int_to_alphabet(idx),color))
   wr("</style>\n")

def draw_legend():
   if args.heatmap_width == 100:
       wr("<!-- LEGEND OMMITTED -->\n")
       return
   size_scale_height = 100.0 - args.heatmap_height - args.legend_gap
   legend_width = 100.0 - args.heatmap_width - args.legend_gap
   legend_height = args.scale_height*(100.0 - size_scale_height - args.legend_gap)/100.0
   s = '\t<svg id="legend_area" x="{}%" y="{}%" width="{}%" height="{}%">\n'
   wr( s.format( 100-legend_width ,(100.0 - args.scale_height)/2, legend_width , legend_height) )
   draw_scale()
   draw_scale_labels()
   wr('\t</svg>\n')


def draw_scale():
   s = '\t\t<svg id="scale" x="0" y="0" width="{}%" height="100%" viewBox="0 0 {} {}" '\
       'preserveAspectRatio="none">\n'
   wr(s.format(args.scale_width, scale_factor, args.num_levels * scale_factor))

   wr('\t\t\t<g id="scale_colors" transform="scale({},{})">\n'.format(scale_factor,scale_factor) )
   wr('\t\t\t\t<rect id="c" x="0" width="1" height="1"/>\n')
   for i,color in enumerate(palette):
      s = '\t\t\t\t<use xlink:href="#c" y="{}" class="{}"/>\n'
      wr(s.format(i, int_to_alphabet(i)) )
   wr('\t\t\t</g>\n')
   draw_scale_outline()
   wr('\t\t</svg>\n')

def draw_scale_outline():
   wr('\t\t\t<!-- legend outline -->\n')
   w = scale_factor*args.line_width
   scale_height = args.image_height * args.scale_height / 100.0
   widht_h = w * args.num_levels / (scale_height)
   scale_width = args.image_width*(100-args.heatmap_width-args.legend_gap)/100.0*(args.scale_width/100.0)
   widht_v = w / (scale_width)
   s = '\t\t\t<line x1="%d%%" x2="%d%%" y1="%d%%" y2="%d%%" style="fill:\
   none;stroke:black;stroke-width:%fpx"/>\n'
   wr(s % (0,100,0,0,widht_h *2) )
   wr(s % (0,100,100,100,widht_h *2) )

   wr(s % (0,0,0,100,widht_v * 2 ) )
   wr(s % (100,100,0,100,widht_v * 2 ) )

def draw_scale_labels():
   delta_t = float((args.max_t - args.min_t)) / args.num_labels
   # Compute the number of decimals to keep (location of MSB of delta_t)
   if delta_t == 0: # the whole chip is the same temperature
       num_decimals = 2
   else:
       # e.g if the step is 0.55, keep only two decimal places 0.XX
       # e.g if the step is 1.505, keep one decimal places X.X
       num_decimals = int(-floor(log10(delta_t))) + 1
       # Keep at most 2 decimals
       num_decimals = min(num_decimals, 2)
       # Keep at least 0 decimals
       num_decimals = max(num_decimals, 0)

   # format like XXX.num_decimals
   msbs = 3 + num_decimals

   labels = []
   label_format = "%.{}g".format(msbs)
   for i in range(args.num_labels):
      value = args.max_t - (i+0.5)*delta_t
      # round to the appropriate decimal place
      value = round(value,num_decimals)
      labels.append(label_format % (value))


   # adjust font size based on vetrical pixels
   scale_vertical_px = args.image_height * (args.scale_height / 100.0)
   font_size_limit = scale_vertical_px/(args.num_labels) * 1.25
   scaled_font_size = args.font_size
   if scaled_font_size > font_size_limit:
       scaled_font_size = font_size_limit

   # adjust font size based on horizontal space
   label_len = max([len(l) for l in labels])
   ### Aspect ratio of the font
   font_aspect_ratio = 0.65
   legend_text_width = args.image_width * (100.0 - args.scale_width) / 100.0 * (100.0 - args.heatmap_width -
   2*args.legend_gap) / 100.0
   if scaled_font_size * font_aspect_ratio * label_len > legend_text_width:
       scaled_font_size = legend_text_width / (font_aspect_ratio * label_len)
   if scaled_font_size < args.font_size_min:
       sys.stderr.write("WARNING: Legend font size was scaled to {}, which is below the minimum of "\
       "{}\n".format(scaled_font_size, args.font_size_min))

   wr('\t\t<svg id="scale_labels" x="%f%%" y="0" width="%f%%" height="100%%">\n' \
      % (args.scale_width,100.0-args.scale_width))
   wr('\t\t\t<g fill="black" style="font-size:{}px" text-anchor="start"'\
   ' transform="translate({},{})">\n'.format(scaled_font_size,
   args.legend_gap*args.image_width/100.0, scaled_font_size*(0.75 / 2.0 )))
   #% (scaled_font_size, scaled_font_size/(2.0)*0.9) )
   text_offset = 0
   step = 100.0 / args.num_labels

   for i, label in enumerate(labels):
      text = '\t\t\t\t<text x="{}" y="{}%">{}</text>\n'
      wr(text.format(text_offset, step*(i + 0.5) , float(label)))


   wr('\t\t\t</g>\n')
   wr('\t\t</svg>\n')

def draw_size_scale():
   if args.heatmap_height == 100:
       wr("<!-- SIZE SCALE OMMITTED -->\n")
       return
   def resize_units(size):
     power_of_ten = floor(log10(size))
     if power_of_ten <= -4:
        power, unit = 6, "um"
     elif power_of_ten <= -3:
        power, unit = 3, "mm"
     elif power_of_ten <= -1:
        power, unit = 2, "cm"
     elif power_of_ten <= 1:
        power, unit = 0, "m"
     else:
        power, unit = 0, "?m"
     return pow(10,power)*size, unit
   size_scale_height = 100.0 - args.heatmap_height - args.legend_gap
   s = '\t<svg id="size_scale_area" x="{}%" y="{}%" width="{}%" height="{}%">\n'
   wr( s.format(0,100-size_scale_height, args.heatmap_width, size_scale_height))

   wr('\t\t<g id="size_scale_lines" style="stroke: black;stroke-width:%fpx; fill: none;">\n'\
   % (args.line_width))
   line_width_as_percent = 100.0 * args.line_width / args.image_width

   line = '\t\t\t<line x1="%f%%" x2="%f%%" y1="%f%%" y2="%f%%"/>\n'

   # Draw top line from left to right for total width
   wr(line % (line_width_as_percent/2, line_width_as_percent/2, 0,100))
   wr(line % (100-line_width_as_percent/2, 100-line_width_as_percent/2, 0,100))
   wr(line % (0, 100, 50,50))
   size_in_new_units, unit_str = resize_units(flp.width)
   flp_width_str = "{:.2f}{}".format(size_in_new_units, unit_str)
   text = '\t\t\t\t<text x="%f%%" y="%f%%" text-anchor="%s" '\
   'style="font-size:%dpx;fill:black;" >%s</text>\n'
   wr(text % (50, 45, "middle", args.image_height*(size_scale_height/100)*0.45, flp_width_str))

   num_ticks = int(size_in_new_units)
   #TODO: MIN_TICK command line arg
   MIN_TICKS = 4
   if num_ticks < MIN_TICKS:
      scale_0 = 10
   else:
      scale_0 = 1
   scaled_size_in_new_units, scaled_unit_str = resize_units(flp.width/scale_0)
   num_ticks = int(scale_0*scaled_size_in_new_units)

   #TODO: MAX_TICK command line arg
   MAX_TICKS = 11
   if num_ticks <= MAX_TICKS:
       step = 1
   elif num_ticks <= MAX_TICKS*2:
       step = 2
   elif num_ticks <= MAX_TICKS*5:
       step = 5
   elif num_ticks <= MAX_TICKS*10:
       step = 10
   elif num_ticks <= MAX_TICKS*20:
       step = 20
   elif num_ticks <= MAX_TICKS*50:
       step = 50
   elif num_ticks <= MAX_TICKS*100:
       step = 100
   elif num_ticks <= MAX_TICKS*200:
       step = 200
   elif num_ticks <= MAX_TICKS*500:
       step = 500
   else:
       step = 1000
   for i in range(step,num_ticks,step):
      x_pos = (i)
      x_percent = 100 * x_pos / num_ticks
      wr(line % (x_percent, x_percent, 50, 75   ))

   #TODO: Show tick labels command line arg
      if args.scale_labels:
         label_str = "{:d}{}".format(x_pos, scaled_unit_str)
         wr(text % (x_percent, 95, "end", 20, label_str))

   wr('\t\t</g>\n')

   wr('\t</svg>\n')

def int_to_alphabet(num):
    """Converts a positive integer into a base54? string."""
    assert num >= 0
    digits = 'abcdefghijklmnopqrstuvwxyz'
    res = ''
    while not res or num > 0:
        num, i = divmod(num, len(digits))
        res = digits[i] + res
    return res

def draw_power_densities(flp, power_densities):
   s = '\t<svg id="heatmap_area" width="%f%%" viewBox="%f %f %f %f" preserveAspectRatio="xMaxYMin">\n'
   #TODO: Should the y value be flipped in sign? miny negative?
   wr(s % (args.heatmap_width, scale_factor*(flp.minx - args.flp_offsetx),
   scale_factor*(flp.miny - args.flp_offsety), scale_factor * args.layer_width , scale_factor * args.layer_height) )

   #TODO: power_density rectangles:
   draw_svg_power_densities(flp, power_densities)
   draw_floorplan(flp)
   label_floorplan(flp)

   wr('\t</svg>\n')

def draw_svg_power_densities(flp, power_densities):
   s = '\t\t<g id="heatmap_power_densities" transform="translate(%f,%f)">\n'
   wr( s % (-scale_factor*args.flp_offsetx, -scale_factor*args.flp_offsety))

   bucket_width = (args.max_t - args.min_t) / args.num_levels
   for el in flp.elements:
      t = power_densities[el.name]
      if bucket_width > 0:
         level = int((args.max_t - t) / bucket_width)
         level = max(level, 0)
         level = min(level, args.num_levels - 1)
      else:
         level = 0
      x1_ = el.minx
      x2_ = el.maxx
      y1_ = flp.maxy - el.miny
      y2_ = flp.maxy - el.maxy

      x1 = scale_factor * x1_
      x2 = scale_factor * x2_
      y1 = scale_factor * y1_
      y2 = scale_factor * y2_
      s = '\t\t\t<rect x="%f" y="%f" width="%f" height="%f" class="%s"/>\n'
      wr(s % (x1, y1 , x2-x1, y2-y1, int_to_alphabet(level)) )
   wr('\t\t</g>\n')

def draw_heatmap_area(flp, temps):
   s = '\t<svg id="heatmap_area" width="%f%%" viewBox="%f %f %f %f" preserveAspectRatio="xMaxYMin">\n'
   #TODO: Should the y value be flipped in sign? miny negative?
   wr(s % (args.heatmap_width, scale_factor*(flp.minx - args.flp_offsetx),
   scale_factor*(flp.miny - args.flp_offsety), scale_factor * args.layer_width , scale_factor * args.layer_height) )

   draw_svg_temps(temps)
   draw_floorplan(flp)
   label_floorplan(flp)

   wr('\t</svg>\n')

def draw_svg_temps(temps):
   if len(temps) == 0:
       wr("<!-- HEATMAP TEMPS OMMITTED -->\n")
       return
   def get_row_col_level(t, idx):
      if bucket_width > 0:
         level = int((args.max_t - t) / bucket_width)
         level = max(level, 0)
         level = min(level, args.num_levels - 1)
      else:
         level = 0
      row, col = int(idx//args.cols), idx % args.cols
      return row, col, level

   s = '\t\t<g id="heatmap_temps" transform="translate(%f,%f) scale(%f,%f)">\n'
   wr( s % (
      -scale_factor*args.flp_offsetx, -scale_factor*args.flp_offsety,
      scale_factor*(args.layer_width)/args.cols ,\
      scale_factor*(args.layer_height)/args.rows) )
   bucket_width = (args.max_t - args.min_t) / args.num_levels
   temp_iter = iter(temps)
   curr_temp, idx = next(temp_iter), 0
   while curr_temp is not None:
      row, col, level = get_row_col_level(curr_temp, idx)

      width = 1
      next_temp = next(temp_iter, None)
      if next_temp is None:
          next_row = row+1
      idx += 1
      while next_temp is not None:
          next_row, next_col, next_level = get_row_col_level(next_temp, idx)
          if next_row == row and next_level==level:
              width+=1
              next_temp = next(temp_iter, None)
              idx += 1
          else:
              break
      if col==0:
          wr("\t\t\t\t")
      if width==-1:
          s = '<use xlink:href="#%d" x="%d" y="%d"/>'
          wr(s % (level, col, row))
      else:
          color = ("rgb%s" % (palette[level],)).replace(" ","")
          s = '<rect x="%d" y="%d" width="%d" height="1" class="%s"/>'
          wr(s  % (col, row, width, int_to_alphabet(level)))
      if next_row==row+1:
          wr('\n')
      curr_temp = next_temp
   wr('\t\t</g>\n')

def draw_floorplan(flp):
   line_width = flp.height * (args.line_width / args.image_height) * scale_factor
   wr('\t\t<g id="floorplan_outlines" style="stroke: black;stroke-width:%fpx; fill: none;">\n'\
   % (line_width))

   line = '\t\t\t<line x1="%f" x2="%f" y1="%f" y2="%f"/>\n'
   for e in flp.elements:
      x1_ = e.minx
      x2_ = e.maxx
      y1_ = flp.maxy - e.miny
      y2_ = flp.maxy - e.maxy

      x1 = scale_factor * x1_
      x2 = scale_factor * x2_
      y1 = scale_factor * y1_
      y2 = scale_factor * y2_

      if y1_ == args.layer_height:
         y1 -= line_width / 2.0

      if y2_ == -args.flp_offsety:
         y2 += line_width / 2.0

      if x1_ == -args.flp_offsetx:
         x1 += line_width / 2.0
      if x2_ == args.layer_width:
         x2 -= line_width / 2.0

      wr(line % (x1-line_width/2.0,x2+line_width/2.0,y1,y1))
      wr(line % (x1-line_width/2.0,x2+line_width/2.0,y2,y2))
      wr(line % (x1,x1,y1+line_width/2.0,y2-line_width/2.0))
      wr(line % (x2,x2,y1+line_width/2.0,y2-line_width/2.0))
   wr('\t\t</g>\n')

def label_floorplan(flp):
   # Compute the unscaled font sizes and line_width
   font_size = args.font_size * (args.layer_height) / (args.image_height)
   font_size_min = args.font_size_min * (args.layer_height) / (args.image_height)
   font_size_vert = args.font_size * (args.layer_width) / (args.image_width*args.heatmap_width/100.0)
   width = (args.layer_height) * (args.line_width / args.image_height)

   # Scale them to fit the rest of the scaled heatmap_area
   font_size *= scale_factor
   font_size_min *= scale_factor
   font_size_vert *= scale_factor
   width *= scale_factor

   # Rescale such that the smallest font has two digits before the decimal [XX.XXXX]
   font_scale_factor = pow(10,floor(log10(font_size_min)-1))
   font_size /= font_scale_factor
   font_size_min /= font_scale_factor
   font_size_vert /= font_scale_factor
   width /= font_scale_factor

   combined_scale_factor = scale_factor / font_scale_factor
   margin_around_text = 1.0 / 4.0
   top_margin_around_text = 0.25*margin_around_text
   bot_margin_around_text = 1.75*margin_around_text

   wr('\t\t<g id="floorplan_labels" style="font-size:{0}px;stroke:black;fill:black;"\
   transform="translate({1},{2}) scale({3},{3})">\n'.format(font_size,
   font_scale_factor*(font_size_vert*margin_around_text + width /2.0), \
   font_scale_factor*(-font_size*bot_margin_around_text - width/2.0), font_scale_factor))

   for e in flp.elements:
      x1 = combined_scale_factor * ( e.minx            )
      x2 = combined_scale_factor * ( e.maxx            )
      y1 = combined_scale_factor * ( flp.maxy - e.miny )
      y2 = combined_scale_factor * ( flp.maxy - e.maxy )
      name = e.name

      # Trim the height of the font if required
      if (1 + 2*margin_around_text)*font_size > (y1-y2 - width):
         scaled_font_size = (y1-y2 -width) / (1 + 2*margin_around_text)
      else:
         scaled_font_size = font_size

      ## Aspect ratio of the font
      font_aspect_ratio = 0.65

      if font_size_vert * ((len(name))*font_aspect_ratio) > x2 - x1 - width:
         scaled_font_size_vert = (x2-x1 - width) / ((len(name))*font_aspect_ratio)
         scaled_font_size = min(scaled_font_size,scaled_font_size_vert *\
         (font_size)/(font_size_vert))

      if scaled_font_size != font_size:
         style = ' style="font-size:%fpx;" transform="translate(%f,%f)"' \
         % (scaled_font_size , -font_size_vert*margin_around_text + scaled_font_size*margin_around_text  , \
         font_size*bot_margin_around_text - scaled_font_size*bot_margin_around_text)
      else:
         style = ''

      if scaled_font_size > font_size_min:
         wr('\t\t\t<text x="%f" y="%f"%s>%s</text>\n'\
         % (x1,y1,style,name))
   wr('\t\t</g>\n')

def load_avgp(flp, avgp_file):
    powers = {}
    with open(avgp_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and line[0]=="#":
                continue
            core_name, power = line.split()
            powers[core_name] = float(power)

    power_densities = {}
    for el in flp.elements:
        if el.name  in powers:
            power = powers[el.name]
        else:
            print("[W] No power value available for {}; setting it to 0".format(el.name))
            power = 0.0
        area = el.area
        pd = power / (area * 100.0 * 100.0) # W/m^2 to W/cm^2
        power_densities[el.name] = pd
    return power_densities

def load_ptrace(flp, ptrace_file):
    with open(ptrace_file, 'r') as f:
       cores = f.readline().strip().split()
       max_powers = {c:0.0 for c in cores}
       for line in f.readlines():
           powers = line.strip().split()
           if len(powers) == 0:
               continue
           assert len(powers) == len(cores)
           for p,c in zip(powers, cores):
               p = float(p)
               max_powers[c] = max(p, max_powers[c])

    power_densities = {}
    for el in flp.elements:
        power = max_powers[el.name]
        area = el.area
        pd = power / (area * 100.0 * 100.0) # W/m^2 to W/cm^2
        power_densities[el.name] = pd
    return power_densities


if __name__ == "__main__":
   args = parse_args()
   palette = get_color_scheme(args.color_scheme, args.num_levels)

   flp = Floorplan.from_file(args.flp_file)
   update_layer_size(flp)

   if args.input_type=='grid':
       heatmap = GridHeatmap.from_file(args.input_file, width = args.cols, height = args.rows)
       update_temp_range(heatmap.temps)
   elif args.input_type=='average_power':
       power_densities = load_avgp(flp, args.input_file)
       update_temp_range(power_densities.values())
   elif args.input_type=='power_trace':
       power_densities = load_ptrace(flp, args.input_file)
       update_temp_range(power_densities.values())
   elif args.input_type=='floorplan':
      args.heatmap_width = 100
   else:
       raise Exception("[E] Unrecognized input type: {}".format(args.input_type))

   set_image_sizes()
   write_svg_header()
   if args.input_type=='grid':
       draw_heatmap_area(flp, heatmap.temps)
   elif args.input_type=='floorplan':
       draw_heatmap_area(flp, [])
   else:
       draw_power_densities(flp, power_densities)
   draw_size_scale()
   draw_legend()
   wr('</svg>\n')

   args.output_file.close()
