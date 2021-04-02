from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt
from datetime import date
import geopandas
from geopandas import GeoSeries
import shapely.wkt
import matplotlib.pyplot as plt
from shapely.ops import cascaded_union
import re
import os
import os.path
import zipfile
import pathlib
import rasterio
from pprint import pprint
import rasterio.merge
from rasterio.plot import show
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio.mask

def draw_granule_envelopes(L):
    print(len(L))
    fig, ax = plt.subplots(figsize = (20,16))
    L1 = [shapely.wkt.loads(x["footprint"]) for x in L]
    L2 = sorted(L1,key=lambda x: x.area,reverse=True)
    p = GeoSeries(L2)
    p.plot(ax=ax,edgecolor='k',linewidth=1)

def draw_union():
    fig, ax = plt.subplots(figsize = (20,16))
    pu = cascaded_union([shapely.wkt.loads(x["footprint"]) for x in L])
    GeoSeries(pu).plot(ax=ax,edgecolor='k',linewidth=1)

def min_cover_1(U):
    """
    This algorithm goes through all polygons and adds them to union_poly only if they're
    not already contained in union_poly.
    (in other words, we're only adding them to union_poly if they can increase the total area)
    
    performance:
    input: p1_large_ro_area.geojson with 2046 polygons
    output: 26 polygons
    time: O(n) where n is the total number of operations (intersections or unions)
    """
    whole = cascaded_union([shapely.wkt.loads(x["footprint"]) for x in U])
    union_poly = shapely.wkt.loads(U[0]["footprint"])
    union_parts = [U[0],]
    for fp in U[1:]:
        p = shapely.wkt.loads(fp["footprint"])
        common = union_poly.intersection(p)
        if p.area - common.area < 0.001:
            pass
        else:
            union_parts.append(fp)
            union_poly = union_poly.union(p)
    return union_parts

def min_cover_2(U):
    """
    This algorithm computes a minimal covering set of the entire area.
    This means we're going to eliminate some of the images. We do this
    by checking the union of all polygons before and after removing
    each image.
    If by removing the image, the total area is the same, then the image
    can be eliminated since it didn't have any contribution.
    If the area decreases by removing the image, then it can stay.

    performance:
    input: p1_large_ro_area.geojson cu 2046 poligoane
    output: 13 polygons
    time: O(n^2) because we're executing cascaded_union 2046 times, and in the best
    case we're removing one polygon for each iteration, and cascaded_union is at least
    linear so we have quadratic complexity.
    """
    whole = cascaded_union([shapely.wkt.loads(x["footprint"]) for x in U])
    L = [shapely.wkt.loads(x["footprint"]) for x in U]
    V = []
    i = 0
    j = 0
    while j < len(U):
        without = cascaded_union(L[:i] + L[i+1:])
        if whole.area - without.area < 0.001:
            L.pop(i)
        else:
            V.append(U[j])
            i += 1
        j += 1

        if j % 20 == 0:
            print(i,j,len(L))
    return V


class Processor():

    def __init__(self, sentinel_user, sentinel_pass, start_date, end_date, dl_dir, input_file, debug=False):
        self.SENTINEL_USER = sentinel_user
        self.SENTINEL_PASS = sentinel_pass
        self.DL_DIR = dl_dir
        self.INPUT_FILE = input_file
        self.START_DATE = start_date
        self.END_DATE = end_date
        self.DEBUG = debug

        if not os.path.exists(self.DL_DIR):
            os.mkdir(self.DL_DIR)

    def phase_1(self):
        self.api = SentinelAPI(self.SENTINEL_USER,self.SENTINEL_PASS)
        self.aoi_footprint = geojson_to_wkt(read_geojson(self.INPUT_FILE))

    def phase_2(self):
        self.api_products = self.api.query(
                self.aoi_footprint,
                date=(self.START_DATE, self.END_DATE),
                area_relation='Intersects',
                platformname='Sentinel-2',
                cloudcoverpercentage=(0, 30),
                )
    def phase_3(self):
        """
        We're doing the conversion from a GeoDataFrame to a list of dictionaries.
        
        After the conversion we intend to use the "footprint" and the "index" columns.

        This step is required because there are multiple products with the same footprint
        and later on we need the index in order to download the images from SentinelAPI.
        """
        
        self.product_df = self.api.to_dataframe(self.api_products)

        if len(self.product_df.index) == 0:
            raise Exception("No images for selected period")

        self.product_df = self.product_df.sort_values(['cloudcoverpercentage', 'ingestiondate'],ascending=[True, True])
        self.tile_footprints = []
        for x in self.product_df[["size","tileid","processinglevel","footprint"]].T.to_dict().items():
            self.tile_footprints.append({**x[1], "index": x[0]})

        if self.DEBUG:
            pprint(self.tile_footprints[:3])

    def phase_4(self):
        L1 = min_cover_1(self.tile_footprints)
        if self.DEBUG: print("{} tiles after the 1st reduction".format(len(L1)))
        L2 = min_cover_2(L1)
        if self.DEBUG: print("{} tiles after the 2nd reduction".format(len(L2)))
        self.reduced_footprints = L2

    def phase_5(self):
        dl_indexes = [x["index"] for x in self.reduced_footprints]
        self.api.download_all(dl_indexes,directory_path=self.DL_DIR)

        if self.DEBUG:
            pprint(dl_indexes)

    def phase_6(self):
        """
        We're decompressing the archives unless they're already decompressed.
        """
        for p in pathlib.Path(self.DL_DIR).iterdir():
            p_dir = re.sub('\.zip$','.SAFE',str(p))
            if os.path.isfile(p) and not os.path.exists(p_dir):
                extract_path = os.path.dirname(p)
                print("Dezarhivare " + str(p))
                with zipfile.ZipFile(p, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)

    def phase_7(self):
        """
        Converting the .jp2 images to .tiff
        """
        def select_files(path, pattern):
            L=[]
            for root, dirs, files in os.walk(path):
                if len(dirs) == 0:
                    for f in files:
                        if re.match(pattern,f):
                            L.append(os.path.join(root,f))
            return L

        def convert_to_tiff(paths):
            tiff_paths = []
            for p in paths:
                print("Converting " + p)
                with rasterio.open(p,mode="r") as src:
                    profile = src.meta.copy()
                    profile.update(driver="GTiff")
                    
                    outfile = re.sub(".jp2", ".tiff", p)
                    with rasterio.open(outfile, 'w', **profile) as dst:
                        dst.write(src.read())
                        tiff_paths.append(outfile)
            return tiff_paths

        self.jp2_paths  = select_files(self.DL_DIR, ".*_TCI.jp2$")
        self.tiff_paths = convert_to_tiff(self.jp2_paths)

    def phase_8(self):
        """
        We're mergin the raster images.
        """

        raster_list = [rasterio.open(f,mode='r',driver="GTiff") for f in self.tiff_paths]
        merged_data, out_trans = rasterio.merge.merge(raster_list)

        if self.DEBUG:
            fig, ax = plt.subplots(figsize = (14,14))
            show(merged_data, cmap='terrain',ax=ax)

        merged_meta = raster_list[0].meta.copy()
        merged_meta.update({"driver": "GTiff",
                            "height": merged_data.shape[1],
                            "width": merged_data.shape[2],
                            "transform": out_trans,
                            "crs": raster_list[0].crs,
                            "count": 3,
                           })
        if self.DEBUG:
            for x in [x.meta for x in raster_list] + [merged_meta]:
                pprint(x)


        self.MERGED_RAW = os.path.join(self.DL_DIR,"merged1.tiff")
        with rasterio.open(self.MERGED_RAW, mode="w", **merged_meta) as dest:
            dest.write(merged_data)


    def phase_9(self):
        """
        Reprojecting the images to  EPSG:4326
        """

        dst_crs = 'EPSG:4326'

        with rasterio.open(self.MERGED_RAW) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
            self.MERGED_4326 = os.path.join(self.DL_DIR,"merged1_4326.tiff")
            with rasterio.open(self.MERGED_4326, mode="w", **kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest)


    def phase_10(self):
        """
        We're clipping the area of interest.
        """

        with rasterio.open(self.MERGED_4326) as src:
            out_image, out_transform = rasterio.mask.mask(src, [shapely.wkt.loads(self.aoi_footprint)] , crop=True)
            out_meta = src.meta
            out_meta.update({"driver": "GTiff",
                             "height": out_image.shape[1],
                             "width": out_image.shape[2],
                             "transform": out_transform,
                            })

            self.MERGED_REGION = os.path.join(self.DL_DIR,"merged1_region.tiff")
            with rasterio.open(self.MERGED_REGION, "w", **out_meta) as dest:
                dest.write(out_image)

                if self.DEBUG:
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots(figsize = (14,14))
                    from rasterio.plot import show
                    show(out_image,cmap='terrain',ax=ax)

    def reset(self):
        """
        We're resetting object state to allow for a subsequent run.
        """
        self.aoi_footprint = None
        self.api_products = None
        self.product_df = None
        self.tile_footprints = None
        self.reduced_footprints = None
        self.jp2_paths  = None
        self.tiff_paths = None
        self.MERGED_RAW = None
        self.MERGED_4326 = None
        self.MERGED_REGION = None

