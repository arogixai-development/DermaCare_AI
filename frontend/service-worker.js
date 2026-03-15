const CACHE_NAME = 'dermacare-v2';

// We must carefully cache the exact paths the browser will request
const ASSETS_TO_CACHE = [
  './index.html',
  './styles.css',
  './app.js',
  './storage.js',
  './manifest.json'
];

// Install Event: Cache all core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Opened cache and caching assets');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  // Force waiting service worker to become active
  self.skipWaiting();
});

// Activate Event: Cleanup old caches when we bump the CACHE_NAME version
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // Ensure service worker takes control immediately
  self.clients.claim();
});

// Fetch Event: strictly "Cache-First" Strategy for offline rendering
self.addEventListener('fetch', (event) => {
  // Never intercept API requests heading to our FastAPI port 8000
  if (event.request.url.includes(':8000')) {
      return; // Let the browser handle these normally (they fail naturally if offline)
  }

  // Only intercept GET requests for our UI assets
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      // 1. Return the file perfectly from cache if it exists
      if (cachedResponse) {
        return cachedResponse;
      }
      
      // 2. Otherwise fall back to network fetch
      return fetch(event.request).then(response => {
           return response;
      }).catch((err) => {
           console.error("Fetch failed in service worker due to network", err);
           throw err;
      });
    })
  );
});
