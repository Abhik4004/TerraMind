/**
 * TerraMind Service Worker — offline Mapbox tile caching.
 *
 * Only intercepts Mapbox tile/style requests; all other network calls
 * (API, geocoding) pass through normally.
 *
 * Note: Caching Mapbox tiles for offline use is intended for development /
 * demo purposes. For production offline maps, use the Mapbox Offline SDK.
 */

const CACHE_NAME = "terramind-tiles-v1";

// Patterns that identify cacheable Mapbox tile/sprite/font requests
const TILE_PATTERNS = [
  /api\.mapbox\.com\/v4\//,
  /api\.mapbox\.com\/styles\/v1\/.*\/tiles\//,
  /api\.mapbox\.com\/fonts\//,
  /api\.mapbox\.com\/sprites\//,
];

function isCacheable(url) {
  return TILE_PATTERNS.some((re) => re.test(url));
}

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_NAME));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  // Remove old cache versions
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("terramind-tiles-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (!isCacheable(e.request.url)) return; // let non-tile requests pass through

  e.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(e.request).then((cached) => {
        if (cached) return cached;

        return fetch(e.request)
          .then((response) => {
            if (response.ok) {
              cache.put(e.request, response.clone());
            }
            return response;
          })
          .catch(() => cached); // serve stale if network fails
      })
    )
  );
});
