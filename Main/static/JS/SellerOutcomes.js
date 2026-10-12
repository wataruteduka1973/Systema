/** Confirmed-sale analysis: period filter, summary, monthly trend, expense breakdown and tables. */
(() => {
    'use strict';

    // Validated pair (dataviz palette check, light surface): sales teal, profit coral.
    const SALES_COLOR = '#0f8a70';
    const PROFIT_COLOR = '#c2532c';
    let monthlyChart = null;

    const yen = value => `${Number(value || 0).toLocaleString('ja-JP')} 円`;
    const cell = (value, className = '') => { const node = document.createElement('td'); node.textContent = value; node.className = className; return node; };
    const emptyRow = (target, message, columns) => { const row = document.createElement('tr'); const node = cell(message, 'text-muted'); node.colSpan = columns; row.append(node); target.replaceChildren(row); };
    const profitClass = value => (value < 0 ? 'text-danger fw-bold' : 'fw-bold');
    const message = (text, level = 'danger') => {
        const node = document.getElementById('outcomeMessage');
        node.textContent = text;
        node.className = text ? `alert alert-${level}` : 'alert d-none';
    };

    // --- Period ---------------------------------------------------------------------------
    const iso = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;

    function presetRange(preset, today = new Date()) {
        const year = today.getFullYear();
        const month = today.getMonth();
        switch (preset) {
            case 'this-month': return [new Date(year, month, 1), today];
            case 'last-month': return [new Date(year, month - 1, 1), new Date(year, month, 0)];
            case 'last-3-months': return [new Date(year, month - 2, 1), today];
            case 'last-12-months': return [new Date(year, month - 11, 1), today];
            case 'this-year': return [new Date(year, 0, 1), today];
            default: return [null, null];
        }
    }

    function periodText(period) {
        const format = value => value.replaceAll('-', '/');
        if (!period.from && !period.to) return '全期間の実績を表示しています。';
        if (period.from && period.to) return `${format(period.from)} 〜 ${format(period.to)} の実績を表示しています。`;
        return period.from ? `${format(period.from)} 以降の実績を表示しています。` : `${format(period.to)} までの実績を表示しています。`;
    }

    // --- Rendering ------------------------------------------------------------------------
    function summary(data) {
        const cards = [['販売件数', `${data.saleCount} 件`], ['売上', yen(data.totalSales)], ['費用', yen(data.totalExpenses)], ['純利益', yen(data.totalProfit)], ['黒字 / 赤字', `${data.profitableCount} 件 / ${data.lossCount} 件`]];
        document.getElementById('outcomeSummary').replaceChildren(...cards.map(([label, value]) => {
            const col = document.createElement('div');
            col.className = 'col-sm-6 col-lg';
            const card = document.createElement('div');
            card.className = 'card h-100';
            const body = document.createElement('div');
            body.className = 'card-body';
            const caption = document.createElement('div');
            caption.className = 'text-muted small';
            caption.textContent = label;
            const amount = document.createElement('div');
            amount.className = 'fs-5 fw-bold';
            amount.textContent = value;
            body.append(caption, amount);
            card.append(body);
            col.append(card);
            return col;
        }));
    }

    function breakdown(items) {
        const total = items.reduce((sum, item) => sum + Math.max(item.amount, 0), 0);
        document.getElementById('expenseBreakdown').replaceChildren(...items.map(item => {
            const share = total > 0 ? Math.round((Math.max(item.amount, 0) / total) * 1000) / 10 : 0;
            const entry = document.createElement('li');
            entry.className = 'mb-3';
            entry.dataset.expense = item.key;
            const line = document.createElement('div');
            line.className = 'd-flex justify-content-between gap-2 small';
            const label = document.createElement('span');
            label.textContent = item.label;
            const amount = document.createElement('span');
            amount.className = 'fw-bold text-nowrap';
            amount.textContent = `${yen(item.amount)}（${share}%）`;
            line.append(label, amount);
            const bar = document.createElement('div');
            bar.className = 'outcome-breakdown-bar mt-1';
            bar.setAttribute('aria-hidden', 'true');
            const fill = document.createElement('span');
            fill.style.width = `${share}%`;
            bar.append(fill);
            entry.append(line, bar);
            return entry;
        }));
    }

    function monthly(rows) {
        const empty = rows.every(row => row.saleCount === 0);
        document.getElementById('monthlyEmpty').hidden = !empty;
        document.getElementById('monthlyChartArea').hidden = empty;
        const table = document.getElementById('monthlyTable');
        table.replaceChildren(...rows.map(row => {
            const tr = document.createElement('tr');
            tr.append(cell(row.month.replace('-', '/')), cell(`${row.saleCount} 件`), cell(yen(row.totalSales)), cell(yen(row.totalExpenses)), cell(yen(row.totalProfit), profitClass(row.totalProfit)));
            return tr;
        }));
        if (monthlyChart) monthlyChart.destroy();
        monthlyChart = null;
        if (empty || !window.Chart) return;
        const series = (label, key, color) => ({ label, data: rows.map(row => row[key]), backgroundColor: color, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 28 });
        monthlyChart = new window.Chart(document.getElementById('monthlyChart'), {
            type: 'bar',
            data: {
                labels: rows.map(row => row.month.replace('-', '/')),
                datasets: [series('売上', 'totalSales', SALES_COLOR), series('純利益', 'totalProfit', PROFIT_COLOR)],
            },
            options: {
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', align: 'end', labels: { color: '#362f28', boxWidth: 12 } },
                    tooltip: {
                        callbacks: {
                            label: context => `${context.dataset.label}: ${yen(context.parsed.y)}`,
                            footer: items => `販売件数: ${rows[items[0].dataIndex].saleCount} 件`,
                        },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#6b6158' } },
                    y: { grid: { color: 'rgba(54, 47, 40, 0.08)' }, ticks: { color: '#6b6158', callback: value => `¥${Number(value).toLocaleString('ja-JP')}` } },
                },
            },
        });
    }

    function categories(items) {
        const root = document.getElementById('outcomeCategories');
        if (!items.length) return emptyRow(root, 'この期間の確定した販売結果はありません。', 5);
        root.replaceChildren(...items.map(item => { const row = document.createElement('tr'); row.append(cell(item.category), cell(`${item.saleCount} 件`), cell(yen(item.totalSales)), cell(yen(item.totalExpenses)), cell(yen(item.totalProfit), profitClass(item.totalProfit))); return row; }));
    }

    function lowProfit(items) {
        const root = document.getElementById('outcomeLowProfit');
        if (!items.length) return emptyRow(root, 'この期間の確定した販売結果はありません。', 6);
        root.replaceChildren(...items.map(item => { const row = document.createElement('tr'); row.append(cell(item.name), cell(item.category), cell(new Date(item.soldAt).toLocaleDateString('ja-JP')), cell(yen(item.salePrice)), cell(yen(item.totalExpenses)), cell(yen(item.confirmedProfit), profitClass(item.confirmedProfit))); return row; }));
    }

    // --- Loading --------------------------------------------------------------------------
    const form = document.getElementById('outcomePeriodForm');
    const preset = document.getElementById('outcomePeriod');
    const fromInput = document.getElementById('outcomeFrom');
    const toInput = document.getElementById('outcomeTo');

    async function load() {
        const params = new URLSearchParams();
        if (fromInput.value) params.set('from', fromInput.value);
        if (toInput.value) params.set('to', toInput.value);
        const query = params.toString();
        try {
            const response = await fetch(`/taskle/api/v1/seller-outcomes${query ? `?${query}` : ''}`);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error?.message || '販売実績を取得できませんでした');
            message('');
            const data = result.data;
            document.getElementById('outcomePeriodLabel').textContent = periodText(data.period);
            summary(data.summary);
            monthly(data.monthly);
            breakdown(data.expenseBreakdown);
            categories(data.categories);
            lowProfit(data.lowProfitSales);
            const url = new URL(window.location.href);
            url.search = query;
            window.history.replaceState(null, '', url);
        } catch (error) {
            message(error.message);
        }
    }

    preset.addEventListener('change', () => {
        if (preset.value === 'custom') {
            fromInput.focus();
            return;
        }
        const [from, to] = presetRange(preset.value);
        fromInput.value = from ? iso(from) : '';
        toInput.value = to ? iso(to) : '';
        load();
    });
    [fromInput, toInput].forEach(input => input.addEventListener('input', () => { preset.value = 'custom'; }));
    form.addEventListener('submit', event => {
        event.preventDefault();
        load();
    });

    // A shared or reloaded URL keeps its period.
    const initial = new URLSearchParams(window.location.search);
    fromInput.value = initial.get('from') || '';
    toInput.value = initial.get('to') || '';
    if (fromInput.value || toInput.value) preset.value = 'custom';
    load();
})();
