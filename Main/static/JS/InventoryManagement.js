document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('inventoryCreateForm').addEventListener('submit', createInventory);
    document.getElementById('watchConversionForm').addEventListener('submit', convertWatchItem);
    loadWatchCandidates();
    loadInventory();
});

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
}

async function loadWatchCandidates() {
    try {
        const result = await requestJson('/taskle/watchlist?status=active');
        const select = document.getElementById('watchItemSelect');
        select.replaceChildren(new Option('購入候補を選択', ''));
        result.items.forEach(item => {
            const option = new Option(`${item.name}（${formatYen(item.currentPrice)}）`, item.id);
            option.dataset.price = item.currentPrice;
            select.add(option);
        });
        select.onchange = () => {
            document.getElementById('watchAcquisitionCost').value = select.selectedOptions[0]?.dataset.price || '';
        };
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function createInventory(event) {
    event.preventDefault();
    try {
        await requestJson('/taskle/api/v1/inventory-items', {
            method: 'POST',
            headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                name: document.getElementById('inventoryName').value,
                acquisitionCost: Number(document.getElementById('inventoryCost').value),
                category: document.getElementById('inventoryCategory').value,
                note: document.getElementById('inventoryNote').value,
                status: 'acquired',
            }),
        });
        event.target.reset();
        showMessage('在庫を登録しました。');
        await loadInventory();
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function convertWatchItem(event) {
    event.preventDefault();
    const watchItemId = document.getElementById('watchItemSelect').value;
    if (!watchItemId) return showMessage('購入候補を選択してください。', true);
    try {
        const result = await requestJson(`/taskle/api/v1/watch-items/${watchItemId}/convert-to-inventory`, {
            method: 'POST',
            headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ acquisitionCost: Number(document.getElementById('watchAcquisitionCost').value) }),
        });
        showMessage(result.created ? '購入候補を在庫へ移しました。' : 'この購入候補はすでに在庫化されています。');
        await Promise.all([loadWatchCandidates(), loadInventory()]);
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function loadInventory() {
    const status = document.getElementById('inventoryStatusFilter').value;
    try {
        const result = await requestJson(`/taskle/api/v1/inventory-items${status ? `?status=${encodeURIComponent(status)}` : ''}`);
        renderInventory(result.items);
    } catch (error) {
        showMessage(error.message, true);
    }
}

function renderInventory(items) {
    const list = document.getElementById('inventoryList');
    const empty = document.getElementById('inventoryEmpty');
    list.replaceChildren();
    empty.classList.toggle('d-none', items.length > 0);
    items.forEach(item => list.appendChild(createInventoryCard(item)));
}

function createInventoryCard(item) {
    const column = document.createElement('div');
    column.className = 'col-12';
    const card = document.createElement('article');
    card.className = 'card inventory-card';
    const body = document.createElement('div');
    body.className = 'card-body';
    const heading = document.createElement('h3');
    heading.className = 'h5';
    heading.textContent = item.name;
    const form = document.createElement('form');
    form.className = 'row g-2 inventory-edit';
    form.innerHTML = `
        <div class="col-md-2"><label class="form-label" for="inventory-${item.id}-cost">仕入価格</label><input id="inventory-${item.id}-cost" name="acquisitionCost" type="number" min="0" class="form-control" value="${item.acquisitionCost}"></div>
        <div class="col-md-2"><label class="form-label" for="inventory-${item.id}-status">状態</label><select id="inventory-${item.id}-status" name="status" class="form-select">${statusOptions(item.status)}</select></div>
        <div class="col-md-2"><label class="form-label" for="inventory-${item.id}-category">カテゴリ</label><input id="inventory-${item.id}-category" name="category" class="form-control" maxlength="100"></div>
        <div class="col-md-4"><label class="form-label" for="inventory-${item.id}-note">メモ</label><textarea id="inventory-${item.id}-note" name="note" class="form-control" maxlength="2000"></textarea></div>
        <div class="col-md-2 d-flex align-items-end gap-1"><button class="btn btn-outline-primary" type="submit">保存</button><button class="btn btn-outline-danger inventory-delete" type="button">削除</button></div>`;
    form.elements.category.value = item.category || '';
    form.elements.note.value = item.note || '';
    form.addEventListener('submit', event => updateInventory(event, item.id));
    form.querySelector('.inventory-delete').addEventListener('click', () => deleteInventory(item.id));
    const simulator = createProfitSimulator(item);
    body.append(heading, form, simulator);
    card.appendChild(body);
    column.appendChild(card);
    return column;
}

function createProfitSimulator(item) {
    const details = document.createElement('details');
    details.className = 'mt-3 border-top pt-3';
    const summary = document.createElement('summary');
    summary.className = 'fw-bold';
    summary.textContent = '見込み利益を計算';
    const form = document.createElement('form');
    form.className = 'row g-2 mt-1';
    form.innerHTML = `<div class="col-sm-2"><label class="form-label" for="profit-${item.id}-sale">想定販売価格</label><input id="profit-${item.id}-sale" name="salePrice" type="number" min="0" class="form-control" required></div><div class="col-sm-2"><label class="form-label" for="profit-${item.id}-shipping">送料</label><input id="profit-${item.id}-shipping" name="shippingCost" type="number" min="0" value="0" class="form-control"></div><div class="col-sm-2"><label class="form-label" for="profit-${item.id}-packaging">梱包費</label><input id="profit-${item.id}-packaging" name="packagingCost" type="number" min="0" value="0" class="form-control"></div><div class="col-sm-2"><label class="form-label" for="profit-${item.id}-other">その他費用</label><input id="profit-${item.id}-other" name="otherCost" type="number" min="0" value="0" class="form-control"></div><div class="col-sm-2"><label class="form-label" for="profit-${item.id}-fee">手数料率</label><input id="profit-${item.id}-fee" name="feeRate" type="number" min="0" max="1" step="0.00001" value="0.10" class="form-control"></div><div class="col-sm-2 d-flex align-items-end"><button class="btn btn-success" type="submit">計算</button></div><div class="col-12 money-result" role="status"></div>`;
    form.addEventListener('submit', event => simulateProfit(event, item.id));
    details.append(summary, form);
    return details;
}

async function updateInventory(event, itemId) {
    event.preventDefault();
    const form = event.target;
    try {
        await requestJson(`/taskle/api/v1/inventory-items/${itemId}`, {
            method: 'PATCH', headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ acquisitionCost: Number(form.elements.acquisitionCost.value), status: form.elements.status.value, category: form.elements.category.value, note: form.elements.note.value }),
        });
        showMessage('在庫情報を保存しました。');
        await loadInventory();
    } catch (error) { showMessage(error.message, true); }
}

async function deleteInventory(itemId) {
    if (!window.confirm('この在庫を削除しますか？')) return;
    try {
        await requestJson(`/taskle/api/v1/inventory-items/${itemId}`, { method: 'DELETE', headers: window.systemaCsrfHeaders() });
        showMessage('在庫を削除しました。');
        await loadInventory();
    } catch (error) { showMessage(error.message, true); }
}

async function simulateProfit(event, itemId) {
    event.preventDefault();
    const form = event.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
        const result = await requestJson(`/taskle/api/v1/inventory-items/${itemId}/profit-simulation`, {
            method: 'POST', headers: window.systemaCsrfHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload),
        });
        const data = result.data;
        form.querySelector('[role="status"]').textContent = `手数料 ${formatYen(data.feeEstimate)}／総費用 ${formatYen(data.totalCost)}／見込み利益 ${formatYen(data.estimatedProfit)}／利益率 ${data.profitMarginPercent ?? 'N/A'}%／損益分岐 ${data.breakEvenPrice == null ? '算出不能' : formatYen(data.breakEvenPrice)}`;
    } catch (error) { showMessage(error.message, true); }
}

function statusOptions(selected) {
    return [['planned', '購入予定'], ['acquired', '仕入済み'], ['preparing', '出品準備中'], ['listed', '出品中'], ['sold', '販売済み'], ['disposed', '処分済み']]
        .map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('');
}

function formatYen(value) { return `${Number(value).toLocaleString()}円`; }

function showMessage(message, isError = false) {
    const box = document.getElementById('inventoryMessage');
    box.className = `alert ${isError ? 'alert-danger' : 'alert-success'}`;
    box.textContent = message;
}
