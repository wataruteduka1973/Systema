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

function updatePredictionChart() {
    if (!predictionChart) {
        const ctx = document.getElementById('predictionChart').getContext('2d');
        predictionChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, title: { display: true, text: '価格 (円)' } } },
                plugins: { legend: { position: 'top' }, tooltip: { mode: 'index', intersect: false } }
            }
        });
    }

    const labels = currentData.price_trends.map(item => item.date.split(' ')[0]); // 日付のみ
    const prices = currentData.price_trends.map(item => item.price);
    const movingAverages = currentData.price_trends.map(item => item.moving_avg);
    const predictedPrice = currentData.predicted_price || 0;
    const confidenceInterval = currentData.confidence_interval || [0, 0];

    predictionChart.data = {
        labels: [...labels, '1ヶ月後'],
        datasets: [
            {
                label: '過去価格',
                data: prices,
                borderColor: '#1E90FF',
                fill: false,
                tension: 0.1
            },
            {
                label: '移動平均 (30日)',
                data: movingAverages,
                borderColor: '#32CD32',
                fill: false,
                tension: 0.1
            },
            {
                label: '予測価格',
                data: [...Array(labels.length).fill(null), predictedPrice],
                borderColor: '#FF4500',
                fill: false,
                tension: 0.1
            },
            {
                label: '信頼区間 (95%)',
                data: [...Array(labels.length).fill(null), confidenceInterval[0], confidenceInterval[1]],
                borderColor: '#FFD700',
                fill: false,
                borderDash: [5, 5],
                pointRadius: 0
            }
        ]
    };
    predictionChart.update();

    const chartContainer = document.querySelector('.chart-container');
    let annotation = chartContainer.querySelector('.chart-annotation');
    if (!annotation) {
        annotation = document.createElement('div');
        annotation.className = 'chart-annotation';
        chartContainer.insertBefore(annotation, chartContainer.firstChild);
    }
    annotation.innerHTML = `
        <p style="color: #ffffff; background-color: rgba(0, 0, 0, 0.7); padding: 5px; border-radius: 3px;">
            信頼区間 (95%): 予測価格の上下10%範囲を示し、95%の確率で実際の価格がこの範囲内に入ると予想。
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

