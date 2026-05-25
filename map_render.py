import json
import os

import numpy as np
from scipy.spatial import KDTree

# ---------------------------------------------------------------------------
# Module-level cache for the Fibonacci land matrix skeleton.
# Pre-computed locally; committed as land_skeleton.npz so global-land-mask
# (which uses ~200 MB RAM) never runs in the server process.
# ---------------------------------------------------------------------------

_SKELETON_PATH = os.path.join(os.path.dirname(__file__), "land_skeleton.npz")

_land_skeleton = None  # (land_lats_deg, land_lons_deg, kdtree)

# ---------------------------------------------------------------------------
# Shared globe-style config (commited alongside the repo)
# ---------------------------------------------------------------------------

_STYLE_PATH = os.path.join(
    os.path.dirname(__file__),
    "globe_style.json",
)
with open(_STYLE_PATH) as _f:
    _STYLE_CONFIG = json.load(_f)


def _get_land_skeleton():
    global _land_skeleton
    if _land_skeleton is not None:
        return _land_skeleton

    data = np.load(_SKELETON_PATH)
    land_lat = data["lat"]
    land_lon = data["lon"]

    # Build 3-D cartesian coordinates for KDTree (avoids pole distortion)
    lat_r = np.radians(land_lat)
    lon_r = np.radians(land_lon)
    cartesian = np.column_stack((
        np.cos(lat_r) * np.cos(lon_r),
        np.sin(lat_r),
        np.cos(lat_r) * np.sin(lon_r),
    ))

    tree = KDTree(cartesian)

    _land_skeleton = (land_lat, land_lon, tree)
    return _land_skeleton


# ---------------------------------------------------------------------------
# Public entry-point used by routes.py
# ---------------------------------------------------------------------------
def generate_globe_map(records):
    """Return a complete HTML page rendering a Fibonacci land-matrix globe.

    Parameters
    ----------
    records : list of (lat, lon, city, country, timestamp) tuples
        Visitor records from the database, sorted newest-first.

    Returns
    -------
    str
        Self-contained HTML with inline CSS + JS.
    """
    land_lat, land_lon, tree = _get_land_skeleton()

    # ------ Group & snap visitors to the nearest land point ------
    land_counts = {i: 0 for i in range(len(land_lat))}
    land_cities = {i: {} for i in range(len(land_lat))}
    current_visitor = None  # dict for the newest visitor's HTML overlay

    if records:
        grouped = {}
        current_key = None

        for lat, lon, city, country, _ts in records:
            if lat is None or lon is None:
                continue
            c_name = city if city else "Unknown City"
            c_country = country if country else ""
            key = (c_name, c_country)

            if current_key is None:
                current_key = key

            if key not in grouped:
                grouped[key] = {"lat": lat, "lng": lon, "count": 0}
            grouped[key]["count"] += 1

        for key, data in grouped.items():
            lat_r = np.radians(data["lat"])
            lng_r = np.radians(data["lng"])
            c_x = np.cos(lat_r) * np.cos(lng_r)
            c_y = np.sin(lat_r)
            c_z = np.cos(lat_r) * np.sin(lng_r)

            _, idx = tree.query([c_x, c_y, c_z])
            land_counts[idx] += data["count"]

            city_label = key[0]
            land_cities[idx][city_label] = land_cities[idx].get(city_label, 0) + data["count"]

            if key == current_key:
                current_visitor = {
                    "lat": float(land_lat[idx]),
                    "lng": float(land_lon[idx]),
                    "city": key[0],
                    "country": key[1],
                    "count": data["count"],
                }

    # ------ Build point-cloud array (every land cell) ------
    point_cloud = []
    for i, cnt in land_counts.items():
        cities = sorted(land_cities[i].items(), key=lambda x: x[1], reverse=True)[:3]
        point_cloud.append({
            "lat": float(land_lat[i]),
            "lon": float(land_lon[i]),
            "count": cnt,
            "cities": [{"name": c[0], "count": c[1]} for c in cities],
        })

    current_data = [current_visitor] if current_visitor else []

    return _build_html(point_cloud, current_data)


# ---------------------------------------------------------------------------
# HTML / JS template
# ---------------------------------------------------------------------------
def _build_html(point_cloud, current_data):
    pc_json = json.dumps(point_cloud)
    cv_json = json.dumps(current_data)

    sc = _STYLE_CONFIG

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Visitor Map</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: transparent; overflow: hidden; }}
#globeViz {{ width: 100vw; height: 100vh; }}
.pulsing-dot {{
    background-color: var(--current-dot);
    border-radius: 50%;
    width: 14px;
    height: 14px;
    box-shadow: 0 0 0 rgba(var(--current-dot-rgba), 0.4);
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(var(--current-dot-rgba), 0.7); }}
    70%  {{ box-shadow: 0 0 0 15px rgba(var(--current-dot-rgba), 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(var(--current-dot-rgba), 0); }}
}}
.visitor-container {{
    position: relative;
    padding: 10px;
    cursor: pointer;
}}
.html-tooltip {{
    visibility: hidden;
    position: absolute;
    bottom: 25px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--tooltip-bg);
    color: var(--tooltip-text);
    padding: 5px 10px;
    border-radius: 4px;
    font-family: sans-serif;
    font-size: 12px;
    white-space: nowrap;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s;
}}
.visitor-container:hover .html-tooltip {{
    visibility: visible;
    opacity: 1;
}}
.float-tooltip-kap {{
    background: transparent !important;
    padding: 0 !important;
    box-shadow: none !important;
    max-width: none !important;
}}
</style>
</head>
<body>
<div id="globeViz"></div>
<script type="module">
import Globe from "https://esm.sh/globe.gl";

var STYLE = {json.dumps(sc)};

var pointCloud = {pc_json};
var currentData = {cv_json};

// ---------- Catppuccin themes (same palette as citation_map) ----------
var themes = {{
    dark: {{
        bg: "rgba(30, 30, 46, 0)",
        ocean: "#1e1e2e",
        atmosphere: "#585b70",
        emptyLand: "#585b70",
        stop1: [0.4, 0.32, 0.55],
        stop2: [0.8, 0.65, 0.97],
        stop3: [0.96, 0.88, 0.86],
        tooltipBg: "#6c7086",
        tooltipText: "#11111b",
        currentDot: "#f5e0dc",
        currentDotRgba: "245, 224, 220",
    }},
    light: {{
        bg: "rgba(230, 233, 239, 0)",
        ocean: "#eff1f5",
        atmosphere: "#ccd0da",
        emptyLand: "#ccd0da",
        stop1: [0.88, 0.65, 0.6],
        stop2: [0.65, 0.45, 0.85],
        stop3: [0.35, 0.25, 0.55],
        tooltipBg: "#9ca0b0",
        tooltipText: "#e6e9ef",
        currentDot: "#8839ef",
        currentDotRgba: "136, 57, 239",
    }}
}};

var currentTheme = themes.dark;

// ---------- Colour helpers (identical to citation_map) ----------
function hexToRgb(hex) {{
    var m = /^#?([a-f\\d]{{2}})([a-f\\d]{{2}})([a-f\\d]{{2}})$/i.exec(hex);
    return m ? [
        parseInt(m[1], 16) / 255,
        parseInt(m[2], 16) / 255,
        parseInt(m[3], 16) / 255,
    ] : [1, 1, 1];
}}

function rgbToHex(r, g, b) {{
    function h(c) {{ return Math.round(c * 255).toString(16).padStart(2, "0"); }}
    return "#" + h(r) + h(g) + h(b);
}}

function interpolateColor(c1, c2, factor) {{
    return [
        c1[0] + (c2[0] - c1[0]) * factor,
        c1[1] + (c2[1] - c1[1]) * factor,
        c1[2] + (c2[2] - c1[2]) * factor,
    ];
}}

// ---------- Scale functions ----------
var maxCount = Math.max(1, ...pointCloud.map(function (d) {{ return d.count; }}));

function getColor(weight) {{
    if (weight === 0) return currentTheme.emptyLand;
    if (maxCount <= 1) return rgbToHex(currentTheme.stop1[0], currentTheme.stop1[1], currentTheme.stop1[2]);
    var factor = Math.log(weight) / Math.log(maxCount);
    var rgb;
    if (factor < 0.5) {{
        rgb = interpolateColor(currentTheme.stop1, currentTheme.stop2, factor * 2);
    }} else {{
        rgb = interpolateColor(currentTheme.stop2, currentTheme.stop3, (factor - 0.5) * 2);
    }}
    return rgbToHex(rgb[0], rgb[1], rgb[2]);
}}

function getRadius(weight) {{
    if (weight === 0) return STYLE.pointRadius.empty;
    if (maxCount <= 1) return STYLE.pointRadius.min;
    var ratio = Math.log(weight) / Math.log(maxCount);
    return STYLE.pointRadius.min + (STYLE.pointRadius.max - STYLE.pointRadius.min) * ratio;
}}

// ---------- Globe initialisation ----------
var myGlobe = Globe()(document.getElementById("globeViz"))
    .backgroundColor(currentTheme.bg)
    .showGlobe(true)
    .showAtmosphere(true)
    .atmosphereColor(currentTheme.atmosphere)
    .atmosphereAltitude(STYLE.atmosphereAltitude)

    // Layer 1 — Fibonacci land-matrix point cloud (heatmap)
    .pointsData(pointCloud)
    .pointLat("lat")
    .pointLng("lon")
    .pointRadius(function (d) {{ return getRadius(d.count); }})
    .pointAltitude(STYLE.pointAltitude)
    .pointColor(function (d) {{ return getColor(d.count); }})
    .pointResolution(STYLE.pointResolution)
    .pointLabel(function (d) {{
        if (d.count === 0) return null;
        var html = "<div style=\\"background:" + currentTheme.tooltipBg + ";color:" + currentTheme.tooltipText + ";padding:6px 10px;border-radius:6px;font-weight:500;font-size:13px;box-shadow:0 4px 6px rgba(0,0,0,0.1);line-height:1.2;\\"><b>" + d.count + " visitor" + (d.count > 1 ? "s" : "") + "</b>";
        if (d.cities && d.cities.length > 0) {{
            html += "<br/><small>";
            for (var ci = 0; ci < d.cities.length; ci++) {{
                if (ci > 0) html += "<br/>";
                html += d.cities[ci].name + " (" + d.cities[ci].count + ")";
            }}
            html += "</small>";
        }}
        return html + "</div>";
    }})
    .onPointHover(function (d) {{
        if (d) {{
            myGlobe.controls().autoRotateSpeed = 0;
        }} else {{
            myGlobe.controls().autoRotateSpeed = currentBaseSpeed;
        }}
    }})

    // Layer 2 — single HTML overlay for the pulsing current-visitor dot
    .htmlElementsData(currentData)
    .htmlLat("lat")
    .htmlLng("lng")
    .htmlElement(function (d) {{
        var el = document.createElement("div");
        var loc = d.country ? d.city + ", " + d.country : d.city;
        var vtxt = d.count + " visitor" + (d.count > 1 ? "s" : "");
        el.innerHTML =
            '<div class="visitor-container">' +
            '<div class="pulsing-dot"></div>' +
            '<div class="html-tooltip"><b>' + loc + '</b><br/><small>Current Visitor</small><br/><small>' + vtxt + '</small></div>' +
            '</div>';
        el.style.transform = "translate(-50%, -50%)";
        el.style.pointerEvents = "auto";
        el.style.zIndex = 1000;
        el.onmouseenter = function () {{ myGlobe.controls().autoRotateSpeed = 0; }};
        el.onmouseleave = function () {{ myGlobe.controls().autoRotateSpeed = currentBaseSpeed; }};
        return el;
    }});

// ---------- Globe material (flat emissive surface) ----------
setTimeout(function () {{
    try {{
        // Transparent background so parent page shows through
        myGlobe._renderer.setClearAlpha(0);
    }} catch (e) {{
        console.log("setClearAlpha not available:", e);
    }}
    var mat = myGlobe.globeMaterial();
    if (mat) {{
        mat.color.set("#000000");
        mat.emissive.set(currentTheme.ocean);
        mat.emissiveIntensity = 1.0;
        mat.roughness = 1.0;
        mat.metalness = 0.0;
    }}
}}, 100);

// ---------- Theme switching ----------
var currentBaseSpeed = STYLE.autoRotateSpeed;

function setTheme(mode) {{
    try {{
        console.log("setTheme called with mode=" + mode);
        var t = themes[mode] || themes.dark;
        currentTheme = t;

        document.documentElement.style.setProperty("--current-dot", t.currentDot);
        document.documentElement.style.setProperty("--current-dot-rgba", t.currentDotRgba);
        document.documentElement.style.setProperty("--tooltip-bg", t.tooltipBg);
        document.documentElement.style.setProperty("--tooltip-text", t.tooltipText);

        myGlobe.backgroundColor(t.bg);
        myGlobe.atmosphereColor(t.atmosphere);
        try {{
            myGlobe._renderer.setClearAlpha(0);
        }} catch (e) {{}}
        var mat = myGlobe.globeMaterial();
        if (mat) {{
            console.log("setTheme: setting emissive to " + t.ocean);
            mat.emissive.set(t.ocean);
        }} else {{
            console.log("setTheme: globeMaterial() returned null");
        }}
        myGlobe.pointColor(myGlobe.pointColor());
        myGlobe.pointLabel(myGlobe.pointLabel());
        console.log("setTheme complete");
    }} catch (e) {{
        console.error("setTheme error:", e);
    }}
}}

// Initial theme: URL param ?theme=… > system preference > dark
(function () {{
    try {{
        console.log("IIFE: initial theme detection starting");
        var params = new URLSearchParams(window.location.search);
        var mode = params.get("theme");
        if (!mode) {{
            mode = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
        }}
        console.log("IIFE: detected mode=" + mode);
        setTheme(mode);
        console.log("IIFE: setTheme called OK");
    }} catch (e) {{
        console.error("IIFE error:", e);
    }}
}})();

window.addEventListener("message", function (event) {{
    try {{
        console.log("message received:", event.data);
        if (event.data && event.data.theme) setTheme(event.data.theme);
    }} catch (e) {{
        console.error("message handler error:", e);
    }}
}});
console.log("message listener registered");

// ---------- Controls: zoom enabled, auto-rotate with speed tied to zoom ----------
try {{
    var ctrl = myGlobe.controls();
    console.log("controls() returned:", ctrl);
    if (ctrl) {{
        ctrl.autoRotate = true;
        ctrl.autoRotateSpeed = currentBaseSpeed;
        ctrl.enableZoom = true;
        console.log("controls configured: autoRotate=" + ctrl.autoRotate + " speed=" + ctrl.autoRotateSpeed);
    }} else {{
        console.log("controls() returned null/undefined");
    }}
}} catch (e) {{
    console.error("controls init error:", e);
}}

setInterval(function () {{
    try {{
        var pov = myGlobe.pointOfView();
        if (pov && pov.altitude) {{
            currentBaseSpeed = Math.max(0.05, Math.min(1.5, pov.altitude * 0.6));
            if (myGlobe.controls().autoRotateSpeed !== 0) {{
                myGlobe.controls().autoRotateSpeed = currentBaseSpeed;
            }}
        }}
    }} catch (e) {{
        console.log("rotation interval: POV not ready yet");
    }}
}}, 100);
</script>
</body>
</html>"""
