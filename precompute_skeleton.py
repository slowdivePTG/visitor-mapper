#!/usr/bin/env python3
"""One-off: generate land-skeleton binary file and commit it.

Replaces the earlier global-land-mask-based generator. Land/ocean boundaries
are now defined by precise polygons instead of a coarse raster mask, following
the strategy used for the site's atlas globes:

  - Land: standard world-map country polygons (自然资源部 GS(2016)1666 号
    standard map, converted to WGS84 GeoJSON). A point is land iff it lies
    inside a country polygon; inter-country gaps (Mediterranean, Caspian,
    Black Sea, ...) are therefore ocean.
  - Lakes: Natural Earth 1:110m lakes, subtracted so large inland water
    bodies (Great Lakes, Baikal, Victoria, ...) render as ocean too.

Requires numpy, scipy, shapely, and the two GeoJSON files alongside this file.
"""
import json
import os

import numpy as np
import shapely
from shapely.geometry import shape, Polygon

_LAND_GEOJSON = os.path.join(os.path.dirname(__file__), "world_land_boundaries.geojson")
_LAKES_GEOJSON = os.path.join(os.path.dirname(__file__), "world_lakes.geojson")


def _split_wrapping_polygon(polygon):
    """Split a polygon whose exterior ring wraps the antimeridian.

    A few countries (Russia, Antarctica) are stored as a single ring spanning
    ~360 deg of longitude, crossing the dateline. As a planar lon/lat polygon
    that ring is invalid and shapely misclassifies whole regions (e.g. a
    spurious band of ocean across eastern Siberia). Cutting the ring at the
    dateline seam yields a valid non-wrapping polygon. Non-wrapping polygons
    are returned unchanged.
    """
    coords = np.asarray(polygon.exterior.coords)
    lon_jumps = np.where(np.abs(np.diff(coords[:, 0])) > 180.0)[0]
    if len(lon_jumps) == 0:
        return [polygon]
    start, end = lon_jumps[0], lon_jumps[-1]
    indices = list(range(end + 1, len(coords))) + list(range(0, start + 1))
    body = np.vstack([coords[indices], coords[indices][0]])
    return [Polygon(body)]


def _split_antimeridian(geometry):
    """Return non-wrapping geometry pieces equivalent to ``geometry``."""
    if geometry.geom_type == "Polygon":
        return _split_wrapping_polygon(geometry)
    if geometry.geom_type == "MultiPolygon":
        pieces = []
        for part in geometry.geoms:
            pieces.extend(_split_wrapping_polygon(part))
        return pieces
    return [geometry]


def _load_boundaries():
    with open(_LAND_GEOJSON) as f:
        land_features = json.load(f)["features"]
    with open(_LAKES_GEOJSON) as f:
        lake_features = json.load(f)["features"]

    # Split any antimeridian-wrapping ring before sanitizing, otherwise
    # make_valid / union produce spurious ocean holes (e.g. eastern Siberia).
    land = shapely.union_all([
        shapely.make_valid(piece)
        for feature in land_features
        for piece in _split_antimeridian(shape(feature["geometry"]))
    ])
    lakes = shapely.union_all([
        shapely.make_valid(shape(feature["geometry"]))
        for feature in lake_features
    ])
    return land, lakes


def main():
    samples = 20000
    phi = np.pi * (3.0 - np.sqrt(5.0))
    indices = np.arange(samples)
    y = 1 - (indices / float(samples - 1)) * 2
    radius = np.sqrt(1 - y * y)
    theta = phi * indices

    lat_deg = np.degrees(np.arcsin(y))
    lon_deg = np.degrees(np.arctan2(np.sin(theta) * radius, np.cos(theta) * radius))

    land, lakes = _load_boundaries()
    points = shapely.points(lon_deg, lat_deg)
    is_land = shapely.contains(land, points) & ~shapely.contains(lakes, points)
    land_lat = lat_deg[is_land]
    land_lon = lon_deg[is_land]

    out_path = os.path.join(os.path.dirname(__file__), "land_skeleton.npz")
    np.savez_compressed(out_path, lat=land_lat, lon=land_lon)
    print(f"Saved {len(land_lat)} land points to {out_path}")


if __name__ == "__main__":
    main()
