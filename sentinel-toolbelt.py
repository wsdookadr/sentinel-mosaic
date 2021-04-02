import os.path
import argparse
import re
import json
import datetime as dt
from datetime import datetime, timedelta
from sentinel.mosaic import Processor

def valid_file(f):
    if os.path.exists(f) and os.path.isdir(f):
        return f
    return None

def valid_directory(f):
    if os.path.exists(f) and os.path.isfile(f):
        return f
    return None

DESCRIPTION='Tool for joining, clipping and creating mosaics from satellite images of Earth taken by Sentinel-2A and Sentinel-2B, given an initial area of interest'
parser = argparse.ArgumentParser(description=DESCRIPTION)
parser.add_argument('--auth_file', dest='auth_file', action='store', type=str, help='', required=True)
parser.add_argument('--aoi_file', dest='aoi_file', action='store', type=str, help='area of interest in GeoJSON format',required=True)
parser.add_argument('--dl_dir', dest='dl_dir', action='store', type=str, help='directory where satellite images will be downloaded', required=True)
parser.add_argument('--start_date', dest='start_date', action='store', default=None, type=str, required=False)
parser.add_argument('--end_date',   dest='end_date',   action='store', default=None, type=str, required=False)

args   = parser.parse_args()
print(args)

if args.start_date or args.end_date:
    fmt = "%Y-%m-%d"
    start_date = datetime.strptime(args.start_date, fmt)
    end_date   = datetime.strptime(args.end_date, fmt)
else:
    start_date = datetime.now() - timedelta(days=4 * 30)
    end_date   = datetime.now() - timedelta(days=10)

print("Images between ",start_date," ", end_date)


auth_info = {}
with open(args.auth_file,'r') as f:
    auth_info = json.load(f)

p = Processor(
        auth_info["user"],
        auth_info["pass"],
        start_date,
        end_date,
        args.dl_dir,
        args.aoi_file,
        debug=True,
        )

p.phase_1()
p.phase_2()
p.phase_3()
p.phase_4()
p.phase_5()
p.phase_6()
p.phase_7()
p.phase_8()
p.phase_9()
p.phase_10()


