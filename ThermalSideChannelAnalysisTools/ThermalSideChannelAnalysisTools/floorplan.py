import os
import re
import errno

from copy import deepcopy
from math import floor, ceil
try:
    from StringIO import StringIO ## for Python 2
except ImportError:
    from io import StringIO ## for Python 3

from .GridHeatmap import GridHeatmap

class Floorplan(object):
   """Contains an array of FloorplanElements and a name"""

   def __init__(self, elements, name = None, preserve_offset=False):
      self.elements = elements
      self.name = name
      if not preserve_offset and len(elements) > 0:
         self.reset_to_origin()

   def reset_to_origin(self):
      self.minx = 0
      self.miny = 0

   @property
   def minx(self):
      """Returns the left-most x-coordinate in the floorplan"""
      return min([e.minx for e in self.elements])

   @minx.setter
   def minx(self, minx):
     delta = minx - self.minx
     for e in self.elements:
        e.minx += delta

   @property
   def maxx(self):
      """Returns the right-most x-coordinate in the floorplan"""
      return max([e.maxx for e in self.elements])

   @maxx.setter
   def maxx(self, maxx):
     raise AttributeError("Cannot set maxx of {}".format(self.__class__.__name__))

   @property
   def miny(self):
      """Returns the lowest y-coordinate in the floorplan"""
      return min([e.miny for e in self.elements])

   @miny.setter
   def miny(self, miny):
     delta = miny - self.miny
     for e in self.elements:
        e.miny += delta

   @property
   def maxy(self):
      """Returns the highest y-coordinate in the floorplan"""
      return max([e.maxy for e in self.elements])

   @maxy.setter
   def maxy(self, maxy):
     raise AttributeError("Cannot set maxy of {}".format(self.__class__.__name__))

   @property
   def min_element_size(self):
      """Returns the smallest dimension (width or height) of the elements in the Floorplan"""
      return min([min(e.height, e.width) for e in self.elements])

   @property
   def width(self):
      """The overall width of the floorplan"""
      return self.maxx - self.minx

   @property
   def height(self):
      """The overall height of the floorplan"""
      return self.maxy - self.miny

   @property
   def max_dim(self):
      """The max of height and width"""
      return max(self.height, self.width)

   @property
   def area(self):
      """The area of the rectangular bounding box of the floorplan"""
      return self.width * self.height

   def __mul__(self, scalar):
      """Creates a new Floorplan scaled by scalar amount in both dimensions"""
      scaled_elements = [el * scalar for el in self.elements]
      return self.__class__(scaled_elements, name = self.name)

   __rmul__ = __mul__

   def __add__(self, other):
       new_els = deepcopy(self.elements) + deepcopy(other.elements)
       return Floorplan(new_els)

   def __iadd__(self, other):
       self.elements += deepcopy(other.elements)
       return self

   def create_numbered_instance(self, n, frmt='{name}_{n:01d}'):
       new_els = deepcopy(self.elements)
       for el in new_els:
           el.name = frmt.format(name=el.name, n=n)
       return Floorplan(new_els, preserve_offset=True)

   def mirror_horizontal(self):
      for el in self.elements:
         el.minx = -1*el.width - el.minx

   def mirror_vertical(self):
      for el in self.elements:
         el.miny = -1*el.height - el.miny
      self.reset_to_origin()

   def rotate_left(self, n=1):
      for _ in range(n):
         for el in self.elements:
            el_copy = deepcopy(el)
            el.height = el_copy.width
            el.width = el_copy.height
            el.maxx = -1*el_copy.miny
            el.maxy = el_copy.maxx
      self.reset_to_origin()

   def rotate_right(self, n=1):
      for _ in range(n):
         for el in self.elements:
            el_copy = deepcopy(el)
            el.height = el_copy.width
            el.width = el_copy.height
            el.maxx = el_copy.maxy
            el.maxy = -1*el_copy.minx
      self.reset_to_origin()

   def auto_place_element(self, name, area, where='below'):
       assert where in ['below', 'right', 'left', 'above']
       if where == 'below':
           el_width = self.width
           el_height = area / el_width
           el_x = self.minx
           el_y = self.miny - el_height
       elif where == 'above':
           el_width = self.width
           el_height = area / el_width
           el_x = self.minx
           el_y = self.maxy
       elif where == 'right':
           el_height = self.height
           el_width = area / el_height
           el_y = self.miny
           el_x = self.maxx
       elif where == 'left':
           el_height = self.height
           el_width = area / el_height
           el_y = self.miny
           el_x = self.minx - el_width
       el = FloorplanElement(name, el_width, el_height, el_x, el_y)
       self.elements.append(el)

   def get_masks(self, width=64, height=64, strictly_internal = False):
      """
      Creates masks for each FloorplanElement of the specified grid size

      :param width: width of the grid
      :param height: height of the grid
      :param strictly_internal: if False: grid squares partially in the FloorplanElement are
         excluded. if True: they are included
      :type width: int, long
      :type height: int, long
      :type strictly_internal: Boolean
      :rtype: GridHeatmap[] of size len(Floorplan.elements)
      """
      return [self.get_mask(e,width,height,strictly_internal) for e in self.elements]

   def get_mask(self, el, width=64, height=64, strictly_internal = False):
      """
      Creates a single mask for a given element with the specified grid size

      :param width: width of the grid
      :param height: height of the grid
      :param strictly_internal: if False: grid squares partially in the FloorplanElement are
         excluded. if True: they are included
      :type width: int, long
      :type height: int, long
      :type strictly_internal: Boolean
      :rtype: GridHeatmap
      """
      # Get the bounds/dimesions of the FloorplanElement and the Floorplan
      el_minx , el_maxx = el.minx, el.maxx
      el_miny , el_maxy = el.miny, el.maxy
      flp_minx , flp_maxx = self.minx, self.maxx
      flp_miny , flp_maxy = self.miny, self.maxy
      flp_width = self.width
      flp_height = self.height
      # Assert that the FloorplanElement lies inside the Floorplan
      assert el_minx >= flp_minx
      assert el_maxx <= flp_maxx
      assert el_miny >= flp_miny
      assert el_maxy <= flp_maxy
      # Compute the x,y locations of the FloorplanElement on the Floorplan normalized to
      # (0.0,0.0) to (width,height)
      x1 = el_minx - flp_minx
      x2 = el_maxx - flp_minx
      y1 = el_miny - flp_miny
      y2 = el_maxy - flp_miny
      nx1 = ( x1 / flp_width ) * width
      nx2 = ( x2 / flp_width ) * width
      ny1 = ( y1 / flp_height ) * height
      ny2 = ( y2 / flp_height ) * height
      # Round up or down to include or omit partial grid tiles
      if strictly_internal:
         nx1 = ceil(nx1)
         nx2 = floor(nx2)
         ny1 = ceil(ny1)
         ny2 = floor(ny2)
      # Invert the y-values
      ny1 = height - ny1 # the new upper y-bound
      ny2 = height - ny2 # the new lower y-bound
      return GridHeatmap.create_mask(nx1,nx2,ny2,ny1,width=width,height=height,\
         name=el.name)

   def weighted_elements_heatmap(self, weights_dict, width, height, name=None, **kwargs):
      if name is None:
          name = "weighted_heatmap"
      temps = [0]*(width*height)
      hmap = GridHeatmap(name,temps,width,height)
      for el in self.elements:
         if el.name in weights_dict:
            w = weights_dict[el.name]
            hmap += self.get_mask(el, width, height, **kwargs)*w
      return hmap

   @classmethod
   def from_file(cls, flp_file, flp_name = None):
      """
      Loads a flp file

      :param flp_name: flp file name
      :param name: name for the floorplan, defaults to flp file name
      :type flp_file: string
      :type name: string
      :rtype: Floorplan

      .. note:: Line Format: <unit-name> <width> <height> <left-x> <bottom-y>. Comments begin with a
         #. Comments and lines that don't match the format above are ignored.

      .. todo:: Add support for optional [<specific-heat>] [<resistivity>] at the end of the line
      """
      # The line is name num num num num
      # Each {num} is either X or X.X, where X is at least one digit
      regex = re.compile('[^ \t\n\r\f\v#]\S*(\s+-?\d+(\.\d+)?){4}')
      elements = []
      # Read the flp file line by line
      with open(flp_file) as f:
         for line in f:
            # Match each line with the desired regex
            if regex.match(line):
               # Trim whitespace and split into tokens
               vals = line.strip("\n").split()
               # Double check that we have the correct number of tokens
               assert (len(vals) == 5), "Wrong number of tokens when loading floorplan"
               # Extract the values from the tokens
               name = vals[0]
               # [width, height, minx, miny]
               dims = [float(v) for v in vals[1:5]]
               # Create a new FloorplanElement and append it to the list
               el = FloorplanElement(name, *dims)
               elements.append(el)
      # Give it a default name if none is provided
      if flp_name == None:
         flp_name = flp_file
      return cls(elements,flp_name)

   def to_file(self, file_name=None):
      if file_name is None:
         file_name = self.name
      output = StringIO()
      for el in self.elements:
         output.write(el.frmt_for_flp_file())
      contents = output.getvalue()
      write_or_update_file(file_name, contents)


def write_or_update_file(file_name, contents, warn=True, info=False):
    if os.path.isfile(file_name):
        with open(file_name, 'r') as f:
            new_contents = f.read()
            if new_contents == contents: # the file is already up to date
                return True
            elif warn:
                print('[W] {} has outdated contents and is being overwritten.'.format(file_name))
    elif info:
        print('[I] {} is being created'.format(file_name))

    if mkdir_p(os.path.dirname(file_name)):
        print("[I] Made directory {} for file {}".format(os.path.dirname(file_name),
                                                             os.path.basename(file_name)))
    with open(file_name, 'w') as f:
        f.write(contents)
    return True

def mkdir_p(path):
   try:
      os.makedirs(path)
   except OSError as exc:
      if exc.errno == errno.EEXIST and os.path.isdir(path):
         pass
      else:
         print("Failed to make directory {}".format(path))
         raise

class FloorplanElement(object):
   """A single element on a floorplan, i.e. a rectangle with a name"""

   def __init__(self, name, width, height, minx, miny):
      self.name = name
      self.width  = width
      self.height = height
      self.minx   = minx
      self.miny   = miny

   @property
   def area(self):
      """The area of the FloorplanElement"""
      return self.width * self.height

   @area.setter
   def area(self, area):
     raise AttributeError("Cannot set area of {}".format(self.__class__.__name__))

   @property
   def maxx(self):
      """Returns the right-most x-coordinate in the FloorplanElement"""
      return self.minx + self.width

   @maxx.setter
   def maxx(self, maxx):
      self.set_maxx(maxx)

   def set_maxx(self, maxx, preserve_size = True):
      if preserve_size:
         self.minx = maxx - self.width
      else:
         delta = maxx - self.maxx
         self.width += delta

   @property
   def maxy(self):
      """Returns the highest y-coordinate in the FloorplanElement"""
      return self.miny + self.height

   @maxy.setter
   def maxy(self, maxy):
      self.set_maxy(maxy)

   def set_maxy(self, maxy, preserve_size = True):
      if preserve_size:
         self.miny = maxy - self.height
      else:
         delta = maxy - self.maxy
         self.height += delta

   def __mul__(self, scalar):
      """Returns a FloorplanElement scaled by a scalar amound in both dimensions"""
      w, h, minx, miny = scalar*self.width, scalar*self.height, scalar*self.minx, scalar*self.miny
      return self.__class__(self.name, w, h, minx, miny)

   __rmul__ = __mul__

   def frmt_for_flp_file(self):
      return "{}\t{:0.11f}\t{:0.11f}\t{:0.11f}\t{:0.11f}\n".format(self.name, self.width, self.height, self.minx, self.miny)

   def __repr__(self):
      return "{}: ({},{})-({},{})".format(self.name, self.minx, self.miny, self.maxx, self.maxy)
