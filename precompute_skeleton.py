#!/usr/bin/env python3
"""One-off: generate land-skeleton binary file and commit it.

Removes the need for global-land-mask at runtime (saves ~200 MB RAM).
"""
import numpy as np
from global_land_mask import globe as land_mask_globe

samples = 20000
phi = np.pi * (3.0 - np.sqrt(5.0))
indices = np.arange(samples)
y = 1 - (indices / float(samples - 1)) * 2
radius = np.sqrt(1 - y * y)
theta = phi * indices

x = np.cos(theta) * radius
z = np.sin(theta) * radius

lat_deg = np.degrees(np.arcsin(y))
lon_deg = np.degrees(np.arctan2(z, x))

is_land = land_mask_globe.is_land(lat_deg, lon_deg)
land_lat = lat_deg[is_land]
land_lon = lon_deg[is_land]

np.savez_compressed("land_skeleton.npz", lat=land_lat, lon=land_lon)
print(f"Saved {len(land_lat)} land points to land_skeleton.npz")
