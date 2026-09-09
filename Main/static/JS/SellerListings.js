(() => {
    'use strict';
    const base = '/taskle/api/v1/seller-listings';
    const statuses = {draft: '登録済み', active: '出品中', ended: '終了', sold: '落札済み', cancelled: '見送り', relist: '再出品待ち'};
    let page = 1;
    let loadId = 0;
    const yen = value => value == null ? '未取得・未設定' : `${Number(value).toLocaleString()}円`;
    const date = value => value ? new Date(value).toLocaleString('ja-JP') : '未取得';
    const localDateTime = value => {
        const time = value ? new Date(value) : new Date();
        return new Date(time.getTime() - time.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    };
    const el = (tag, text = '', cls = '') => {
        const node = document.createElement(tag);
        node.textContent = text;
        node.className = cls;
        return node;
    };
    function message(text, error = false) {
        const node = document.getElementById('sellerMessage');
        node.textContent = text;
        node.className = `alert ${error ? 'alert-danger' : 'alert-success'}`;
    }
    async function api(url, method = 'GET', payload) {
        const response = await fetch(url, {
            method, headers: window.systemaCsrfHeaders({'Content-Type': 'application/json'}),
            ...(payload === undefined ? {} : {body: JSON.stringify(payload)}),
        });
        if (response.status === 204) return {};
        let result;
        try { result = await response.json(); } catch (_) { throw new Error(`通信に失敗しました（HTTP ${response.status}）。ログイン状態を確認してください。`); }
        if (!response.ok) throw new Error(result.error?.message || result.error || `HTTP ${response.status}`);
        return result;
    }
    async function busy(button, action) {
        button.disabled = true;
        try { await action(); } catch (error) { message(error.message, true); }
        finally { button.disabled = false; }
    }
    function button(text, action, cls = 'btn btn-outline-secondary') {
        const node = el('button', text, cls);
        node.type = 'button';
        node.addEventListener('click', () => busy(node, action));
        return node;
    }
    function field(form, prefix, key, label, value, type = 'number') {
        const wrap = el('div', '', 'col-md-4');
        const input = el(type === 'textarea' ? 'textarea' : 'input', '', 'form-control');
        input.id = `${prefix}-${key}`;
        input.name = key;
        if (type !== 'textarea') input.type = type;
        if (type === 'number') { input.min = '0'; input.max = '1000000000000'; input.step = '1'; }
        input.value = value ?? '';
        const title = el('label', label, 'form-label');
        title.htmlFor = input.id;
        wrap.append(title, input);
        form.append(wrap);
        return input;
    }
    function pager(container, meta, callback) {
        container.replaceChildren();
        const previous = button('前へ', () => callback(meta.page - 1));
        previous.disabled = meta.page <= 1;
        const next = button('次へ', () => callback(meta.page + 1));
        next.disabled = meta.page * meta.pageSize >= meta.total;
        container.append(previous, el('span', `${meta.page}ページ ／ 全${meta.total}件`), next);
    }
    function renderSummary(summary) {
        const container = document.getElementById('sellerSummary');
        const values = [
            ['全出品', summary.total, ''],
            ['要対応', summary.requiresAction, ''],
            ['優先度1', summary.urgent, ''],
            ['販売結果待ち', summary.saleResultMissing, 'sale_result_missing'],
        ];
        container.replaceChildren(...values.map(([label, value, action]) => {
            const column = el('div', '', 'col-6 col-lg-3');
            const content = el(action ? 'button' : 'div', '', `card card-body text-start h-100${action ? ' btn btn-outline-secondary' : ''}`);
            content.append(el('span', label, 'small text-muted'), el('strong', `${value}件`, 'fs-4'));
            if (action) {
                content.type = 'button';
                content.addEventListener('click', () => {
                    document.getElementById('sellerAction').value = action;
                    page = 1;
                    load();
                });
            }
            column.append(content);
            return column;
        }));
    }
    async function load() {
        const current = ++loadId;
        const list = document.getElementById('sellerList');
        list.setAttribute('aria-busy', 'true');
        list.replaceChildren(el('p', '出品一覧を読み込み中…', 'text-muted'));
        document.getElementById('sellerPages').replaceChildren();
        try {
            const status = document.getElementById('sellerStatus').value;
            const action = document.getElementById('sellerAction').value;
            const sort = document.getElementById('sellerSort').value;
            const result = await api(`${base}?${new URLSearchParams({page, status, action, sort})}`);
            if (current !== loadId) return;
            renderSummary(result.summary);
            if (!result.data.length && page > 1) { page = Math.max(1, Math.ceil(result.meta.total / result.meta.pageSize)); return await load(); }
            list.replaceChildren(...result.data.map(card));
            if (!result.data.length) list.append(el('p', '該当する出品はありません。URLを登録すると管理を始められます。', 'alert alert-secondary'));
            pager(document.getElementById('sellerPages'), result.meta, async number => { page = number; await load(); });
        } catch (error) { if (current === loadId) { list.replaceChildren(el('p', '一覧を取得できませんでした。「一覧を再読込」で再試行してください。', 'alert alert-danger')); message(error.message, true); } }
        finally { if (current === loadId) list.removeAttribute('aria-busy'); }
    }
    function card(item) {
        const node = el('article', '', 'card card-body mb-3');
        const link = el('a', item.name, 'h5');
        link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        node.append(link, el('p', `${statuses[item.status]} ／ 現在価格 ${yen(item.currentPrice)} ／ 入札 ${item.bidding ?? '未取得'}件 ／ 終了 ${date(item.endsAt)} ／ 残り ${item.remainingSeconds == null ? '未取得' : Math.ceil(item.remainingSeconds / 60) + '分'}`));
        node.append(el('p', `最終取得 ${date(item.lastCheckedAt)}。現在価格・入札数は取得時点の情報です。`, 'small text-muted'));
        const profit = item.profit;
        const action = item.actionStatus;
        const actionClasses = {sale_result_missing: 'alert-warning', loss_risk: 'alert-danger', cost_incomplete: 'alert-warning', target_unmet: 'alert-warning', ending_without_bids: 'alert-warning', bid_stalled: 'alert-info', stale: 'alert-secondary', needs_refresh: 'alert-warning', price_missing: 'alert-warning', ok: 'alert-success', sold: 'alert-success', cancelled: 'alert-secondary', relist: 'alert-info'};
        actionClasses.ending_soon = 'alert-warning';
        actionClasses.status_check = 'alert-info';
        const nextAction = el('div', '', `alert ${actionClasses[action.status] || 'alert-secondary'} mb-2`);
        nextAction.append(el('p', `優先度 ${action.priority} ／ ${action.label} — ${action.nextAction}：${action.reason}`, 'mb-2'));
        node.prepend(nextAction);
        if (item.purchaseDecision?.version) node.append(window.renderPurchaseDecision(item.purchaseDecision));
        if (item.missingCostFields?.length) node.append(el('p', '引継ぎ費用に不明項目があります。費用編集で空欄を確認するまで利益は算出しません。', 'alert alert-warning'));
        const source = {manual: '手入力価格', currentPrice: '取得した現在価格', manualMarketMedian: '手入力相場中央値', unknown: '未設定'};
        node.append(el('p', profit ? `想定販売価格 ${yen(profit.salePrice)} ／ 見込み利益 ${yen(profit.estimatedProfit)} ／ 利益率 ${profit.profitMarginPercent == null ? '算出不能' : profit.profitMarginPercent + '%'} ／ 損益分岐 ${profit.breakEvenPrice == null ? '算出不能' : yen(profit.breakEvenPrice)} ／ 目標との差 ${yen(profit.estimatedProfit - item.targetProfit)}` : '見込み利益：価格未取得・未設定のため算出できません。', profit?.estimatedProfit < 0 ? 'text-danger fw-bold' : 'fw-bold'));
        node.append(el('p', `計算価格の根拠：${source[item.priceSource]}。相場中央値（手入力）：${item.marketMedian ? yen(item.marketMedian) : '未設定'}。確定利益ではありません。`, 'small text-muted'));
        const actions = el('div', '', 'd-flex flex-wrap gap-2 mb-3');
        const refresh = button('公開情報を更新', async () => {
            await api(`${base}/${item.id}/refresh`, 'POST', {});
            message('公開情報を更新し、利益計算条件とともに履歴を保存しました。');
            await load();
        }, 'btn btn-outline-primary');
        actions.append(refresh);
        actions.append(button('削除', async () => {
            if (!window.confirm('出品とその観測履歴を削除します。元の在庫は削除されません。よろしいですか？')) return;
            await api(`${base}/${item.id}`, 'DELETE'); await load(); message('出品を削除しました。');
        }, 'btn btn-outline-danger'));
        node.append(actions);
        const details = el('details');
        details.id = `seller-${item.id}-edit`;
        details.append(el('summary', '費用・想定価格・状態を編集'));
        const form = el('form', '', 'row g-3 mt-1');
        field(form, item.id, 'name', '商品名', item.name, 'text').maxLength = 1000;
        const statusWrap = el('div', '', 'col-md-4');
        const status = el('select', '', 'form-select'); status.name = 'status'; status.id = `seller-${item.id}-status`;
        Object.entries(statuses).forEach(([value, label]) => status.add(new Option(label, value)));
        status.value = item.status;
        const statusLabel = el('label', '管理状態（落札済みは手動指定）', 'form-label'); statusLabel.htmlFor = status.id;
        statusWrap.append(statusLabel, status); form.append(statusWrap);
        const fields = {acquisitionCost:'仕入価格', purchaseShippingCost:'仕入時の送料', shippingCostEstimate:'販売時の発送送料見積', packagingCostEstimate:'梱包費見積', otherCostEstimate:'その他費用', targetProfit:'目標利益', marketMedian:'相場中央値（手入力・0は未設定）', predictedSalePrice:'想定販売価格（空欄は現在価格等）', feeRate:'手数料率（0〜1、例：0.10）'};
        Object.entries(fields).forEach(([key, label]) => {
            const input = field(form, `seller-${item.id}`, key, label, item.missingCostFields?.includes(key) ? null : item[key]);
            input.required = key !== 'predictedSalePrice';
            if (key === 'feeRate') { input.max = '1'; input.step = '0.00001'; }
        });
        field(form, `seller-${item.id}`, 'note', 'メモ', item.note, 'textarea').maxLength = 2000;
        const saveWrap = el('div', '', 'col-12');
        const save = el('button', '費用・状態を保存', 'btn btn-outline-primary'); save.type = 'submit';
        saveWrap.append(save); form.append(saveWrap);
        form.addEventListener('submit', event => {
            event.preventDefault();
            busy(save, async () => {
                const payload = Object.fromEntries(new FormData(form));
                if (payload.predictedSalePrice === '') payload.predictedSalePrice = null;
                await api(`${base}/${item.id}`, 'PATCH', payload);
                message('保存しました。過去の観測履歴は変更されません。'); await load();
            });
        });
        details.append(form); node.append(details);
        const editTargets = {
            cost_incomplete: item.missingCostFields?.[0] || 'acquisitionCost',
            price_missing: 'predictedSalePrice',
            loss_risk: 'predictedSalePrice',
            target_unmet: 'targetProfit',
            status_check: 'status', cancelled: 'status', relist: 'status',
        };
        const target = editTargets[action.status];
        if (target) {
            const edit = button(action.nextAction, () => {
                details.open = true;
                const input = form.elements.namedItem(target);
                input.focus();
                input.scrollIntoView({block: 'center'});
            }, 'btn btn-primary');
            edit.setAttribute('aria-controls', details.id);
            nextAction.append(edit);
        } else if (['needs_refresh', 'stale', 'ending_soon', 'ending_without_bids', 'bid_stalled'].includes(action.status)) {
            refresh.className = 'btn btn-primary';
            nextAction.append(refresh);
        }
        if (['status_check', 'sold'].includes(action.status)) {
            details.append(el('p', '管理状態はユーザーが明示的に記録します。公開ページの終了だけでは販売済みにしません。', 'small text-muted mt-2'));
        }
        const sale = item.saleRecord;
        if (action.status === 'sale_result_missing' || sale) {
            const saleDetails = el('details');
            saleDetails.id = `seller-${item.id}-sale`;
            saleDetails.append(el('summary', sale ? '販売結果を確認・修正' : '販売結果を入力'));
            const saleForm = el('form', '', 'row g-3 mt-1');
            const saleFields = [
                ['salePrice', '販売価格', sale?.salePrice],
                ['actualFee', '実手数料', sale?.actualFee ?? 0],
                ['actualShippingCost', '実送料', sale?.actualShippingCost ?? item.shippingCostEstimate],
                ['actualPackagingCost', '実梱包費', sale?.actualPackagingCost ?? item.packagingCostEstimate],
                ['actualOtherCost', 'その他実費', sale?.actualOtherCost ?? item.otherCostEstimate],
            ];
            saleFields.forEach(([key, label, value]) => { field(saleForm, `sale-${item.id}`, key, label, value).required = true; });
            const soldAt = field(saleForm, `sale-${item.id}`, 'soldAt', '販売日時', '', 'datetime-local');
            soldAt.value = localDateTime(sale?.soldAt || item.endsAt);
            soldAt.required = true;
            if (sale) saleForm.append(el('p', `確定利益 ${yen(sale.confirmedProfit)}。仕入価格と仕入時送料を含め、サーバーで再計算した結果です。`, sale.confirmedProfit < 0 ? 'col-12 text-danger fw-bold' : 'col-12 fw-bold'));
            const saveSale = el('button', sale ? '販売結果を更新' : '販売結果を確定', 'btn btn-primary');
            saveSale.type = 'submit';
            const saveWrap = el('div', '', 'col-12'); saveWrap.append(saveSale); saleForm.append(saveWrap);
            saleForm.addEventListener('submit', event => {
                event.preventDefault();
                busy(saveSale, async () => {
                    const payload = Object.fromEntries(new FormData(saleForm));
                    payload.soldAt = new Date(payload.soldAt).toISOString();
                    const result = await api(`${base}/${item.id}/sale`, 'PUT', payload);
                    message(`販売結果を保存しました。確定利益は${yen(result.data.confirmedProfit)}です。`);
                    await load();
                });
            });
            saleDetails.append(saleForm); node.append(saleDetails);
            if (['sale_result_missing', 'sold'].includes(action.status)) {
                const saleAction = button(action.nextAction, () => {
                    saleDetails.open = true;
                    saleForm.elements.namedItem('salePrice').focus();
                    saleForm.elements.namedItem('salePrice').scrollIntoView({block: 'center'});
                }, 'btn btn-primary');
                saleAction.setAttribute('aria-controls', saleDetails.id);
                nextAction.append(saleAction);
            }
        }
        const history = el('div', '', 'mt-3');
        node.append(button('価格・入札・利益の履歴', () => loadHistory(item.id, history, 1)), history);
        return node;
    }
    async function loadHistory(id, node, historyPage) {
        const result = await api(`${base}/${id}/snapshots?page=${historyPage}`);
        node.replaceChildren();
        if (!result.data.length) { node.append(el('p', '履歴はありません。「公開情報を更新」で観測を保存します。')); return; }
        const newest = result.data[0], oldest = result.data[result.data.length - 1];
        node.append(el('p', result.data.length < 2 ? '比較には2回以上の観測が必要です。' : `このページ内の推移：価格 ${yen(newest.currentPrice - oldest.currentPrice)} ／ 入札 ${newest.bidding - oldest.bidding}件 ／ 見込み利益 ${yen(newest.estimatedProfit == null || oldest.estimatedProfit == null ? null : newest.estimatedProfit - oldest.estimatedProfit)}`));
        node.append(el('p', '新しい順。利益変化には価格だけでなく、費用・手数料・想定価格の設定変更も含まれます。', 'small text-muted'));
        const wrap = el('div', '', 'table-responsive');
        const table = el('table', '', 'table table-sm');
        const head = el('thead'), row = el('tr');
        ['観測日時', '現在価格', '入札', '想定販売価格', '手数料', '見込み利益', '当時の計算条件'].forEach(text => { const cell = el('th', text); cell.scope = 'col'; row.append(cell); });
        head.append(row); table.append(head);
        const body = el('tbody');
        result.data.forEach(snapshot => {
            const row = el('tr');
            [date(snapshot.observedAt), yen(snapshot.currentPrice), snapshot.bidding, yen(snapshot.predictedSalePrice), yen(snapshot.estimatedFee), yen(snapshot.estimatedProfit)].forEach(value => row.append(el('td', String(value))));
            const inputs = snapshot.calculationInputs;
            row.append(el('td', `仕入 ${yen(inputs.acquisition_cost)}／送料 ${yen(inputs.shipping_cost)}／梱包 ${yen(inputs.packaging_cost)}／その他 ${yen(inputs.other_cost)}／料率 ${inputs.fee_rate}`)); body.append(row);
        });
        table.append(body); wrap.append(table); node.append(wrap);
        const pages = el('div', '', 'd-flex flex-wrap gap-2 align-items-center');
        pager(pages, result.meta, number => loadHistory(id, node, number)); node.append(pages);
    }
    async function inventoryOptions() {
        try {
            const result = await api('/taskle/api/v1/inventory-items');
            const select = document.getElementById('sellerInventory');
            const selected = select.value;
            select.replaceChildren(new Option('紐付けなし', ''));
            result.items.forEach(item => select.add(new Option(`${item.name}（${yen(item.acquisitionCost)}）`, item.id)));
            select.value = selected;
        } catch (error) { message(error.message, true); }
    }
    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('sellerCreateForm');
        form.addEventListener('submit', event => {
            event.preventDefault();
            busy(form.querySelector('button'), async () => {
                const payload = Object.fromEntries(new FormData(form));
                if (!payload.inventoryItemId) delete payload.inventoryItemId;
                if (!payload.name.trim()) delete payload.name;
                await api(base, 'POST', payload); form.reset(); page = 1;
                document.getElementById('sellerStatus').value = '';
                document.getElementById('sellerAction').value = '';
                message('出品を登録しました。費用を確認し「公開情報を更新」を押してください。'); await load();
            });
        });
        document.getElementById('sellerStatus').addEventListener('change', () => { page = 1; load(); });
        ['sellerAction', 'sellerSort'].forEach(id => document.getElementById(id).addEventListener('change', () => { page = 1; load(); }));
        document.getElementById('sellerReload').addEventListener('click', () => { load(); inventoryOptions(); });
        inventoryOptions(); load();
    });
})();
