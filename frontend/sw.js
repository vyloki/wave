/**
 * Wave — Service Worker Self-Purge
 * Clears all stale caches and unregisters.
 */

self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    // Network only — do not cache
    return;
});
