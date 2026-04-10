import re
from xml.etree import ElementTree

class EditSniperXMLFile(object):
    def __init__(self, xml_file):
        self.xml_file = SniperXMLFile(xml_file, lazy=True)
    def __enter__(self):
        self.xml_file.load()
        return self.xml_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.xml_file.save()
        self.xml_file.unload()

class SniperXMLFile(object):
    def __init__(self, xml_file, lazy=False):
        self.xml_file = xml_file
        self.loaded = False
        if not lazy:
            self.load()

    def save(self):
        self.tree.write(self.xml_file)

    def unload(self):
        if not self.loaded:
            return
        delattr(self, 'tree')
        delattr(self, 'root')
        if hasattr(self, '__VF_units'):
            delattr(self, '__VF_units')
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.tree = ElementTree.parse(self.xml_file)
        self.root = self.tree.getroot()
        self.__VF_units = None
        self.loaded = True

    @staticmethod
    def set_property_by_name(xml_root, property_name, value, singleton=False):
        matches = xml_root.findall(".//*[@name='{}']".format(property_name))
        if singleton:
            assert len(matches) == 1, 'Mutiple matches for singleton name=\'{}\''.format(property_name)
        for match in matches:
            match.attrib['value'] = str(value)

    @staticmethod
    def get_property_by_name(xml_root, property_name, singleton=False, dtype=float):
        matches = xml_root.findall(".//*[@name='{}']".format(property_name))
        if singleton:
            assert len(matches) == 1, 'Mutiple matches for singleton name=\'{}\''.format(property_name)
        return [dtype(match.attrib['value']) for match in matches]

    @property
    def _VF_units(self):
        if self.__VF_units is not None:
            return self.__VF_units
        units = []
        for child in self.root[0]:
            # Make sure the child has an id before accessing it...
            if 'id' not in child.attrib:
                continue

            # Ignore units that we don't scale V/F for
            unit = '.'.join(child.attrib['id'].split('.')[1:])
            if unit in ['mc', 'niu', 'pcie', 'flashc']:
                continue

            units.append(child)
        self.__VF_units = units
        return self.__VF_units

    def set_tech_node(self, tech_node):
        SniperXMLFile.set_property_by_name(self.root, 'core_tech_node', tech_node)

    def get_tech_node(self):
        return SniperXMLFile.get_property_by_name(self.root, 'core_tech_node')

    def set_clock_rate(self, clock_rate_MHz):
        SniperXMLFile.set_property_by_name(self.root, 'target_core_clockrate', clock_rate_MHz)
        for unit in self._VF_units:
            SniperXMLFile.set_property_by_name(unit, 'clockrate', clock_rate_MHz)
            SniperXMLFile.set_property_by_name(unit, 'clock_rate', clock_rate_MHz)

    def get_clock_rate(self):
        freqs = []
        freqs.extend(SniperXMLFile.get_property_by_name(self.root, 'target_core_clockrate'))
        for unit in self._VF_units:
            freqs.extend(SniperXMLFile.get_property_by_name(unit, 'clockrate'))
            freqs.extend(SniperXMLFile.get_property_by_name(unit, 'clock_rate'))
        return freqs

    def set_VDD(self, VDD):
        for unit in self._VF_units:
            SniperXMLFile.set_property_by_name(unit, 'vdd', VDD)

    def get_VDD(self):
        vdds = []
        for unit in self._VF_units:
            vdds.extend(SniperXMLFile.get_property_by_name(unit, 'vdd'))
        return vdds
