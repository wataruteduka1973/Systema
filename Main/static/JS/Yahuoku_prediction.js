// グローバル変数
let currentData = {};
let predictionChart = null;

function Prediction_Search() {
    const searchKeyword = document.getElementById('search').value.trim();
    if (!searchKeyword) {
        alert('検索キーワードを入力してください');
        return;
    }

    const params = new URLSearchParams({ keyword: searchKeyword });
    const spinner = document.getElementById('searchSpinner');
    const button = document.getElementById('button-search');

    spinner.style.display = 'inline-block';
    button.disabled = true;

    fetch(`/taskle/prediction_market?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 400 || response.status === 500) {
                    return response.text().then(text => {
                        throw new Error(`Error page rendered: ${text}`);
                    });
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(result => {
            currentData = result;
            if (currentData.error) {
                alert(`エラー: ${currentData.error}`);
                return;
            }

            // データが少ない場合の警告
            if (!currentData.price_trends || currentData.price_trends.length < 10) {
                showPredictionWarning("データが少なく情報の偏りがある可能性があります。");
            } else {
                showPredictionWarning(""); // 警告を消す
            }

            // 中央値から40%以上乖離しているデータを除外
            const prices = currentData.price_trends.map(item => item.price).filter(v => typeof v === "number" && !isNaN(v));
            const median = calculateMedian(prices);
            currentData.price_trends = currentData.price_trends.filter(item => {
                if (typeof item.price !== "number" || isNaN(item.price)) return false;
                return Math.abs(item.price - median) / median <= 0.4;
            });

            // 日付順にソート
            currentData.price_trends.sort((a, b) => {
                const dateA = new Date(`${new Date().getFullYear()}-${a.date.split('/')[0]}-${a.date.split('/')[1].split(' ')[0]} ${a.date.split(' ')[1]}`);
                const dateB = new Date(`${new Date().getFullYear()}-${b.date.split('/')[0]}-${b.date.split('/')[1].split(' ')[0]} ${b.date.split(' ')[1]}`);
                return dateA - dateB;
            });

            updatePredictionChart();
            updatePredictionTable();
        })
        .catch(error => {
            console.error('検索エラー:', error);
            alert('検索に失敗しました: ' + error.message);
        })
        .finally(() => {
            spinner.style.display = 'none';
            button.disabled = false;
        });
}

// 警告表示用
function showPredictionWarning(msg) {
    let warn = document.getElementById('prediction-warning');
    if (!warn) {
        warn = document.createElement('div');
        warn.id = 'prediction-warning';
        warn.className = 'alert alert-warning mt-2';
        const chartContainer = document.querySelector('.chart-container');
        if (chartContainer) {
            chartContainer.parentNode.insertBefore(warn, chartContainer);
        } else {
            document.body.insertBefore(warn, document.body.firstChild);
        }
    }
    warn.style.display = msg ? 'block' : 'none';
    warn.textContent = msg;
}

// 中央値計算
function calculateMedian(arr) {
    if (!arr.length) return 0;
    const sorted = arr.slice().sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
        ? sorted[mid]
        : (sorted[mid - 1] + sorted[mid]) / 2;
}

function updatePredictionChart() {
    if (!window.Chart) return;

    const labels = currentData.price_trends.map(item => item.date.split(' ')[0]);
    const prices = currentData.price_trends.map(item => item.price);
    const movingAverages = currentData.price_trends.map(item => item.moving_avg);
    const predictedPrice = currentData.predicted_price || 0;

    const barLabels = [...labels, '1ヶ月後'];
    const barData = [...prices, predictedPrice];

    const hasMovingAvg = movingAverages.some(v => v !== null && v !== undefined);

    if (predictionChart) {
        predictionChart.destroy();
    }

    const ctx = document.getElementById('predictionChart').getContext('2d');
    const datasets = [
        {
            type: 'bar',
            label: '価格推移',
            data: barData.map((v, i) => i === barData.length - 1 ? null : v),
            backgroundColor: barData.map((v, i) => i === barData.length - 1 ? 'rgba(0,0,0,0)' : '#1E90FF'),
            borderWidth: 1
        },
        {
            type: 'bar',
            label: '1ヶ月後予測',
            data: barData.map((v, i) => i === barData.length - 1 ? v : null),
            backgroundColor: barData.map((v, i) => i === barData.length - 1 ? '#ff4d4d' : '#ff4d4d'),
            borderWidth: 1
        }
    ];

    if (hasMovingAvg) {
        datasets.push({
            type: 'line',
            label: '90日移動平均',
            data: movingAverages.concat([null]),
            borderColor: '#32CD32',
            backgroundColor: 'rgba(50,205,50,0.1)',
            fill: false,
            tension: 0.1,
            yAxisID: 'y'
        });
    }

    predictionChart = new Chart(ctx, {
        data: {
            labels: barLabels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: '価格 (円)' }
                }
            },
            plugins: {
                legend: { position: 'top' }, // グラフ上部のラベルを赤色に
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function (context) {
                            // 価格推移バー
                            if (context.dataset.label === '価格推移' && context.parsed.y !== null) {
                                return `価格推移: ${context.parsed.y.toLocaleString()} 円`;
                            }
                            // 1ヶ月後予測バー
                            if (context.dataset.label === '1ヶ月後予測' && context.parsed.y !== null) {
                                return `1ヶ月後予測: ${context.parsed.y.toLocaleString()} 円`;
                            }
                            // 90日移動平均
                            if (context.dataset.label === '90日移動平均' && context.parsed.y !== null) {
                                return `90日移動平均: ${context.parsed.y.toLocaleString()} 円`;
                            }
                            return '';
                        },
                        // 他の系列のツールチップを非表示
                        filter: function (context) {
                            return context.parsed.y !== null;
                        }
                    }
                }
            }
        }
    });


    const chartContainer = document.querySelector('.chart-container');
    let annotation = chartContainer.querySelector('.chart-annotation');
    if (!annotation) {
        annotation = document.createElement('div');
        annotation.className = 'chart-annotation';
        chartContainer.insertBefore(annotation, chartContainer.firstChild);
    }
    annotation.innerHTML = `
        <p style="color: #ffffff; background-color: rgba(0, 0, 0, 0.7); padding: 5px; border-radius: 3px;">
            1ヶ月後の価格予想は赤色のバーで表示されます。${hasMovingAvg ? '緑線は90日移動平均です。' : ''}
        </p>
    `;
}

function updatePredictionTable() {
    const tableBody = document.getElementById('predictionTable').getElementsByTagName('tbody')[0];
    if (!tableBody) return;

    tableBody.innerHTML = '';
    const data = [
        { label: '移動平均 (90日)', value: currentData.moving_average || 'N/A' },
        { label: '1ヶ月予測', value: currentData.predicted_price || 'N/A' },
        { label: '信頼区間下限', value: currentData.confidence_interval?.[0] || 'N/A' },
        { label: '信頼区間上限', value: currentData.confidence_interval?.[1] || 'N/A' }
    ];

    data.forEach(item => {
        if (item.label === '移動平均 (90日)' && (!currentData.moving_average || isNaN(currentData.moving_average))) return;
        const row = tableBody.insertRow();
        row.insertCell(0).textContent = item.label;
        row.insertCell(1).textContent = item.value;
    });
}

// Chart.jsの非同期ロードと初期化
document.addEventListener('DOMContentLoaded', () => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.onload = () => {
        console.log('Chart.js loaded');
    };
    script.onerror = () => console.error('Failed to load Chart.js');
    document.head.appendChild(script);
});

