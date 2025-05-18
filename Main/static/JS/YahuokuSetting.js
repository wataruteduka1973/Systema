let currentData = [];

let history = ['キーワード1', 'キーワード2'];

let resizeTimeout;

const ITEMS_PER_PAGE = 10;
let currentPage = 1;

function suggestKeyword() {
    const input = document.getElementById('search');
    const datalist = document.getElementById('searchHistory');
    datalist.innerHTML = '';
    const value = input.value.toLowerCase();
    history.filter(k => k.toLowerCase().includes(value)).forEach(k => {
        const option = document.createElement('option');
        option.value = k;
        datalist.appendChild(option);
    });
}

function performSearch() {
    const searchKeyword = document.getElementById("search").value.trim();
    if (!searchKeyword) {
        alert('検索キーワードを入力してください');
        return;
    }
    const spinner = document.getElementById('searchSpinner');
    const button = document.getElementById('button-search');
    spinner.style.display = 'inline-block';
    button.disabled = true;
    fetch(`/taskle/perform_search?keyword=${encodeURIComponent(searchKeyword)}`)
        .then(response => {
            if (!response.ok) throw new Error('ネットワークエラー');
            return response.json();
        })
        .then(result => {
            currentData = result.data || [];
            if (Array.isArray(currentData) && currentData.length > 0) {
                currentPage = 1
                updateTable(paginateData(currentData));
                generateWordCloud(currentData);
                document.querySelector('.Main-Element').style.display = 'block';
                const prices = currentData.map(item => item.price).filter(price => !isNaN(price));
                const median = calculateMedian(prices);
                document.getElementById("medianPrice").textContent = `終了価格の中央値: ${median.toLocaleString()} 円`;
                document.getElementById("medianPrice").style.display = "block";
                document.getElementById('wordcloud').style.display = 'block';
                setTimeout(() => generateWordCloud(currentData), 0);
                updatePagination();
            } else {
                console.error('Error: Data is not a non-empty array');
                document.getElementById("medianPrice").style.display = "none";
                document.querySelector('.table-container').style.display = 'none';
                document.getElementById('wordcloud').style.display = 'none';
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
    const totalPages = Math.ceil(currentData.length / ITEMS_PER_PAGE);
    if (currentPage > totalPages) currentPage = totalPages;
    updateTable(paginateData(currentData));
    updatePagination();
}

function calculateMedian(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}

function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();

        const productNameCell = row.insertCell(0);
        productNameCell.textContent = item.name;

        const endPriceCell = row.insertCell(1);
        endPriceCell.textContent = item.price.toLocaleString();

        const startPriceCell = row.insertCell(2);
        startPriceCell.textContent = item.startPrice.toLocaleString();

        const biddingCell = row.insertCell(3);
        biddingCell.textContent = item.bidding;

        const productURLCell = row.insertCell(4);
        const link = document.createElement("a");
        link.href = item.url;
        link.textContent = "商品リンクURL";
        link.target = "_blank"
        productURLCell.appendChild(link);
    });
}

function sortData(key, order) {
    currentData.sort((a, b) => {
        let valueA = a[key];
        let valueB = b[key];

        if (typeof valueA === 'string') valueA = parseFloat(valueA.replace(/[^\d.-]/g, ''));
        if (typeof valueB === 'string') valueB = parseFloat(valueB.replace(/[^\d.-]/g, ''));

        if (order === 'asc') {
            return valueA - valueB;
        } else {
            return valueB - valueA;
        }
    });

    updateTable(currentData);
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

function generateWordCloud(data) {
    const container = document.querySelector('.wordcloud-container');
    const width = container.offsetWidth;
    const height = container.offsetHeight;
    const allText = data.map(item => item.name).join(' ');
    const wordCounts = {};
    allText.split(/\s+/).forEach(word => {
        if (word.length > 1) {
            wordCounts[word] = (wordCounts[word] || 0) + 1;
        }
    });


    const words = Object.entries(wordCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 50)
        .map(([text, size]) => ({ text, size }));

    const layout = d3.layout.cloud()
        .size([width, height])
        .words(words)
        .padding(5)
        .rotate(() => ~~(Math.random() * 2) * 90)
        .font("Impact")
        .fontSize(d => Math.sqrt(d.size) * (width / 800) * 10)
        .on("end", draw);

    layout.start();

    function draw(words) {
        d3.select("#wordcloud").html("");
        const svg = d3.select("#wordcloud").append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .append("g")
            .attr("transform", `translate(${width / 2},${height / 2})`);

        svg.selectAll("text")
            .data(words)
            .enter().append("text")
            .style("font-size", d => d.size + "px")
            .style("font-family", "Impact")
            .style("fill", () => d3.schemeCategory10[Math.floor(Math.random() * 10)])
            .attr("text-anchor", "middle")
            .attr("transform", d => `translate(${d.x},${d.y})rotate(${d.rotate})`)
            .text(d => d.text);
    }
}



window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (currentData.length > 0) {
            generateWordCloud(currentData);
        }
    }, 200);
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelector('.Main-Element').style.display = 'none';
});