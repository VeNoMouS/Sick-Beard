import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import requests
requests.packages.urllib3.disable_warnings()
