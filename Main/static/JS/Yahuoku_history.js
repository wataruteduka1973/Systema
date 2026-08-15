const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let sortKey = null;
let sortOrder = null;
let marketData = [];
let filteredData = [...marketData];
let conditionSummary = null;
let marketStatistics = null;
//ソートした際のアイコン表示
document.addEventListener('DOMContentLoaded', function () {
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(button => {
        button.addEventListener('click', function () {
            const key = this.dataset.sort;
            const order = this.dataset.order;

            sortData(key, order);

            this.dataset.order = order === 'asc' ? 'desc' : 'asc';
            updateSortIcon(this);
        });
    });
});
// ページ読み込み時にソートアイコンを初期化
// ボタンのクリックイベントを設定
document.addEventListener('DOMContentLoaded', () => {
    refreshSearchWordDropdown();

    const dropdown = document.getElementById('searchWordDropdown');
    const SearchDBButton = document.getElementById('SearchDBButton');
    const updateMarketDataButton = document.getElementById('updateMarketData');
    const deleteMarketDataButton = document.getElementById('deleteMarketData');
    const spinner = document.getElementById('updateSpinner');
    document.querySelectorAll('.condition-filter').forEach(input => input.addEventListener('change', filterData));
    document.getElementById('historyExcludeJunk').addEventListener('change', filterData);

    SearchDBButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        fetch(`/taskle/get_market_data?keyword=${encodeURIComponent(searchWord)}`)
            .then(response => response.json())
            .then(result => {
                marketData = result.data || [];
                filteredData = [...marketData];
                conditionSummary = result.analysis?.conditionMarket || null;
                marketStatistics = result.analysis?.summary || null;
                if (window.MarketComparison) {
                    window.MarketComparison.configure({ statistics: marketStatistics });
                }
                currentPage = 1;
                const EndPrices = marketData.map(item => item.EndPrice).filter(EndPrice => !isNaN(EndPrice));
                const median = calculateMedian(EndPrices);
                document.getElementById("medianPrice").textContent = `終了価格の中央値: ${median.toLocaleString()} 円`;
                document.getElementById("medianPrice").style.display = "block";
                updateTable(paginateData(marketData));
                updatePagination();
                document.getElementById('minPrice').value = '0';
                document.getElementById('maxPrice').value = '';
                document.getElementById('bid0_10').checked = false;
                document.getElementById('bid10_20').checked = false;
                document.getElementById('bid20_30').checked = false;
                document.getElementById('bid30_40').checked = false;
                document.getElementById('bid40_50').checked = false;
                document.getElementById('bid50_plus').checked = false;
                clearConditionFilters();
                renderConditionSummary(conditionSummary);
            })
            .catch(error => {
                console.error('検索エラー:', error);
                alert('検索に失敗しました');
            })
    });

    updateMarketDataButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        spinner.style.display = 'inline-block';
        updateMarketDataButton.disabled = true;
        fetch(`/taskle/update_market_data?keyword=${encodeURIComponent(searchWord)}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                alert(data.message || '相場データを更新しました');
                refreshSearchWordDropdown(searchWord);
                SearchDBButton.click();
            })
            .catch(error => alert('更新に失敗しました: ' + error))
            .finally(() => {
                spinner.style.display = 'none';
                updateMarketDataButton.disabled = false;
            });
    });

    deleteMarketDataButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        if (!confirm('本当に削除しますか？')) return;
        fetch(`/taskle/delete_market_data?keyword=${encodeURIComponent(searchWord)}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                alert(data.message || '相場データを削除しました');
                refreshSearchWordDropdown();
                marketData = [];
                filteredData = [];
                updateTable([]);
                updatePagination();
            })
            .catch(error => alert('削除に失敗しました: ' + error));
    });
});
// ページ読み込み時にテーブルを初期化
function paginateData(data) {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    return data.slice(start, end);
}
// 中央値を計算する関数
function calculateMedian(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}
// テーブルとページネーションを更新する関数
function updatePagination() {
    const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
    const pagination = document.createElement('nav');
    pagination.innerHTML = `
        <ul class="pagination justify-content-center mt-3">
            <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage - 1}); return false;">前</a>
            </li>
            ${Array.from({ length: totalPages }, (_, i) => `
                <li class="page-item ${currentPage === i + 1 ? 'active' : ''}";>
                    <a class="page-link" href="#" onclick="changePage(${i + 1}); return false;" style="${currentPage === i + 1 ? 'background-color: #ffd700; color: #000000;' : ''}">${i + 1}</a>
                </li>
            `).join('')}
            <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage + 1}); return false;">次</a>
            </li>
        </ul>
    `;
    const container = document.getElementById('dataTableContainer');
    const existingPagination = container.querySelector('nav');
    if (existingPagination) existingPagination.remove();
    container.appendChild(pagination);
}
// ページを変更する関数
function changePage(page) {
    currentPage = page;
    if (currentPage < 1) currentPage = 1;
    const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
    if (currentPage > totalPages) currentPage = totalPages;
    updateTable(paginateData(filteredData));
    updatePagination();
}
// テーブルを更新する関数
function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();

        const compareCell = row.insertCell(0);
        if (window.MarketComparison) compareCell.appendChild(window.MarketComparison.createSelector(item));

        const productNameCell = row.insertCell(1);
        productNameCell.textContent = item.name || item.Name;

        const conditionCell = row.insertCell(2);
        const badge = document.createElement('span');
        badge.className = `badge ${item.condition === 'junk' ? 'bg-danger' : item.condition === 'new' ? 'bg-success' : item.condition === 'used' ? 'bg-primary' : 'bg-secondary'}`;
        badge.textContent = item.conditionLabel || '未分類';
        conditionCell.appendChild(badge);
        if (Array.isArray(item.attributeLabels) && item.attributeLabels.length) {
            const attributes = document.createElement('div');
            attributes.className = 'small text-muted mt-1';
            attributes.textContent = item.attributeLabels.join('・');
            conditionCell.appendChild(attributes);
        }

        const endPriceCell = row.insertCell(3);
        endPriceCell.textContent = item.EndPrice.toLocaleString();

        const startPriceCell = row.insertCell(4);
        startPriceCell.textContent = item.StartPrice.toLocaleString();

        const biddingCell = row.insertCell(5);
        biddingCell.textContent = item.Bidding;

        const productURLCell = row.insertCell(6);
        const link = document.createElement("a");
        link.href = item.URL || "#";
        link.textContent = "商品リンクURL";
        link.target = "_blank"
        productURLCell.appendChild(link);
    });
}

// ソート機能を実装する関数
function sortData(key, order) {
    sortKey = key;
    sortOrder = order;
    filteredData.sort((a, b) => {
        let valueA = a[key];
        let valueB = b[key];
        if (typeof valueA === 'string') valueA = parseFloat(valueA.replace(/[^\d.-]/g, '')) || 0;
        if (typeof valueB === 'string') valueB = parseFloat(valueB.replace(/[^\d.-]/g, '')) || 0;
        return order === 'asc' ? valueA - valueB : valueB - valueA;
    });
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();

}
// ソートアイコンを更新する関数
function updateSortIcon(button) {
    const svg = button.querySelector('svg');
    if (button.dataset.order === 'asc') {
        svg.innerHTML = `
            <path d="M3.5 13.5a.5.5 0 0 1-1 0V4.707L1.354 5.854a.5.5 0 1 1-.708-.708l2-1.999.007-.007a.498.498 0 0 1 .7.006l2 2a.5.5 0 1 1-.707.708L3.5 4.707V13.5zm4-9.5a.5.5 0 0 1 0-1h1a.5.5 0 0 1 0 1h-1zm0 3a.5.5 0 0 1 0-1h3a.5.5 0 0 1 0 1h-3zm0 3a.5.5 0 0 1 0-1h5a.5.5 0 0 1 0 1h-5zM7 12.5a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 0-1h-7a.5.5 0 0 0-.5.5z"/>
        `;
    } else {
        svg.innerHTML = `
            <path d="M3.5 2.5a.5.5 0 0 0-1 0v8.793l-1.146-1.147a.5.5 0 0 0-.708.708l2 1.999.007.007a.497.497 0 0 0 .7-.006l2-2a.5.5 0 0 0-.707-.708L3.5 11.293V2.5zm3.5 1a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5zM7.5 6a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm0 3a.5.5 0 0 0 0 1h3a.5.5 0 0 0 0-1h-3zm0 3a.5.5 0 0 0 0 1h1a.5.5 0 0 0 0-1h-1z"/>
        `;
    }
}
// フィルタリング機能に関する関数
function filterData() {
    const minPriceInput = document.getElementById('minPrice').value;
    const maxPriceInput = document.getElementById('maxPrice').value;
    const bid0_10 = document.getElementById('bid0_10').checked;
    const bid10_20 = document.getElementById('bid10_20').checked;
    const bid20_30 = document.getElementById('bid20_30').checked;
    const bid30_40 = document.getElementById('bid30_40').checked;
    const bid40_50 = document.getElementById('bid40_50').checked;
    const bid50_plus = document.getElementById('bid50_plus').checked;
    const selectedConditions = Array.from(document.querySelectorAll('.condition-filter:checked')).map(input => input.value);
    const excludeJunk = document.getElementById('historyExcludeJunk').checked;
    const minPrice = minPriceInput ? parseFloat(minPriceInput) : 0;
    const maxPrice = maxPriceInput ? parseFloat(maxPriceInput) : Infinity;


    if (minPrice < 0 || (maxPriceInput && maxPrice < 0)) {
        alert('価格は0以上の値を入力してください');
        return;
    }
    if (maxPriceInput && minPrice > maxPrice) {
        alert('最低価格は最高価格以下にしてください');
        return;
    }

    filteredData = marketData.filter(item => {
        const price = parseFloat(item.EndPrice) || 0;
        const bidding = parseInt(item.Bidding) || 0;

        if (price < minPrice || price > maxPrice) return false;
        const condition = item.condition || 'unknown';
        if (excludeJunk && condition === 'junk') return false;
        if (selectedConditions.length && !selectedConditions.includes(condition)) return false;
        const noBidFilter = !bid0_10 && !bid10_20 && !bid20_30 && !bid30_40 && !bid40_50 && !bid50_plus;
        if (noBidFilter) return true;
        if (bid0_10 && bidding >= 0 && bidding < 10) return true;
        if (bid10_20 && bidding >= 10 && bidding < 20) return true;
        if (bid20_30 && bidding >= 20 && bidding < 30) return true;
        if (bid30_40 && bidding >= 30 && bidding < 40) return true;
        if (bid40_50 && bidding >= 40 && bidding < 50) return true;
        if (bid50_plus && bidding >= 50) return true;
        return false;
    });

    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();
    updateVisibleSummary();
}
// フィルタリングのためのイベントリスナーを設定
function clearFilters() {
    document.getElementById('minPrice').value = '0';
    document.getElementById('maxPrice').value = '';
    ['bid0_10', 'bid10_20', 'bid20_30', 'bid30_40', 'bid40_50', 'bid50_plus']
        .forEach(id => { document.getElementById(id).checked = false; });
    clearConditionFilters();
    filterData();
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();
}

function clearConditionFilters() {
    document.querySelectorAll('.condition-filter').forEach(input => { input.checked = false; });
    const excludeJunk = document.getElementById('historyExcludeJunk');
    if (excludeJunk) excludeJunk.checked = false;
}
// 価格フィルタリングのためのイベントリスナーを設定
function validateAndFilterData() {
    const minText = document.getElementById('minPrice').value;
    const maxText = document.getElementById('maxPrice').value;
    const minPrice = minText ? parseInt(minText, 10) : 0;
    const maxPrice = maxText ? parseInt(maxText, 10) : null;

    if (maxPrice !== null && minPrice > maxPrice) {
        alert('最低価格は最高価格以下である必要があります。');
        return;
    }
    if (isNaN(minPrice) || (maxPrice !== null && isNaN(maxPrice))) {
        alert('価格は数値で入力してください。');
        return;
    }
    filterData();
}
// 検索ワードのドロップダウンを更新する関数
function refreshSearchWordDropdown(selectedValue = "") {
    fetch('/taskle/get_search_words')
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

function renderConditionSummary(summary) {
    const container = document.getElementById('conditionSummary');
    container.innerHTML = '';
    if (!summary || !Array.isArray(summary.conditions)) return;
    summary.conditions.forEach(item => {
        const column = document.createElement('div');
        column.className = 'col-6 col-md-3';
        column.innerHTML = `<div class="border rounded bg-light p-2 h-100">
            <div class="fw-bold small">${item.label}</div>
            <div>${item.count}件 / ${item.medianPrice == null ? '中央値なし' : `中央値 ${Number(item.medianPrice).toLocaleString()}円`}</div>
        </div>`;
        container.appendChild(column);
    });
}

function summarizeConditions(items) {
    const definitions = [
        ['new', '新品・未使用'],
        ['used', '中古・動作品'],
        ['junk', 'ジャンク・故障品'],
        ['unknown', '未分類'],
    ];
    return {
        conditions: definitions.map(([condition, label]) => {
            const matching = items.filter(item => (item.condition || 'unknown') === condition);
            const prices = matching.map(item => Number(item.EndPrice)).filter(price => price > 0);
            return {
                condition,
                label,
                count: matching.length,
                medianPrice: prices.length ? calculateMedian(prices) : null,
            };
        }),
    };
}

function updateVisibleSummary() {
    const prices = filteredData.map(item => Number(item.EndPrice)).filter(price => price > 0);
    const medianArea = document.getElementById('medianPrice');
    medianArea.textContent = prices.length
        ? `絞り込み結果の終了価格中央値: ${calculateMedian(prices).toLocaleString()} 円（${filteredData.length}件）`
        : '条件に一致する価格データがありません';
    renderConditionSummary(summarizeConditions(filteredData));
}

