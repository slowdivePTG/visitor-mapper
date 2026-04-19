import json

def generate_folium_map(records):
    """
    Generate a 3D revolving Globe.gl map showing visitor locations.
    Kept the function name `generate_folium_map` for compatibility with routes.py,
    but it now returns a fully custom Globe.gl HTML template.
    """
    html_data = []

    if records:
        grouped = {}
        current_key = None

        for lat, lon, city, country, ts in records:
            if lat is None or lon is None:
                continue
            
            c_name = city if city else "Unknown City"
            c_country = country if country else ""
            key = (c_name, c_country)

            # The first valid record we encounter is the most recent visitor
            if current_key is None:
                current_key = key

            if key not in grouped:
                grouped[key] = {
                    "lat": lat,
                    "lng": lon,
                    "city": c_name,
                    "country": c_country,
                    "count": 0,
                    "is_current": False
                }
            
            grouped[key]["count"] += 1

        if current_key in grouped:
            grouped[current_key]["is_current"] = True
            
        html_data = list(grouped.values())

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: transparent; overflow: hidden; }}
            #globeViz {{ width: 100vw; height: 100vh; }}
            .pulsing-dot {{
                background-color: #DEA193; /* Rose gold */
                border-radius: 50%;
                box-shadow: 0 0 0 rgba(222,161,147, 0.4);
                animation: pulse 2s infinite;
            }}
            .historical-dot {{
                background-color: #6D8196; /* Grey-ish blue */
                border-radius: 50%;
                box-shadow: 0 0 2px rgba(0,0,0,0.3); /* Subtle shadow to detach from globe */
            }}
            @keyframes pulse {{
                0% {{ box-shadow: 0 0 0 0 rgba(222,161,147, 0.7); }}
                70% {{ box-shadow: 0 0 0 15px rgba(222,161,147, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(222,161,147, 0); }}
            }}
            .globe-tooltip {{
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-family: sans-serif;
                font-size: 12px;
            }}
            .visitor-container {{
                position: relative;
                padding: 10px; /* Expands the hoverable hit-area for the dot */
                cursor: pointer;
            }}
            .html-tooltip {{
                visibility: hidden;
                position: absolute;
                bottom: 25px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.8);
                color: white;
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
        </style>
        <script src="https://unpkg.com/globe.gl"></script>
    </head>
    <body>
        <div id="globeViz"></div>
        <script>
            const htmlData = {json.dumps(html_data)};

            // Define a dynamic base speed that will adjust based on zoom level
            let currentBaseSpeed = 1.5;

            // 2. Initialize Globe
            const myGlobe = Globe()
                (document.getElementById('globeViz'))
                .backgroundColor('rgba(0,0,0,0)') // Fully transparent canvas!
                .showGlobe(true)
                .showAtmosphere(true) // Re-enables the 3D edge shading!
                .atmosphereColor('#8a9cb0') // Darker grey-blue shadow for deeper contrast at the edge
                .atmosphereAltitude(0.10) // Shallower atmosphere (reduced from 0.15)
                
                // All visitors (Current and Historical) rendered as flat 2D HTML elements
                .htmlElementsData(htmlData)
                .htmlElement(d => {{
                    // Logarithmic Size Scaling
                    const maxCount = Math.max(1, ...htmlData.map(x => x.count));
                    const minSize = 5;
                    const maxSize = 15;
                    let ratio = 0;
                    if (maxCount > 1) {{
                        ratio = Math.log(d.count) / Math.log(maxCount);
                    }}
                    const size = minSize + (maxSize - minSize) * ratio;

                    const el = document.createElement('div');
                    const locationText = d.country ? `${{d.city}}, ${{d.country}}` : d.city;
                    const visitorText = `${{d.count}} visitor${{d.count > 1 ? 's' : ''}}`;
                    
                    if (d.is_current) {{
                        el.innerHTML = `
                            <div class="visitor-container">
                                <div class="pulsing-dot" style="width: ${{size}}px; height: ${{size}}px;"></div>
                                <div class="html-tooltip"><b>${{locationText}}</b><br><small>Current Visitor</small><br><small>${{visitorText}}</small></div>
                            </div>
                        `;
                    }} else {{
                        el.innerHTML = `
                            <div class="visitor-container">
                                <div class="historical-dot" style="width: ${{size}}px; height: ${{size}}px;"></div>
                                <div class="html-tooltip"><b>${{locationText}}</b><br><small>${{visitorText}}</small></div>
                            </div>
                        `;
                    }}
                    
                    el.style.transform = 'translate(-50%, -50%)'; // center the dot
                    el.style.pointerEvents = 'auto'; // CRITICAL: allows the HTML element to receive mouse hover events!
                    
                    // Stop rotation when any visitor dot is hovered
                    el.onmouseenter = () => {{ myGlobe.controls().autoRotateSpeed = 0; }};
                    el.onmouseleave = () => {{ myGlobe.controls().autoRotateSpeed = currentBaseSpeed; }};
                    
                    return el;
                }});

            // Force the ocean (the globe's sphere) to emit pure flat color, ignoring all 3D shadows/lighting!
            const globeMat = myGlobe.globeMaterial();
            // Since Globe.gl uses Three.js internally, the material is a Three material.
            // By setting the emissive color (which produces light itself), the sphere becomes perfectly flat 2D!
            globeMat.color.set('#000000'); // Base color black
            globeMat.emissive.set('#f3f6f8'); 
            globeMat.emissiveIntensity = 1.0; 

            // 3. Fetch landmass GeoJSON
            // We use the countries dataset but color borders the exact same as land 
            // to completely remove political boundaries visually!
            fetch('https://unpkg.com/globe.gl/example/datasets/ne_110m_admin_0_countries.geojson')
                .then(res => res.json())
                .then(countries => {{
                    myGlobe
                        .polygonsData(countries.features)
                        .polygonCapColor(() => '#e0e0e3') // Light grey land
                        .polygonSideColor(() => '#e0e0e3')
                        .polygonStrokeColor(() => '#e0e0e3') // Same as cap color -> invisible borders!
                        .polygonAltitude(0.005);
                }})
                .catch(err => console.error("Error loading landmass data:", err));

            // 4. Auto-rotate controls
            myGlobe.controls().autoRotate = true;
            myGlobe.controls().autoRotateSpeed = currentBaseSpeed;
            
            // 5. Enable zoom and bounds
            myGlobe.controls().enableZoom = true;
            // DO NOT set minDistance / maxDistance here - Globe.gl manages its own camera bounds!
            
            // Safely monitor zoom distance without blocking the WebGL render loop!
            // Three.js OrbitControls 'change' events fire on every frame during rotation, 
            // which causes infinite loops/crashes when modifying speed inside them.
            setInterval(() => {{
                try {{
                    const pov = myGlobe.pointOfView();
                    if (pov && pov.altitude) {{
                        // pov.altitude is relative to globe radius. Default is ~2.5. Zoomed in is ~0.1.
                        // Map altitude to rotation speed: altitude 0.2 -> speed ~0.1, altitude 2.5 -> speed 1.5
                        currentBaseSpeed = Math.max(0.05, Math.min(1.5, pov.altitude * 0.6));
                        
                        // Only apply immediately if we aren't currently hovering over a halted dot
                        if (myGlobe.controls().autoRotateSpeed !== 0) {{
                            myGlobe.controls().autoRotateSpeed = currentBaseSpeed;
                        }}
                    }}
                }} catch (e) {{
                    console.warn("Globe POV not ready yet");
                }}
            }}, 100);
        </script>
    </body>
    </html>
    """
    return html_template
