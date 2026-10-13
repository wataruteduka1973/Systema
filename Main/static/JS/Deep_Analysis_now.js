let currentData = null; // null until the first result; the watchlist reload must not show an empty result.
let currentMedianPrice = 0;
let watchedByUrl = new Map();
let watchlistItems = [];

document.addEventListener("DOMContentLoaded", function () {

    const searchInput = document.getElementById('search');
    const searchForm = document.getElementById('targetSearchForm');

    searchForm?.addEventListener('submit', function (event) {
        event.preventDefault();
        TargetSearch();
    });

    // Enterキーで検索
    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            TargetSearch();
        }
    });

    // 人気ワード取得・ボタン生成
    fetch('/taskle/get_popular_words?top=10')
        .then(res => res.json())
        .then(data => {
            const area = document.getElementById('popularWordsBtnGroup');
            area.innerHTML = '';
            (data.words || []).forEach(word => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-outline-danger btn-sm';
                btn.textContent = word;
                btn.onclick = function () {
                    const searchInput = document.getElementById('search');
                    if (searchInput.value) {
                        searchInput.value += ' ' + word;
                    } else {
                        searchInput.value = word;
                    }
                    searchInput.focus();
                };
                area.appendChild(btn);
            });

        });

    loadWatchlist().then(openRequestedBudget);

});

// 市場検索の「仕入れ予算」から ?budget=<ウォッチID> で開かれたときは、その商品の試算を開く。
function openRequestedBudget() {
    const watchId = new URLSearchParams(window.location.search).get('budget');
    const editor = document.getElementById('purchaseBudgetEditor');
    const item = watchlistItems.find(entry => String(entry.id) === watchId);
    if (!watchId || !editor || !item) return;
    window.openPurchaseBudget(item);
    editor.scrollIntoView({ block: 'start' });
}
// 検索ボタンのクリックイベント
function TargetSearch() {
    const searchKeyword = document.getElementById("search").value.trim();
    if (!searchKeyword) {
        window.SystemaFeedback.warning('検索キーワードを入力してください');
        return;
    }
    const params = new URLSearchParams({
        keyword: searchKeyword,
        condition: document.getElementById('targetCondition')?.value || '',
        minimumPrice: document.getElementById('targetMinimumPrice')?.value || '0',
        maximumPrice: document.getElementById('targetMaximumPrice')?.value || '',
        excludedKeywords: document.getElementById('targetExcludedKeywords')?.value || '',
        endingWithinMinutes: document.getElementById('targetEndingWithinMinutes')?.value || '',
        sortOrder: document.getElementById('targetSortOrder')?.value || 'default',
    });

    const spinner = document.getElementById('searchSpinner');
    const button = document.getElementById('button-search');
    const buttonLabel = document.getElementById('searchButtonLabel');
    if (button.disabled) return;
    const originalButtonLabel = buttonLabel.textContent;
    spinner.style.display = 'inline-block';
    buttonLabel.textContent = '検索・分析中...';
    button.disabled = true;
    const savedSearchPromise = window.saveTargetSearchConditions
        ? window.saveTargetSearchConditions(document.getElementById('targetSearchForm'))
        : Promise.resolve(null);
    savedSearchPromise
        .then(savedSearch => fetch(
            savedSearch
                ? `/taskle/api/v1/saved-searches/${savedSearch.id}/run`
                : `/taskle/complex_market_data?${params.toString()}`,
            savedSearch
                ? { method: 'POST', headers: window.systemaCsrfHeaders() }
                : undefined,
        ))
        .then(response => {
            if (!response.ok) {
                // Keep the form and current results; show the server's message in the page.
                return window.SystemaFeedback.responseError(response, '検索に失敗しました').then(error => { throw error; });
            }
            return response.json();
        })
        .then(result => window.renderTargetAnalysisResult(result))
        .catch(error => {
            console.error('検索エラー:', error);
            if (error.message === 'SERVER_RESTART_REQUIRED') {
                window.SystemaFeedback.error('更新前のサーバーが動作しています。Systemaを停止し、run_systema.batから再起動してください。');
            } else {
                window.SystemaFeedback.errorFrom(error, '検索に失敗しました');
            }
        })
        .finally(() => {
            spinner.style.display = 'none';
            buttonLabel.textContent = originalButtonLabel;
            button.disabled = false;
        });
}

window.renderTargetAnalysisResult = function (result) {
    const recommendations = result.recommend_items || [];
    if (recommendations.length && recommendations.some(item => !item.buyDecision || !item.condition)) {
        throw new Error('SERVER_RESTART_REQUIRED');
    }
    if (typeof result.medianPrice !== "undefined") {
        currentMedianPrice = Number(result.medianPrice) || 0;
        document.getElementById('medianPrice').textContent = Math.round(result.medianPrice).toLocaleString();
        document.getElementById('medianPriceBox').style.display = "block";
    } else {
        document.getElementById('medianPriceBox').style.display = "none";
    }
    currentData = recommendations;
    if (window.MarketComparison) {
        window.MarketComparison.configure({ statistics: result.marketStatistics || null });
    }
    updateTable(currentData);
};

function updateTable(data) {
    const list = document.getElementById('targetResults');
    list.replaceChildren(...data.map(createResultCard));
    document.getElementById('targetResultsHeader').hidden = false;
    document.getElementById('targetResultCount').textContent = `${data.length}件`;
    document.getElementById('targetResultsEmpty').hidden = data.length > 0;
}

// Same rule as the server (Main/domain/listing_image.py): only https Yahoo image hosts.
function safeImageUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === 'https:' && (url.hostname === 'yimg.jp' || url.hostname.endsWith('.yimg.jp')) ? url.href : '';
    } catch {
        return '';
    }
}

function safeListingUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : '';
    } catch {
        return '';
    }
}

function formatYen(value) {
    return value !== undefined && value !== null && value !== '' && Number.isFinite(Number(value))
        ? `¥${Math.round(Number(value)).toLocaleString()}` : '不明';
}

function createFact(label, value) {
    const wrapper = document.createElement('div');
    const term = document.createElement('dt');
    term.textContent = label;
    const detail = document.createElement('dd');
    if (value instanceof Node) detail.appendChild(value);
    else detail.textContent = value;
    wrapper.append(term, detail);
    return wrapper;
}

// Image area shared by result and watchlist cards; a missing or failed image shows the placeholder.
function createListingMedia(listingUrl, rawImageUrl) {
    const media = document.createElement(listingUrl ? 'a' : 'div');
    media.className = 'target-result-media';
    if (listingUrl) {
        media.href = listingUrl;
        media.target = '_blank';
        media.rel = 'noopener noreferrer';
        media.tabIndex = -1;
        media.setAttribute('aria-hidden', 'true');
    }
    const placeholder = document.createElement('span');
    placeholder.className = 'target-result-placeholder';
    placeholder.textContent = '画像なし';
    media.appendChild(placeholder);
    const imageUrl = safeImageUrl(rawImageUrl);
    if (imageUrl) {
        const image = document.createElement('img');
        image.alt = '';
        image.loading = 'lazy';
        image.referrerPolicy = 'no-referrer';
        image.addEventListener('error', () => image.remove(), { once: true });
        image.src = imageUrl;
        media.appendChild(image);
    }
    return media;
}

function createResultCard(item) {
    const card = document.createElement('article');
    card.className = 'target-result-card';
    card.setAttribute('role', 'listitem');
    const listingUrl = safeListingUrl(item.url);

    const media = createListingMedia(listingUrl, item.imageUrl);

    const body = document.createElement('div');
    body.className = 'target-result-body';
    const tags = document.createElement('div');
    tags.className = 'target-result-tags';
    tags.append(createDecisionBadge(item.buyDecision), createConditionBadge(item));

    const name = document.createElement(listingUrl ? 'a' : 'span');
    name.className = 'target-result-name';
    name.textContent = item.name || '名称不明';
    name.title = item.name || '';
    if (listingUrl) {
        name.href = listingUrl;
        name.target = '_blank';
        name.rel = 'noopener noreferrer';
    }

    const priceRow = document.createElement('div');
    priceRow.className = 'target-result-price-row';
    const price = document.createElement('span');
    price.className = 'target-result-price';
    price.textContent = formatYen(item.price);
    priceRow.appendChild(price);
    const comparison = item.marketComparison || {};
    if (comparison.differenceRate !== null && comparison.differenceRate !== undefined) {
        const rate = Number(comparison.differenceRate);
        const chip = document.createElement('span');
        chip.className = `target-result-diff is-${comparison.position || 'near'}`;
        chip.textContent = `相場比 ${rate > 0 ? '+' : ''}${rate.toFixed(1)}%`;
        priceRow.appendChild(chip);
    }

    const facts = document.createElement('dl');
    facts.className = 'target-result-facts';
    facts.append(
        createFact('入札', item.bidding !== undefined && item.bidding !== null ? `${item.bidding}件` : '不明'),
        createFact('残り時間', item.remainingTime || '不明'),
        createFact('相場中央値', formatYen(item.marketMedian ?? currentMedianPrice)),
    );

    body.append(tags, name, priceRow, facts);
    if (item.buyDecision && item.buyDecision.reason) {
        const reason = document.createElement('p');
        reason.className = 'target-result-reason';
        reason.textContent = item.buyDecision.reason;
        body.appendChild(reason);
    }

    const actions = document.createElement('div');
    actions.className = 'target-result-actions';
    if (window.MarketComparison) {
        const compare = document.createElement('label');
        compare.className = 'target-result-compare';
        const selector = window.MarketComparison.createSelector(item);
        compare.append(selector.querySelector('input'), document.createTextNode('比較'));
        actions.appendChild(compare);
    }
    if (listingUrl) {
        const link = document.createElement('a');
        link.className = 'btn btn-sm btn-outline-secondary';
        link.href = listingUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = '商品ページ';
        actions.appendChild(link);
    }
    const watch = createWatchButton(item);
    watch.classList.add('target-result-watch');
    actions.appendChild(watch);

    card.append(media, body, actions);
    return card;
}

function createConditionBadge(item) {
    const badge = document.createElement('span');
    const color = item.condition === 'junk' ? 'bg-danger'
        : item.condition === 'new' ? 'bg-success'
            : item.condition === 'used' ? 'bg-primary' : 'bg-secondary';
    badge.className = `badge ${color}`;
    badge.textContent = item.conditionLabel || '未分類';
    return badge;
}

function createDecisionBadge(decision) {
    const badge = document.createElement('span');
    const status = decision ? decision.status : 'insufficient';
    const color = status === 'strong_buy' ? 'bg-success'
        : status === 'buy' ? 'bg-primary'
            : status === 'consider' ? 'bg-warning text-dark'
                : status === 'caution' ? 'bg-danger' : 'bg-secondary';
    badge.className = `badge ${color}`;
    badge.textContent = decision ? `${decision.label} (${decision.score})` : '判定材料不足';
    return badge;
}

function createWatchButton(item) {
    const button = document.createElement('button');
    button.type = 'button';
    const watched = watchedByUrl.get(item.url);
    button.className = watched ? 'btn btn-sm btn-outline-danger' : 'btn btn-sm btn-primary';
    button.textContent = watched ? 'ウォッチ解除' : 'ウォッチリストへ追加';
    button.addEventListener('click', () => watched ? removeWatchItem(watched.id) : addWatchItem(item));
    return button;
}

async function loadWatchlist() {
    const empty = document.getElementById('watchlistEmpty');
    try {
        const response = await fetch('/taskle/watchlist');
        if (response.status === 404) throw new Error('SERVER_RESTART_REQUIRED');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        empty.className = 'alert alert-secondary';
        empty.textContent = 'ウォッチ中の商品はありません。';
        watchlistItems = result.items || [];
        watchedByUrl = new Map(watchlistItems.map(item => [item.url, item]));
        renderFilteredWatchlist();
        if (currentData) updateTable(currentData);
    } catch (error) {
        console.error('ウォッチリスト取得エラー:', error);
        if (error.message === 'SERVER_RESTART_REQUIRED') {
            empty.className = 'alert alert-danger';
            empty.textContent = '更新前のサーバーが動作しています。Systemaを停止し、run_systema.batから再起動してください。';
        }
    }
}

function renderFilteredWatchlist() {
    const status = document.getElementById('watchStatusFilter')?.value ?? '';
    const priority = document.getElementById('watchPriorityFilter')?.value ?? '';
    const condition = document.getElementById('watchConditionFilter')?.value ?? '';
    const items = watchlistItems.filter(item =>
        (!status || item.lifecycleStatus === status) &&
        (priority === '' || String(item.priority) === priority) &&
        (!condition || item.condition === condition)
    );
    renderWatchlist(items);
}

async function addWatchItem(item) {
    const payload = {
        ...item,
        currentPrice: item.price,
        marketMedian: currentMedianPrice,
        searchKeyword: document.getElementById('search').value.trim(),
    };
    try {
        const response = await fetch('/taskle/watchlist', {
            method: 'POST',
            headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        await loadWatchlist();
    } catch (error) {
        console.error('ウォッチ登録エラー:', error);
        window.SystemaFeedback.error(`ウォッチリストへ追加できませんでした: ${error.message}`);
    }
}

async function removeWatchItem(itemId) {
    try {
        const response = await fetch(`/taskle/watchlist/${itemId}`, {
            method: 'DELETE',
            headers: window.systemaCsrfHeaders(),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        await loadWatchlist();
    } catch (error) {
        console.error('ウォッチ解除エラー:', error);
        window.SystemaFeedback.error(`ウォッチを解除できませんでした: ${error.message}`);
    }
}

const LIFECYCLE_LABELS = { active: '追跡中', purchased: '購入済み', skipped: '見送り', ended: '終了', archived: 'アーカイブ' };
const PRIORITY_LABELS = { 1: '優先度 通常', 2: '優先度 高', 3: '最優先' };

function renderWatchlist(items) {
    const list = document.getElementById('watchlistCards');
    const empty = document.getElementById('watchlistEmpty');
    list.replaceChildren(...items.map(createWatchCard));
    list.hidden = !items.length;
    empty.style.display = items.length ? 'none' : 'block';
}

function createTag(text, className) {
    const tag = document.createElement('span');
    tag.className = `badge ${className}`;
    tag.textContent = text;
    return tag;
}

function createWatchCard(item) {
    const card = document.createElement('article');
    card.className = 'target-result-card watch-card';
    card.setAttribute('role', 'listitem');
    card.dataset.watchId = String(item.id);
    const listingUrl = safeListingUrl(item.url);

    const body = document.createElement('div');
    body.className = 'target-result-body';
    const tags = document.createElement('div');
    tags.className = 'target-result-tags';
    tags.append(
        createDecisionBadge(item.buyDecision),
        createConditionBadge(item),
        createTag(LIFECYCLE_LABELS[item.lifecycleStatus] || item.lifecycleStatus, 'text-bg-light border'),
    );
    if (PRIORITY_LABELS[item.priority]) tags.appendChild(createTag(PRIORITY_LABELS[item.priority], 'bg-warning text-dark'));
    if (item.category) tags.appendChild(createTag(item.category, 'text-bg-light border'));

    const name = document.createElement(listingUrl ? 'a' : 'span');
    name.className = 'target-result-name';
    name.textContent = item.name;
    name.title = item.name;
    if (listingUrl) {
        name.href = listingUrl;
        name.target = '_blank';
        name.rel = 'noopener noreferrer';
    }

    const priceRow = document.createElement('div');
    priceRow.className = 'target-result-price-row';
    const price = document.createElement('span');
    price.className = 'target-result-price';
    price.textContent = formatYen(item.currentPrice);
    const change = Number(item.priceChange) || 0;
    const chip = document.createElement('span');
    chip.className = `target-result-diff ${change < 0 ? 'is-below' : change > 0 ? 'is-above' : 'is-near'}`;
    chip.textContent = change ? `追加時から ${change > 0 ? '+' : '-'}¥${Math.abs(change).toLocaleString()}` : '追加時から変化なし';
    priceRow.append(price, chip);

    const facts = document.createElement('dl');
    facts.className = 'target-result-facts';
    facts.append(
        createFact('追加時価格', formatYen(item.addedPrice)),
        createFact('相場中央値', item.marketMedian ? formatYen(item.marketMedian) : '不明'),
        createFact('入札', `${Number(item.bidding) || 0}件`),
    );

    const history = createHistorySummary(item.historyAnalysis);
    history.classList.add('watch-history-summary');

    body.append(tags, name, priceRow, facts, history);
    if (item.buyDecision && item.buyDecision.reason) {
        const reason = document.createElement('p');
        reason.className = 'target-result-reason';
        reason.textContent = item.buyDecision.reason;
        body.appendChild(reason);
    }
    if (item.note) {
        const note = document.createElement('p');
        note.className = 'watch-note';
        note.textContent = item.note;
        body.appendChild(note);
    }
    const checked = document.createElement('p');
    checked.className = 'target-result-reason';
    checked.textContent = `最終確認 ${formatCheckedAt(item.lastCheckedAt)}${item.remainingTime ? `・確認時の残り ${item.remainingTime}` : ''}`;
    body.appendChild(checked);

    const editor = document.createElement('details');
    editor.className = 'watch-editor';
    const summary = document.createElement('summary');
    summary.textContent = '判断を編集';
    editor.append(summary, createWatchEditor(item));
    body.appendChild(editor);

    const historyPanel = document.createElement('div');
    historyPanel.className = 'watch-history';
    historyPanel.hidden = true;
    historyPanel.setAttribute('aria-live', 'polite');
    body.appendChild(historyPanel);

    const actions = document.createElement('div');
    actions.className = 'target-result-actions';
    if (document.getElementById('purchaseBudgetEditor')) {
        const budgetButton = document.createElement('button');
        budgetButton.type = 'button';
        budgetButton.className = 'btn btn-sm btn-outline-success';
        budgetButton.textContent = '購入上限・利益';
        budgetButton.addEventListener('click', () => {
            window.openPurchaseBudget(item);
            document.getElementById('purchaseBudgetEditor').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        actions.appendChild(budgetButton);
    }
    const historyButton = document.createElement('button');
    historyButton.type = 'button';
    historyButton.className = 'btn btn-sm btn-outline-primary';
    historyButton.textContent = '履歴';
    historyButton.setAttribute('aria-expanded', 'false');
    historyButton.addEventListener('click', () => toggleWatchHistory(item.id, historyPanel, historyButton));
    actions.appendChild(historyButton);
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'btn btn-sm btn-outline-danger';
    removeButton.textContent = 'ウォッチ解除';
    removeButton.addEventListener('click', () => removeWatchItem(item.id));
    actions.appendChild(removeButton);

    card.append(createListingMedia(listingUrl, item.imageUrl), body, actions);
    return card;
}

function createHistorySummary(analysis) {
    const wrapper = document.createElement('div');
    if (!analysis || !analysis.observationCount) {
        wrapper.textContent = '分析材料不足';
        return wrapper;
    }
    const trend = document.createElement('div');
    trend.className = analysis.trend === 'down' ? 'text-success' : analysis.trend === 'up' ? 'text-danger' : '';
    trend.textContent = `${analysis.trendLabel}（${analysis.observationCount}回観測）`;
    wrapper.appendChild(trend);
    if (analysis.minimumPrice != null) {
        const minimum = document.createElement('small');
        minimum.className = 'd-block text-muted';
        minimum.textContent = `最安 ${Number(analysis.minimumPrice).toLocaleString()}円`;
        wrapper.appendChild(minimum);
    }
    if (analysis.marketDiscountRate != null) {
        const market = document.createElement('small');
        market.className = 'd-block text-muted';
        market.textContent = `相場比 ${analysis.marketDiscountRate >= 0 ? '-' : '+'}${Math.abs(analysis.marketDiscountRate)}%`;
        wrapper.appendChild(market);
    }
    return wrapper;
}

function createWatchEditor(item) {
    const wrapper = document.createElement('div');
    wrapper.className = 'd-grid gap-1';
    const priority = document.createElement('select');
    priority.className = 'form-select form-select-sm';
    [['0', '未設定'], ['1', '通常'], ['2', '高'], ['3', '最優先']].forEach(([value, label]) => {
        priority.add(new Option(label, value, false, String(item.priority) === value));
    });
    const status = document.createElement('select');
    status.className = 'form-select form-select-sm';
    [['active', '追跡中'], ['purchased', '購入済み'], ['skipped', '見送り'], ['ended', '終了'], ['archived', 'アーカイブ']].forEach(([value, label]) => {
        status.add(new Option(label, value, false, item.lifecycleStatus === value));
    });
    const note = document.createElement('textarea');
    note.className = 'form-control form-control-sm';
    note.rows = 2;
    note.maxLength = 2000;
    note.placeholder = '判断メモ';
    note.value = item.note || '';
    const category = document.createElement('input');
    category.type = 'text';
    category.className = 'form-control form-control-sm';
    category.maxLength = 100;
    category.placeholder = 'カテゴリ';
    category.value = item.category || '';
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'btn btn-sm btn-outline-secondary';
    save.textContent = '判断を保存';
    save.addEventListener('click', () => updateWatchItem(item.id, {
        priority: Number(priority.value),
        lifecycleStatus: status.value,
        note: note.value,
        category: category.value,
    }));
    wrapper.append(priority, status, category, note, save);
    return wrapper;
}

async function updateWatchItem(itemId, payload) {
    try {
        const response = await fetch(`/taskle/watchlist/${itemId}`, {
            method: 'PATCH',
            headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        await loadWatchlist();
    } catch (error) {
        console.error('ウォッチ判断更新エラー:', error);
        window.SystemaFeedback.error(`判断結果を保存できませんでした: ${error.message}`);
    }
}

async function toggleWatchHistory(itemId, panel, button) {
    if (!panel.hidden) {
        panel.hidden = true;
        button.setAttribute('aria-expanded', 'false');
        return;
    }
    try {
        const response = await fetch(`/taskle/watchlist/${itemId}/snapshots`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        const heading = document.createElement('strong');
        heading.textContent = `価格・入札履歴（${result.snapshots.length}件）`;
        const list = document.createElement('ul');
        list.className = 'mb-0 mt-1';
        result.snapshots.slice(-10).reverse().forEach(snapshot => {
            const entry = document.createElement('li');
            entry.textContent = `${formatCheckedAt(snapshot.observedAt)}: ${Number(snapshot.price).toLocaleString()}円・入札${snapshot.bidding}件`;
            list.appendChild(entry);
        });
        panel.replaceChildren(heading, list);
        panel.hidden = false;
        button.setAttribute('aria-expanded', 'true');
    } catch (error) {
        console.error('ウォッチ履歴取得エラー:', error);
        window.SystemaFeedback.error(`価格履歴を取得できませんでした: ${error.message}`);
    }
}

function formatCheckedAt(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleString('ja-JP');
}
