let currentData = [];

document.addEventListener("DOMContentLoaded", function () {

    const searchInput = document.getElementById('search');

    // Enterキーで検索
    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            TargetSearch();
        }
    });


    // Enterキーで検索
    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            Prediction_Search();
        }
    });

    // 人気ワード取得・ボタン生成
    fetch('/taskle/get_popular_words?top=10')
        .then(res => res.json())
        .then(data => {
            const area = document.getElementById('popularWordsBtnGroup');
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

        });

});
// 検索ボタンのクリックイベント
function TargetSearch() {
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
    fetch(`/taskle/complex_market_data?${params.toString()}`)
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
            if (typeof result.medianPrice !== "undefined") {
                document.getElementById('medianPrice').textContent = Math.round(result.medianPrice).toLocaleString();
                document.getElementById('medianPriceBox').style.display = "block";
            } else {
                document.getElementById('medianPriceBox').style.display = "none";
            }
            currentData = result.recommend_items || [];
            updateTable(currentData);
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

function updateTable(data) {
    const tableBody = document.getElementById("dataTable").getElementsByTagName("tbody")[0];
    tableBody.innerHTML = "";

    data.forEach(item => {
        const row = tableBody.insertRow();
        const productNameCell = row.insertCell(0);
        productNameCell.textContent = item.name || 'N/A';
        const currentPriceCell = row.insertCell(1);
        currentPriceCell.textContent = item.price !== undefined && item.price !== null ? item.price.toLocaleString() : 'N/A';
        const biddingCell = row.insertCell(2);
        biddingCell.textContent = item.bidding !== undefined ? item.bidding : 'N/A';
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