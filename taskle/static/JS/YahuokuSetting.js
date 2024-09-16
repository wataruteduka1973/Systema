let currentData = [];

// 検索を実行する関数
function performSearch() {
    // 検索キーワードを取得
    const searchKeyword = document.getElementById("search").value;

    // サーバーに検索リクエストを送信
    fetch(`/taskle/search?keyword=${searchKeyword}`)
        .then(response => response.json())
        .then(result => {
            currentData = result.data;

            // データが配列で、かつ空でない場合
            if (Array.isArray(currentData) && currentData.length > 0) {
                updateTable(currentData);
                generateWordCloud(currentData);

                document.querySelector('.Main-Element').style.display = 'block';
                // テーブルのbody要素を取得
                const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];

                // テーブルの内容をクリア
                tableBody.innerHTML = "";

                // 終了価格を抽出し、数値に変換
                const prices = currentData.map(item => item.price).filter(price => !isNaN(price));

                // 中央値を計算
                const median = calculateMedian(prices);

                // 中央値を表示
                const medianDisplay = document.getElementById("medianPrice");
                medianDisplay.textContent = `終了価格の中央値: ${median.toLocaleString()} 円`;
                medianDisplay.style.display = "block"; // 要素を表示

                // 各データ項目に対してテーブルの行を作成
                currentData.forEach(item => {
                    const row = tableBody.insertRow();

                    // 商品名のセルを作成
                    const productNameCell = row.insertCell(0);
                    productNameCell.textContent = item.name;

                    // 終了価格のセルを作成
                    const endPriceCell = row.insertCell(1);
                    endPriceCell.textContent = item.price;

                    // 開始価格のセルを作成
                    const startPriceCell = row.insertCell(2);
                    startPriceCell.textContent = item.startPrice;

                    // 入札数のセルを作成
                    const biddingCell = row.insertCell(3);
                    biddingCell.textContent = item.bidding;

                    // 商品URLのセルを作成
                    const productURLCell = row.insertCell(4);

                    // URLリンクを作成
                    const link = document.createElement("a");
                    link.href = item.url;
                    link.textContent = "商品リンクURL";
                    link.target = "_blank"
                    productURLCell.appendChild(link);
                });
            } else {
                console.error('Error: Data is not a non-empty array');
                document.getElementById("medianPrice").style.display = "none";
                document.querySelector('.table-container').style.display = 'none';
                document.getElementById('wordcloud').style.display = 'none';

            }

        });

    // 中央値を計算する関数
    function calculateMedian(numbers) {
        const sorted = numbers.slice().sort((a, b) => a - b);
        const middle = Math.floor(sorted.length / 2);

        if (sorted.length % 2 === 0) {
            return (sorted[middle - 1] + sorted[middle]) / 2;
        }

        return sorted[middle];
    }
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

        // 数値として比較
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

// ソートボタンのイベントリスナーを設定
document.addEventListener('DOMContentLoaded', function () {
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(button => {
        button.addEventListener('click', function () {
            const key = this.dataset.sort;
            const order = this.dataset.order;

            // ソート実行
            sortData(key, order);

            // ボタンの状態を更新
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
    // 全商品名を結合
    const allText = data.map(item => item.name).join(' ');

    // 単語の出現回数をカウント（簡易的な実装）
    const wordCounts = {};
    allText.split(/\s+/).forEach(word => {
        if (word.length > 1) { // 1文字の単語は除外
            wordCounts[word] = (wordCounts[word] || 0) + 1;
        }
    });

    // 上位50単語を選択
    const words = Object.entries(wordCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 50)
        .map(([text, size]) => ({ text, size }));

    // D3.jsを使用してワードクラウドを生成
    const layout = d3.layout.cloud()
        .size([800, 400])
        .words(words)
        .padding(5)
        .rotate(() => ~~(Math.random() * 2) * 90)
        .font("Impact")
        .fontSize(d => Math.sqrt(d.size) * 10)
        .on("end", draw);

    layout.start();

    function draw(words) {
        d3.select("#wordcloud").html(""); // 既存のワードクラウドをクリア
        const svg = d3.select("#wordcloud").append("svg")
            .attr("width", layout.size()[0])
            .attr("height", layout.size()[1])
            .append("g")
            .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")");

        svg.selectAll("text")
            .data(words)
            .enter().append("text")
            .style("font-size", d => d.size + "px")
            .style("font-family", "Impact")
            .style("fill", () => d3.schemeCategory10[Math.floor(Math.random() * 10)]) // ランダムな色を追加
            .attr("text-anchor", "middle")
            .attr("transform", d => "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")")
            .text(d => d.text);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelector('.Main-Element').style.display = 'none';
});