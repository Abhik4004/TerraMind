import { useRef, useEffect } from "react";
import mapboxgl from "mapbox-gl";
import MapboxGeocoder from "@mapbox/mapbox-gl-geocoder";
import "mapbox-gl/dist/mapbox-gl.css";
import "@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.css";

mapboxgl.accessToken =
  "pk.eyJ1IjoiYW1pdHJha3NoYXItY2hha3JhYm9ydHkiLCJhIjoiY21keW96bjluMDQyNTJrcjVtNzBxNzE5NyJ9.H7LQ3sYbd3lRynYROs7E5g";

/**
 * MapSelector — embeddable map picker used by WeatherAnalyze and the /map route.
 *
 * Props:
 *   selected  {lat, lng} | null   — current selection (used for initial marker)
 *   onSelect  ({lat, lng}) => void — called when user pins a location
 *   height    string               — CSS height for the map container (default "400px")
 */
export default function MapSelector({ selected, onSelect, height = "400px" }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const initCenter = selected
      ? [selected.lng, selected.lat]
      : [88.3639, 22.5726]; // default: Kolkata

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/streets-v11",
      center: initCenter,
      zoom: 12,
    });
    mapRef.current = map;

    map.addControl(new mapboxgl.NavigationControl(), "top-right");

    const geocoder = new MapboxGeocoder({
      accessToken: mapboxgl.accessToken,
      mapboxgl,
      marker: false,
      placeholder: "Search for a location...",
    });
    map.addControl(geocoder, "top-left");

    geocoder.on("result", (e) => {
      const [lng, lat] = e.result.center;
      placeMarker(map, lat, lng);
      onSelect?.({ lat, lng });
    });

    map.on("click", ({ lngLat: { lat, lng } }) => {
      placeMarker(map, lat, lng);
      onSelect?.({ lat, lng });
    });

    // Place initial marker if a selection exists
    if (selected) {
      map.on("load", () => placeMarker(map, selected.lat, selected.lng));
    }

    return () => {
      markerRef.current?.remove();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function placeMarker(map, lat, lng) {
    markerRef.current?.remove();
    markerRef.current = new mapboxgl.Marker({ color: "#4CAF50" })
      .setLngLat([lng, lat])
      .addTo(map);
  }

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height, borderRadius: "4px", overflow: "hidden" }}
    />
  );
}
