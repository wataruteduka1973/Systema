// 相場分析。キーワードを検索履歴から選ぶか新しく入力し、保存データの概要と30日後の相場予想を表示する。
document.addEventListener('DOMContentLoaded', () => {
    const dropdown = document.getElementById('searchWordDropdown');
    const searchInput = document.getElementById('search');
    const searchButton = document.getElementById('button-search');
    const searchSpinner = document.getElementById('searchSpinner');
    const analyzeButton = document.getElementById('analyzeMarketPrice');
    const predictSavedButton = document.getElementById('predictSavedKeyword');
    const updateButton = document.getElementById('updateMarketData');
    const updateSpinner = document.getElementById('updateSpinner');
    const deleteButton = document.getElementById('deleteMarketData');
    const saveButton = document.getElementById('saveKeyword');
    const storedSection = document.getElementById('storedAnalysis');
    let unsavedKeyword = '';

    function setSource(source) {
        document.querySelectorAll('[data-source]').forEach(tab => {
            const active = tab.dataset.source === source;
            tab.classList.toggle('active', active);
            tab.setAttribute('aria-selected', String(active));
            document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
        });
        const url = new URL(window.location.href);
        if (source === 'new') url.searchParams.set('source', 'new'); else url.searchParams.delete('source');
        url.searchParams.delete('keyword');
        window.history.replaceState(null, '', url);
    }

    function clearResults() {
        storedSection.hidden = true;
        saveButton.hidden = true;
        unsavedKeyword = '';
        window.SystemaPrediction.hide();
    }

    function selectedKeyword() {
        if (!dropdown.value) window.SystemaFeedback.warning('検索ワードを選択してください');
        return dropdown.value;
    }

    // 処理中はボタンを止めてスピナーを出す。
    async function busy(button, spinner, task) {
        spinner.style.display = 'inline-block';
        button.disabled = true;
        try {
            return await task();
        } finally {
            spinner.style.display = 'none';
            button.disabled = false;
        }
    }

    async function showStoredAnalysis(keyword) {
        try {
            const response = await fetch(`/taskle/get_market_data?keyword=${encodeURIComponent(keyword)}`);
            if (!response.ok) throw await window.SystemaFeedback.responseError(response, '相場データを取得できませんでした');
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            renderMarketSummary(data.analysis?.summary || {});
            renderConditionStats(data.analysis?.conditionMarket || {});
            document.getElementById('searchDay').textContent = data.searchDay || '';
            storedSection.hidden = false;
        } catch (error) {
            console.error('Error fetching market data:', error);
            window.SystemaFeedback.errorFrom(error, '相場データを取得できませんでした');
        }
    }

    document.querySelectorAll('[data-source]').forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.classList.contains('active')) return;
            setSource(tab.dataset.source);
            clearResults();
        });
    });
    const query = new URLSearchParams(window.location.search);
    setSource(query.get('source') === 'new' ? 'new' : 'history');
    refreshSearchWordDropdown().then(() => {
        // 市場検索の「相場分析で予想を見る」から来たときは、そのキーワードの予想をすぐ表示する。
        const keyword = query.get('source') === 'new' ? (query.get('keyword') || '').trim() : '';
        if (!keyword) return;
        searchInput.value = keyword;
        predictNewKeyword();
    });
    window.SystemaPrediction.loadPopularWords(searchInput);

    analyzeButton.addEventListener('click', () => {
        const keyword = selectedKeyword();
        if (keyword) showStoredAnalysis(keyword);
    });

    predictSavedButton.addEventListener('click', () => {
        const keyword = selectedKeyword();
        if (!keyword) return;
        saveButton.hidden = true;
        busy(predictSavedButton, predictSavedButton.querySelector('.spinner-border'),
            () => window.SystemaPrediction.run(keyword));
    });

    async function predictNewKeyword() {
        const keyword = searchInput.value.trim();
        if (!keyword) {
            window.SystemaFeedback.warning('検索キーワードを入力してください');
            return;
        }
        saveButton.hidden = true;
        const result = await busy(searchButton, searchSpinner, () => window.SystemaPrediction.run(keyword));
        if (!result) return;
        unsavedKeyword = result.keyword || keyword;
        const saved = Array.from(dropdown.options).some(option => option.value === unsavedKeyword);
        saveButton.hidden = saved;
    }

    searchButton.addEventListener('click', predictNewKeyword);
    searchInput.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            predictNewKeyword();
        }
    });

    async function storeMarketData(keyword) {
        const response = await fetch(`/taskle/update_market_data?keyword=${encodeURIComponent(keyword)}`, {
            method: 'POST',
            headers: window.systemaCsrfHeaders(),
        });
        if (!response.ok) throw await window.SystemaFeedback.responseError(response, '保存に失敗しました');
        return response.json();
    }

    saveButton.addEventListener('click', () => {
        const keyword = unsavedKeyword;
        if (!keyword) return;
        busy(saveButton, saveButton.querySelector('.spinner-border'), async () => {
            try {
                await storeMarketData(keyword);
                window.SystemaFeedback.success('検索履歴に保存しました');
                saveButton.hidden = true;
                unsavedKeyword = '';
                await refreshSearchWordDropdown(keyword);
                setSource('history');
                await showStoredAnalysis(keyword);
            } catch (error) {
                window.SystemaFeedback.errorFrom(error, '保存に失敗しました');
            }
        });
    });

    updateButton.addEventListener('click', () => {
        const keyword = selectedKeyword();
        if (!keyword) return;
        busy(updateButton, updateSpinner, async () => {
            try {
                const data = await storeMarketData(keyword);
                window.SystemaFeedback.success(data.message || '相場データを更新しました');
                await refreshSearchWordDropdown(keyword);
                await showStoredAnalysis(keyword);
            } catch (error) {
                window.SystemaFeedback.errorFrom(error, '更新に失敗しました');
            }
        });
    });

    deleteButton.addEventListener('click', () => {
        const keyword = selectedKeyword();
        if (!keyword || !confirm('本当に削除しますか？')) return;
        fetch(`/taskle/delete_market_data?keyword=${encodeURIComponent(keyword)}`, {
            method: 'DELETE',
            headers: window.systemaCsrfHeaders(),
        })
            .then(async response => {
                if (!response.ok) throw await window.SystemaFeedback.responseError(response, '削除に失敗しました');
                return response.json();
            })
            .then(data => {
                window.SystemaFeedback.success(data.message || '相場データを削除しました');
                refreshSearchWordDropdown();
                clearResults();
            })
            .catch(error => window.SystemaFeedback.errorFrom(error, '削除に失敗しました'));
    });
});

function refreshSearchWordDropdown(selectedValue = '') {
    return fetch('/taskle/get_search_words')
        .then(response => response.json())
        .then(data => {
            const dropdown = document.getElementById('searchWordDropdown');
            dropdown.innerHTML = '<option value="">選択してください</option>';
            data.searchWords.forEach(word => {
                const option = document.createElement('option');
                option.value = word;
                option.textContent = word;
                dropdown.appendChild(option);
            });
            if (selectedValue) dropdown.value = selectedValue;
        })
        .catch(error => console.error('Error fetching search words:', error));
}

function formatYen(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toLocaleString()}円` : '—';
}

function renderMarketSummary(summary) {
    const values = [
        ['商品数', `${summary.count || 0}件`],
        ['中央値', formatYen(summary.median)],
        ['平均価格', formatYen(summary.mean)],
        ['価格変動', summary.coefficientOfVariation == null ? '—' : `${summary.coefficientOfVariation}%`],
        ['中央50%の幅', formatYen(summary.iqr)],
        ['外れ値候補', `${summary.outlierCount || 0}件`]
    ];
    document.getElementById('marketSummaryCards').innerHTML = values.map(([label, value]) => `
        <div class="col-6 col-lg-2"><div class="analysis-card">
            <div class="text-muted small">${label}</div><div class="value">${value}</div>
        </div></div>`).join('');
}

function renderConditionStats(market) {
    const rows = market.conditions || [];
    const target = document.getElementById('conditionStats');
    if (!rows.length) {
        target.innerHTML = '<p class="text-muted">状態別に集計できるデータがありません。</p>';
        return;
    }
    target.innerHTML = `<table class="table table-striped align-middle mb-0">
        <thead><tr><th>商品状態</th><th>件数</th><th>中央値</th></tr></thead>
        <tbody>${rows.map(row => `<tr><td>${row.label}</td><td>${row.count}件</td><td>${formatYen(row.medianPrice)}</td></tr>`).join('')}</tbody>
    </table>`;
}
