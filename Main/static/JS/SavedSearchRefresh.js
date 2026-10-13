// アラート画面の「保存検索の取得状況」。取得頻度・自動取得のオン／オフ・今すぐ取得と、直近の結果を表示する。
(() => {
    const list = document.getElementById('refreshList');
    if (!list) return;
    const message = document.getElementById('refreshMessage');
    const intervals = [[1, '1時間ごと'], [6, '6時間ごと'], [24, '24時間ごと']];

    const csrf = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    const api = async (url, options = {}) => {
        const response = await fetch(url, {...options, headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}});
        let data = {};
        try { data = await response.json(); } catch (_) { /* handled by status */ }
        if (!response.ok) throw new Error(data.error || '保存検索を更新できませんでした');
        return data;
    };
    const show = (text, danger = false) => {
        message.textContent = text;
        message.className = `alert ${danger ? 'alert-danger' : 'alert-success'}`;
    };
    const element = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const dateText = value => new Date(value).toLocaleString('ja-JP', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'});

    const statusLines = item => {
        const status = item.refresh || {};
        const lines = [];
        lines.push(status.lastSuccessAt
            ? `最終成功：${dateText(status.lastSuccessAt)}（出品${Number(status.lastSuccessItemCount || 0).toLocaleString('ja-JP')}件）`
            : '最終成功：まだありません');
        if (status.lastAttemptFailed) {
            lines.push(`直近の失敗：${status.lastFailureAt ? dateText(status.lastFailureAt) : '-'}　${status.lastFailureReason || '取得に失敗しました'}`);
        }
        if (!item.isActive) lines.push('次回予定：停止中');
        // A time already passed means the next hourly wake-up takes it.
        else if (status.nextRefreshAt && new Date(status.nextRefreshAt) > new Date()) lines.push(`次回予定：${dateText(status.nextRefreshAt)}ごろ`);
        else lines.push('次回予定：次の自動実行で取得');
        return lines;
    };

    const update = async (item, payload, success) => {
        await api(`/taskle/api/v1/saved-searches/${item.id}`, {method: 'PATCH', body: JSON.stringify(payload)});
        show(success);
        await load();
    };

    const card = item => {
        const failed = item.isActive && item.refresh?.lastAttemptFailed;
        const article = element('article', `card refresh-card${failed ? ' has-failure' : ''}${item.isActive ? '' : ' is-paused'}`);
        article.dataset.savedSearchId = item.id;
        const body = element('div', 'card-body d-flex flex-wrap justify-content-between gap-3');
        const info = element('div', 'flex-grow-1');
        const title = element('h3', 'h6 mb-1', item.name);
        if (failed) title.prepend(element('span', 'badge bg-danger me-2', '取得失敗'));
        info.append(title, element('p', 'small text-muted mb-1', `キーワード：${item.keyword}`));
        statusLines(item).forEach(line => info.append(element('p', 'small mb-0 refresh-status', line)));

        const controls = element('div', 'd-flex flex-wrap align-items-center gap-2');
        const select = element('select', 'form-select form-select-sm');
        select.setAttribute('aria-label', `${item.name}の取得頻度`);
        intervals.forEach(([value, label]) => {
            const option = element('option', '', label);
            option.value = String(value);
            select.append(option);
        });
        select.value = String(item.refreshIntervalHours);
        select.addEventListener('change', async () => {
            select.disabled = true;
            try { await update(item, {refreshIntervalHours: Number(select.value)}, '取得頻度を変更しました。'); }
            catch (error) { show(error.message, true); select.value = String(item.refreshIntervalHours); select.disabled = false; }
        });

        const toggleWrap = element('div', 'form-check form-switch mb-0');
        const toggle = element('input', 'form-check-input');
        Object.assign(toggle, {type: 'checkbox', id: `refreshToggle${item.id}`, checked: item.isActive});
        const label = element('label', 'form-check-label', item.isActive ? '自動取得' : '停止中');
        label.htmlFor = toggle.id;
        toggle.addEventListener('change', async () => {
            toggle.disabled = true;
            try { await update(item, {isActive: toggle.checked}, toggle.checked ? '自動取得を再開しました。' : '自動取得を停止しました。'); }
            catch (error) { show(error.message, true); toggle.checked = !toggle.checked; toggle.disabled = false; }
        });
        toggleWrap.append(toggle, label);

        const runButton = element('button', 'btn btn-sm btn-outline-danger', '今すぐ取得');
        runButton.type = 'button';
        runButton.disabled = !item.isActive;
        if (!item.isActive) runButton.title = '停止中の保存検索は取得できません';
        runButton.addEventListener('click', async () => {
            runButton.disabled = true;
            runButton.textContent = '取得中…';
            try {
                await api(`/taskle/api/v1/saved-searches/${item.id}/run`, {method: 'POST', body: '{}'});
                show(`「${item.name}」を取得しました。`);
            } catch (error) {
                show(`「${item.name}」を取得できませんでした：${error.message}`, true);
            }
            await load();
        });

        controls.append(select, toggleWrap, runButton);
        body.append(info, controls);
        article.append(body);
        return article;
    };

    const load = async () => {
        try {
            const {items} = await api('/taskle/api/v1/saved-searches');
            if (!items.length) {
                const empty = element('div', 'card card-body text-muted', '保存検索はまだありません。ターゲット分析で検索すると自動で保存されます。');
                list.replaceChildren(empty);
                return;
            }
            list.replaceChildren(...items.map(card));
        } catch (error) {
            show(error.message, true);
        }
    };

    load();
})();
