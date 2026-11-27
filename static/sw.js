// Service worker بسيط: مطلوب عشان أندرويد يعرض "تثبيت التطبيق". مش بيخزن حاجة.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
