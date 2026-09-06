/* Owner-scoped purchase decisions; render user content through textContent. */
(() => {
    'use strict';
    const labels = {salePrice: '想定販売価格', feeRate: '販売手数料率（0〜1、例：0.10）', purchaseShipping: '仕入時の送料', shippingCost: '販売時の発送送料', packagingCost: '梱包費', otherCost: 'その他費用', targetProfit: '目標利益'};
    const yen = value => value == null ? '不明' : `${Number(value).toLocaleString()}円`;
    const el = (tag, text = '', cls = '') => { const node = document.createElement(tag); node.textContent = text; node.className = cls; return node; };
    async function api(url, method = 'GET', payload) {
        const response = await fetch(url, {method, headers: window.systemaCsrfHeaders({'Content-Type': 'application/json'}), ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
        let result;
        try { result = await response.json(); } catch (_) { throw new Error('応答を読み取れません。ログイン状態を確認してください。'); }
        if (!response.ok) throw new Error(result.error?.message || result.error || `HTTP ${response.status}`);
        return result;
    }
    function field(form, key, label, value, prefix, type = 'number') {
        const wrap = el('div', '', 'col-md-4');
        const input = el(type === 'textarea' ? 'textarea' : 'input', '', 'form-control');
        input.id = `${prefix}-${key}`; input.name = key;
        if (type !== 'textarea') input.type = type;
        if (type === 'number') { input.min = '0'; input.max = key === 'feeRate' ? '1' : '1000000000000'; input.step = key === 'feeRate' ? '0.00001' : '1'; }
        if (type === 'textarea') input.maxLength = 2000;
        input.value = value ?? '';
        const title = el('label', label, 'form-label'); title.htmlFor = input.id;
        wrap.append(title, input); form.append(wrap); return input;
    }
    function values(form, keys) { return Object.fromEntries(keys.map(key => [key, form.elements.namedItem(key).value === '' ? null : form.elements.namedItem(key).value])); }
    function action(text, handler) {
        const button = el('button', text, 'btn btn-outline-primary'); button.type = 'button';
        button.addEventListener('click', handler); return button;
    }
    let selection = 0;
    window.renderPurchaseDecision = snapshot => {
        const view = el('details', '', 'mt-3'); view.append(el('summary', '保存した購入判断・根拠'));
        if (!snapshot || !snapshot.result) { view.append(el('p', '購入判断は保存されていません。')); return view; }
        const result = snapshot.result;
        const status = {insufficient: '判定材料不足', no_budget: '目標を満たす購入額なし', within_budget: '購入上限内', over_budget: '購入上限を超過'};
        view.append(el('p', `${status[result.status]} ／ 購入上限 ${yen(result.purchaseLimit)} ／ 見込み利益 ${yen(result.estimatedProfit)} ／ 目標との差 ${yen(result.targetDifference)}`, 'fw-bold'));
        view.append(el('p', `保存日時 ${new Date(snapshot.savedAt).toLocaleString('ja-JP')} ／ 試算した購入価格 ${yen(snapshot.candidatePrice)}。入札価格は最終取得価格ではありません。`, 'small'));
        Object.entries(labels).forEach(([key, label]) => view.append(el('div', `${label}：${key === 'feeRate' ? snapshot.assumptions[key] ?? '不明' : yen(snapshot.assumptions[key])}`)));
        const evidence = snapshot.evidence;
        view.append(el('p', `売価根拠：${evidence.source === 'closed_search' ? '保存済み落札検索の中央値' : '手入力'} ／ 根拠件数 ${evidence.count ?? '不明'} ／ 観測日時 ${evidence.observedAt ? new Date(evidence.observedAt).toLocaleString('ja-JP') : '不明'} ／ 落札対象期間：不明。検索結果全体が同条件の商品とは限りません。`, 'mt-2'));
        view.append(el('p', evidence.note || '根拠メモなし'));
        if (evidence.items?.length) {
            const refs = el('details'); refs.append(el('summary', `参照商品 ${evidence.items.length}件`));
            evidence.items.forEach(item => {
                const row = el('p', `${item.Name} ／ ${yen(item.EndPrice)} `);
                try { const url = new URL(item.URL); if (['https:', 'http:'].includes(url.protocol) && ['auctions.yahoo.co.jp', 'page.auctions.yahoo.co.jp'].includes(url.hostname)) { const link = el('a', '出典'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; row.append(link); } } catch (_) { /* Invalid source stays plain text. */ }
                refs.append(row);
            }); view.append(refs);
        }
        return view;
    };
    window.openPurchaseBudget = async item => {
        const root = document.getElementById('purchaseBudgetEditor'); if (!root) return;
        const ticket = ++selection;
        root.replaceChildren(el('p', '購入判断を読み込み中…')); root.scrollIntoView({block: 'start'});
        try {
            const [data, settings] = await Promise.all([api(`/taskle/api/v1/watch-items/${item.id}/purchase-budget`), api('/taskle/api/v1/cost-settings')]);
            if (ticket !== selection) return;
            root.replaceChildren(el('h3', `${item.name} の購入判断`, 'h5'));
            root.append(el('p', `現在の観測価格 ${yen(data.currentPrice)}。保存した判断は保存時点の価格を使います。変更後の価格で判断する場合は再保存してください。`, 'small text-muted'));
            const saved = data.data;
            const form = el('form', '', 'row g-3');
            const assumptions = saved.assumptions || data.defaults;
            Object.entries(labels).forEach(([key, label]) => field(form, key, label, assumptions[key], 'budget'));
            const wrap = el('div', '', 'col-12');
            const evidence = el('select', '', 'form-select'); evidence.name = 'evidenceRunId'; evidence.id = 'budget-evidence';
            evidence.add(new Option('手入力（根拠メモを入力）', ''));
            settings.evidenceRuns.forEach(run => evidence.add(new Option(`${run.keyword} ／ ${new Date(run.observedAt).toLocaleString('ja-JP')} ／ ${run.count}件`, run.id)));
            if (saved.evidence?.runId && !settings.evidenceRuns.some(run => run.id === saved.evidence.runId)) {
                evidence.add(new Option('保存時の検索履歴（再保存時に存在を確認）', saved.evidence.runId));
            }
            evidence.value = saved.evidence?.runId || '';
            const label = el('label', '売価の根拠（落札検索を選ぶと保存時に中央値を使用）', 'form-label'); label.htmlFor = evidence.id;
            wrap.append(label, evidence); form.append(wrap);
            field(form, 'evidenceNote', '売価の根拠・商品条件についてのメモ', saved.evidence?.note, 'budget', 'textarea');
            const changeEvidence = () => { form.elements.salePrice.disabled = !!evidence.value || data.locked; };
            evidence.addEventListener('change', changeEvidence); changeEvidence();
            const actions = el('div', '', 'col-12 d-flex flex-wrap gap-2');
            const status = el('p', '', 'col-12'); status.setAttribute('role', 'status');
            const output = el('div', '', 'col-12'); output.append(window.renderPurchaseDecision(saved));
            const save = el('button', '計算して購入判断を保存', 'btn btn-primary'); save.type = 'submit';
            const apply = action('共通の費用設定を適用', async () => {
                apply.disabled = true;
                try { const latest = await api('/taskle/api/v1/cost-settings'); Object.keys(latest.data).forEach(key => { form.elements.namedItem(key).value = latest.data[key] ?? ''; }); status.textContent = '費用設定を適用しました。保存すると購入判断に反映されます。'; }
                catch (error) { status.textContent = error.message; } finally { apply.disabled = false; }
            });
            actions.append(save, apply); form.append(actions, status, output); root.append(form);
            if (data.locked) { [...form.elements].forEach(input => { input.disabled = true; }); status.textContent = '在庫化済みです。購入時の判断を表示しています。'; return; }
            form.addEventListener('submit', async event => {
                event.preventDefault(); const payload = {assumptions: values(form, Object.keys(labels)), evidenceRunId: evidence.value || null, evidenceNote: form.elements.evidenceNote.value};
                const controls = [...form.elements]; controls.forEach(input => { input.disabled = true; }); status.textContent = '計算・保存中…';
                try { const response = await api(`/taskle/api/v1/watch-items/${item.id}/purchase-budget`, 'POST', payload); output.replaceChildren(window.renderPurchaseDecision(response.data)); output.firstChild.open = true; status.textContent = '購入判断を保存しました。'; }
                catch (error) { status.textContent = error.message; }
                finally { controls.forEach(input => { input.disabled = false; }); changeEvidence(); }
            });
            const link = el('a', '購入後は在庫・出品管理へ', 'd-inline-block mt-3'); link.href = '/taskle/seller-management'; root.append(link);
        } catch (error) { if (ticket === selection) root.replaceChildren(el('p', error.message, 'alert alert-danger'), action('再読み込み', () => window.openPurchaseBudget(item))); }
    };
    document.addEventListener('DOMContentLoaded', async () => {
        const root = document.getElementById('purchaseCostSettings'); if (!root) return;
        const load = async () => {
            root.replaceChildren(el('p', '費用設定を読み込み中…'));
            try {
                const result = await api('/taskle/api/v1/cost-settings');
                const form = el('form', '', 'row g-3');
                Object.entries(labels).filter(([key]) => key !== 'salePrice').forEach(([key, label]) => field(form, key, label, result.data[key], 'cost'));
                const wrap = el('div', '', 'col-12'); const save = el('button', '共通の費用設定を保存', 'btn btn-outline-primary'); save.type = 'submit';
                const status = el('p'); status.setAttribute('role', 'status'); wrap.append(save, status); form.append(wrap); root.replaceChildren(form);
                form.addEventListener('submit', async event => {
                    event.preventDefault(); const payload = values(form, Object.keys(labels).filter(key => key !== 'salePrice'));
                    const controls = [...form.elements]; controls.forEach(input => { input.disabled = true; }); status.textContent = '保存中…';
                    try { await api('/taskle/api/v1/cost-settings', 'PUT', payload); status.textContent = '保存しました。保存済みの商品別判断は変わりません。'; }
                    catch (error) { status.textContent = error.message; } finally { controls.forEach(input => { input.disabled = false; }); }
                });
            } catch (error) { root.replaceChildren(el('p', error.message, 'alert alert-danger'), action('再読み込み', load)); }
        }; await load();
    });
})();
