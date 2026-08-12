let currentData = [];
const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let filteredData = [...currentData];
let sortKey = null;
let sortOrder = null;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJsonWithRetry(url, options = {}, retryConfig = {}) {
    const { maxRetries = 3, delayMs = 1200, alertOnFailure = true } = retryConfig;
    let lastError = null;

    for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            lastError = error;
            if (attempt < maxRetries) {
                console.warn(`[fetchJsonWithRetry] attempt ${attempt} failed, retrying:`, error);
                await sleep(delayMs);
                continue;
            }
            if (alertOnFailure) {
                alert('データ取得に失敗しました。再試行しましたが取得できませんでした。\n時間をおいて再度お試しください。');
            }
            throw error;
        }
    }

    throw lastError;
}

// 初期データの取得とテーブルの初期化
document.addEventListener('DOMContentLoaded', function () {
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(button => {
        button.addEventListener('click', function () {
            const key = this.dataset.sort;
            const order = this.dataset.order;

            if (!key || !order) return;

            sortData(key, order);

            this.dataset.order = order === 'asc' ? 'desc' : 'asc';
            updateSortIcon(this);
        });
    });

    const searchInput = document.getElementById('search');

    if (searchInput) {
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
    }

    fetchJsonWithRetry('/taskle/get_popular_words?top=10', {}, { maxRetries: 2, delayMs: 1000, alertOnFailure: false })
        .then(data => {
            const area = document.getElementById('popularWordsBtnGroup');
            if (!area) return;
            area.innerHTML = '';
            (data.words || []).forEach(word => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-outline-danger btn-sm';
                btn.textContent = word;
                btn.onclick = function () {
                    const searchInput = document.getElementById('search');
                    if (searchInput.value) {
                        searchInput.value += ' ' + word;
                    } else {
                        searchInput.value = word;
                    }
                    searchInput.focus();
                };
                area.appendChild(btn);
            });
        })
        .catch(error => {
            console.warn('人気ワードの取得に失敗しました:', error);
        });
});
// 検索ボタンのクリックイベントを設定
async function performSearch() {
    const searchKeyword = document.getElementById("search").value.trim();
    if (!searchKeyword) {
        alert('検索キーワードを入力してください');
        return;
    }
    const params = new URLSearchParams({
        keyword: searchKeyword,
    });

    const spinner = document.getElementById('searchSpinner');
    const button = document.getElementById('button-search');
    if (spinner) spinner.style.display = 'inline-block';
    if (button) button.disabled = true;

    try {
        const result = await fetchJsonWithRetry(`/taskle/perform_search?${params.toString()}`, {}, { maxRetries: 3, delayMs: 1500, alertOnFailure: true });
        currentData = result.data || [];
        filteredData = [...currentData];
        if (Array.isArray(currentData) && currentData.length > 0) {
            currentPage = 1;
            updateTable(paginateData(filteredData));
            document.querySelector('.Main-Element').style.display = 'block';
            const prices = currentData.map(item => Number(item.price) || 0).filter(price => !isNaN(price));
            const median = calculateMedian(prices);
            updatePagination();
            document.getElementById("medianPrice").textContent = `終了価格の中央値: ${median.toLocaleString()} 円`;
            document.getElementById("medianPrice").style.display = "block";
            document.getElementById('minPrice').value = '0';
            document.getElementById('maxPrice').value = '';
            document.getElementById('bid0_10').checked = false;
            document.getElementById('bid10_20').checked = false;
            document.getElementById('bid20_30').checked = false;
            document.getElementById('bid30_40').checked = false;
            document.getElementById('bid40_50').checked = false;
            document.getElementById('bid50_plus').checked = false;
        } else {
            console.error('Error: Data is not a non-empty array');
            document.getElementById("medianPrice").style.display = "none";
            document.querySelector('.table-container').style.display = 'none';
        }
    } catch (error) {
        console.error('検索エラー:', error);
        alert('検索に失敗しました。再試行を実行しましたが、データを取得できませんでした。');
    } finally {
        if (spinner) spinner.style.display = 'none';
        if (button) button.disabled = false;
    }
}

// ページネーションのためのデータを取得
function paginateData(data) {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    return data.slice(start, end);
}
// ページネーションの更新
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
// ページ変更の処理
function changePage(page) {
    currentPage = page;
    if (currentPage < 1) currentPage = 1;
    const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
    if (currentPage > totalPages) currentPage = totalPages;
    updateTable(paginateData(filteredData));
    updatePagination();
}
// 終了価格の中央値を計算
function calculateMedian(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}
// テーブルの更新
function normalizeItemUrl(url) {
    if (!url || url === '#') return '#';
    const value = String(url).trim();
    if (/^https?:\/\//i.test(value)) return value;
    if (value.startsWith('//')) return `https:${value}`;
    if (value.startsWith('/')) return `https://auctions.yahoo.co.jp${value}`;
    if (value.startsWith('jp/auction/') || value.startsWith('auction/')) return `https://auctions.yahoo.co.jp/${value}`;
    return value;
}

function toSortableValue(value, key) {
    if (key === 'time') {
        if (!value) return 0;
        const iso = String(value).trim();
        if (!iso || iso === 'N/A') return 0;
        const date = new Date(iso);
        if (!isNaN(date.getTime())) return date.getTime();
        const slash = iso.match(/(\d{1,2})\/(\d{1,2})(?:\([^)]{1,3}\))?\s+(\d{1,2}:\d{2})/);
        if (slash) {
            const currentYear = new Date().getFullYear();
            const month = Number(slash[1]);
            const day = Number(slash[2]);
            const [hour, minute] = slash[3].split(':').map(Number);
            return new Date(currentYear, month - 1, day, hour, minute).getTime();
        }
        return 0;
    }

    if (typeof value === 'string') {
        const stripped = value.replace(/[^\d.-]/g, '');
        return Number(stripped || 0);
    }
    if (typeof value === 'number') return value;
    return 0;
}

function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();

        const productNameCell = row.insertCell(0);
        productNameCell.textContent = item.name || 'N/A';

        const endPriceCell = row.insertCell(1);
        endPriceCell.textContent = Number(item.price || 0).toLocaleString();

        const startPriceCell = row.insertCell(2);
        startPriceCell.textContent = Number(item.startPrice || 0).toLocaleString();

        const timeCell = row.insertCell(3);
        timeCell.textContent = item.time || 'N/A';

        const biddingCell = row.insertCell(4);
        biddingCell.textContent = Number(item.bidding || 0).toLocaleString();

        const productURLCell = row.insertCell(5);
        const link = document.createElement("a");
        const href = normalizeItemUrl(item.url);
        link.href = href;
        link.textContent = href === '#' ? 'URLなし' : '商品リンクURL';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.style.color = href === '#' ? '#666' : '#0d6efd';
        productURLCell.appendChild(link);
    });
}

// ソート機能
function sortData(key, order) {
    sortKey = key;
    sortOrder = order;
    filteredData.sort((a, b) => {
        const valueA = toSortableValue(a[key], key);
        const valueB = toSortableValue(b[key], key);
        return order === 'asc' ? valueA - valueB : valueB - valueA;
    });
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();

}

// ソートアイコンの更新
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
// フィルタリング機能
function filterData() {
    const minPriceInput = document.getElementById('minPrice').value;
    const maxPriceInput = document.getElementById('maxPrice').value;
    const bid0_10 = document.getElementById('bid0_10').checked;
    const bid10_20 = document.getElementById('bid10_20').checked;
    const bid20_30 = document.getElementById('bid20_30').checked;
    const bid30_40 = document.getElementById('bid30_40').checked;
    const bid40_50 = document.getElementById('bid40_50').checked;
    const bid50_plus = document.getElementById('bid50_plus').checked;
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

    filteredData = currentData.filter(item => {
        const price = parseFloat(item.price) || 0;
        const bidding = parseInt(item.bidding) || 0;

        if (price < minPrice || price > maxPrice) return false;
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
}
// フィルタリングのためのイベントリスナーを設定
function clearFilters() {
    document.getElementById('minPrice').value = '0';
    document.getElementById('maxPrice').value = '';
    filterData();
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();
}
// 価格フィルタリングのためのイベントリスナーを設定
function validateAndFilterData() {
    const minPrice = parseInt(document.getElementById('minPrice').value, 10);
    const maxPrice = parseInt(document.getElementById('maxPrice').value, 10);

    if (minPrice > maxPrice) {
        alert('最低価格は最高価格以下である必要があります。');
        return;
    }
    if (isNaN(minPrice) || isNaN(maxPrice)) {
        alert('価格は数値で入力してください。');
        return;
    }
    filterData();
}

