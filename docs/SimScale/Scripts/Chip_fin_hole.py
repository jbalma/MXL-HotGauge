import FreeCAD as App
import Part

doc = App.newDocument("Chip_fins_box")

total_width = 40

nfins = 15
fin_width = total_width / (2 * nfins - 1)
fin_height = 40
fin_distance = fin_width
fin_depth = 100

fin_base_width = total_width
fin_base_height = 2
fin_base_depth = fin_depth

fins = [0] * (nfins + 1)

for i in range(nfins):
    fins[i] =  Part.makeBox(fin_width, fin_height, fin_depth)
    fins[i].translate(App.Vector(i * (fin_width + fin_distance), 0, 0))

fins_total = fins[0]
for i in range(nfins - 1):
    fins_total = fins_total.fuse(fins[i + 1])

fins[nfins] = Part.makeBox(fin_base_width, fin_base_height, fin_base_depth)
fins[nfins] = fins[nfins].translate(App.Vector(0, - fin_base_height, 0))

fins_total = fins_total.fuse(fins[nfins])

base_width = 25
base_height = 2
base_depth = 50

base =  Part.makeBox(base_width, base_height, base_depth)
base.translate(App.Vector((total_width - base_width) / 2, - (fin_base_height + base_height), (fin_depth - base_depth) / 2))

chip_width = 10
chip_height = 150e-3
chip_depth = 10

chip =  Part.makeBox(chip_width, chip_height, chip_depth)
chip = chip.translate(App.Vector((total_width - chip_width) / 2, - (fin_base_height + base_height + chip_height), (fin_depth - chip_depth) / 2))

hotspot_width = 400e-3
hotspot_height = chip_height
hotspot_depth = 400e-3

hotspot = Part.makeBox(hotspot_width, hotspot_height, hotspot_depth)
hotspot = hotspot.translate(App.Vector((total_width - hotspot_width) / 2, - (fin_base_height + base_height + hotspot_height), (fin_depth - hotspot_depth) / 2))

chip = chip.cut(hotspot)

# Aggiunta al documento
obj = doc.addObject("Part::Feature", "Fins")
obj.Shape = fins_total

# Aggiunta al documento
obj = doc.addObject("Part::Feature", "Base")
obj.Shape = base

# Aggiunta al documento
obj = doc.addObject("Part::Feature", "Chip")
obj.Shape = chip

# Aggiunta al documento
obj = doc.addObject("Part::Feature", "Hotspot")
obj.Shape = hotspot

# Definizione del parallelepipedo principale
larghezza = 80  # mm
altezza = 60     # mm
profondita = 140  # mm
wall = 1
box = Part.makeBox(larghezza, altezza, profondita)

box2 = Part.makeBox(larghezza - wall, altezza - wall, profondita + 10)
box2.translate(App.Vector(0.5, 0.5,  - 5))

box = box.cut(box2)

larghezza2 = 40  # mm
altezza2 = 40     # mm
yshift = fin_base_height + base_height + chip_height

boxb = Part.makeBox(larghezza, altezza, wall)
boxb.translate(App.Vector(0, 0, profondita))

boxb2 = Part.makeBox(larghezza2, altezza2, wall)
boxb2.translate(App.Vector((larghezza - larghezza2) / 2, yshift, profondita))

boxb = boxb.cut(boxb2)

boxn = box.fuse(boxb)

boxb = Part.makeBox(larghezza, altezza, wall)
boxb.translate(App.Vector(0, 0, 0))

boxb2 = Part.makeBox(larghezza2, altezza2, wall)
boxb2.translate(App.Vector((larghezza - larghezza2) / 2, yshift, 0))

boxb = boxb.cut(boxb2)

boxn = boxn.fuse(boxb)

boxn = boxn.translate(App.Vector( - (larghezza - total_width) / 2, - (fin_base_height + base_height + chip_height),  - (profondita - fin_depth) / 2))

boxn = boxn.cut(fins_total)
boxn = boxn.cut(base)
boxn = boxn.cut(chip)
boxn = boxn.cut(hotspot)

# Aggiunta al documento
obj = doc.addObject("Part::Feature", "Box")
obj.Shape = boxn

# Aggiornamento vista
doc.recompute()