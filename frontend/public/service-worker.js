/**
 * Intelligence OS Service Worker
 * Provides offline caching, network-first fallback, and robust cache hygiene.
 */

const CACHE_NAME = 'intelligence-os-cache-v1';

// Assets to cache immediately on service worker install
const PRECACHE_ASSETS = [
  '/',
  '/favicon.ico'
];

// Service Worker Install Event
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Pre-cache warning during SW installation:', err);
      });
    })
  );
});

// Service Worker Activate Event
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Helper: Determine if request should be intercepted and cached
function shouldHandleRequest(request) {
  // Only intercept GET requests
  if (request.method !== 'GET') {
    return false;
  }

  // Strictly filter out non-HTTP/HTTPS schemes (e.g. chrome-extension://, moz-extension://)
  if (!request.url.startsWith('http://') && !request.url.startsWith('https://')) {
    return false;
  }

  const url = new URL(request.url);

  // Skip WebSocket connections, Next.js HMR endpoints, and API backend routes
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.includes('/_next/webpack-hmr') ||
    url.pathname.includes('/_next/turbopack') ||
    url.pathname.startsWith('/socket.io')
  ) {
    return false;
  }

  return true;
}

// Fetch Interception
self.addEventListener('fetch', (event) => {
  if (!shouldHandleRequest(event.request)) {
    return;
  }

  // Network-first strategy with cache fallback for HTML pages
  const isPageNavigation = event.request.mode === 'navigate';

  if (isPageNavigation) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              if (!event.request.url.startsWith('http://') && !event.request.url.startsWith('https://')) return;
              cache.put(event.request, responseToCache).catch((err) => {
                console.warn('Page cache put failed:', err);
              });
            });
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/')))
    );
    return;
  }

  // Static Assets & Resources: Cache-first with network fallback
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(event.request)
        .then((networkResponse) => {
          // Verify response validity
          if (
            !networkResponse ||
            networkResponse.status !== 200 ||
            (networkResponse.type !== 'basic' && networkResponse.type !== 'cors')
          ) {
            return networkResponse;
          }

          const responseToCache = networkResponse.clone();

          caches.open(CACHE_NAME).then((cache) => {
            // Protocol check: Ignore non-http schemes before caching to prevent extension schema errors
            if (!event.request.url.startsWith('http://') && !event.request.url.startsWith('https://')) return;
            cache.put(event.request, responseToCache).catch((err) => {
              console.warn('Cache put failed:', err);
            });
          });

          return networkResponse;
        })
        .catch((err) => {
          console.warn('Fetch failed for resource:', event.request.url, err);
          return cachedResponse || Response.error();
        });
    })
  );
});
