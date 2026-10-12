// 30日後の相場予想。相場分析画面の両方のタブ（検索履歴・新しいキーワード）から呼び出す。
(function () {
    let currentData = {};
    let predictionChart = null;

    function yen(value) {
        return Number.isFinite(Number(value)) ? `${Number(value).toLocaleString()}円` : '—';
    }

    // 指定キーワードの落札データを取得して予想を描画する。成功時は結果、失敗時は null を返す。
    async function run(keyword) {
        try {
            const response = await fetch(`/taskle/prediction_market?${new URLSearchParams({ keyword })}`);
            if (!response.ok) throw await window.SystemaFeedback.responseError(response, '相場予想に失敗しました');
            const result = await response.json();
            if (result.error) throw new Error(result.error);
            currentData = result;
            render(keyword);
            return result;
        } catch (error) {
            console.error('相場予想エラー:', error);
            window.SystemaFeedback.errorFrom(error, '相場予想に失敗しました');
            return null;
        }
    }

    function render(keyword) {
        document.getElementById('predictionKeyword').textContent = `：${keyword}`;
        document.getElementById('predictionSection').hidden = false;
        showWarning(currentData.quality?.warning || '');
        updateSummary();
        updateChart();
        updateTable();
        updateBacktest();
    }

    function hide() {
        document.getElementById('predictionSection').hidden = true;
    }

    function showWarning(message) {
        const warning = document.getElementById('prediction-warning');
        warning.style.display = message ? 'block' : 'none';
        warning.textContent = message;
    }

    function updateChart() {
        if (!window.Chart) return;
        const daily = currentData.daily_trends || [];
        const labels = daily.map(item => item.date);
        const forecastLabel = labels.length
            ? new Date(new Date(`${labels[labels.length - 1]}T00:00:00`).getTime() + 30 * 86400000).toISOString().slice(0, 10)
            : '1ヶ月後';
        const interval = currentData.prediction_interval || currentData.confidence_interval || [0, 0];
        const empty = daily.map(() => null);
        if (predictionChart) predictionChart.destroy();
        predictionChart = new Chart(document.getElementById('predictionChart').getContext('2d'), {
            data: {
                labels: [...labels, forecastLabel],
                datasets: [
                    {
                        type: 'line', label: '日次中央値',
                        data: daily.map(item => item.median).concat([null]),
                        borderColor: '#0f8a70', backgroundColor: '#0f8a70', pointRadius: 3, tension: 0.2
                    },
                    {
                        type: 'line', label: '14日移動中央値',
                        data: daily.map(item => item.rollingMedian).concat([null]),
                        borderColor: '#8a7d6e', pointRadius: 0, borderWidth: 2, tension: 0.25
                    },
                    {
                        type: 'line', label: '予測範囲（上限）',
                        data: empty.concat([interval[1]]),
                        borderColor: 'rgba(194,83,44,.3)', backgroundColor: 'rgba(194,83,44,.15)', pointRadius: 0
                    },
                    {
                        type: 'line', label: '予測範囲（下限）',
                        data: empty.concat([interval[0]]),
                        borderColor: 'rgba(194,83,44,.3)', backgroundColor: 'rgba(194,83,44,.15)', fill: '-1', pointRadius: 0
                    },
                    {
                        type: 'line', label: '30日後予測',
                        data: empty.concat([currentData.predicted_price]),
                        borderColor: '#c2532c', backgroundColor: '#c2532c', pointRadius: 7, borderDash: [6, 4]
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: '価格 (円)' } },
                    x: { title: { display: true, text: '落札日' } }
                },
                plugins: {
                    legend: { position: 'top', labels: { filter: item => !item.text.includes('予測範囲') || item.text.includes('上限') } },
                    tooltip: { mode: 'index', intersect: false, callbacks: { label: context => context.parsed.y == null ? '' : `${context.dataset.label}: ${context.parsed.y.toLocaleString()}円` } }
                }
            }
        });
    }

    function updateTable() {
        const tableBody = document.querySelector('#predictionTable tbody');
        const interval = currentData.prediction_interval || currentData.confidence_interval || [];
        const rows = [
            ['直近14日移動中央値', currentData.moving_average],
            ['1ヶ月予測', currentData.predicted_price],
            ['予測範囲下限', interval[0]],
            ['予測範囲上限', interval[1]]
        ].filter(([label, value]) => label !== '直近14日移動中央値' || Number.isFinite(Number(value)) && value);
        tableBody.innerHTML = '';
        rows.forEach(([label, value]) => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = label;
            row.insertCell().textContent = typeof value === 'number' ? yen(value) : 'N/A';
        });
    }

    function card(label, value) {
        return `<div class="col-6 col-lg-3"><div class="analysis-card">
            <div class="text-muted small">${label}</div><div class="value">${value}</div></div></div>`;
    }

    function updateSummary() {
        const quality = currentData.quality || {};
        const interval = currentData.prediction_interval || currentData.confidence_interval || [];
        const trend = quality.trendPercent30Days;
        document.getElementById('predictionSummary').innerHTML = [
            card('30日後予測', currentData.predicted_price ? yen(currentData.predicted_price) : '—'),
            card('予測範囲', interval.length ? `${interval[0].toLocaleString()}～${yen(interval[1])}` : '—'),
            card('30日トレンド', trend == null ? '—' : `${trend >= 0 ? '+' : ''}${trend}%`),
            card('分析データ', `${quality.usedCount || 0}/${quality.sampleCount || 0}件`)
        ].join('');
        const qualityBox = document.getElementById('predictionQuality');
        qualityBox.style.display = 'block';
        qualityBox.textContent = `分析方法: ${quality.method || '—'} / 対象期間: ${quality.lookbackDays || 90}日 / 外れ値候補: ${quality.outlierCount || 0}件`;
    }

    function updateBacktest() {
        const backtest = currentData.backtest || {};
        const status = document.getElementById('backtestStatus');
        const summary = document.getElementById('backtestSummary');
        const warning = document.getElementById('backtestWarning');
        const tableBody = document.querySelector('#backtestTable tbody');
        warning.textContent = backtest.warning || '';
        warning.style.display = backtest.warning ? 'block' : 'none';
        tableBody.innerHTML = '';
        if (!backtest.available) {
            status.className = 'badge bg-secondary'; status.textContent = 'データ不足'; summary.innerHTML = ''; return;
        }
        status.className = 'badge bg-success'; status.textContent = `${backtest.windowCount}期間を検証`;
        summary.innerHTML = [
            card('平均絶対誤差', yen(backtest.mae)), card('平均誤差率', `${backtest.mape}%`),
            card('方向的中率', `${backtest.directionAccuracy}%`), card('予測範囲内', `${backtest.intervalCoverage}%`)
        ].join('');
        (backtest.points || []).forEach(point => {
            const row = tableBody.insertRow();
            [point.cutoffDate, point.targetDate, yen(point.predictedPrice), yen(point.actualPrice),
                `${yen(point.absoluteError)} (${point.percentageError}%)`,
                point.directionCorrect ? '的中' : '不一致'].forEach(value => { row.insertCell().textContent = value; });
        });
    }

    // よく使われるキーワードを入力欄に追記するボタンを並べる。
    function loadPopularWords(input) {
        fetch('/taskle/get_popular_words?top=10')
            .then(response => response.json())
            .then(data => {
                const words = data.words || [];
                const area = document.getElementById('popularWordsBtnGroup');
                document.getElementById('popularWordsArea').hidden = !words.length;
                area.replaceChildren(...words.map(word => {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'btn btn-outline-danger btn-sm';
                    button.textContent = word;
                    button.addEventListener('click', () => {
                        input.value = input.value ? `${input.value} ${word}` : word;
                        input.focus();
                    });
                    return button;
                }));
            })
            .catch(error => console.error('Error fetching popular words:', error));
    }

    window.SystemaPrediction = { run, hide, loadPopularWords };
})();
