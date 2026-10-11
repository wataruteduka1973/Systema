/** Top-page recommendation cards: image fallback and "add to watchlist". */
(function () {
    'use strict';

    const source = document.getElementById('recommendationPayloads');
    const payloads = source ? JSON.parse(source.textContent) : [];

    // A broken or blocked image falls back to the placeholder behind it.
    document.querySelectorAll('.recommendation-image img').forEach(image => {
        const drop = () => image.remove();
        if (image.complete && image.naturalWidth === 0) drop();
        else image.addEventListener('error', drop, { once: true });
    });

    document.querySelectorAll('.recommendation-watch').forEach(button => {
        button.addEventListener('click', async () => {
            const payload = payloads[Number(button.dataset.index)];
            if (!payload) return;
            button.disabled = true;
            try {
                const response = await fetch('/taskle/watchlist', {
                    method: 'POST',
                    headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    throw await window.SystemaFeedback.responseError(response, 'ウォッチリストへ追加できませんでした');
                }
                button.textContent = 'ウォッチ中';
                window.SystemaFeedback.success(`「${payload.name}」をウォッチリストに追加しました`);
            } catch (error) {
                button.disabled = false;
                window.SystemaFeedback.errorFrom(error, 'ウォッチリストへ追加できませんでした');
            }
        });
    });
})();
