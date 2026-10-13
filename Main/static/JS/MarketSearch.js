(() => {
    'use strict';
    const SIZE = 20;
    const state = { mode: document.body.dataset.activeMode || 'closed', items: [], filtered: [], page: 1, keyword: '', closedMarket: null };
    const signedIn = () => document.body.dataset.authenticated === 'true';
    const yen = value => `${Math.round(value).toLocaleString()}円`;
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
            imageUrl: String(item.imageUrl || ''),
            // Current listings are judged against the saved closed market; closed rows against their own median.
            comparison: (current ? item.closedMarketComparison : item.marketComparison) || null,
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

    function setItems(items, keyword = '', closedMarket = null) {
        state.items = (items || []).map(normalize);
        state.keyword = keyword;
        state.closedMarket = closedMarket;
        state.page = 1;
        filter();
    }

    function filter() {
        const min = Math.max(0, numeric(el.min.value));
        const max = el.max.value.trim() ? numeric(el.max.value) : Infinity;
        if (max < min) return message('最低価格は最高価格以下にしてください。', 'warning');
        state.filtered = state.items.filter(item => item.price >= min && item.price <= max && (!el.condition.value || item.condition === el.condition.value));
        const [key, direction] = el.sort.value.split('-');
        if (key !== 'default') {
            const multiplier = direction === 'desc' ? -1 : 1;
            state.filtered.sort((a, b) => (a[key] - b[key]) * multiplier);
        }
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
        result.append(cell(item.name), cell(`${item.price.toLocaleString()}円`), cell(`${item.startPrice.toLocaleString()}円`), cell(String(item.bidding)), cell(item.time || '-'), cell(item.conditionLabel), compareCell(item.comparison));
        const urlCell = document.createElement('td');
        if (/^https?:\/\//.test(item.url)) {
            const link = document.createElement('a');
            Object.assign(link, { href: item.url, target: '_blank', rel: 'noopener noreferrer', textContent: '商品を見る' });
            urlCell.appendChild(link);
        } else urlCell.textContent = '-';
        result.appendChild(urlCell);
        if (state.mode === 'current') result.appendChild(actionCell(item));
        return result;
    }

    function compareCell(comparison) {
        const result = document.createElement('td');
        if (!comparison || comparison.differenceRate == null) { result.textContent = '-'; return result; }
        const chip = document.createElement('span');
        const rate = comparison.differenceRate;
        chip.className = `compare-chip ${comparison.position || ''}`;
        chip.textContent = `${rate > 0 ? '+' : ''}${rate}%`;
        chip.title = comparison.label || '';
        chip.setAttribute('aria-label', `相場比 ${chip.textContent}（${comparison.label || ''}）`);
        result.appendChild(chip);
        return result;
    }

    function actionButton(text, className, handler) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = `btn btn-sm ${className}`; button.textContent = text;
        button.addEventListener('click', () => handler(button));
        return button;
    }

    function actionCell(item) {
        const result = document.createElement('td');
        const actions = document.createElement('div');
        actions.className = 'row-actions';
        if (item.watchId) {
            const watched = actionButton('ウォッチ中', 'btn-success', () => {});
            watched.disabled = true;
            actions.appendChild(watched);
        } else {
            actions.appendChild(actionButton('ウォッチ', 'btn-outline-success', button => watch(item, button)));
        }
        if (signedIn()) actions.appendChild(actionButton('仕入れ予算', 'btn-outline-danger', button => openBudget(item, button)));
        result.appendChild(actions);
        return result;
    }

    async function addToWatchlist(item) {
        const result = await json('/taskle/watchlist', {
            method: 'POST',
            headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                name: item.name, url: item.url, currentPrice: item.price, bidding: item.bidding,
                remainingTime: item.time, condition: item.condition, conditionLabel: item.conditionLabel,
                marketMedian: state.closedMarket?.median || 0, searchKeyword: state.keyword, imageUrl: item.imageUrl,
            }),
        });
        item.watchId = result.item.id;
        return result.item.id;
    }

    async function watch(item, button) {
        button.disabled = true;
        try {
            await addToWatchlist(item);
            render();
            message(`「${item.name}」をウォッチリストに追加しました。ターゲット分析のウォッチリストで確認できます。`, 'success');
        } catch (error) {
            button.disabled = false;
            message(`ウォッチリストへ追加できませんでした: ${error.message}`);
        }
    }

    async function openBudget(item, button) {
        button.disabled = true;
        try {
            const watchId = item.watchId || await addToWatchlist(item);
            window.location.href = `/taskle/Deep_Analysis_now?budget=${encodeURIComponent(watchId)}`;
        } catch (error) {
            button.disabled = false;
            message(`仕入れ予算を開けませんでした: ${error.message}`);
        }
    }

    function render() {
        const start = (state.page - 1) * SIZE;
        el.body.replaceChildren(...state.filtered.slice(start, start + SIZE).map(row));
        const prices = state.filtered.map(item => item.price).filter(Boolean).sort((a, b) => a - b);
        const middle = Math.floor(prices.length / 2);
        const median = !prices.length ? null : prices.length % 2 ? prices[middle] : (prices[middle - 1] + prices[middle]) / 2;
        el.summary.textContent = `${state.filtered.length.toLocaleString()}件を表示`;
        renderInsights();
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

    // Linear-interpolated quantile, matching the server's pandas statistics.
    function quantile(sorted, ratio) {
        const position = (sorted.length - 1) * ratio;
        const lower = Math.floor(position);
        const upper = Math.ceil(position);
        return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
    }

    function marketSummary(items) {
        const prices = items.map(item => item.price).filter(price => price > 0).sort((a, b) => a - b);
        if (!prices.length) return null;
        const q1 = quantile(prices, 0.25);
        const q3 = quantile(prices, 0.75);
        const iqr = q3 - q1;
        const inRange = items.filter(item => item.price > 0 && item.price >= q1 - 1.5 * iqr && item.price <= q3 + 1.5 * iqr);
        const kept = inRange.map(item => item.price);
        const low = Math.min(...kept);
        const high = Math.max(...kept);
        const binCount = Math.min(8, new Set(inRange.map(item => item.price)).size);
        const width = (high - low) / binCount || 1;
        const bins = Array.from({ length: binCount }, (_, index) => ({ lower: low + width * index, upper: low + width * (index + 1), count: 0, bids: 0 }));
        inRange.forEach(item => {
            const bin = bins[Math.min(binCount - 1, Math.floor((item.price - low) / width))];
            bin.count += 1; bin.bids += item.bidding;
        });
        const busiest = bins.reduce((best, bin) => (bin.bids > (best?.bids || 0) ? bin : best), null);
        return { count: prices.length, median: quantile(prices, 0.5), q1, q3, bins, busiest, outliers: prices.length - inRange.length };
    }

    function tile(label, value, note = '') {
        const column = document.createElement('div');
        column.className = 'col-6 col-lg-3';
        const box = document.createElement('div');
        box.className = 'insight-tile';
        const title = document.createElement('div'); title.className = 'small text-muted'; title.textContent = label;
        const body = document.createElement('div'); body.className = 'value'; body.textContent = value;
        box.append(title, body);
        if (note) { const small = document.createElement('div'); small.className = 'small text-muted'; small.textContent = note; box.appendChild(small); }
        column.appendChild(box);
        return column;
    }

    const band = bin => `${yen(bin.lower)}〜${yen(bin.upper)}`;

    function renderDistribution(summary) {
        const peak = Math.max(...summary.bins.map(bin => bin.count), 1);
        el.distribution.setAttribute('aria-label', `価格の分布。中央50%は${yen(summary.q1)}〜${yen(summary.q3)}`);
        el.distribution.replaceChildren(...summary.bins.map(bin => {
            const column = document.createElement('div');
            const core = bin.upper >= summary.q1 && bin.lower <= summary.q3;
            column.className = `distribution-bin${core ? ' core' : ''}`;
            column.title = `${band(bin)}: ${bin.count}件・入札${bin.bids}件${bin === summary.busiest ? '（入札が最も集まる価格帯）' : ''}`;
            const count = document.createElement('span'); count.className = 'count'; count.textContent = bin.count ? `${bin.count}件` : '';
            const bar = document.createElement('div'); bar.className = 'bar'; bar.style.height = `${(bin.count / peak) * 85}%`;
            column.append(count, bar);
            return column;
        }));
        el.distributionLabels.replaceChildren(...summary.bins.map(bin => {
            const label = document.createElement('span');
            label.textContent = `${bin.lower >= 10000 ? `${(bin.lower / 10000).toFixed(1)}万` : Math.round(bin.lower).toLocaleString()}〜`;
            if (bin === summary.busiest) {
                const mark = document.createElement('span'); mark.className = 'bid-mark d-block'; mark.textContent = '▲入札集中';
                label.appendChild(mark);
            }
            return label;
        }));
        el.distributionNote.textContent = `濃い棒が中央50%の価格帯です。${summary.outliers ? `外れ値${summary.outliers}件は分布から除いています。` : ''}`;
        el.distributionTable.replaceChildren(...summary.bins.map(bin => {
            const tr = document.createElement('tr');
            tr.append(cell(band(bin)), cell(`${bin.count}件`), cell(`${bin.bids}件`));
            return tr;
        }));
    }

    function renderClosedMarketNote() {
        const note = el.closedNote;
        note.hidden = state.mode !== 'current';
        if (note.hidden) return;
        const market = state.closedMarket;
        const text = document.createElement('span');
        text.textContent = market
            ? `相場比は保存済みの落札相場（${new Date(market.searchedAt).toLocaleDateString('ja-JP')}取得・${market.count}件）の中央値${yen(market.median)}と比べています。`
            : '保存済みの落札相場がないため、相場比を出せません。';
        const button = actionButton(market ? '落札相場を取得し直す' : '落札相場を取得して比較', 'btn-outline-danger', fetchClosedMarket);
        button.id = 'fetchClosedMarket';
        note.replaceChildren(text, button);
    }

    function insightActions() {
        const keyword = state.keyword;
        const actions = [];
        if (state.mode === 'current') {
            actions.push(actionButton('落札相場を見る', 'btn-outline-danger', () => searchIn('closed', keyword)));
        } else {
            actions.push(actionButton('出品中の商品を探す', 'btn-danger', () => searchIn('current', keyword)));
            const link = document.createElement('a');
            link.className = 'btn btn-sm btn-outline-danger';
            link.href = `/taskle/Deep_Analysis?${new URLSearchParams({ source: 'new', keyword })}`;
            link.textContent = '相場分析で予想を見る';
            actions.push(link);
        }
        el.insightActions.replaceChildren(...actions);
    }

    function renderInsights() {
        const summary = marketSummary(state.filtered);
        el.insights.hidden = !summary || !state.keyword;
        if (el.insights.hidden) return;
        const tiles = [];
        if (state.mode === 'current') {
            const below = state.filtered.filter(item => item.comparison?.position === 'below').length;
            tiles.push(
                tile('出品中', `${summary.count.toLocaleString()}件`),
                tile('現在価格の中央値', yen(summary.median)),
                tile('落札相場の中央値', state.closedMarket ? yen(state.closedMarket.median) : '—'),
                tile('相場より安い出品', state.closedMarket ? `${below}件` : '—', '落札相場より15%以上安い'),
            );
        } else {
            tiles.push(
                tile('落札件数', `${summary.count.toLocaleString()}件`),
                tile('落札価格の中央値', yen(summary.median)),
                tile('よく売れている価格帯', `${yen(summary.q1)}〜${yen(summary.q3)}`, '中央50%'),
                tile('入札が集まる価格帯', summary.busiest ? band(summary.busiest) : '—', '入札数の合計が最も多い'),
            );
        }
        el.tiles.replaceChildren(...tiles);
        renderClosedMarketNote();
        renderDistribution(summary);
        insightActions();
    }

    function searchIn(mode, keyword) {
        activate(mode);
        el.keyword.value = keyword;
        externalSearch();
    }

    async function fetchClosedMarket(button) {
        button.disabled = true;
        try {
            await json(`/taskle/perform_search?${criteriaParams(state.keyword).toString()}`);
            await externalSearch();
        } catch (error) {
            button.disabled = false;
            message(`落札相場を取得できませんでした: ${error.message}`);
        }
    }

    function criteriaParams(keyword) {
        return new URLSearchParams({
            keyword,
            minimumPrice: String(Math.max(0, numeric(el.min.value))),
            maximumPrice: el.max.value.trim(),
            condition: el.condition.value,
            sortOrder: el.sort.value,
        });
    }

    async function externalSearch() {
        const keyword = el.keyword.value.trim();
        if (!keyword) return message('検索キーワードを入力してください。', 'warning');
        clearMessage(); el.search.disabled = true; el.spinner.classList.remove('d-none');
        try {
            const endpoint = state.mode === 'current' ? 'RealtimeSearch' : 'perform_search';
            const params = criteriaParams(keyword);
            const result = await json(`/taskle/${endpoint}?${params.toString()}`);
            setItems(result.data, result.keyword || keyword, result.closedMarket || null); message(`${keyword} の検索結果を取得しました。`, 'success');
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
        try { const result = await json(`/taskle/get_market_data?keyword=${encodeURIComponent(keyword)}`); setItems(result.data, keyword); message(`${keyword} の保存済みデータを読み込みました。`, 'success'); }
        catch (error) { message(error.message); }
    }

    async function updateHistory() {
        const keyword = historyKeyword(); if (!keyword) return;
        try {
            const result = await json(`/taskle/update_market_data?${criteriaParams(keyword).toString()}`, { method: 'POST', headers: window.systemaCsrfHeaders() });
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
                button.addEventListener('click', () => {
                    const currentWords = el.keyword.value.trim().split(/\s+/).filter(Boolean);
                    if (!currentWords.includes(word)) currentWords.push(word);
                    el.keyword.value = currentWords.join(' ');
                    el.keyword.focus();
                });
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
        id('actionHeading').classList.toggle('d-none', state.mode !== 'current');
        setItems([]); clearMessage();
        const url = new URL(window.location.href); url.searchParams.set('mode', state.mode); window.history.replaceState({}, '', url);
        if (history) loadWords();
    }

    document.addEventListener('DOMContentLoaded', () => {
        Object.assign(el, { keyword:id('marketKeyword'),search:id('marketSearchButton'),spinner:id('marketSearchSpinner'),keywordGroup:id('keywordSearchGroup'),historyGroup:id('historySearchGroup'),actions:id('historyActions'),history:id('historyKeyword'),message:id('marketMessage'),popular:id('popularWords'),min:id('minimumPrice'),max:id('maximumPrice'),condition:id('conditionFilter'),sort:id('sortOrder'),body:id('resultTable').querySelector('tbody'),insights:id('marketInsights'),tiles:id('insightTiles'),insightActions:id('insightActions'),closedNote:id('closedMarketNote'),distribution:id('priceDistribution'),distributionLabels:id('distributionLabels'),distributionNote:id('distributionNote'),distributionTable:id('distributionTable').querySelector('tbody'),pages:id('resultPagination'),summary:id('resultSummary'),detail:id('resultDetail') });
        el.search.addEventListener('click', externalSearch); el.keyword.addEventListener('keydown', event => { if (event.key === 'Enter') externalSearch(); });
        id('historyLoadButton').addEventListener('click', loadHistory); id('historyUpdateButton').addEventListener('click', updateHistory); id('historyDeleteButton').addEventListener('click', deleteHistory);
        el.min.addEventListener('input', filter); el.max.addEventListener('input', filter); el.condition.addEventListener('change', filter); el.sort.addEventListener('change', () => { state.page = 1; filter(); });
        id('resetFilters').addEventListener('click', () => { el.min.value='0';el.max.value='';el.condition.value='';el.sort.value='default';filter(); });
        document.querySelectorAll('.mode-button').forEach(button => button.addEventListener('click', () => activate(button.dataset.mode)));
        popularWords(); activate(state.mode);
    });
})();
