from math import ceil,floor

def get_color_scheme(scheme_num, levels):
   if   scheme_num == 0:
      palette = get_RGB_palette(levels)
   elif scheme_num == 1:
      palette = get_hot_palette(levels,False)
   elif scheme_num == 2:
      palette = get_hot_palette(levels,True)
   elif scheme_num == 3:
      palette = get_grayscale_palette(levels, 50)
   else:
      print("[W] Unrecognized color scheme[{}]. Defaulting to RGB".format(scheme_num))
      palette = get_RGB_palette(levels)
   return palette

# Generates an RGB pallette from red to blue
def get_RGB_palette(levels):
   half_len = int((levels)/2)
   qlen1 , qlen2 = int(floor(half_len/2.0)) , int(ceil(half_len/2.0))
   low = half_len*[0]
   ramp = [255 * i/(qlen2) for i in range(0,qlen2)]
   high = ((qlen1)*[255])
   p = low[:]
   p.extend(ramp)
   p.extend(high)
   p2 = p[:]
   p2.extend([255])
   p2.reverse()
   p.extend(p2)
   R = p[2*half_len : 2*half_len + levels]
   G = p[half_len:levels + half_len]
   B = p[0:levels]
   assert len(R) == levels
   assert len(G) == levels
   assert len(B) == levels
   return [(R[i],G[i],B[i]) for i in range(levels)]

# Generates an grayscale palette from white to dark(defined by R=G=V=min_val)
def get_grayscale_palette(levels, min_val = 0):
   return get_blended_palette(levels,[[255]*3,[min_val]*3 ])

def get_hot_palette(levels, include_black = True):
   colors = [(255,255,255),(200,200,0),(150,100,0),(200,0,0),(100,0,0)]
   if include_black:
      colors.append((0,0,0))
   return get_blended_palette(levels,colors)
   #get_blended_palette(args.num_levels,[(255,255,255),(255,0,0),(0,0,0)])
   #palette =\
   #get_blended_palette(args.num_levels,[(255,255,255),(255,0,0),(0,0,0)])

# Generates a blednded palette between consecutive colors in RGB_values
def get_blended_palette(levels,RGB_values):
   NBins = len(RGB_values) - 1
   binLength = int(levels / NBins)
   p=[]
   for i in range(NBins):
      # Distribute the extra levels evenly among the first bins
      if i < levels % NBins:
         n = binLength + 1
      else:
         n = binLength
      if n >= 1:
         d1 = [float(v) / (n) for v in RGB_values[i]]
         d2 = [float(v) / (n) for v in RGB_values[i+1]]
         for j in range(n):
            R = int(RGB_values[i][0] - d1[0] * (j+0.5) + d2[0] * (j+0.5))
            G = int(RGB_values[i][1] - d1[1] * (j+0.5) + d2[1] * (j+0.5))
            B = int(RGB_values[i][2] - d1[2] * (j+0.5) + d2[2] * (j+0.5))
            p.append((min(255,R),min(255,G),min(255,B)))
   assert(len(p) == levels)
   return p
