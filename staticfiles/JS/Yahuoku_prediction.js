let currentData = {};
let predictionChart = null;
// 初期データの取得
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search');

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
            showPredictionWarning(currentData.quality?.warning || '');

            // 日付順にソート
            currentData.price_trends.sort((a, b) => {
                return parsePredictionDate(a.date) - parsePredictionDate(b.date);
            });

            updatePredictionChart();
            updatePredictionTable();
            updatePredictionSummary();
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
// グラフの更新
function parsePredictionDate(value) {
    const text = String(value || '').trim();
    if (/^\d{4}-\d{2}-\d{2}[T\s]/.test(text)) {
        return new Date(text);
    }

    const match = text.match(/^(\d{1,2})\/(\d{1,2})\s+(\d{1,2}:\d{2})$/);
    if (!match) return new Date(0);
    return new Date(`${new Date().getFullYear()}-${match[1].padStart(2, '0')}-${match[2].padStart(2, '0')}T${match[3]}:00`);
}

function updatePredictionChart() {
    if (!window.Chart) return;
    const daily = currentData.daily_trends || [];
    const labels = daily.map(item => item.date);
    const forecastLabel = labels.length
        ? new Date(new Date(`${labels[labels.length - 1]}T00:00:00`).getTime() + 30 * 86400000).toISOString().slice(0, 10)
        : '1ヶ月後';
    const allLabels = [...labels, forecastLabel];
    const interval = currentData.prediction_interval || currentData.confidence_interval || [0, 0];
    if (predictionChart) predictionChart.destroy();
    const ctx = document.getElementById('predictionChart').getContext('2d');
    const datasets = [
        {
            type: 'line', label: '日次中央値',
            data: daily.map(item => item.median).concat([null]),
            borderColor: '#2563eb', backgroundColor: '#2563eb', pointRadius: 4, tension: 0.2
        },
        {
            type: 'line', label: '14日移動中央値',
            data: daily.map(item => item.rollingMedian).concat([null]),
            borderColor: '#16a34a', pointRadius: 0, borderWidth: 2, tension: 0.25
        },
        {
            type: 'line', label: '予測範囲（上限）',
            data: daily.map(() => null).concat([interval[1]]),
            borderColor: 'rgba(220,38,38,.25)', backgroundColor: 'rgba(220,38,38,.15)', pointRadius: 0
        },
        {
            type: 'line', label: '予測範囲（下限）',
            data: daily.map(() => null).concat([interval[0]]),
            borderColor: 'rgba(220,38,38,.25)', backgroundColor: 'rgba(220,38,38,.15)', fill: '-1', pointRadius: 0
        },
        {
            type: 'line', label: '30日後予測',
            data: daily.map(() => null).concat([currentData.predicted_price]),
            borderColor: '#dc2626', backgroundColor: '#dc2626', pointRadius: 7, borderDash: [6, 4]
        }
    ];
    predictionChart = new Chart(ctx, {
        data: { labels: allLabels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, title: { display: true, text: '価格 (円)' } },
                x: { title: { display: true, text: '日付' } }
            },
            plugins: {
                legend: { position: 'top', labels: { filter: item => !item.text.includes('予測範囲') || item.text.includes('上限') } },
                tooltip: { mode: 'index', intersect: false, callbacks: { label: context => context.parsed.y == null ? '' : `${context.dataset.label}: ${context.parsed.y.toLocaleString()}円` } }
            }
        }
    });
}
// 予測テーブルの更新
function updatePredictionTable() {
    const tableBody = document.getElementById('predictionTable').getElementsByTagName('tbody')[0];
    if (!tableBody) return;

    tableBody.innerHTML = '';
    const data = [
        { label: '直近14日移動中央値', value: currentData.moving_average || 'N/A' },
        { label: '1ヶ月予測', value: currentData.predicted_price || 'N/A' },
        { label: '予測範囲下限', value: currentData.prediction_interval?.[0] || currentData.confidence_interval?.[0] || 'N/A' },
        { label: '予測範囲上限', value: currentData.prediction_interval?.[1] || currentData.confidence_interval?.[1] || 'N/A' }
    ];

    data.forEach(item => {
        if (item.label === '直近14日移動中央値' && (!currentData.moving_average || isNaN(currentData.moving_average))) return;
        const row = tableBody.insertRow();
        row.insertCell(0).textContent = item.label;
        row.insertCell(1).textContent = typeof item.value === 'number' ? `${item.value.toLocaleString()}円` : item.value;
    });
}

function updatePredictionSummary() {
    const quality = currentData.quality || {};
    const interval = currentData.prediction_interval || currentData.confidence_interval || [];
    const cards = [
        ['30日後予測', currentData.predicted_price ? `${currentData.predicted_price.toLocaleString()}円` : '—'],
        ['予測範囲', interval.length ? `${interval[0].toLocaleString()}～${interval[1].toLocaleString()}円` : '—'],
        ['30日トレンド', quality.trendPercent30Days == null ? '—' : `${quality.trendPercent30Days >= 0 ? '+' : ''}${quality.trendPercent30Days}%`],
        ['分析データ', `${quality.usedCount || 0}/${quality.sampleCount || 0}件`]
    ];
    document.getElementById('predictionSummary').innerHTML = cards.map(([label, value]) => `
        <div class="col-6 col-lg-3"><div class="prediction-card">
            <div class="text-muted small">${label}</div><div class="value">${value}</div>
        </div></div>`).join('');
    const qualityBox = document.getElementById('predictionQuality');
    qualityBox.style.display = 'block';
    qualityBox.textContent = `分析方法: ${quality.method || '—'} / 対象期間: ${quality.lookbackDays || 90}日 / 外れ値候補: ${quality.outlierCount || 0}件`;
}
