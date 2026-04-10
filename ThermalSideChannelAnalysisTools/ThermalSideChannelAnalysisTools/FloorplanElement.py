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
