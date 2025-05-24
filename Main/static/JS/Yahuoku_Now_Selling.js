let currentData = [];
const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let filteredData = [...currentData];
let sortKey = null;
let sortOrder = null;

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
    fetch(`/taskle/RealtimeSearch?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 400 || response.status === 500) {
                    return response.text().then(text => {
                        document.open();
                        document.write(text);
                        document.close();
                        throw new Error(`Error page rendered: ${response.status}`);
                    });
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })

        .then(result => {
            currentData = result.data || [];
            filteredData = [...currentData];
            if (Array.isArray(currentData) && currentData.length > 0) {
                currentPage = 1
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
            } else {
                console.error('Error: Data is not a non-empty array');
                document.querySelector('.table-container').style.display = 'none';
            }
        })
        .catch(error => {
            console.error('検索エラー:', error);
            alert('検索に失敗しました');
        })
        .finally(() => {
            spinner.style.display = 'none';
            button.disabled = false;
        });
}


function paginateData(data) {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    return data.slice(start, end);
}

function updatePagination() {
    const totalPages = Math.ceil(currentData.length / ITEMS_PER_PAGE);
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

function changePage(page) {
    currentPage = page;
    if (currentPage < 1) currentPage = 1;
    const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
    if (currentPage > totalPages) currentPage = totalPages;
    updateTable(paginateData(filteredData));
    updatePagination();
}


function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();
        const productNameCell = row.insertCell(0);
        productNameCell.textContent = item.name || 'N/A';
        const currentPriceCell = row.insertCell(1);
        currentPriceCell.textContent = (item.currentPrice || 0).toLocaleString();
        const biddingCell = row.insertCell(2);
        biddingCell.textContent = item.bidding || 0;
        const remainingTimeCell = row.insertCell(3);
        remainingTimeCell.textContent = item.remainingTime || 'N/A';
        const productURLCell = row.insertCell(4);
        const link = document.createElement("a");
        link.href = item.url || '#';
        link.textContent = "商品リンクURL";
        link.target = "_blank";
        productURLCell.appendChild(link);
    });
}


function sortData(key, order) {
    sortKey = key;
    sortOrder = order;
    filteredData.sort((a, b) => {
        let valueA = a[key];
        let valueB = b[key];
        if (key === 'remainingTime') {
            valueA = parseRemainingTime(valueA);
            valueB = parseRemainingTime(valueB);
        } else {
            if (typeof valueA === 'string') valueA = parseFloat(valueA.replace(/[^\d.-]/g, '')) || 0;
            if (typeof valueB === 'string') valueB = parseFloat(valueB.replace(/[^\d.-]/g, '')) || 0;
        }
        return order === 'asc' ? valueA - valueB : valueB - valueA;
    });
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();

}

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
    document.getElementById('wordCloudFilterToggle').checked = true;;
}

function clearFilters() {
    document.getElementById('minPrice').value = '0';
    document.getElementById('maxPrice').value = '';
    filterData();
    currentPage = 1;
    updateTable(paginateData(filteredData));
    updatePagination();
}

function parseRemainingTime(str) {
    if (!str) return 0;
    let days = 0, hours = 0, minutes = 0;
    const dayMatch = str.match(/(\d+)日/);
    const hourMatch = str.match(/(\d+)時間/);
    const minMatch = str.match(/(\d+)分/);
    if (dayMatch) days = parseInt(dayMatch[1]);
    if (hourMatch) hours = parseInt(hourMatch[1]);
    if (minMatch) minutes = parseInt(minMatch[1]);
    return days * 24 * 60 + hours * 60 + minutes;
}