(function () {
    const MAX_ITEMS = 4;
    const selectedItems = new Map();
    let marketStatistics = null;

    function configure(options = {}) {
        marketStatistics = options.statistics || null;
        selectedItems.clear();
        ensureComparisonUi();
        renderStatistics();
        renderTray();
    }

    function createSelector(item) {
        const wrapper = document.createElement('div');
        wrapper.className = 'form-check d-flex justify-content-center';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'form-check-input compare-item-checkbox';
        checkbox.setAttribute('aria-label', `${item.name || '商品'}を比較対象に追加`);
        const key = itemKey(item);
        checkbox.checked = selectedItems.has(key);
        checkbox.addEventListener('change', () => {
            if (checkbox.checked && selectedItems.size >= MAX_ITEMS) {
                checkbox.checked = false;
                alert(`比較できる商品は${MAX_ITEMS}件までです。`);
                return;
            }
            if (checkbox.checked) selectedItems.set(key, item);
            else selectedItems.delete(key);
            renderTray();
        });
        wrapper.appendChild(checkbox);
        return wrapper;
    }

    function ensureComparisonUi() {
        if (document.getElementById('marketComparisonTray')) return;

        const tray = document.createElement('div');
        tray.id = 'marketComparisonTray';
        tray.className = 'position-fixed bottom-0 start-50 translate-middle-x bg-dark text-white rounded-top shadow p-3';
        tray.style.cssText = 'z-index:1050; width:min(760px, calc(100% - 24px)); display:none;';

        const row = document.createElement('div');
        row.className = 'd-flex flex-wrap align-items-center justify-content-between gap-2';
        const status = document.createElement('span');
        status.id = 'marketComparisonStatus';
        const actions = document.createElement('div');
        actions.className = 'd-flex gap-2';
        const clearButton = document.createElement('button');
        clearButton.type = 'button';
        clearButton.className = 'btn btn-sm btn-outline-light';
        clearButton.textContent = '選択解除';
        clearButton.addEventListener('click', clear);
        const compareButton = document.createElement('button');
        compareButton.type = 'button';
        compareButton.className = 'btn btn-sm btn-warning';
        compareButton.textContent = '選択した商品を比較';
        compareButton.addEventListener('click', openComparison);
        actions.append(clearButton, compareButton);
        row.append(status, actions);
        tray.appendChild(row);
        document.body.appendChild(tray);

        const modal = document.createElement('div');
        modal.id = 'marketComparisonModal';
        modal.className = 'modal fade';
        modal.tabIndex = -1;
        modal.setAttribute('aria-hidden', 'true');
        modal.innerHTML = `
            <div class="modal-dialog modal-xl modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 class="modal-title fs-5">検索結果の比較</h2>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="閉じる"></button>
                    </div>
                    <div class="modal-body">
                        <div id="marketComparisonStatistics" class="row g-2 mb-4"></div>
                        <h3 class="fs-6">相場中央値に対する価格位置</h3>
                        <div id="marketComparisonBars" class="mb-4"></div>
                        <div class="table-responsive"><table class="table table-bordered align-middle">
                            <thead><tr><th>商品</th><th>価格</th><th>相場との差</th><th>状態</th><th>入札</th><th>時間</th></tr></thead>
                            <tbody id="marketComparisonBody"></tbody>
                        </table></div>
                        <h3 class="fs-6 mt-4">市場全体の価格分布</h3>
                        <div id="marketHistogram" class="d-flex align-items-end gap-1 border-bottom p-2" style="height:180px"></div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
    }

    function renderStatistics() {
        const container = document.getElementById('marketStatisticsSummary');
        if (!container) return;
        container.innerHTML = '';
        if (!marketStatistics || !marketStatistics.count) return;
        const cards = [
            ['データ件数', `${marketStatistics.count}件`],
            ['中央値', formatYen(marketStatistics.median)],
            ['価格変動幅', formatYen(marketStatistics.priceRange)],
            ['四分位範囲', formatYen(marketStatistics.iqr)],
            ['変動係数', `${marketStatistics.coefficientOfVariation}%`],
            ['外れ値候補', `${marketStatistics.outlierCount}件`],
        ];
        cards.forEach(([label, value]) => container.appendChild(createMetricCard(label, value)));
    }

    function renderTray() {
        const tray = document.getElementById('marketComparisonTray');
        if (!tray) return;
        tray.style.display = selectedItems.size ? 'block' : 'none';
        document.getElementById('marketComparisonStatus').textContent =
            `${selectedItems.size}/${MAX_ITEMS}件を選択中`;
    }

    function openComparison() {
        if (selectedItems.size < 2) {
            alert('比較する商品を2件以上選択してください。');
            return;
        }
        renderComparison();
        const modalElement = document.getElementById('marketComparisonModal');
        if (window.bootstrap && window.bootstrap.Modal) {
            window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
        }
    }

    function renderComparison() {
        const items = Array.from(selectedItems.values());
        const maximum = Math.max(...items.map(getPrice), 1);
        const body = document.getElementById('marketComparisonBody');
        const bars = document.getElementById('marketComparisonBars');
        body.innerHTML = '';
        bars.innerHTML = '';

        items.forEach(item => {
            const comparison = item.marketComparison || {};
            const row = body.insertRow();
            row.insertCell(0).textContent = item.name || 'N/A';
            row.insertCell(1).textContent = formatYen(getPrice(item));
            const differenceCell = row.insertCell(2);
            differenceCell.textContent = comparison.differenceRate == null
                ? '比較不可'
                : `${comparison.differenceRate > 0 ? '+' : ''}${comparison.differenceRate}%`;
            differenceCell.className = comparison.position === 'below' ? 'text-success'
                : comparison.position === 'above' ? 'text-danger' : '';
            row.insertCell(3).textContent = item.conditionLabel || '未分類';
            row.insertCell(4).textContent = Number(item.bidding || 0).toLocaleString();
            row.insertCell(5).textContent = item.remainingTime || item.time || 'N/A';
            bars.appendChild(createPriceBar(item, maximum));
        });

        const statisticsArea = document.getElementById('marketComparisonStatistics');
        statisticsArea.innerHTML = '';
        if (marketStatistics) {
            [
                ['中央値', formatYen(marketStatistics.median)],
                ['第1～第3四分位', `${formatYen(marketStatistics.q1)} ～ ${formatYen(marketStatistics.q3)}`],
                ['標準偏差', formatYen(marketStatistics.standardDeviation)],
                ['価格変動幅', formatYen(marketStatistics.priceRange)],
            ].forEach(([label, value]) => statisticsArea.appendChild(createMetricCard(label, value)));
        }
        renderHistogram();
    }

    function createPriceBar(item, maximum) {
        const wrapper = document.createElement('div');
        wrapper.className = 'mb-2';
        const label = document.createElement('div');
        label.className = 'small text-truncate';
        label.textContent = `${item.name || 'N/A'} — ${formatYen(getPrice(item))}`;
        const track = document.createElement('div');
        track.className = 'bg-light rounded';
        track.style.height = '18px';
        const bar = document.createElement('div');
        const position = item.marketComparison?.position;
        bar.className = `h-100 rounded ${position === 'below' ? 'bg-success' : position === 'above' ? 'bg-danger' : 'bg-primary'}`;
        bar.style.width = `${Math.max(2, getPrice(item) / maximum * 100)}%`;
        track.appendChild(bar);
        wrapper.append(label, track);
        return wrapper;
    }

    function renderHistogram() {
        const container = document.getElementById('marketHistogram');
        container.innerHTML = '';
        const histogram = marketStatistics?.histogram || [];
        const maximum = Math.max(...histogram.map(bin => bin.count), 1);
        histogram.forEach(bin => {
            const column = document.createElement('div');
            column.className = 'd-flex flex-column justify-content-end text-center';
            column.style.cssText = 'height:100%; flex:1; min-width:34px';
            const count = document.createElement('span');
            count.className = 'small';
            count.textContent = bin.count;
            const bar = document.createElement('div');
            bar.className = 'bg-primary mx-auto';
            bar.style.cssText = `width:80%; height:${Math.max(3, bin.count / maximum * 120)}px`;
            const label = document.createElement('span');
            label.className = 'small text-muted';
            label.textContent = `${compactNumber(bin.lower)}～${compactNumber(bin.upper)}`;
            column.append(count, bar, label);
            container.appendChild(column);
        });
    }

    function createMetricCard(label, value) {
        const column = document.createElement('div');
        column.className = 'col-6 col-md-4 col-xl-2';
        const card = document.createElement('div');
        card.className = 'border rounded bg-white p-2 h-100';
        const title = document.createElement('div');
        title.className = 'small text-muted';
        title.textContent = label;
        const metric = document.createElement('div');
        metric.className = 'fw-bold';
        metric.textContent = value;
        card.append(title, metric);
        column.appendChild(card);
        return column;
    }

    function clear() {
        selectedItems.clear();
        document.querySelectorAll('.compare-item-checkbox').forEach(input => { input.checked = false; });
        renderTray();
    }

    function itemKey(item) {
        return item.url || `${item.name || ''}:${getPrice(item)}`;
    }

    function getPrice(item) {
        return Number(item.currentPrice ?? item.price ?? 0) || 0;
    }

    function formatYen(value) {
        return value == null ? 'N/A' : `${Number(value).toLocaleString()}円`;
    }

    function compactNumber(value) {
        return Number(value).toLocaleString('ja-JP', { notation: 'compact', maximumFractionDigits: 1 });
    }

    window.MarketComparison = { configure, createSelector, clear };
})();
