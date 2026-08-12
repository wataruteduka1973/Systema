let currentData = [];
const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let filteredData = [...currentData];
let sortKey = null;
let sortOrder = null;

function fetchJsonWithRetry(url, options = {}, maxRetries = 3) {
    return fetch(url, options).then(async (response) => {
        if (!response.ok) {
            if (response.status >= 500 || response.status === 429) {
                throw new Error(`HTTP ${response.status}`);
            }
            throw new Error(`Request failed with status ${response.status}`);
        }
        const text = await response.text();
        if (!text) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            return {};
        }
    }).catch(async (error) => {
        if (maxRetries <= 0) {
            throw error;
        }
        await new Promise(resolve => setTimeout(resolve, 500));
        return fetchJsonWithRetry(url, options, maxRetries - 1);
    });
}

function normalizeItemUrl(url) {
    if (!url) return '#';
    const value = String(url).trim();
    if (!value || value === '#') return '#';
    if (value.startsWith('http://') || value.startsWith('https://')) return value;
    if (value.startsWith('//')) return `https:${value}`;
    if (value.startsWith('/item/')) return `https://paypayfleamarket.yahoo.co.jp${value}`;
    if (value.startsWith('/jp/auction/')) return `https://auctions.yahoo.co.jp${value}`;
    if (value.startsWith('/')) return `https://auctions.yahoo.co.jp${value}`;
    if (value.startsWith('auction/')) return `https://auctions.yahoo.co.jp/${value}`;
    if (value.startsWith('jp/auction/')) return `https://auctions.yahoo.co.jp/${value}`;
    if (value.includes('paypayfleamarket.yahoo.co.jp')) return value;
    return value;
}

// 初期データの取得とテーブルの初期化
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
    const searchInput = document.getElementById('search');
    // Enterキーで検索
    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            RealtimeSearch();
        }
    });

    // 人気ワードの取得と表示
    fetchJsonWithRetry('/taskle/get_popular_words?top=10')
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
            console.error('人気ワード取得エラー:', error);
        });
});

// 検索ボタンのクリックイベント
function RealtimeSearch() {
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
    spinner.style.display = 'inline-block';
    button.disabled = true;

    fetchJsonWithRetry(`/taskle/RealtimeSearch?${params.toString()}`)
        .then(result => {
            currentData = (result.data || []).map(item => {
                const currentPrice = Number(item.currentPrice ?? item.price ?? 0) || 0;
                const bidding = Number(item.bidding ?? item.bidCount ?? 0) || 0;
                const remainingTime = item.remainingTime || item.time || 'N/A';
                const url = normalizeItemUrl(item.url || item.link || '#');
                return {
                    ...item,
                    currentPrice,
                    bidding,
                    remainingTime,
                    url
                };
            });
            filteredData = [...currentData];
            if (Array.isArray(currentData) && currentData.length > 0) {
                currentPage = 1;
                updateTable(paginateData(currentData));
                document.querySelector('.Main-Element').style.display = 'block';
                updatePagination();
                document.getElementById('minPrice').value = '0';
                document.getElementById('maxPrice').value = '';
                document.getElementById('bid0_10').checked = false;
                document.getElementById('bid10_20').checked = false;
                document.getElementById('bid20_30').checked = false;
                document.getElementById('bid30_40').checked = false;
                document.getElementById('bid40_50').checked = false;
                document.getElementById('bid50_plus').checked = false;
                const prices = currentData.map(item => item.currentPrice).filter(currentPrice => !isNaN(currentPrice));
                const band = findMostFrequentPriceBand(prices);
                if (band) {
                    document.getElementById("medianPrice").textContent =
                        `特に多い価格帯 ${band.lower.toLocaleString()} 円から ${band.upper.toLocaleString()} 円`;
                    document.getElementById("medianPrice").style.display = "block";
                }
            } else {
                console.error('Error: Data is not a non-empty array');
                document.querySelector('.table-container').style.display = 'none';
            }
        })
        .catch(error => {
            console.error('検索エラー:', error);
            alert('検索に失敗しました。再試行しても取得できない場合は、しばらくしてから再度お試しください。');
        })
        .finally(() => {
            spinner.style.display = 'none';
            button.disabled = false;
        });
}
// 中央値の計算
function calculateMedian(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}

function findMostFrequentPriceBand(prices, binCount = 10) {
    if (!prices.length) return null;
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    if (min === max) {
        return { lower: min, upper: max };
    }
    const binWidth = (max - min) / binCount;
    const counts = new Array(binCount).fill(0);
    prices.forEach(p => {
        const idx = Math.min(Math.floor((p - min) / binWidth), binCount - 1);
        counts[idx]++;
    });
    const modeIdx = counts.indexOf(Math.max(...counts));
    return {
        lower: Math.floor(min + modeIdx * binWidth),
        upper: Math.ceil(min + (modeIdx + 1) * binWidth)
    };
}
// ページネーションのデータを取得
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
// ページ変更処理
function changePage(page) {
    currentPage = page;
    if (currentPage < 1) currentPage = 1;
    const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
    if (currentPage > totalPages) currentPage = totalPages;
    updateTable(paginateData(filteredData));
    updatePagination();
}

//テーブルの更新
function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();
        const productNameCell = row.insertCell(0);
        productNameCell.textContent = item.name || 'N/A';
        const currentPriceCell = row.insertCell(1);
        currentPriceCell.textContent = Number(item.currentPrice || 0).toLocaleString();
        const biddingCell = row.insertCell(2);
        biddingCell.textContent = item.bidding ?? 0;
        const remainingTimeCell = row.insertCell(3);
        remainingTimeCell.textContent = item.remainingTime || 'N/A';
        const productURLCell = row.insertCell(4);
        const link = document.createElement("a");
        link.href = normalizeItemUrl(item.url || '#');
        link.textContent = "商品リンクURL";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        productURLCell.appendChild(link);
    });
}

// 検索ボタンのクリックイベント
function sortData(key, order) {
    sortKey = key;
    sortOrder = order;
    filteredData.sort((a, b) => {
        let valueA = a[key];
        let valueB = b[key];
        if (key === 'remainingTime') {
            valueA = parseRemainingTime(valueA);
            valueB = parseRemainingTime(valueB);
        } else if (key === 'currentPrice' || key === 'bidding') {
            valueA = Number(valueA) || 0;
            valueB = Number(valueB) || 0;
        }
        return order === 'asc' ? valueA - valueB : valueB - valueA;
    });
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();

}

//　アイコンの切り替え
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
        const price = Number(item.currentPrice) || 0;
        const bidding = Number(item.bidding) || 0;

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
// フィルタリングのリセット
function clearFilters() {
    document.getElementById('minPrice').value = '0';
    document.getElementById('maxPrice').value = '';
    filterData();
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();
}
// 残り時間のパース
function parseRemainingTime(str) {
    if (!str) return 0;
    const value = String(str).replace(/\s+/g, '');
    let days = 0, hours = 0, minutes = 0;
    const dayMatch = value.match(/(\d+)日/);
    const hourMatch = value.match(/(\d+)時間/);
    const minMatch = value.match(/(\d+)分/);
    if (dayMatch) days = parseInt(dayMatch[1], 10);
    if (hourMatch) hours = parseInt(hourMatch[1], 10);
    if (minMatch) minutes = parseInt(minMatch[1], 10);
    return days * 24 * 60 + hours * 60 + minutes;
}
//ソート処置
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