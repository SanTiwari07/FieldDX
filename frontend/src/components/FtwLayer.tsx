import { useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";
import { leafletLayer, LineSymbolizer, PolygonSymbolizer, type Feature } from "protomaps-leaflet";

export interface PickedField {
  key: string;
  point: [number, number]; // [lng, lat] of the tap; the field is the polygon that holds it
  areaHa: number | null;
}

/** A field's identity in the tiles: its FTW id when the tiles carry one, else its rounded extent. */
function keyOf(f: Feature, layer: string): string {
  const p = f.props as Record<string, unknown>;
  const id = p.id ?? p.ftw_id ?? p.fid;
  if (id !== undefined && id !== null) return `${layer}:${String(id)}`;
  return `${layer}:${f.bbox.minX | 0},${f.bbox.minY | 0},${f.bbox.maxX | 0},${f.bbox.maxY | 0}`;
}

function haOf(f: Feature): number | null {
  const p = f.props as Record<string, unknown>;
  const a = Number(p["metrics:area"] ?? p.area ?? NaN);
  return Number.isFinite(a) ? a / 10_000 : null;
}

/**
 * The published Fields of the World field shapes for a state, drawn straight from its PMTiles on
 * Source Cooperative (only the tiles in view are fetched). In pick mode a tap toggles the field under it.
 */
export function FtwLayer({ url, layer = "2025", picking, picked, onPick }: {
  url: string;
  layer?: string;
  picking: boolean;
  picked: PickedField[];
  onPick: (f: PickedField) => void;
}) {
  const map = useMap();
  const lyr = useRef<ReturnType<typeof leafletLayer> | null>(null);
  const pickedKeys = useRef(new Set<string>());

  useEffect(() => {
    const isPicked = (_z: number, f: Feature) => pickedKeys.current.has(keyOf(f, layer));
    const l = leafletLayer({
      url,
      maxDataZoom: 13, // the FTW state tiles stop at z13; deeper zooms overzoom them
      attribution: "Fields: <a href='https://fieldsofthe.world'>Fields of the World</a> (CC-BY-4.0)",
      paintRules: [
        { dataLayer: layer, symbolizer: new PolygonSymbolizer({ fill: "#facc15", opacity: 0.12 }) },
        { dataLayer: layer, symbolizer: new LineSymbolizer({ color: "#fde047", width: (z: number) => (z >= 15 ? 0.6 : 0.9), opacity: 0.8 }) },
        { dataLayer: layer, filter: isPicked, symbolizer: new PolygonSymbolizer({ fill: "#22c55e", opacity: 0.55 }) },
        { dataLayer: layer, filter: isPicked, symbolizer: new LineSymbolizer({ color: "#ffffff", width: 2 }) },
      ],
    });
    l.addTo(map);
    lyr.current = l;
    return () => { l.remove(); lyr.current = null; };
  }, [map, url, layer]);

  useEffect(() => {
    pickedKeys.current = new Set(picked.map((p) => p.key));
    lyr.current?.rerenderTiles();
  }, [picked]);

  useMapEvents({
    click(e) {
      if (!picking || !lyr.current) return;
      const hits = lyr.current.queryTileFeaturesDebug(e.latlng.lng, e.latlng.lat, 1);
      for (const feats of hits.values()) {
        const f = feats.find((pf) => pf.layerName === layer && pf.feature.geomType === 3);
        if (f) {
          onPick({ key: keyOf(f.feature, layer), point: [e.latlng.lng, e.latlng.lat], areaHa: haOf(f.feature) });
          return;
        }
      }
    },
  });

  return null;
}
