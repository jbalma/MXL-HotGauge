import os
import re

#FLP_REGEX = re.compile(r'skylake(.*)nm_7core_3.*_3D-ICE_template.flp')
FLP_REGEX = re.compile(r'^skylake(\d+)nm_(?:7core|core)_3.*_3D-ICE_template\.flp$')
def get_flp_info(flp_file):
    
    #strips file path just to file name
    flp_file = os.path.basename(flp_file)

    #extract the tech node
    node = int(FLP_REGEX.match(flp_file).group(1))
    
    #return tech node
    return {'node' : node, 'node_nm' : '{}nm'.format(node)}
