(() => {
    const form = document.getElementById('alertRuleForm');
    if (!form) return;
    const targets = JSON.parse(document.getElementById('alert-target-data').textContent);
    const targetType = document.getElementById('alertTargetType');
    const targetId = document.getElementById('alertTargetId');
    const ruleType = document.getElementById('alertRuleType');
    const threshold = document.getElementById('alertThreshold');
    const cooldown = document.getElementById('alertCooldown');
    const enabled = document.getElementById('alertEnabled');
    const ruleId = document.getElementById('alertRuleId');
    const list = document.getElementById('alertRuleList');
    const message = document.getElementById('alertRuleMessage');
    const submit = document.getElementById('alertSubmit');
    const cancel = document.getElementById('alertCancel');
    const thresholdHelp = document.getElementById('thresholdHelp');
    const buyerRules = [
        ['price_below', '指定価格以下', '円'], ['median_discount', '相場からの割安率', '%'],
        ['ending_soon', '終了までの時間', '分'], ['low_bids', '入札数', '件以下'],
        ['buy_score', '買い時点数', '点以上'], ['new_listing', '新着候補', '0を指定'],
        ['within_budget', '購入上限内', '費用設定を使用'],
    ];
    const sellerRules = [
        ['bid_stalled', '入札停滞', '時間'], ['ending_without_bids', '終了間近で入札ゼロ', '分'],
        ['loss_risk', '赤字見込み', '赤字額（円）'], ['target_profit', '目標利益到達', '円'],
        ['market_decline', '相場下落', '%'],
    ];
    // Display unit and the value a new rule starts with ('' means the user must choose, e.g. a price).
    const ruleInfo = {
        price_below: {unit: '円', defaultValue: ''}, median_discount: {unit: '%', defaultValue: '20'},
        ending_soon: {unit: '分', defaultValue: '60'}, low_bids: {unit: '件以下', defaultValue: '0'},
        buy_score: {unit: '点以上', defaultValue: '70'}, new_listing: {note: 'しきい値は使いません', defaultValue: '0'},
        within_budget: {note: '費用設定を使います', defaultValue: '0'}, bid_stalled: {unit: '時間', defaultValue: '24'},
        ending_without_bids: {unit: '分', defaultValue: '60'}, loss_risk: {unit: '円以上の赤字', defaultValue: '0'},
        target_profit: {unit: '円', defaultValue: ''}, market_decline: {unit: '%', defaultValue: '10'},
    };
    const targetNames = {savedSearch: '保存検索', watchItem: 'ウォッチ商品', sellerListing: '出品'};
    const thresholdText = item => {
        const info = ruleInfo[item.ruleType] || {};
        if (info.note) return info.note;
        const value = Number(item.thresholdValue);
        const number = Number.isFinite(value) ? value.toLocaleString('ja-JP', {maximumFractionDigits: 4}) : item.thresholdValue;
        return `${number}${info.unit || ''}`;
    };
    const dateText = value => new Date(value).toLocaleString('ja-JP', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    const applyDefault = () => {
        if (ruleId.value) return;
        const value = ruleInfo[ruleType.value]?.defaultValue ?? '0';
        threshold.value = value;
        threshold.placeholder = value === '' ? '値を入力' : '';
    };
    const csrf = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    const api = async (url, options = {}) => {
        const response = await fetch(url, {...options, headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}});
        if (response.status === 204) return {};
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'アラート条件を更新できませんでした');
        return data;
    };
    const show = (text, danger = false) => {
        message.textContent = text;
        message.className = `alert mt-3 mb-0 ${danger ? 'alert-danger' : 'alert-success'}`;
    };
    const option = (value, label) => {
        const item = document.createElement('option'); item.value = value; item.textContent = label; return item;
    };
    const refreshInputs = () => {
        const currentTarget = targetId.value;
        targetId.replaceChildren(...(targets[targetType.value] || []).map(item => option(item.id, item.label)));
        if ([...targetId.options].some(item => item.value === currentTarget)) targetId.value = currentTarget;
        const rules = targetType.value === 'sellerListing' ? sellerRules : buyerRules.filter(item => targetType.value === 'savedSearch' || !['new_listing', 'within_budget'].includes(item[0]));
        const currentRule = ruleType.value;
        ruleType.replaceChildren(...rules.map(item => option(item[0], item[1])));
        if ([...ruleType.options].some(item => item.value === currentRule)) ruleType.value = currentRule;
        thresholdHelp.textContent = rules.find(item => item[0] === ruleType.value)?.[2] || '';
    };
    const reset = () => {
        form.reset(); ruleId.value = ''; submit.textContent = '条件を追加'; cancel.classList.add('d-none');
        targetType.disabled = false; targetId.disabled = false; refreshInputs(); applyDefault();
    };
    const edit = item => {
        ruleId.value = item.id; targetType.value = item.targetType; refreshInputs(); targetId.value = item.targetId;
        ruleType.value = item.ruleType; threshold.value = String(Number(item.thresholdValue)); cooldown.value = item.cooldownMinutes;
        enabled.checked = item.isEnabled; submit.textContent = '変更を保存'; cancel.classList.remove('d-none');
        targetType.disabled = true; targetId.disabled = true; thresholdHelp.textContent = (targetType.value === 'sellerListing' ? sellerRules : buyerRules).find(row => row[0] === ruleType.value)?.[2] || '';
        form.scrollIntoView({behavior: 'smooth', block: 'start'});
    };
    const element = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const ruleCard = item => {
        const card = element('article', `card alert-rule-card${item.isEnabled ? '' : ' is-paused'}`);
        card.dataset.ruleId = item.id;
        const body = element('div', 'card-body d-flex flex-wrap justify-content-between align-items-start gap-3');
        const info = element('div', 'flex-grow-1');
        info.append(
            element('h4', 'h6 mb-1', item.ruleLabel),
            element('p', 'mb-1 alert-rule-threshold', `しきい値：${thresholdText(item)}・通知間隔：${Number(item.cooldownMinutes).toLocaleString('ja-JP')}分`),
            element('p', 'small text-muted mb-0', item.lastTriggeredAt ? `最終通知：${dateText(item.lastTriggeredAt)}` : 'まだ通知していません'),
        );
        const controls = element('div', 'd-flex flex-wrap align-items-center gap-2');
        const toggleWrap = element('div', 'form-check form-switch mb-0');
        const toggle = element('input', 'form-check-input');
        Object.assign(toggle, {type: 'checkbox', id: `alertToggle${item.id}`, checked: item.isEnabled});
        const toggleLabel = element('label', 'form-check-label', item.isEnabled ? '通知する' : '停止中');
        toggleLabel.htmlFor = toggle.id;
        toggle.addEventListener('change', async () => {
            toggle.disabled = true;
            try {
                await api(`/taskle/api/v1/alert-rules/${item.id}`, {method: 'PATCH', body: JSON.stringify({isEnabled: toggle.checked})});
                show(toggle.checked ? 'アラート条件を再開しました。' : 'アラート条件を停止しました。');
                await load();
            } catch (error) { toggle.checked = !toggle.checked; show(error.message, true); toggle.disabled = false; }
        });
        toggleWrap.append(toggle, toggleLabel);
        const editButton = element('button', 'btn btn-sm btn-outline-primary', '編集'); editButton.type = 'button'; editButton.addEventListener('click', () => edit(item));
        const deleteButton = element('button', 'btn btn-sm btn-outline-danger', '削除'); deleteButton.type = 'button'; deleteButton.addEventListener('click', async () => { deleteButton.disabled = true; try { await api(`/taskle/api/v1/alert-rules/${item.id}`, {method: 'DELETE'}); show('アラート条件を削除しました。'); await load(); } catch (error) { show(error.message, true); deleteButton.disabled = false; } });
        controls.append(toggleWrap, editButton, deleteButton);
        body.append(info, controls); card.append(body);
        return card;
    };
    const render = items => {
        if (!items.length) { const empty = element('div', 'card card-body text-muted', 'アラート条件はまだありません。'); list.replaceChildren(empty); return; }
        // One group per target, ordered by target kind and then name, so each target's rules read together.
        const order = Object.keys(targetNames);
        const groups = new Map();
        [...items].sort((a, b) => order.indexOf(a.targetType) - order.indexOf(b.targetType) || String(a.targetLabel).localeCompare(String(b.targetLabel), 'ja') || a.id - b.id)
            .forEach(item => {
                const key = `${item.targetType}:${item.targetId}`;
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push(item);
            });
        list.replaceChildren(...[...groups.values()].map(rules => {
            const section = element('section', 'alert-target-group');
            const header = element('h3', 'h6 alert-target-label mb-2');
            header.append(element('span', 'badge alert-target-kind me-2', targetNames[rules[0].targetType] || ''), document.createTextNode(rules[0].targetLabel));
            const count = element('span', 'text-muted small ms-2', `${rules.length}件`);
            header.append(count);
            const stack = element('div', 'd-grid gap-2');
            stack.append(...rules.map(ruleCard));
            section.append(header, stack);
            return section;
        }));
    };
    const load = async () => { try { render((await api('/taskle/api/v1/alert-rules')).items); } catch (error) { show(error.message, true); } };
    targetType.addEventListener('change', () => { refreshInputs(); applyDefault(); }); ruleType.addEventListener('change', () => { refreshInputs(); applyDefault(); }); cancel.addEventListener('click', reset);
    form.addEventListener('submit', async event => {
        event.preventDefault(); submit.disabled = true;
        const payload = {ruleType: ruleType.value, thresholdValue: threshold.value, cooldownMinutes: cooldown.value, isEnabled: enabled.checked};
        if (!ruleId.value) payload[`${targetType.value}Id`] = Number(targetId.value);
        try { await api(ruleId.value ? `/taskle/api/v1/alert-rules/${ruleId.value}` : '/taskle/api/v1/alert-rules', {method: ruleId.value ? 'PATCH' : 'POST', body: JSON.stringify(payload)}); show(ruleId.value ? 'アラート条件を更新しました。' : 'アラート条件を追加しました。'); reset(); await load(); }
        catch (error) { show(error.message, true); } finally { submit.disabled = false; }
    });
    refreshInputs(); applyDefault(); load();
})();
