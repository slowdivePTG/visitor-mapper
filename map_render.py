import json
import os
from datetime import datetime, timezone, timedelta

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
def generate_globe_map(records, show_current=True):
    """Return a complete HTML page rendering a Fibonacci land-matrix globe.

    Parameters
    ----------
    records : list of (lat, lon, city, country, timestamp) tuples
        Visitor records from the database, sorted newest-first.
    show_current : bool
        Whether to highlight the newest record as a pulsing "current visitor" dot.
        Set False for archival maps.

    Returns
    -------
    str
        Self-contained HTML with inline CSS + JS.
    """
    land_lat, land_lon, tree = _get_land_skeleton()

    # ------ Group & snap visitors to the nearest land point ------
    land_counts = {i: 0 for i in range(len(land_lat))}
    land_cities = {i: {} for i in range(len(land_lat))}
    
    current_data = []
    
    if records:
        grouped = {}
        active_keys = set()
        
        # cutoff time for "current visitor" (last 6 hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=6)

        for lat, lon, city, country, _ts in records:
            if lat is None or lon is None:
                continue
            c_name = city if city else "Unknown City"
            c_country = country if country else ""
            key = (c_name, c_country)

            # Ensure we can compare naive and aware datetimes if needed
            if isinstance(_ts, str):
                try:
                    # simplistic fallback if string
                    _ts = datetime.fromisoformat(_ts.replace('Z', '+00:00'))
                except ValueError:
                    _ts = datetime.min.replace(tzinfo=timezone.utc)
            
            if _ts and getattr(_ts, 'tzinfo', None) is None:
                _ts = _ts.replace(tzinfo=timezone.utc)

            if _ts is not None and _ts >= cutoff_time:
                active_keys.add(key)

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

            if show_current and key in active_keys:
                current_data.append({
                    "lat": float(land_lat[idx]),
                    "lng": float(land_lon[idx]),
                    "city": key[0],
                    "country": key[1],
                    "count": data["count"],
                })

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

    return _build_html(point_cloud, current_data)


# ---------------------------------------------------------------------------
# HTML / JS template
# ---------------------------------------------------------------------------
def _build_html(point_cloud, current_data):
    pc_json = json.dumps(point_cloud, indent=2)
    cv_json = json.dumps(current_data, indent=2)

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
    width: var(--dot-size, 18px);
    height: var(--dot-size, 18px);
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(var(--current-dot-rgba), 0.7); }}
    70%  {{ box-shadow: 0 0 0 var(--pulse-radius, 25px) rgba(var(--current-dot-rgba), 0); }}
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
import Globe from "https://esm.sh/globe.gl@2.31.0";

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
        stop1: [0.64, 0.60, 0.69],
        stop2: [0.46, 0.42, 0.53],
        stop3: [0.34, 0.29, 0.41],
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
    .onPointHover(function (d) {{}})

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
(function initGlobeMaterial(retries) {{
    var mat = myGlobe.globeMaterial();
    if (mat) {{
        mat.color.set("#000000");
        mat.emissive.set(currentTheme.ocean);
        mat.emissiveIntensity = 1.0;
        mat.roughness = 1.0;
        mat.metalness = 0.0;
        trySetClearAlpha(20);
    }} else if (retries > 0) {{
        setTimeout(function () {{ initGlobeMaterial(retries - 1); }}, 200);
    }}
}})(30);

function trySetClearAlpha(attempts) {{
    try {{
        if (myGlobe._renderer && typeof myGlobe._renderer.setClearAlpha === "function") {{
            myGlobe._renderer.setClearAlpha(0);
        }} else if (attempts > 0) {{
            setTimeout(function () {{ trySetClearAlpha(attempts - 1); }}, 200);
        }}
    }} catch (e) {{
        if (attempts > 0) {{
            setTimeout(function () {{ trySetClearAlpha(attempts - 1); }}, 200);
        }}
    }}
}}

// Pause rotation while mouse is over the globe container
var globeContainer = document.getElementById("globeViz");
globeContainer.addEventListener("mouseenter", function () {{
    myGlobe.controls().autoRotateSpeed = 0;
}});
globeContainer.addEventListener("mouseleave", function () {{
    myGlobe.controls().autoRotateSpeed = currentBaseSpeed;
}});

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
        trySetClearAlpha(20);
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
            // Scale pulsing current-visitor dot proportionally to zoom and window size
            var dot = document.querySelector(".pulsing-dot");
            if (dot) {{
                var viewScale = 2.5 / pov.altitude;
                var baseWin = Math.min(window.innerWidth, window.innerHeight);
                var winScale = Math.min(1.0, baseWin / 800.0);
                var finalScale = viewScale * winScale;
                var size = Math.max(2, Math.round(17 * finalScale));
                var pulse = Math.max(4, Math.round(23 * finalScale));
                document.documentElement.style.setProperty("--dot-size", size + "px");
                document.documentElement.style.setProperty("--pulse-radius", pulse + "px");
            }}
        }}
    }} catch (e) {{
        console.log("rotation interval: POV not ready yet");
    }}
}}, 100);
</script>
</body>
</html>"""
