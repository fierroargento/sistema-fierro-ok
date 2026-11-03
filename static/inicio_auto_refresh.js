"use strict";
(() => {
    const key = document.currentScript?.dataset.filtroStorageKey;
    const onHome = () => window.location.pathname === '/';
    if (!onHome()) {
        try { if (key) localStorage.removeItem(key); } catch (_) {}
        return;
    }
    let navigating = false;
    let lastRefreshAt = Date.now();
    function refresh(force) {
        if (navigating || !onHome()) return;
        if (force || Date.now() - lastRefreshAt >= 20000) {
            lastRefreshAt = Date.now();
            window.location.reload();
        }
    }
    // La URL todavía dice Inicio mientras el servidor prepara el destino.
    window.addEventListener('click', event => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest?.('a[href]');
        if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
        const url = new URL(link.href, window.location.href);
        if (url.origin === window.location.origin && (url.pathname !== '/' || url.search !== window.location.search)) navigating = true;
    });
    window.addEventListener('submit', event => {
        if (!event.defaultPrevented && (!event.target.target || event.target.target === '_self')) navigating = true;
    });
    window.addEventListener('pageshow', () => { navigating = false; lastRefreshAt = Date.now(); });
    setInterval(() => refresh(false), 20000);
    window.addEventListener('focus', () => refresh(true));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });
})();
