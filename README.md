# Downtown Fort Lauderdale — interactive 3D

An interactive 3D map of downtown Fort Lauderdale rendered in the browser with Three.js. Every building footprint, street, park, and the New River come from real OpenStreetMap data — 4,200+ extruded buildings, the actual street grid, animated boats on the river, traffic on the avenues, palms on the Riverwalk, and a day/dusk lighting toggle with lit windows after dark.

**Live:** https://davidshulman22.github.io/ftl-3d-map/

## Controls

- Drag to orbit, scroll to zoom, right-drag (or shift-drag) to pan
- Click any landmark tower for details and a Google Maps link
- Preset views: Reset, Top down, Riverfront
- Dusk button switches to evening lighting

## Files

- `index.html` — the whole app (Three.js via CDN import map)
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
