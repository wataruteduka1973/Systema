(() => {
    const list = document.getElementById('notificationList');
    if (!list) return;

    const unreadOnly = document.getElementById('unreadOnly');
    const message = document.getElementById('notificationMessage');
    const previous = document.getElementById('previousPage');
    const next = document.getElementById('nextPage');
    const status = document.getElementById('pageStatus');
    const markAll = document.getElementById('markAllRead');
    const categories = document.getElementById('notificationCategories');
    let page = 1;
    let category = '';
    let currentItems = [];
    const yen = value => (Number.isFinite(Number(value)) && value !== null && value !== '' ? `${Number(value).toLocaleString()}円` : '-');
    const localTime = value => {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };
    const safeLink = value => (/^https?:\/\//.test(String(value || '')) ? String(value) : '');
    const safeImage = value => (/^https:\/\/[^/]+\.yimg\.jp\//.test(String(value || '')) ? String(value) : '');
    const chip = rate => {
        if (rate === null || rate === undefined || rate === '' || !Number.isFinite(Number(rate))) return '';
        const value = Number(rate);
        const position = value <= -15 ? 'below' : value >= 15 ? 'above' : 'near';
        return `<span class="compare-chip ${position}">相場比 ${value > 0 ? '+' : ''}${escapeHtml(value)}%</span>`;
    };
    const candidateHtml = (candidate, itemIndex, candidateIndex) => {
        const link = safeLink(candidate.url);
        const image = safeImage(candidate.imageUrl);
        const name = escapeHtml(candidate.name || '商品名なし');
        return `
            <div class="notification-candidate border rounded p-2 mb-2">
                <div class="candidate-image">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '画像なし'}</div>
                <div class="candidate-body">
                    ${link ? `<a class="candidate-name" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${name}</a>` : `<span class="candidate-name">${name}</span>`}
                    <div class="small text-muted mt-1">現在価格 ${escapeHtml(yen(candidate.currentPrice))} / 相場中央値 ${escapeHtml(yen(candidate.marketMedian))} ${chip(candidate.differenceRate)}</div>
                    <div class="small text-muted">取得 ${escapeHtml(localTime(candidate.observedAt))}</div>
                    <button class="btn btn-sm btn-outline-success mt-2 add-watch" type="button" data-item-index="${itemIndex}" data-candidate-index="${candidateIndex}">ウォッチへ登録</button>
                </div>
            </div>`;
    };
    const updateSummaryHtml = item => {
        const searches = item.payload?.searches;
        if (!searches || typeof searches !== 'object') return '';
        const rows = Object.values(searches).map(entry => `<li>${escapeHtml(entry.name)}：${escapeHtml(entry.itemCount)}件（${escapeHtml(localTime(entry.lastRunAt))}）</li>`).join('');
        return `<ul class="small text-muted mb-3">${rows}</ul>`;
    };

    const csrf = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));

    const showMessage = (text, danger = false) => {
        message.textContent = text;
        message.className = `alert ${danger ? 'alert-danger' : 'alert-info'}`;
    };
    const request = async (url, options = {}) => {
        const response = await fetch(url, {
            ...options,
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), ...(options.headers || {}) },
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '通知を更新できませんでした');
        return data;
    };
    const render = data => {
        currentItems = data.items;
        if (!data.items.length) {
            list.innerHTML = '<div class="card"><div class="card-body text-muted">表示する通知はありません。</div></div>';
        } else {
            list.innerHTML = data.items.map((item, itemIndex) => {
                const allCandidates = Array.isArray(item.payload?.candidates) ? item.payload.candidates : [];
                const candidates = allCandidates.slice(0, 3).map((candidate, candidateIndex) => candidateHtml(candidate, itemIndex, candidateIndex)).join('');
                const total = Number(item.payload?.candidateCount) || allCandidates.length;
                const more = total > 3 ? `<p class="small text-muted">ほか${total - 3}件${item.targetUrl ? 'は「確認する」から見られます' : 'があります'}。</p>` : '';
                return `
                <article class="card notification-card ${item.isRead ? '' : 'is-unread'}" data-notification-id="${item.id}">
                    <div class="card-body">
                        <div class="d-flex flex-wrap justify-content-between gap-2">
                            <h2 class="h5 mb-1">${escapeHtml(item.title)}</h2>
                            <time class="small text-muted" datetime="${escapeHtml(item.createdAt)}">${new Date(item.createdAt).toLocaleString('ja-JP')}</time>
                        </div>
                        <p class="notification-message mb-3">${escapeHtml(item.message)}</p>
                        ${updateSummaryHtml(item)}${candidates}${more}
                        <div class="d-flex flex-wrap gap-2">
                            ${item.targetUrl ? `<a class="btn btn-sm btn-primary" href="${escapeHtml(item.targetUrl)}">確認する</a>` : ''}
                            <button class="btn btn-sm btn-outline-secondary toggle-read" type="button" data-read="${item.isRead ? 'false' : 'true'}">${item.isRead ? '未読に戻す' : '既読にする'}</button>
                        </div>
                    </div>
                </article>`;
            }).join('');
        }
        status.textContent = `${data.page}ページ（全${data.total}件・未読${data.unreadCount}件）`;
        previous.disabled = data.page <= 1;
        next.disabled = !data.hasNext;
        markAll.disabled = data.unreadCount === 0;
    };
    const load = async () => {
        message.classList.add('d-none');
        try {
            const query = new URLSearchParams({ unreadOnly: String(unreadOnly.checked), page: String(page) });
            if (category) query.set('category', category);
            render(await request(`/taskle/api/v1/notifications?${query}`));
        } catch (error) {
            showMessage(error.message, true);
        }
    };

    list.addEventListener('click', async event => {
        const addWatch = event.target.closest('.add-watch');
        if (addWatch) {
            addWatch.disabled = true;
            const item = currentItems[Number(addWatch.dataset.itemIndex)];
            const candidate = item?.payload?.candidates?.[Number(addWatch.dataset.candidateIndex)];
            try {
                await request('/taskle/watchlist', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: candidate.name, url: candidate.url,
                        currentPrice: candidate.currentPrice, bidding: candidate.bidding || 0,
                        remainingSeconds: candidate.remainingSeconds,
                        marketMedian: candidate.marketMedian || 0,
                    }),
                });
                showMessage('候補をウォッチへ登録しました。');
                addWatch.textContent = '登録済み';
                return;
            } catch (error) {
                showMessage(error.message, true);
                addWatch.disabled = false;
                return;
            }
        }
        const button = event.target.closest('.toggle-read');
        if (!button) return;
        button.disabled = true;
        try {
            const card = button.closest('[data-notification-id]');
            await request(`/taskle/api/v1/notifications/${card.dataset.notificationId}`, {
                method: 'PATCH', body: JSON.stringify({ read: button.dataset.read === 'true' }),
            });
            await load();
        } catch (error) {
            showMessage(error.message, true);
            button.disabled = false;
        }
    });
    unreadOnly.addEventListener('change', () => { page = 1; load(); });
    categories?.addEventListener('click', event => {
        const button = event.target.closest('[data-category]');
        if (!button) return;
        category = button.dataset.category;
        categories.querySelectorAll('[data-category]').forEach(other => {
            const active = other === button;
            other.classList.toggle('active', active);
            other.setAttribute('aria-pressed', String(active));
        });
        page = 1;
        load();
    });
    previous.addEventListener('click', () => { if (page > 1) { page -= 1; load(); } });
    next.addEventListener('click', () => { page += 1; load(); });
    markAll.addEventListener('click', async () => {
        markAll.disabled = true;
        try {
            await request('/taskle/api/v1/notifications/read-all', { method: 'POST', body: '{}' });
            showMessage('すべての通知を既読にしました。');
            await load();
        } catch (error) {
            showMessage(error.message, true);
            markAll.disabled = false;
        }
    });
    load();
})();
