# Fort Lauderdale — interactive 3D

An interactive 3D map of Fort Lauderdale, downtown to the beach.

**Live:** https://davidshulman22.github.io/ftl-3d-map/

Two renderers:

- `index.html` — the real city on Google Photorealistic 3D Tiles, wrapped in a full app: a places panel with 24 curated spots in four groups (skyline, Las Olas & the river, the legal district, beach & Intracoastal), address search, a 10-stop guided tour with story cards, per-place orbit and street-level views, and keyboard-first navigation (`↑↓` browse, `Enter` fly, `O` orbit, `T` tour, `/` search, `Esc` stop).
- `classic.html` — the hand-built Three.js model: 4,200+ extruded buildings from real OpenStreetMap footprints over USGS aerial imagery, animated boats and traffic, and a day/dusk toggle.

## Files

- `index.html` — photorealistic app (Google Maps JS API, `gmp-map-3d`)
- `classic.html` — hand-built model (Three.js via CDN import map)
- `data.js` — compact geometry baked from OpenStreetMap (generated, ~475 KB)
- `build_data.py` — regenerates `data.js` from raw Overpass API responses

## Rebuilding the data

Fetch fresh Overpass extracts for the downtown bounding box (see the query files referenced at the top of `build_data.py`), then:

```
python3 build_data.py
```

Building heights use OSM `height`/`building:levels` tags where present, then measured heights from Overture Maps (`heights.json`, LiDAR/imagery-derived, ~6,100 of 8,500 buildings), hand-patched values for known towers, and modest defaults for the remainder. Landmark positions are stylized only in color and labeling — geometry is real.

## Attribution

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, available under the Open Database License. Rendering © 2026, built with [three.js](https://threejs.org/).
