"""Find the region an officer works in, and where its ready-made field boundaries live.

Place search is OpenStreetMap Nominatim: a district, taluka or village comes back with its real
boundary, which the map then locks to. The state code (ISO 3166-2, e.g. IN-MH) names the Fields of
the World partition that holds the published field polygons for that state (IN_MH.parquet and
IN_MH.pmtiles), so the officer can see real field shapes before anything is built.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from functools import lru_cache

from . import config

_lock = threading.Lock()
MIN_SPAN_DEG = 0.15  # about 16 km
_last_call = 0.0
KINDS = {"state_district": "District", "county": "District", "district": "District", "state": "State",
         "subdistrict": "Taluka", "municipality": "Town", "city": "City", "town": "Town",
         "village": "Village", "hamlet": "Village", "suburb": "Locality", "administrative": "Region"}


def _get(url: str, timeout: float = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": config.HTTP_USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _polite_get(url: str) -> bytes:
    """Nominatim allows one request a second; space calls out rather than get blocked."""
    global _last_call
    with _lock:
        wait = 1.05 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    return _get(url)


@lru_cache(maxsize=512)
def ftw_partition(country: str, subdivision: str) -> dict | None:
    """The FTW global partition for a state, or None when it has not been published."""
    if not country or not subdivision:
        return None
    code = f"{country}_{subdivision}"
    base = f"{config.FTW_GLOBAL_BASE}/admin:country_code={country}/{code}"
    try:
        req = urllib.request.Request(f"{base}.pmtiles", method="HEAD", headers={"User-Agent": config.HTTP_USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            size = int(r.headers.get("Content-Length") or 0)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    if size < 1024:  # an empty partition: the state has no predicted fields
        return None
    return {"code": code, "country": country, "parquet": f"{base}.parquet", "pmtiles": f"{base}.pmtiles",
            "layers": ["2025", "2024"]}


class NotPublished(LookupError):
    pass


_range_cache: "OrderedDict[tuple[str, str], tuple[bytes, int, str]]" = OrderedDict()
_range_bytes = 0
RANGE_CACHE_BYTES = 96 * 1024 * 1024
_cache_lock = threading.Lock()


def ftw_range(code: str, rng: str) -> tuple[bytes, int, str]:
    """One byte range of a partition's PMTiles: (bytes, total size, etag), from a small LRU cache."""
    global _range_bytes
    key = (code, rng)
    with _cache_lock:
        hit = _range_cache.get(key)
        if hit:
            _range_cache.move_to_end(key)
            return hit
    country, _, sub = code.partition("_")
    part = ftw_partition(country, sub)
    if part is None:
        raise NotPublished(code)
    req = urllib.request.Request(part["pmtiles"], headers={"User-Agent": config.HTTP_USER_AGENT, "Range": rng})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        total = int((r.headers.get("Content-Range") or "/0").rsplit("/", 1)[-1] or 0)
        etag = r.headers.get("ETag") or ""
    out = (body, total, etag)
    with _cache_lock:
        _range_cache[key] = out
        _range_bytes += len(body)
        while _range_bytes > RANGE_CACHE_BYTES and _range_cache:
            _, (old, _t, _e) = _range_cache.popitem(last=False)
            _range_bytes -= len(old)
    return out


def _round_geom(g: dict, nd: int = 5) -> dict:
    def walk(x):
        return [walk(v) for v in x] if isinstance(x, list) and x and isinstance(x[0], list) else [round(v, nd) for v in x]
    return {"type": g["type"], "coordinates": walk(g["coordinates"])}


@lru_cache(maxsize=256)
def _search(q: str) -> tuple[dict, ...]:
    params = {"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 8, "polygon_geojson": 1,
              "polygon_threshold": 0.003}
    raw = json.loads(_polite_get(f"{config.NOMINATIM_URL}?{urllib.parse.urlencode(params)}"))
    # a region to work in is a place or an administrative area, not a station or a shop
    regions = [r for r in raw if (r.get("category") or r.get("class")) in ("boundary", "place")]
    out = []
    seen = set()
    for r in regions or raw:
        addr = r.get("address", {})
        iso = addr.get("ISO3166-2-lvl4") or addr.get("ISO3166-2-lvl3") or ""
        country, _, sub = iso.partition("-")
        s, n, w, e = (float(v) for v in r["boundingbox"])
        lat, lon = float(r["lat"]), float(r["lon"])
        half = MIN_SPAN_DEG / 2  # a village is a point; give the map room to find its fields
        s, n, w, e = min(s, lat - half), max(n, lat + half), min(w, lon - half), max(e, lon + half)
        geom = r.get("geojson") or {}
        boundary = _round_geom(geom) if geom.get("type") in ("Polygon", "MultiPolygon") else None
        kind = KINDS.get(r.get("addresstype") or r.get("type"), (r.get("addresstype") or "place").replace("_", " ").capitalize())
        name = r.get("name") or r["display_name"].split(",")[0]
        key = (name, kind, round(s, 2), round(w, 2))
        if key in seen:
            continue
        seen.add(key)
        context = [p.strip() for p in r["display_name"].split(",")[1:]]
        out.append({
            "id": f"osm-{r.get('osm_type', 'x')[:1]}{r.get('osm_id')}",
            "name": name, "kind": kind,
            "context": ", ".join(c for c in context if not c.isdigit())[:120],
            "center": [lat, lon],
            "bounds": [[s, w], [n, e]],
            "boundary": boundary,
            "country": country.upper() or (addr.get("country_code") or "").upper(),
            "subdivision": sub.upper(),
        })
    return tuple(out)


@lru_cache(maxsize=2048)
def nearest_name(lat: float, lon: float) -> str:
    """The village or town nearest a point, for naming a hotspot ("around Korochi")."""
    params = {"lat": round(lat, 4), "lon": round(lon, 4), "format": "jsonv2", "zoom": 14, "addressdetails": 1}
    try:
        r = json.loads(_polite_get(f"{config.NOMINATIM_URL.rsplit('/', 1)[0]}/reverse?{urllib.parse.urlencode(params)}"))
    except (OSError, ValueError):
        return ""
    a = r.get("address", {})
    for k in ("village", "hamlet", "suburb", "town", "city", "municipality", "county"):
        if a.get(k):
            return a[k]
    return r.get("name") or ""


def search(q: str) -> list[dict]:
    q = " ".join(q.split())[:120]
    if len(q) < 2:
        return []
    return [dict(p) for p in _search(q.lower())]
