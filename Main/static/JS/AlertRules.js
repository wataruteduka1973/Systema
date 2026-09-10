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
        targetType.disabled = false; targetId.disabled = false; refreshInputs();
    };
    const edit = item => {
        ruleId.value = item.id; targetType.value = item.targetType; refreshInputs(); targetId.value = item.targetId;
        ruleType.value = item.ruleType; threshold.value = item.thresholdValue; cooldown.value = item.cooldownMinutes;
        enabled.checked = item.isEnabled; submit.textContent = '変更を保存'; cancel.classList.remove('d-none');
        targetType.disabled = true; targetId.disabled = true; thresholdHelp.textContent = (targetType.value === 'sellerListing' ? sellerRules : buyerRules).find(row => row[0] === ruleType.value)?.[2] || '';
        form.scrollIntoView({behavior: 'smooth', block: 'start'});
    };
    const render = items => {
        if (!items.length) { const empty = document.createElement('div'); empty.className = 'card card-body text-muted'; empty.textContent = 'アラート条件はまだありません。'; list.replaceChildren(empty); return; }
        list.replaceChildren(...items.map(item => {
            const card = document.createElement('article'); card.className = 'card';
            const body = document.createElement('div'); body.className = 'card-body';
            const title = document.createElement('h3'); title.className = 'h5'; title.textContent = item.ruleLabel;
            const target = document.createElement('p'); target.className = 'alert-target-label mb-2'; target.textContent = `対象: ${item.targetLabel}`;
            const detail = document.createElement('p'); detail.className = 'text-muted small'; detail.textContent = `しきい値 ${item.thresholdValue} / 通知間隔 ${item.cooldownMinutes}分 / ${item.isEnabled ? '有効' : '停止中'}`;
            const actions = document.createElement('div'); actions.className = 'd-flex gap-2';
            const editButton = document.createElement('button'); editButton.className = 'btn btn-sm btn-outline-primary'; editButton.type = 'button'; editButton.textContent = '編集'; editButton.addEventListener('click', () => edit(item));
            const deleteButton = document.createElement('button'); deleteButton.className = 'btn btn-sm btn-outline-danger'; deleteButton.type = 'button'; deleteButton.textContent = '削除'; deleteButton.addEventListener('click', async () => { deleteButton.disabled = true; try { await api(`/taskle/api/v1/alert-rules/${item.id}`, {method: 'DELETE'}); show('アラート条件を削除しました。'); await load(); } catch (error) { show(error.message, true); deleteButton.disabled = false; } });
            actions.append(editButton, deleteButton); body.append(title, target, detail, actions); card.append(body); return card;
        }));
    };
    const load = async () => { try { render((await api('/taskle/api/v1/alert-rules')).items); } catch (error) { show(error.message, true); } };
    targetType.addEventListener('change', refreshInputs); ruleType.addEventListener('change', refreshInputs); cancel.addEventListener('click', reset);
    form.addEventListener('submit', async event => {
        event.preventDefault(); submit.disabled = true;
        const payload = {ruleType: ruleType.value, thresholdValue: threshold.value, cooldownMinutes: cooldown.value, isEnabled: enabled.checked};
        if (!ruleId.value) payload[`${targetType.value}Id`] = Number(targetId.value);
        try { await api(ruleId.value ? `/taskle/api/v1/alert-rules/${ruleId.value}` : '/taskle/api/v1/alert-rules', {method: ruleId.value ? 'PATCH' : 'POST', body: JSON.stringify(payload)}); show(ruleId.value ? 'アラート条件を更新しました。' : 'アラート条件を追加しました。'); reset(); await load(); }
        catch (error) { show(error.message, true); } finally { submit.disabled = false; }
    });
    refreshInputs(); load();
})();
