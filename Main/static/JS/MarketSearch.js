(() => {
    'use strict';
    const SIZE = 20;
    const state = { mode: document.body.dataset.activeMode || 'closed', items: [], filtered: [], page: 1 };
    const el = {};
    const id = name => document.getElementById(name);
    const numeric = value => Number(String(value ?? 0).replace(/[^0-9.-]/g, '')) || 0;

    function normalizeUrl(value) {
        const url = String(value || '').trim();
        if (url.startsWith('//')) return `https:${url}`;
        if (url.startsWith('/')) return `https://auctions.yahoo.co.jp${url}`;
        return url;
    }

    function normalize(item) {
        const current = state.mode === 'current';
        return {
            name: String(item.name ?? item.Name ?? '商品名なし'),
            price: numeric(current ? item.currentPrice ?? item.price : item.price ?? item.EndPrice),
            startPrice: numeric(item.startPrice ?? item.StartPrice),
            bidding: numeric(item.bidding ?? item.Bidding ?? item.bidCount),
            time: String(current ? item.remainingTime ?? item.time ?? '' : item.searchDay ?? item.SearchDay ?? ''),
            condition: String(item.condition || 'unknown'),
            conditionLabel: String(item.conditionLabel || '未分類'),
            url: normalizeUrl(item.url ?? item.URL ?? item.link),
        };
    }

    async function json(url, options = {}) {
        const response = await fetch(url, options);
        let body = {};
        try { body = await response.json(); } catch (_) { /* handled by status */ }
        if (!response.ok) throw new Error(body.error || `通信エラー (${response.status})`);
        return body;
    }

    function message(text, kind = 'danger') {
        el.message.textContent = text;
        el.message.className = `alert alert-${kind} mt-3 mb-0`;
    }

    function clearMessage() {
        el.message.className = 'alert d-none mt-3 mb-0';
        el.message.textContent = '';
    }

    function setItems(items) {
        state.items = (items || []).map(normalize);
        state.page = 1;
        filter();
    }

    function filter() {
        const min = Math.max(0, numeric(el.min.value));
        const max = el.max.value.trim() ? numeric(el.max.value) : Infinity;
        if (max < min) return message('最低価格は最高価格以下にしてください。', 'warning');
        state.filtered = state.items.filter(item => item.price >= min && item.price <= max && (!el.condition.value || item.condition === el.condition.value));
        state.page = Math.min(state.page, Math.max(1, Math.ceil(state.filtered.length / SIZE)));
        render();
    }

    function cell(text) {
        const result = document.createElement('td');
        result.textContent = text;
        return result;
    }

    function row(item) {
        const result = document.createElement('tr');
        result.append(cell(item.name), cell(`${item.price.toLocaleString()}円`), cell(`${item.startPrice.toLocaleString()}円`), cell(String(item.bidding)), cell(item.time || '-'), cell(item.conditionLabel));
        const urlCell = document.createElement('td');
        if (item.url) {
            const link = document.createElement('a');
            Object.assign(link, { href: item.url, target: '_blank', rel: 'noopener noreferrer', textContent: '商品を見る' });
            urlCell.appendChild(link);
        } else urlCell.textContent = '-';
        result.appendChild(urlCell);
        return result;
    }

    function render() {
        const start = (state.page - 1) * SIZE;
        el.body.replaceChildren(...state.filtered.slice(start, start + SIZE).map(row));
        const prices = state.filtered.map(item => item.price).filter(Boolean).sort((a, b) => a - b);
        const middle = Math.floor(prices.length / 2);
        const median = !prices.length ? null : prices.length % 2 ? prices[middle] : (prices[middle - 1] + prices[middle]) / 2;
        el.summary.textContent = `${state.filtered.length.toLocaleString()}件を表示`;
        el.detail.textContent = median == null ? '価格データがありません。' : `価格中央値: ${median.toLocaleString()}円`;
        el.pages.replaceChildren();
        const count = Math.ceil(state.filtered.length / SIZE);
        for (let page = 1; page <= count; page += 1) {
            const li = document.createElement('li');
            li.className = `page-item${page === state.page ? ' active' : ''}`;
            const button = document.createElement('button');
            button.className = 'page-link'; button.textContent = String(page);
            button.addEventListener('click', () => { state.page = page; render(); });
            li.appendChild(button); el.pages.appendChild(li);
        }
    }

    async function externalSearch() {
        const keyword = el.keyword.value.trim();
        if (!keyword) return message('検索キーワードを入力してください。', 'warning');
        clearMessage(); el.search.disabled = true; el.spinner.classList.remove('d-none');
        try {
            const endpoint = state.mode === 'current' ? 'RealtimeSearch' : 'perform_search';
            const result = await json(`/taskle/${endpoint}?keyword=${encodeURIComponent(keyword)}`);
            setItems(result.data); message(`${keyword} の検索結果を取得しました。`, 'success');
            if (state.mode === 'closed') await loadWords(keyword);
        } catch (error) { message(error.message); }
        finally { el.search.disabled = false; el.spinner.classList.add('d-none'); }
    }

    function historyKeyword() {
        const keyword = el.history.value;
        if (!keyword) message('保存済み検索キーワードを選択してください。', 'warning');
        return keyword;
    }

    async function loadHistory() {
        const keyword = historyKeyword(); if (!keyword) return;
        try { const result = await json(`/taskle/get_market_data?keyword=${encodeURIComponent(keyword)}`); setItems(result.data); message(`${keyword} の保存済みデータを読み込みました。`, 'success'); }
        catch (error) { message(error.message); }
    }

    async function updateHistory() {
        const keyword = historyKeyword(); if (!keyword) return;
        try {
            const result = await json(`/taskle/update_market_data?keyword=${encodeURIComponent(keyword)}`, { method: 'POST', headers: window.systemaCsrfHeaders() });
            message(result.message || '保存済みデータを更新しました。', 'success'); await loadHistory();
        } catch (error) { message(error.message); }
    }

    async function deleteHistory() {
        const keyword = historyKeyword();
        if (!keyword || !window.confirm(`${keyword} の保存済みデータを削除しますか？`)) return;
        try {
            const result = await json(`/taskle/delete_market_data?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE', headers: window.systemaCsrfHeaders() });
            setItems([]); message(result.message || '保存済みデータを削除しました。', 'success'); await loadWords();
        } catch (error) { message(error.message); }
    }

    async function loadWords(selected = '') {
        try {
            const result = await json('/taskle/get_search_words');
            el.history.replaceChildren(new Option('選択してください', ''), ...(result.searchWords || []).map(word => new Option(word, word)));
            if (selected) el.history.value = selected;
        } catch (error) { message(error.message); }
    }

    async function popularWords() {
        try {
            const result = await json('/taskle/get_popular_words?top=10');
            el.popular.replaceChildren(...(result.words || []).map(word => {
                const button = document.createElement('button');
                button.type = 'button'; button.className = 'btn btn-outline-danger btn-sm'; button.textContent = word;
                button.addEventListener('click', () => { el.keyword.value = word; el.keyword.focus(); });
                return button;
            }));
        } catch (_) { el.popular.replaceChildren(); }
    }

    function activate(mode) {
        state.mode = ['closed', 'current', 'history'].includes(mode) ? mode : 'closed';
        document.querySelectorAll('.mode-button').forEach(button => button.setAttribute('aria-selected', String(button.dataset.mode === state.mode)));
        const history = state.mode === 'history';
        el.keywordGroup.classList.toggle('d-none', history); el.historyGroup.classList.toggle('d-none', !history);
        el.actions.classList.toggle('d-none', !history); el.popular.classList.toggle('d-none', history);
        id('priceHeading').textContent = state.mode === 'current' ? '現在価格' : '終了価格';
        id('timeHeading').textContent = state.mode === 'current' ? '残り時間' : '取得日';
        setItems([]); clearMessage();
        const url = new URL(window.location.href); url.searchParams.set('mode', state.mode); window.history.replaceState({}, '', url);
        if (history) loadWords();
    }

    document.addEventListener('DOMContentLoaded', () => {
        Object.assign(el, { keyword:id('marketKeyword'),search:id('marketSearchButton'),spinner:id('marketSearchSpinner'),keywordGroup:id('keywordSearchGroup'),historyGroup:id('historySearchGroup'),actions:id('historyActions'),history:id('historyKeyword'),message:id('marketMessage'),popular:id('popularWords'),min:id('minimumPrice'),max:id('maximumPrice'),condition:id('conditionFilter'),body:id('resultTable').querySelector('tbody'),pages:id('resultPagination'),summary:id('resultSummary'),detail:id('resultDetail') });
        el.search.addEventListener('click', externalSearch); el.keyword.addEventListener('keydown', event => { if (event.key === 'Enter') externalSearch(); });
        id('historyLoadButton').addEventListener('click', loadHistory); id('historyUpdateButton').addEventListener('click', updateHistory); id('historyDeleteButton').addEventListener('click', deleteHistory);
        el.min.addEventListener('input', filter); el.max.addEventListener('input', filter); el.condition.addEventListener('change', filter);
        id('resetFilters').addEventListener('click', () => { el.min.value='0';el.max.value='';el.condition.value='';filter(); });
        document.querySelectorAll('.mode-button').forEach(button => button.addEventListener('click', () => activate(button.dataset.mode)));
        popularWords(); activate(state.mode);
    });
})();
