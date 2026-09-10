(() => {
    const sent = new Set();

    function report(kind) {
        if (sent.has(kind)) return;
        sent.add(kind);
        fetch('/taskle/api/v1/client-errors', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({kind}),
            keepalive: true,
        }).catch(() => {});
    }

    window.addEventListener('error', event => {
        report(event.target === window ? 'error' : 'resource');
    }, true);
    window.addEventListener('unhandledrejection', () => report('unhandledrejection'));
})();
