/**
 * Wave — Service Worker
 * Caches static UI assets for instant app loading and offline capability.
 */

const CACHE_NAME = 'wave-v1';
const STATIC_ASSETS = [
    '/',
    '/static/manifest.json',
    '/static/css/index.css',
    '/static/css/player.css',
    '/static/css/animations.css',
    '/static/js/app.js',
    '/static/js/auth.js',
    '/static/js/player.js',
    '/static/js/library.js',
    '/static/js/lyrics.js',
    '/static/js/local_import.js',
    '/static/js/visualizer.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.debug('Service Worker cache prefetch error:', err);
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    // Only cache GET requests to static assets (never cache API streams or lyrics)
    if (e.request.method !== 'GET' || e.request.url.includes('/api/')) {
        return;
    }

    e.respondWith(
        caches.match(e.request).then((cached) => {
            return cached || fetch(e.request).then((response) => {
                if (response && response.status === 200 && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(e.request, clone);
                    });
                }
                return response;
            });
        }).catch(() => {
            return caches.match('/');
        })
    );
});
