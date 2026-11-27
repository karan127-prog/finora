/* FINORA - Service Worker for PWA Mobile App Support */

const CACHE_NAME = 'finora-v1';
const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/css/components.css',
    '/static/js/main.js',
    '/static/js/charts.js',
    '/static/js/calendar.js',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('Some static assets failed to cache during install:', err);
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Only intercept GET requests for static assets
    if (event.request.method === 'GET' && event.request.url.includes('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request);
            })
        );
    }
});
