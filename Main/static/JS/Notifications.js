(() => {
    const list = document.getElementById('notificationList');
    if (!list) return;

    const unreadOnly = document.getElementById('unreadOnly');
    const message = document.getElementById('notificationMessage');
    const previous = document.getElementById('previousPage');
    const next = document.getElementById('nextPage');
    const status = document.getElementById('pageStatus');
    const markAll = document.getElementById('markAllRead');
    let page = 1;

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
        if (!data.items.length) {
            list.innerHTML = '<div class="card"><div class="card-body text-muted">表示する通知はありません。</div></div>';
        } else {
            list.innerHTML = data.items.map(item => `
                <article class="card notification-card ${item.isRead ? '' : 'is-unread'}" data-notification-id="${item.id}">
                    <div class="card-body">
                        <div class="d-flex flex-wrap justify-content-between gap-2">
                            <h2 class="h5 mb-1">${escapeHtml(item.title)}</h2>
                            <time class="small text-muted" datetime="${escapeHtml(item.createdAt)}">${new Date(item.createdAt).toLocaleString('ja-JP')}</time>
                        </div>
                        <p class="notification-message mb-3">${escapeHtml(item.message)}</p>
                        <div class="d-flex flex-wrap gap-2">
                            ${item.targetUrl ? `<a class="btn btn-sm btn-primary" href="${escapeHtml(item.targetUrl)}">確認する</a>` : ''}
                            <button class="btn btn-sm btn-outline-secondary toggle-read" type="button" data-read="${item.isRead ? 'false' : 'true'}">${item.isRead ? '未読に戻す' : '既読にする'}</button>
                        </div>
                    </div>
                </article>`).join('');
        }
        status.textContent = `${data.page}ページ（全${data.total}件・未読${data.unreadCount}件）`;
        previous.disabled = data.page <= 1;
        next.disabled = !data.hasNext;
        markAll.disabled = data.unreadCount === 0;
    };
    const load = async () => {
        message.classList.add('d-none');
        try {
            render(await request(`/taskle/api/v1/notifications?unreadOnly=${unreadOnly.checked}&page=${page}`));
        } catch (error) {
            showMessage(error.message, true);
        }
    };

    list.addEventListener('click', async event => {
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
