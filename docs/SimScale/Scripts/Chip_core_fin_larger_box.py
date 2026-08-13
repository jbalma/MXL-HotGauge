import FreeCAD as App
import Part

doc = App.newDocument("Chip_core_fin")

# chip

chip_width = 20
chip_height = 500e-3
chip_depth = chip_width

chip = Part.makeBox(chip_width, chip_height, chip_depth)
chip = chip.translate(App.Vector(0, 0, 0))

core_width = 2
core_height = chip_height
core_depth = core_width

ncores_row = 4
translation = (chip_width - ncores_row * core_width) / (ncores_row + 1)

cores = [0] * ncores_row * ncores_row

for i in range(ncores_row):
    for j in range(ncores_row):
        cores[i * ncores_row + j] = Part.makeBox(core_width, core_height, core_depth)
        cores[i * ncores_row + j].translate(App.Vector(translation * (i + 1) + i * core_width, 0, translation * (j + 1) + j * core_width))
        chip = chip.cut(cores[i * ncores_row + j])
        
hotspot_width = 200e-3
hotspot_height = chip_height
hotspot_depth = hotspot_width

hotspots = [0] * ncores_row * ncores_row

translation2 = (core_width - hotspot_width) / 2;

for i in range(ncores_row):
    for j in range(ncores_row):
        hotspots[i * ncores_row + j] = Part.makeBox(hotspot_width, hotspot_height, hotspot_depth)
        hotspots[i * ncores_row + j].translate(App.Vector(translation * (i + 1) + i * core_width + translation2, 0, translation * (j + 1) + j * core_width + translation2))
        cores[i * ncores_row + j] = cores[i * ncores_row + j].cut(hotspots[i * ncores_row + j])
        obj = doc.addObject("Part::Feature", "Cores")
        obj.Shape = cores[i * ncores_row + j]
        obj = doc.addObject("Part::Feature", "Hotspots")
        obj.Shape = hotspots[i * ncores_row + j]

obj = doc.addObject("Part::Feature", "Chip")
obj.Shape = chip

# base

base_width = 40
base_height = 2
base_depth = 60

base =  Part.makeBox(base_width, base_height, base_depth)
base.translate(App.Vector(- (base_width - chip_width) / 2, chip_height, - (base_depth - chip_depth) / 2))

obj = doc.addObject("Part::Feature", "Base")
obj.Shape = base

# fins

total_width = 60

nfins = 20
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

fins_total.translate(App.Vector(- chip_width / 2 - (fin_base_width - base_width) / 2, (chip_height + base_height + fin_base_height), - chip_depth - (fin_base_depth - base_depth) / 2))

obj = doc.addObject("Part::Feature", "Fins")
obj.Shape = fins_total

# air

box_width = 1.2 * total_width
box_height = 1.5 * (fin_height + fin_base_height + base_height + chip_height)
box_depth = 1.5 * fin_depth

air = Part.makeBox(box_width, box_height, box_depth)
air.translate(App.Vector(0, 0, 0))

air.translate(App.Vector(- chip_width / 2 - (box_width - base_width) / 2, 0, - chip_depth - (box_depth - base_depth) / 2))

ext_box_width = 2 * box_width 
ext_box_height = 2 * box_height
ext_box_depth = box_depth

ext_box = Part.makeBox(ext_box_width, ext_box_height, ext_box_depth)
ext_box.translate(App.Vector(0, 0, 0))

ext_box.translate(App.Vector(- chip_width / 2 - (ext_box_width - base_width) / 2, 0, - chip_depth - (ext_box_depth - base_depth) / 2))
ext_box = ext_box.cut(air)

air = air.cut(fins_total)
air = air.cut(base)
air = air.cut(chip)
for i in range(ncores_row):
    for j in range(ncores_row):
        air = air.cut(cores[i * ncores_row + j])
        air = air.cut(hotspots[i * ncores_row + j])

obj = doc.addObject("Part::Feature", "Air")
obj.Shape = air

obj = doc.addObject("Part::Feature", "External_box")
obj.Shape = ext_box

# Aggiornamento vista
doc.recompute()