import { useState, useRef, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import mapboxgl from "mapbox-gl";
import MapboxGeocoder from "@mapbox/mapbox-gl-geocoder";
import "mapbox-gl/dist/mapbox-gl.css";
import "@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.css";

mapboxgl.accessToken =
  "pk.eyJ1IjoiYW1pdHJha3NoYXItY2hha3JhYm9ydHkiLCJhIjoiY21keW96bjluMDQyNTJrcjVtNzBxNzE5NyJ9.H7LQ3sYbd3lRynYROs7E5g";

// Dev: vite proxy handles /api → 127.0.0.1:8000. Prod (single-origin Space):
// relative paths. Override with VITE_API_BASE if hosting API elsewhere.
const API_BASE = import.meta.env.VITE_API_BASE || "";

// Inline SVG icons (per design guidance: use vector icons, not emoji, for
// structural/status UI). Stroke-based, inherit currentColor.
const iconBase = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};
const CalendarIcon = (p) => (
  <svg {...iconBase} {...p} aria-hidden="true">
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4M8 2v4M3 10h18" />
  </svg>
);
const ClockIcon = (p) => (
  <svg {...iconBase} {...p} aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
const PinIcon = (p) => (
  <svg {...iconBase} {...p} aria-hidden="true">
    <path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11z" />
    <circle cx="12" cy="10" r="2.5" />
  </svg>
);

// ── Markdown rendering for LLM answers ──────────────────────────────────────
const mdStyles = {
  h3: { fontSize: "1.18rem", fontWeight: 700, color: "#1b5e20", margin: "1.1rem 0 0.5rem" },
  h4: { fontSize: "1.02rem", fontWeight: 700, color: "#2e7d32", margin: "1rem 0 0.4rem" },
  section: {
    fontSize: "0.9rem",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.03em",
    color: "#1b5e20",
    margin: "1.2rem 0 0.5rem",
    paddingBottom: "0.3rem",
    borderBottom: "1px solid #d7ebdd",
  },
  p: { margin: "0 0 0.6rem", lineHeight: 1.65 },
  ul: { margin: "0 0 0.8rem", paddingLeft: "1.3rem" },
  ol: { margin: "0 0 0.8rem", paddingLeft: "1.4rem" },
  li: { margin: "0 0 0.35rem", lineHeight: 1.55 },
  code: {
    background: "#eef4f0",
    borderRadius: 4,
    padding: "0.1em 0.35em",
    fontSize: "0.9em",
    fontFamily: "ui-monospace, Menlo, Consolas, monospace",
  },
  hr: { border: 0, borderTop: "1px solid #e0e0e0", margin: "1rem 0" },
  tableWrap: {
    overflowX: "auto",
    margin: "0 0 0.9rem",
    border: "1px solid #d7ebdd",
    borderRadius: 8,
  },
  table: {
    borderCollapse: "collapse",
    width: "100%",
    fontSize: "0.88rem",
  },
  th: {
    textAlign: "left",
    padding: "0.55rem 0.75rem",
    background: "#e7f5ec",
    color: "#1b5e20",
    fontWeight: 700,
    borderBottom: "2px solid #c7e6d3",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "0.5rem 0.75rem",
    borderTop: "1px solid #eaf2ec",
    verticalAlign: "top",
    color: "#1f2937",
  },
};

const renderInline = (text, kp = "") => {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, j) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**"))
      return (
        <strong key={kp + j} style={{ color: "#1b5e20" }}>
          {part.slice(2, -2)}
        </strong>
      );
    if (part.startsWith("`") && part.endsWith("`"))
      return (
        <code key={kp + j} style={mdStyles.code}>
          {part.slice(1, -1)}
        </code>
      );
    return <span key={kp + j}>{part}</span>;
  });
};

// Parse a subset of markdown into styled React blocks. Handles ##/### headings,
// **Bold heading:** lines (the generator's section format), grouped bullet and
// numbered lists, horizontal rules, and inline bold/code.
const renderMarkdown = (md) => {
  const lines = String(md).split("\n");
  const blocks = [];
  let list = null;

  const flush = (key) => {
    if (!list) return;
    const items = list.items.map((it, ii) => (
      <li key={ii} style={mdStyles.li}>
        {renderInline(it, `${key}-${ii}-`)}
      </li>
    ));
    blocks.push(
      list.ordered ? (
        <ol key={`ol${key}`} style={mdStyles.ol}>
          {items}
        </ol>
      ) : (
        <ul key={`ul${key}`} style={mdStyles.ul}>
          {items}
        </ul>
      ),
    );
    list = null;
  };

  const parseRow = (row) => {
    let s = row.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|")) s = s.slice(0, -1);
    return s.split("|").map((c) => c.trim());
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const t = raw.trim();

    // ── Table: header row "| a | b |" + separator "|---|---|" + data rows ──
    const next = (lines[i + 1] || "").trim();
    const isSeparator =
      /^[\s:|-]+$/.test(next) && /-{2,}/.test(next) && next.includes("|");
    if (t.includes("|") && isSeparator) {
      flush(i);
      const header = parseRow(t);
      const rows = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim() !== "" && lines[j].includes("|")) {
        rows.push(parseRow(lines[j]));
        j++;
      }
      blocks.push(
        <div key={`tbl${i}`} style={mdStyles.tableWrap}>
          <table style={mdStyles.table}>
            <thead>
              <tr>
                {header.map((h, hi) => (
                  <th key={hi} style={mdStyles.th}>
                    {renderInline(h, `th${i}-${hi}-`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr
                  key={ri}
                  style={ri % 2 ? { background: "#f6faf7" } : undefined}
                >
                  {header.map((_, ci) => (
                    <td key={ci} style={mdStyles.td}>
                      {renderInline(r[ci] ?? "", `td${i}-${ri}-${ci}-`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      i = j - 1; // skip past the consumed table lines
      continue;
    }

    if (t === "") {
      flush(i);
      continue;
    }
    if (/^[-=_*]{3,}$/.test(t)) {
      flush(i);
      blocks.push(<hr key={`hr${i}`} style={mdStyles.hr} />);
      continue;
    }
    if (t.startsWith("## ")) {
      flush(i);
      blocks.push(
        <h3 key={i} style={mdStyles.h3}>
          {renderInline(t.slice(3), `${i}-`)}
        </h3>,
      );
      continue;
    }
    if (t.startsWith("### ")) {
      flush(i);
      blocks.push(
        <h4 key={i} style={mdStyles.h4}>
          {renderInline(t.slice(4), `${i}-`)}
        </h4>,
      );
      continue;
    }
    const bullet = t.match(/^[-•*]\s+(.*)$/);
    if (bullet) {
      if (!list || list.ordered) {
        flush(i);
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
      continue;
    }
    const num = t.match(/^\d+[.)]\s+(.*)$/);
    if (num) {
      if (!list || !list.ordered) {
        flush(i);
        list = { ordered: true, items: [] };
      }
      list.items.push(num[1]);
      continue;
    }
    // A line that is entirely bold (optionally emoji-prefixed) → section heading.
    const heading = t.match(/^(?:[^\w*]+\s*)?\*\*(.+?)\*\*:?$/);
    if (heading) {
      flush(i);
      blocks.push(
        <div key={i} style={mdStyles.section}>
          {heading[1].replace(/:\s*$/, "")}
        </div>,
      );
      continue;
    }
    flush(i);
    blocks.push(
      <p key={i} style={mdStyles.p}>
        {renderInline(t, `${i}-`)}
      </p>,
    );
  }

  flush("end");
  return blocks;
};

// ── Map overlay + query-region helpers ──────────────────────────────────────
// Build a GeoJSON circle polygon (km radius) around a point — used to show the
// 75 km geo-bounds region the current query draws its answers from.
const circlePolygon = (lat, lng, km, points = 64) => {
  const coords = [];
  const dLat = km / 110.574;
  const dLng = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= points; i++) {
    const theta = (i / points) * 2 * Math.PI;
    coords.push([lng + dLng * Math.cos(theta), lat + dLat * Math.sin(theta)]);
  }
  return {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [coords] },
    properties: {},
  };
};

// Per-layer analysis radius (matches backend domain-aware geo-bounds) + the
// color the query-region circle takes when that layer is selected.
const OVERLAYS = [
  { id: "soil", label: "Soil", km: 20, color: "#8a5a2b" },
  { id: "risk", label: "Risk", km: 50, color: "#c1121f" },
  { id: "weather", label: "Weather", km: 75, color: "#1d6fa5" },
];
const DEFAULT_REGION = { km: 75, color: "#2b9348" };

const haversineKm = (lat1, lon1, lat2, lon2) => {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
};

// Actual value shown on the map for each layer — no legend abstraction.
const overlayValue = (layer, p) => {
  if (layer === "weather")
    return p.temp_c != null ? `${p.temp_c}°C · ${p.humidity_pct}%` : "n/a";
  if (layer === "risk") return `Flood: ${p.flood_risk || "?"}`;
  return p.soil_productivity || "Unknown";
};

// Separate the answer body from the appended "Sources Used" section.
const splitSources = (content) => {
  for (const marker of ["**Sources Used:**", "**Sources:**", "**Sources**"]) {
    const idx = content.indexOf(marker);
    if (idx !== -1)
      return {
        body: content.slice(0, idx).trim(),
        sources: content.slice(idx + marker.length).trim(),
      };
  }
  return { body: content, sources: null };
};

export default function LandAnalyze() {
  const location = useLocation();
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const chatContainerRef = useRef(null);

  const [locationInfo, setLocationInfo] = useState(null);
  const [coords, setCoords] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(() => {
    const existingSession = location.state?.sessionData;
    return existingSession?.session_id || `session-${Date.now()}`;
  });
  const [includeLocation, setIncludeLocation] = useState(true);
  const [showThoughts, setShowThoughts] = useState(() => {
    const saved = localStorage.getItem("tm_show_thoughts");
    return saved === null ? true : saved === "true";
  });
  const [reasoningSteps, setReasoningSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState("");
  const [now, setNow] = useState(new Date());
  const [userLocation, setUserLocation] = useState({ status: "locating" });
  const [overlay, setOverlay] = useState(null); // null | 'soil' | 'risk' | 'weather'
  const [overlayLoading, setOverlayLoading] = useState(false);
  const overlayPopupRef = useRef(null);

  useEffect(() => {
    localStorage.setItem("tm_show_thoughts", String(showThoughts));
  }, [showThoughts]);

  // Live clock — tick every second.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Capture the user's own location once (independent of the selected marker).
  useEffect(() => {
    if (!navigator.geolocation) {
      setUserLocation({ status: "unavailable" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        let label = `${latitude.toFixed(3)}, ${longitude.toFixed(3)}`;
        try {
          const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${longitude},${latitude}.json?access_token=${mapboxgl.accessToken}&types=place,locality,region`;
          const res = await fetch(url);
          if (res.ok) {
            const data = await res.json();
            if (data.features && data.features.length > 0) {
              label = data.features[0].text || data.features[0].place_name || label;
            }
          }
        } catch {
          /* keep coordinate label on failure */
        }
        setUserLocation({ status: "ready", label, lat: latitude, lng: longitude });
      },
      () => setUserLocation({ status: "denied" }),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 },
    );
  }, []);

  useEffect(() => {
    const existingSession = location.state?.sessionData;
    if (
      existingSession?.chat_history &&
      existingSession.chat_history.length > 0
    ) {
      const loadedMessages = existingSession.chat_history.map((msg, index) => ({
        id: Date.now() + index,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        hasLocation: false,
      }));
      setMessages(loadedMessages);
      console.log(
        `Loaded ${loadedMessages.length} messages from session ${existingSession.session_id}`,
      );
    }
  }, [location.state]);

  const fetchLocationInfo = useCallback(async (lat, lng) => {
    try {
      const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${lng},${lat}.json?access_token=${mapboxgl.accessToken}&types=place,region,country,postcode,district,locality`;
      const res = await fetch(url);
      if (!res.ok) {
        setLocationInfo(null);
        return;
      }
      const data = await res.json();

      if (data.features && data.features.length > 0) {
        const place = data.features[0];
        const context = place.context || [];

        const getContextValue = (prefixes) => {
          for (const prefix of prefixes) {
            const item = context.find((c) => c.id && c.id.startsWith(prefix));
            if (item?.text) return item.text;
          }
          return "N/A";
        };

        const info = {
          place_name: place.place_name || place.text || "Unknown Place",
          region: getContextValue(["region", "locality"]),
          district: getContextValue(["district", "place", "locality"]),
          state: getContextValue(["region", "province", "state"]),
          country: getContextValue(["country"]),
          postcode: getContextValue(["postcode"]),
        };

        setLocationInfo(info);
        setSearchQuery(info.place_name);
      }
    } catch (err) {
      console.error("Reverse geocoding error:", err);
    }
  }, []);

  const updateMarker = useCallback(
    (coordinates, color = "#2b9348") => {
      if (!mapRef.current) return;
      if (markerRef.current) markerRef.current.remove();

      setCoords(coordinates);
      markerRef.current = new mapboxgl.Marker({ color })
        .setLngLat([coordinates.lng, coordinates.lat])
        .addTo(mapRef.current);

      mapRef.current.flyTo({
        center: [coordinates.lng, coordinates.lat],
        zoom: 13,
        essential: true,
      });

      fetchLocationInfo(coordinates.lat, coordinates.lng);
    },
    [fetchLocationInfo],
  );

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/satellite-streets-v11",
      center: [77.5946, 12.9716],
      zoom: 10,
    });

    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl(), "top-right");

    const geocoder = new MapboxGeocoder({
      accessToken: mapboxgl.accessToken,
      mapboxgl: mapboxgl,
      marker: false,
      placeholder: "Search for a city, place, or address...",
    });

    map.addControl(geocoder, "top-left");

    geocoder.on("result", (e) => {
      const { center, place_name } = e.result;
      if (center && center.length >= 2) {
        const [lng, lat] = center;
        updateMarker({ lat, lng });
        setSearchQuery(place_name);
      }
    });

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude } = pos.coords;
          updateMarker({ lat: latitude, lng: longitude }, "#66bb6a");
        },
        () => console.log("Unable to get location"),
      );
    }

    map.on("click", (e) => {
      const { lng, lat } = e.lngLat;
      updateMarker({ lat, lng });
    });

    map.on("load", () => {
      setTimeout(() => map.resize(), 300);
    });

    return () => {
      if (markerRef.current) markerRef.current.remove();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [updateMarker]);

  // ── Data overlay: fetch layer + paint colored points on the map ────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const SRC = "tm-overlay";
    const removeOverlay = () => {
      if (map.getLayer("tm-overlay-circles")) map.removeLayer("tm-overlay-circles");
      if (map.getLayer("tm-overlay-labels")) map.removeLayer("tm-overlay-labels");
      if (map.getSource(SRC)) map.removeSource(SRC);
      if (overlayPopupRef.current) {
        overlayPopupRef.current.remove();
        overlayPopupRef.current = null;
      }
    };

    if (!overlay) {
      removeOverlay();
      return;
    }

    let cancelled = false;
    setOverlayLoading(true);
    fetch(`${API_BASE}/api/map/overlay?layer=${overlay}`)
      .then((r) => r.json())
      .then((fc) => {
        if (cancelled || !mapRef.current) return;
        removeOverlay();

        // Only show data near the marker: keep features within 75 km of the
        // pin (the geo-bounds radius). No pin → nearest 5 to map center.
        let feats = (fc.features || []).filter(
          (f) => f.geometry && Array.isArray(f.geometry.coordinates),
        );
        const center = coords
          ? { lat: coords.lat, lng: coords.lng }
          : (() => {
              const c = map.getCenter();
              return { lat: c.lat, lng: c.lng };
            })();
        feats = feats
          .map((f) => ({
            ...f,
            _d: haversineKm(
              center.lat,
              center.lng,
              f.geometry.coordinates[1],
              f.geometry.coordinates[0],
            ),
          }))
          .sort((a, b) => a._d - b._d);
        const layerKm = (OVERLAYS.find((o) => o.id === overlay) || DEFAULT_REGION).km;
        const near = feats.filter((f) => f._d <= layerKm);
        feats = (near.length ? near : feats.slice(0, 5)).map((f) => ({
          type: "Feature",
          geometry: f.geometry,
          properties: {
            ...f.properties,
            // Label shows the ACTUAL value (temp, flood band, productivity),
            // so no legend is needed.
            label: f.properties.place
              ? `${f.properties.place}\n${overlayValue(overlay, f.properties)}`
              : overlayValue(overlay, f.properties),
          },
        }));

        map.addSource(SRC, {
          type: "geojson",
          data: { type: "FeatureCollection", features: feats },
        });
        map.addLayer({
          id: "tm-overlay-circles",
          type: "circle",
          source: SRC,
          paint: {
            "circle-radius": 10,
            "circle-color": ["get", "color"],
            "circle-opacity": 0.9,
            "circle-stroke-width": 2.5,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "tm-overlay-labels",
          type: "symbol",
          source: SRC,
          layout: {
            "text-field": ["get", "label"],
            "text-size": 12,
            "text-offset": [0, 1.2],
            "text-anchor": "top",
            "text-font": ["DIN Offc Pro Bold", "Arial Unicode MS Bold"],
          },
          paint: {
            "text-color": "#0d3b23",
            "text-halo-color": "#ffffff",
            "text-halo-width": 2,
          },
        });
        map.on("click", "tm-overlay-circles", (e) => {
          const f = e.features && e.features[0];
          if (!f) return;
          const p = f.properties;
          const rows = Object.entries(p)
            .filter(([k]) => k !== "color" && k !== "label")
            .map(([k, v]) => `<b>${k.replace(/_/g, " ")}:</b> ${v}`)
            .join("<br/>");
          if (overlayPopupRef.current) overlayPopupRef.current.remove();
          overlayPopupRef.current = new mapboxgl.Popup({ closeOnClick: true })
            .setLngLat(f.geometry.coordinates)
            .setHTML(`<div style="font-size:12px;line-height:1.5">${rows}</div>`)
            .addTo(map);
        });
        map.on("mouseenter", "tm-overlay-circles", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "tm-overlay-circles", () => {
          map.getCanvas().style.cursor = "";
        });
      })
      .catch((err) => console.error("Overlay load failed:", err))
      .finally(() => !cancelled && setOverlayLoading(false));

    return () => {
      cancelled = true;
    };
  }, [overlay, coords]);

  // ── Query-region highlight: 75 km geo-bounds circle around the pin ─────────
  const showQueryRegion = useCallback((lat, lng, km = DEFAULT_REGION.km, color = DEFAULT_REGION.color) => {
    const map = mapRef.current;
    if (!map) return;
    const fc = { type: "FeatureCollection", features: [circlePolygon(lat, lng, km)] };
    if (map.getSource("tm-qregion")) {
      map.getSource("tm-qregion").setData(fc);
      map.setPaintProperty("tm-qregion-fill", "fill-color", color);
      map.setPaintProperty("tm-qregion-line", "line-color", color);
    } else {
      map.addSource("tm-qregion", { type: "geojson", data: fc });
      map.addLayer({
        id: "tm-qregion-fill",
        type: "fill",
        source: "tm-qregion",
        paint: { "fill-color": color, "fill-opacity": 0.08 },
      });
      map.addLayer({
        id: "tm-qregion-line",
        type: "line",
        source: "tm-qregion",
        paint: { "line-color": color, "line-width": 2, "line-dasharray": [2, 2] },
      });
    }
    // Zoom so the whole circle is visible, scaled to its radius.
    const dLat = (km / 110.574) * 1.15;
    const dLng = (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * 1.15;
    map.fitBounds(
      [
        [lng - dLng, lat - dLat],
        [lng + dLng, lat + dLat],
      ],
      { padding: 40, duration: 1200 },
    );
  }, []);

  const clearQueryRegion = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer("tm-qregion-fill")) map.removeLayer("tm-qregion-fill");
    if (map.getLayer("tm-qregion-line")) map.removeLayer("tm-qregion-line");
    if (map.getSource("tm-qregion")) map.removeSource("tm-qregion");
  }, []);

  // Selecting a data layer re-draws the query circle in that layer's radius
  // and color (soil 20 km brown, risk 50 km red, weather 75 km blue).
  useEffect(() => {
    if (!coords) return;
    const meta = OVERLAYS.find((o) => o.id === overlay) || DEFAULT_REGION;
    showQueryRegion(coords.lat, coords.lng, meta.km, meta.color);
  }, [overlay, coords, showQueryRegion]);

  const clearSelection = useCallback(() => {
    setCoords(null);
    setLocationInfo(null);
    setSearchQuery("");
    setQuery("");
    setMessages([]);
    setError(null);
    setSessionId(`session-${Date.now()}`);
    if (markerRef.current) markerRef.current.remove();
    clearQueryRegion();
    setOverlay(null);
  }, [clearQueryRegion]);

  const renderValue = (value, indent = 0) => {
    const indentStyle = { marginLeft: `${indent * 1.5}rem` };

    if (value === null || value === undefined) {
      return <span style={{ color: "#6b7280" }}>N/A</span>;
    }

    if (typeof value === "boolean") {
      return (
        <span style={{ color: value ? "#2b9348" : "#ef4444" }}>
          {value ? "Yes" : "No"}
        </span>
      );
    }

    if (typeof value === "number") {
      return (
        <span style={{ color: "#1b5e20", fontWeight: "500" }}>{value}</span>
      );
    }

    if (typeof value === "string") {
      return <span>{value}</span>;
    }

    if (Array.isArray(value)) {
      return (
        <div style={indentStyle}>
          {value.map((item, i) => (
            <div
              key={i}
              style={{
                marginBottom: "0.5rem",
                paddingLeft: "1rem",
                borderLeft: "2px solid #c8e6c9",
              }}
            >
              {typeof item === "object" ? (
                renderValue(item, 0)
              ) : (
                <div>• {renderValue(item, 0)}</div>
              )}
            </div>
          ))}
        </div>
      );
    }

    if (typeof value === "object") {
      return (
        <div style={indentStyle}>
          {Object.entries(value).map(([key, val]) => (
            <div key={key} style={{ marginBottom: "0.5rem" }}>
              <span style={{ fontWeight: "600", color: "#2e7d32" }}>
                {key
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase())}
                :
              </span>{" "}
              {renderValue(val, 0)}
            </div>
          ))}
        </div>
      );
    }

    return <span>{String(value)}</span>;
  };

  const formatMessageContent = (content) => {
    if (!content) return null;

    try {
      // Only treat as structured JSON if it actually looks like an object,
      // otherwise fall through to the markdown renderer.
      const trimmed = content.trim();
      if (!trimmed.startsWith("{")) throw new Error("not-json");
      const parsed = JSON.parse(trimmed);

      const sectionConfig = {
        summary: {
          icon: "📋",
          color: "#1b5e20",
          bg: "#e8f5e9",
          border: "#2b9348",
        },
        location: {
          icon: "📍",
          color: "#00695c",
          bg: "#e0f2f1",
          border: "#00897b",
        },
        key_metrics: {
          icon: "📊",
          color: "#1565c0",
          bg: "#e3f2fd",
          border: "#1976d2",
        },
        environmental: {
          icon: "🌤️",
          color: "#558b2f",
          bg: "#f1f8e9",
          border: "#689f38",
        },
        infrastructure: {
          icon: "🛣️",
          color: "#4527a0",
          bg: "#ede7f6",
          border: "#5e35b1",
        },
        risks: {
          icon: "⚠️",
          color: "#e65100",
          bg: "#fff3e0",
          border: "#ef6c00",
        },
        soil: {
          icon: "🌱",
          color: "#33691e",
          bg: "#f9fbe7",
          border: "#558b2f",
        },
        strengths: {
          icon: "✅",
          color: "#2e7d32",
          bg: "#e8f5e9",
          border: "#43a047",
        },
        challenges: {
          icon: "❌",
          color: "#c62828",
          bg: "#ffebee",
          border: "#d32f2f",
        },
        recommendation: {
          icon: "🏠",
          color: "#6a1b9a",
          bg: "#f3e5f5",
          border: "#8e24aa",
        },
      };

      return (
        <div style={{ fontSize: "0.95rem", lineHeight: "1.65" }}>
          {parsed.summary && (
            <div
              style={{
                marginBottom: "1.25rem",
                padding: "1rem",
                background: sectionConfig.summary.bg,
                borderRadius: "0.5rem",
                borderLeft: `4px solid ${sectionConfig.summary.border}`,
              }}
            >
              <h3
                style={{
                  fontSize: "1.05rem",
                  fontWeight: "bold",
                  marginBottom: "0.5rem",
                  color: sectionConfig.summary.color,
                }}
              >
                {sectionConfig.summary.icon} Summary
              </h3>
              <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {parsed.summary}
              </p>
            </div>
          )}

          {Object.entries(parsed).map(([key, value]) => {
            if (key === "summary" || !value) return null;

            const config = sectionConfig[key] || {
              icon: "📌",
              color: "#388e3c",
              bg: "#f1f8f4",
              border: "#66bb6a",
            };

            return (
              <div
                key={key}
                style={{
                  marginBottom: "1.25rem",
                  padding: "0.875rem",
                  background: config.bg,
                  borderRadius: "0.5rem",
                  borderLeft: `3px solid ${config.border}`,
                }}
              >
                <h3
                  style={{
                    fontSize: "1.05rem",
                    fontWeight: "600",
                    marginBottom: "0.625rem",
                    color: config.color,
                  }}
                >
                  {config.icon}{" "}
                  {key
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (l) => l.toUpperCase())}
                </h3>
                {renderValue(value)}
              </div>
            );
          })}
        </div>
      );
    } catch {
      // Markdown answer — render body, and tuck sources into a collapsible block.
      const { body, sources } = splitSources(content);
      return (
        <div style={{ fontSize: "0.95rem", color: "#1f2937" }}>
          {renderMarkdown(body)}
          {sources && (
            <details
              style={{
                marginTop: "0.85rem",
                background: "#f6faf7",
                border: "1px solid #d7ebdd",
                borderRadius: "0.5rem",
                padding: "0.5rem 0.75rem",
              }}
            >
              <summary
                style={{
                  cursor: "pointer",
                  fontWeight: 600,
                  color: "#2e7d32",
                  fontSize: "0.85rem",
                  userSelect: "none",
                }}
              >
                📚 Sources & tools
              </summary>
              <div
                style={{
                  marginTop: "0.5rem",
                  fontSize: "0.82rem",
                  color: "#4b5563",
                }}
              >
                {renderMarkdown(sources)}
              </div>
            </details>
          )}
        </div>
      );
    }
  };

  const runAnalysis = useCallback(async () => {
    if (!query.trim()) {
      setError("Please enter a query");
      return;
    }
    if (includeLocation && !coords) {
      setError("Select a location or disable location sharing");
      return;
    }

    const userMsg = {
      id: Date.now(),
      role: "user",
      content: query.trim(),
      timestamp: new Date().toISOString(),
      hasLocation: includeLocation && coords,
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setError(null);
    setLoading(true);
    setReasoningSteps([]);
    setCurrentStep("Starting analysis…");

    // Highlight the region the answer will be drawn from (active layer's
    // radius/color if a data layer is selected).
    if (includeLocation && coords) {
      const meta = OVERLAYS.find((o) => o.id === overlay) || DEFAULT_REGION;
      showQueryRegion(coords.lat, coords.lng, meta.km, meta.color);
    }

    const assistantId = Date.now() + 1;

    try {
      // Build query string with location info if available
      let queryText = userMsg.content;
      if (includeLocation && coords && locationInfo) {
        queryText += `\n\nLocation: ${
          locationInfo.place_name || "Unknown"
        } (Lat: ${coords.lat.toFixed(6)}, Lng: ${coords.lng.toFixed(6)})`;
      }

      const response = await fetch(`${API_BASE}/api/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: queryText,
          session_id: sessionId,
          use_cache: true,
        }),
      });

      if (!response.ok || !response.body) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      // Parse the Server-Sent Events stream manually (fetch, not EventSource,
      // because this is a POST with a JSON body).
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedAnswer = "";
      const steps = [];
      let finalMeta = {};
      let assistantAdded = false;

      const upsertAssistant = () => {
        setMessages((prev) => {
          const exists = prev.some((m) => m.id === assistantId);
          if (!exists) {
            return [
              ...prev,
              {
                id: assistantId,
                role: "assistant",
                content: streamedAnswer,
                reasoning: [...steps],
                streaming: true,
                timestamp: new Date().toISOString(),
              },
            ];
          }
          return prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: streamedAnswer, reasoning: [...steps] }
              : m,
          );
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || ""; // keep the trailing partial event

        for (const chunk of chunks) {
          const dataLine = chunk
            .split("\n")
            .find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const payload = dataLine.slice(5).trim();
          if (!payload) continue;

          let evt;
          try {
            evt = JSON.parse(payload);
          } catch {
            continue;
          }

          if (evt.type === "status") {
            steps.push(evt.message);
            setReasoningSteps([...steps]);
            setCurrentStep(evt.message);
          } else if (evt.type === "token") {
            streamedAnswer += evt.content;
            setCurrentStep("Writing the answer…");
            assistantAdded = true;
            upsertAssistant();
          } else if (evt.type === "done") {
            finalMeta = evt;
          } else if (evt.type === "error") {
            throw new Error(evt.detail || "Analysis failed");
          }
        }
      }

      // Finalise the assistant message with metadata (tools, timing, cache).
      if (!assistantAdded) {
        assistantAdded = true;
        upsertAssistant();
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: streamedAnswer,
                reasoning: [...steps],
                streaming: false,
                tools_used: finalMeta.tools_used || [],
                from_cache: finalMeta.from_cache,
                processing_time: finalMeta.processing_time,
              }
            : m,
        ),
      );
      if (finalMeta.session_id) setSessionId(finalMeta.session_id);
    } catch (err) {
      console.error("Analysis error:", err);
      setError(err.message || "Analysis failed");

      const errorMsg = {
        id: Date.now(),
        role: "assistant",
        content: `❌ Error: ${err.message || "Analysis failed"}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      setCurrentStep("");
      setReasoningSteps([]);
    }
  }, [query, coords, locationInfo, includeLocation, sessionId, showQueryRegion, overlay]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const statusChip = {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    padding: "0.4rem 0.7rem",
    background: "rgba(255,255,255,0.16)",
    border: "1px solid rgba(255,255,255,0.28)",
    borderRadius: "0.5rem",
    fontSize: "0.85rem",
    fontWeight: 500,
    color: "white",
    whiteSpace: "nowrap",
    maxWidth: "220px",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        fontFamily: "system-ui, sans-serif",
        background: "#f1f8f4",
      }}
    >
      <header
        style={{
          padding: "0.85rem 1rem",
          background: "linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%)",
          color: "white",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          boxShadow: "0 2px 8px rgba(27, 94, 32, 0.2)",
        }}
      >
        <h1
          style={{
            fontSize: "1.5rem",
            fontWeight: "bold",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          🌿 TerraMind
        </h1>

        {/* Live status bar: date · time · user location */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          <div style={statusChip} aria-label="Current date">
            <CalendarIcon />
            <span>
              {now.toLocaleDateString(undefined, {
                weekday: "short",
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
          </div>
          <div style={statusChip} aria-label="Current time">
            <ClockIcon />
            <span style={{ fontVariantNumeric: "tabular-nums" }}>
              {now.toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          </div>
          <div
            style={statusChip}
            title={
              userLocation.status === "ready"
                ? `${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}`
                : "Your approximate location"
            }
            aria-label="Your location"
          >
            <PinIcon />
            <span>
              {userLocation.status === "ready"
                ? userLocation.label
                : userLocation.status === "locating"
                  ? "Locating…"
                  : userLocation.status === "denied"
                    ? "Location off"
                    : "No location"}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button
            onClick={() => setShowThoughts((v) => !v)}
            title={
              showThoughts
                ? "Hide the step-by-step reasoning"
                : "Show the step-by-step reasoning"
            }
            style={{
              padding: "0.5rem 1rem",
              background: showThoughts
                ? "rgba(255,255,255,0.22)"
                : "rgba(255,255,255,0.08)",
              color: "white",
              border: "1px solid rgba(255,255,255,0.45)",
              borderRadius: "0.5rem",
              cursor: "pointer",
              fontWeight: "500",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              transition: "background 0.2s",
            }}
          >
            <span>🧠 Thinking</span>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                padding: "0.1rem 0.45rem",
                borderRadius: "999px",
                background: showThoughts ? "#43a047" : "rgba(255,255,255,0.2)",
              }}
            >
              {showThoughts ? "ON" : "OFF"}
            </span>
          </button>
          <button
            onClick={clearSelection}
            style={{
              padding: "0.5rem 1rem",
              background: "#c62828",
              color: "white",
              border: "none",
              borderRadius: "0.5rem",
              cursor: "pointer",
              fontWeight: "500",
              transition: "background 0.2s",
            }}
            onMouseOver={(e) => (e.target.style.background = "#d32f2f")}
            onMouseOut={(e) => (e.target.style.background = "#c62828")}
          >
            Clear All
          </button>
        </div>
      </header>

      <main style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <section
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            padding: "1rem",
            borderRight: "1px solid #c8e6c9",
            background: "#ffffff",
            position: "relative",
          }}
        >
          <div
            ref={mapContainer}
            style={{
              flex: 1,
              borderRadius: "0.5rem",
              overflow: "hidden",
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            }}
          />

          {/* Data overlay switcher */}
          <div
            style={{
              position: "absolute",
              bottom: coords ? "5.4rem" : "1.6rem",
              left: "1.6rem",
              zIndex: 5,
              display: "flex",
              flexDirection: "column",
              gap: "0.4rem",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: "0.35rem",
                background: "rgba(255,255,255,0.95)",
                borderRadius: "0.5rem",
                padding: "0.35rem",
                boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              }}
            >
              {OVERLAYS.map((o) => (
                <button
                  key={o.id}
                  onClick={() => setOverlay(overlay === o.id ? null : o.id)}
                  style={{
                    padding: "0.35rem 0.7rem",
                    borderRadius: "0.4rem",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    background: overlay === o.id ? o.color : "transparent",
                    color: overlay === o.id ? "#fff" : "#2e7d32",
                  }}
                  title={`${o.label} · ${o.km} km radius`}
                >
                  {o.label}
                </button>
              ))}
              {overlayLoading && (
                <span style={{ fontSize: "0.75rem", color: "#888", alignSelf: "center", padding: "0 0.3rem" }}>
                  loading…
                </span>
              )}
            </div>
          </div>
          {coords && (
            <div
              style={{
                marginTop: "1rem",
                padding: "0.75rem",
                background: "#e8f5e9",
                borderRadius: "0.5rem",
                border: "1px solid #a5d6a7",
                color: "#1b5e20",
              }}
            >
              <strong>📍 Selected:</strong> {searchQuery} •{" "}
              {coords.lat.toFixed(6)}, {coords.lng.toFixed(6)}
            </div>
          )}
        </section>

        <section
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            padding: "1rem",
            background: "#ffffff",
          }}
        >
          <div
            ref={chatContainerRef}
            style={{
              flex: 1,
              overflowY: "auto",
              marginBottom: "1rem",
              padding: "1rem",
              background: "#fafafa",
              borderRadius: "0.5rem",
              border: "1px solid #e0e0e0",
            }}
          >
            {messages.length === 0 && (
              <div
                style={{
                  textAlign: "center",
                  color: "#558b2f",
                  padding: "2rem",
                }}
              >
                <h3
                  style={{
                    color: "#2e7d32",
                    fontSize: "1.5rem",
                    marginBottom: "1rem",
                  }}
                >
                  Welcome to TerraMind! 🌍
                </h3>
                <p style={{ marginBottom: "0.5rem" }}>
                  Select a location on the map and ask questions about the land,
                  terrain, or geography.
                </p>
                <p
                  style={{
                    fontSize: "0.875rem",
                    marginTop: "1rem",
                    color: "#7cb342",
                  }}
                >
                  💡 Tip: Toggle location sharing below to include coordinates
                  with your query
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  marginBottom: "1rem",
                  display: "flex",
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "1rem",
                    borderRadius: "0.75rem",
                    background:
                      m.role === "user"
                        ? "linear-gradient(135deg, #2b9348 0%, #43a047 100%)"
                        : "#f1f8f4",
                    color: m.role === "user" ? "white" : "#1b5e20",
                    boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                  }}
                >
                  {m.role === "user" && (
                    <>
                      {m.content}
                      {m.hasLocation && (
                        <div
                          style={{
                            marginTop: "0.5rem",
                            fontSize: "0.875rem",
                            opacity: 0.9,
                          }}
                        >
                          📍 Location included
                        </div>
                      )}
                    </>
                  )}
                  {m.role === "assistant" && (
                    <>
                      {showThoughts &&
                        m.reasoning &&
                        m.reasoning.length > 0 && (
                          <details
                            style={{
                              marginBottom: "0.75rem",
                              background: "#ffffff",
                              border: "1px solid #c8e6c9",
                              borderRadius: "0.5rem",
                              padding: "0.5rem 0.75rem",
                            }}
                          >
                            <summary
                              style={{
                                cursor: "pointer",
                                fontWeight: 600,
                                color: "#2e7d32",
                                fontSize: "0.85rem",
                                userSelect: "none",
                              }}
                            >
                              🧠 Thought process ({m.reasoning.length} steps)
                            </summary>
                            <ol
                              style={{
                                margin: "0.5rem 0 0",
                                paddingLeft: "1.25rem",
                                color: "#558b2f",
                                fontSize: "0.85rem",
                                lineHeight: 1.6,
                              }}
                            >
                              {m.reasoning.map((step, i) => (
                                <li key={i}>{step}</li>
                              ))}
                            </ol>
                          </details>
                        )}
                      {m.content && formatMessageContent(m.content)}
                      {m.streaming && (
                        <span
                          style={{
                            display: "inline-block",
                            width: "8px",
                            height: "1em",
                            marginLeft: "2px",
                            background: "#2b9348",
                            verticalAlign: "text-bottom",
                            animation: "blink 1s step-start infinite",
                          }}
                        />
                      )}
                      {m.tools_used && m.tools_used.length > 0 && (
                        <div
                          style={{
                            marginTop: "1rem",
                            paddingTop: "0.75rem",
                            borderTop: "1px solid #c8e6c9",
                            fontSize: "0.875rem",
                            color: "#558b2f",
                          }}
                        >
                          <strong>🔧 Tools used:</strong>{" "}
                          {m.tools_used.join(", ")}
                          {m.from_cache && " • 📦 From cache"}
                          {m.processing_time &&
                            ` • ⏱️ ${m.processing_time.toFixed(2)}s`}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-start",
                  marginBottom: "1rem",
                }}
              >
                <div
                  style={{
                    padding: "1rem",
                    background: "#f1f8f4",
                    borderRadius: "0.75rem",
                    color: "#558b2f",
                    minWidth: "240px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: "0.5rem",
                      alignItems: "center",
                      fontWeight: 600,
                      color: "#2e7d32",
                    }}
                  >
                    <div
                      style={{
                        width: "18px",
                        height: "18px",
                        border: "3px solid #c8e6c9",
                        borderTop: "3px solid #2b9348",
                        borderRadius: "50%",
                        animation: "spin 1s linear infinite",
                        flexShrink: 0,
                      }}
                    />
                    <span>{currentStep || "Analyzing…"}</span>
                  </div>
                  {showThoughts && reasoningSteps.length > 0 && (
                    <ol
                      style={{
                        margin: "0.75rem 0 0",
                        paddingLeft: "1.25rem",
                        fontSize: "0.85rem",
                        lineHeight: 1.6,
                      }}
                    >
                      {reasoningSteps.map((step, i) => {
                        const isLast = i === reasoningSteps.length - 1;
                        return (
                          <li
                            key={i}
                            style={{
                              color: isLast ? "#2e7d32" : "#7cb342",
                              fontWeight: isLast ? 600 : 400,
                            }}
                          >
                            {isLast ? "▸ " : "✓ "}
                            {step}
                          </li>
                        );
                      })}
                    </ol>
                  )}
                </div>
              </div>
            )}
          </div>

          <div>
            <div style={{ marginBottom: "0.5rem" }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  color: "#2e7d32",
                  fontWeight: "500",
                }}
              >
                <input
                  type="checkbox"
                  checked={includeLocation}
                  onChange={(e) => setIncludeLocation(e.target.checked)}
                  style={{ accentColor: "#2b9348" }}
                />
                <span>📍 Include location with query</span>
              </label>
              {includeLocation && !coords && (
                <span style={{ color: "#d84315", fontSize: "0.875rem" }}>
                  ⚠️ No location selected
                </span>
              )}
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <textarea
                placeholder="Ask about terrain, land features, soil, or geography..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    runAnalysis();
                  }
                }}
                disabled={loading}
                style={{
                  flex: 1,
                  padding: "0.75rem",
                  border: "2px solid #c8e6c9",
                  borderRadius: "0.5rem",
                  resize: "none",
                  fontFamily: "inherit",
                  fontSize: "1rem",
                }}
                rows={2}
              />
              <button
                onClick={runAnalysis}
                disabled={
                  loading || !query.trim() || (includeLocation && !coords)
                }
                style={{
                  padding: "0.75rem 1.5rem",
                  background:
                    loading || !query.trim() || (includeLocation && !coords)
                      ? "#c8e6c9"
                      : "linear-gradient(135deg, #2b9348 0%, #43a047 100%)",
                  color: "white",
                  border: "none",
                  borderRadius: "0.5rem",
                  cursor:
                    loading || !query.trim() || (includeLocation && !coords)
                      ? "not-allowed"
                      : "pointer",
                  fontSize: "1.25rem",
                  fontWeight: "bold",
                  boxShadow:
                    loading || !query.trim() || (includeLocation && !coords)
                      ? "none"
                      : "0 2px 8px rgba(43, 147, 72, 0.3)",
                  transition: "all 0.2s",
                }}
              >
                {loading ? "⏳" : "➤"}
              </button>
            </div>
          </div>

          {error && (
            <div
              style={{
                marginTop: "0.5rem",
                padding: "0.75rem",
                background: "#ffebee",
                color: "#c62828",
                borderRadius: "0.5rem",
                border: "1px solid #ef9a9a",
                fontWeight: "500",
              }}
            >
              {error}
            </div>
          )}
        </section>
      </main>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
