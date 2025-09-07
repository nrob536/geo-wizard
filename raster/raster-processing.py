import os
import requests
import rioxarray as rxr
from shapely.geometry import box
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from rasterio.enums import Resampling


url = "https://raw.githubusercontent.com/mapbox/rasterio/main/tests/data/RGB.byte.tif"

raster_path = "example.tif"
if not os.path.exists(raster_path):
    r = requests.get(url)
    open(raster_path, "wb").write(r.content)

# Load raster as xarray DataArray (bands, y, x)
da = rxr.open_rasterio(raster_path)

# For this demo use the first band (treat it as a single variable)
band = da.sel(band=1).squeeze()

# Ensure CRS exists -- if your file already has a CRS, skip setting it
if band.rio.crs is None:
    band.rio.write_crs("EPSG:4326", inplace=True)

# Create a simple study region polygon (replace with your shapefile/GeoJSON)
# Here: a small bbox polygon roughly matching the raster area
minx, miny, maxx, maxy = float(band.x.min()), float(band.y.min()), float(band.x.max()), float(band.y.max())
pad_x = (maxx - minx) * 0.25
pad_y = (maxy - miny) * 0.25
study_poly = gpd.GeoDataFrame({"geometry": [box(minx+pad_x, miny+pad_y, maxx-pad_x, maxy-pad_y)]}, crs=band.rio.crs)

# Reproject the raster to a common CRS for analysis (example: Web Mercator)
target_crs = "EPSG:3857"
band_reproj = band.rio.reproject(target_crs)

# Resample to a coarser resolution (e.g., ~1000 m), specify new resolution in target CRS units
# Use the current resolution to determine a sensible coarsening factor
orig_res_x, orig_res_y = abs(band_reproj.rio.resolution()[0]), abs(band_reproj.rio.resolution()[1])
new_res = (1000, 1000)  # metres in EPSG:3857
band_coarse = band_reproj.rio.reproject(
    band_reproj.rio.crs,
    shape=None,
    resolution=new_res,
    resampling=Resampling.average
)

# Clip to study region (reproject polygon into raster CRS first)
study_poly_proj = study_poly.to_crs(band_coarse.rio.crs)
band_clipped = band_coarse.rio.clip(study_poly_proj.geometry, study_poly_proj.crs, drop=True, invert=False)

# Compute simple summaries across the clipped area
data = band_clipped.values
valid = np.isfinite(data)
mean_val = float(np.nanmean(np.where(valid, data, np.nan)))
std_val = float(np.nanstd(np.where(valid, data, np.nan)))
count_valid = int(np.sum(valid))

print(f"Clipped pixels: {count_valid}, mean = {mean_val:.2f}, std = {std_val:.2f}")

# Plot
fig, ax = plt.subplots(1, 1, figsize=(6, 5))
band_clipped.plot(ax=ax, cmap="viridis")
study_poly_proj.boundary.plot(ax=ax, edgecolor="red", linewidth=1)
ax.set_title("Clipped, reprojected & resampled raster (band 1)")
plt.show()