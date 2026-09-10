(() => {
    const yen = value => `${Number(value || 0).toLocaleString('ja-JP')} 円`;
    const cell = (value, className = '') => { const node = document.createElement('td'); node.textContent = value; node.className = className; return node; };
    const emptyRow = (target, message, columns) => { const row = document.createElement('tr'); const node = cell(message, 'text-muted'); node.colSpan = columns; row.append(node); target.replaceChildren(row); };
    const message = (text, level = 'danger') => { const node = document.getElementById('outcomeMessage'); node.textContent = text; node.className = `alert alert-${level}`; };
    function summary(data) {
        const cards = [['販売件数', `${data.saleCount} 件`], ['売上', yen(data.totalSales)], ['費用', yen(data.totalExpenses)], ['純利益', yen(data.totalProfit)], ['黒字 / 赤字', `${data.profitableCount} 件 / ${data.lossCount} 件`]];
        const root = document.getElementById('outcomeSummary'); root.replaceChildren(...cards.map(([label, value]) => { const col = document.createElement('div'); col.className = 'col-sm-6 col-lg'; col.innerHTML = `<div class="card h-100"><div class="card-body"><div class="text-muted small">${label}</div><div class="fs-5 fw-bold">${value}</div></div></div>`; return col; }));
    }
    function categories(items) {
        const root = document.getElementById('outcomeCategories'); if (!items.length) return emptyRow(root, '確定した販売結果はまだありません。', 5);
        root.replaceChildren(...items.map(item => { const row = document.createElement('tr'); row.append(cell(item.category), cell(`${item.saleCount} 件`), cell(yen(item.totalSales)), cell(yen(item.totalExpenses)), cell(yen(item.totalProfit), item.totalProfit < 0 ? 'text-danger fw-bold' : 'fw-bold')); return row; }));
    }
    function lowProfit(items) {
        const root = document.getElementById('outcomeLowProfit'); if (!items.length) return emptyRow(root, '確定した販売結果はまだありません。', 6);
        root.replaceChildren(...items.map(item => { const row = document.createElement('tr'); row.append(cell(item.name), cell(item.category), cell(new Date(item.soldAt).toLocaleDateString('ja-JP')), cell(yen(item.salePrice)), cell(yen(item.totalExpenses)), cell(yen(item.confirmedProfit), item.confirmedProfit < 0 ? 'text-danger fw-bold' : 'fw-bold')); return row; }));
    }
    async function load() { try { const response = await fetch('/taskle/api/v1/seller-outcomes'); const result = await response.json(); if (!response.ok) throw new Error(result.error?.message || '販売実績を取得できませんでした'); summary(result.data.summary); categories(result.data.categories); lowProfit(result.data.lowProfitSales); } catch (error) { message(error.message); } }
    load();
})();
