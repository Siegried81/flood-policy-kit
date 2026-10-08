import React, { useMemo, useState } from "react";

/**
 * An SVG choropleth drawn straight from GeoJSON — no tile provider, no API key.
 *
 * The usual reflex is Leaflet over OpenStreetMap tiles, which means the map stops
 * working the moment the venue Wi-Fi does. Projecting the polygons ourselves and
 * drawing paths costs ~60 lines and the map then renders offline, which is the
 * difference between a demo and a demo that survives the room.
 *
 * The projection is equirectangular (lon/lat scaled linearly to the viewport).
 * That is NOT an equal-area projection and would be the wrong choice for
 * *computing* anything — but nothing is computed here. Every number arrives
 * already aggregated from the server, which worked in EPSG:3035. This is purely
 * how the shapes get onto the screen.
 */

// Sequential, colourblind-safe (ColorBrewer YlOrRd). A diverging ramp would be
// wrong: exposure has a meaningful zero and no meaningful midpoint, so a
// two-ended scale would invent a threshold the data does not have.
const RAMP = ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"];
const NO_DATA = "#d9d9d9";

/** Quantile breaks, so the classes carry roughly equal counts.
 *
 * Equal-interval breaks on a long-tailed distribution — which exposure always is,
 * a few regions carrying most of it — put 95% of regions in the first class and
 * produce a map that looks uniformly empty. Quantiles show the ranking the brief
 * is actually about. Say which you used: the choice changes what the reader sees.
 */
function quantileBreaks(values, classes) {
  const sorted = [...values].filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return [];
  return Array.from({ length: classes - 1 }, (_, i) =>
    sorted[Math.floor(((i + 1) / classes) * (sorted.length - 1))]
  );
}

function colourFor(value, breaks) {
  if (!Number.isFinite(value)) return NO_DATA;
  let i = 0;
  while (i < breaks.length && value > breaks[i]) i += 1;
  return RAMP[i];
}

/** Flatten a GeoJSON geometry to arrays of [lon, lat] rings. */
function ringsOf(geometry) {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

export default function Choropleth({ geojson, values, valueKey, idKey, label }) {
  const [hover, setHover] = useState(null);

  const { paths, breaks, bounds } = useMemo(() => {
    const features = geojson?.features ?? [];
    const numbers = features.map((f) => values.get(f.properties?.[idKey]));
    const breaks = quantileBreaks(numbers, RAMP.length);

    // One pass for the extent: the viewBox has to fit the data, not a hard-coded
    // bounding box, so the same component works for Europe or for one valley.
    let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity];
    for (const feature of features) {
      for (const ring of ringsOf(feature.geometry)) {
        for (const [x, y] of ring) {
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x > maxX) maxX = x;
          if (y > maxY) maxY = y;
        }
      }
    }
    const paths = features.map((feature) => {
      const id = feature.properties?.[idKey];
      const d = ringsOf(feature.geometry)
        .map((ring) =>
          ring
            // y is negated because SVG's y axis grows downward while latitude
            // grows upward — without this the map is upside down.
            .map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(3)} ${(-y).toFixed(3)}`)
            .join(" ") + " Z"
        )
        .join(" ");
      return { id, d, value: values.get(id), name: feature.properties?.name ?? id };
    });
    return { paths, breaks, bounds: [minX, -maxY, maxX - minX, maxY - minY] };
  }, [geojson, values, idKey]);

  if (!geojson) return null;

  return (
    <figure className="choropleth">
      <svg viewBox={bounds.join(" ")} role="img" aria-label={label}>
        {paths.map((p) => (
          <path
            key={p.id}
            d={p.d}
            fill={colourFor(p.value, breaks)}
            className={hover === p.id ? "region hot" : "region"}
            onMouseEnter={() => setHover(p.id)}
            onMouseLeave={() => setHover(null)}
          >
            <title>
              {p.name}: {Number.isFinite(p.value) ? p.value.toLocaleString() : "not measured"}
            </title>
          </path>
        ))}
      </svg>
      <figcaption>
        <span className="legend">
          {RAMP.map((colour, i) => (
            <span key={colour} className="swatch" style={{ background: colour }}>
              <em>{i < breaks.length ? `≤${breaks[i].toFixed(2)}` : "max"}</em>
            </span>
          ))}
          <span className="swatch" style={{ background: NO_DATA }}>
            <em>not measured</em>
          </span>
        </span>
        {label} · quantile classes, so the map shows the ranking rather than a long
        tail. “Not measured” is a region the hazard raster does not cover — not a
        region with nobody exposed.
      </figcaption>
    </figure>
  );
}
