const CACHE = 'crop-bot-v1';
const STATIC = ['/', '/index.html', '/script.js', '/style.css', '/manifest.json', '/icon.svg'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)));
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    const { pathname } = new URL(e.request.url);
    const isApi = ['/ask', '/weather', '/insights', '/crop-calendar', '/feedback', '/health', '/datasets', '/providers'].some(
        (p) => pathname.startsWith(p)
    );

    if (isApi) {
        e.respondWith(
            fetch(e.request).catch(() =>
                new Response(
                    JSON.stringify({ error: 'You are offline. Please check your internet connection.' }),
                    { headers: { 'Content-Type': 'application/json' } }
                )
            )
        );
        return;
    }

    e.respondWith(
        caches.match(e.request).then(
            (cached) =>
                cached ||
                fetch(e.request).then((res) => {
                    if (res.ok && e.request.url.startsWith(self.location.origin)) {
                        caches.open(CACHE).then((c) => c.put(e.request, res.clone()));
                    }
                    return res;
                })
        )
    );
});
