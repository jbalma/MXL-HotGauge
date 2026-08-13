
import sys
from importlib import util
def load_file_as_module(name, location):
    sys.path.insert(0,location.rsplit('/', 1)[0])
    spec = util.spec_from_file_location(name, location)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
sys.argv = [ "/mnt/nfs01/scratch/jbalma/MXL-HotGauge/snipersim/scripts/energystats.py", "200000" ]
load_file_as_module("energystats","/mnt/nfs01/scratch/jbalma/MXL-HotGauge/snipersim/scripts/energystats.py")

sys.argv = [ "/mnt/nfs01/scratch/jbalma/MXL-HotGauge/snipersim/scripts/stop-by-icount.py", "100000000" ]
load_file_as_module("stop-by-icount","/mnt/nfs01/scratch/jbalma/MXL-HotGauge/snipersim/scripts/stop-by-icount.py")

