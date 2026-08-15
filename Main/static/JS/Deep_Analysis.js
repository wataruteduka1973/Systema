document.addEventListener('DOMContentLoaded', () => {
    refreshSearchWordDropdown();
    const dropdown = document.getElementById('searchWordDropdown');
    const analyzeMarketPriceButton = document.getElementById('analyzeMarketPrice');
    const updateMarketDataButton = document.getElementById('updateMarketData');
    const deleteMarketDataButton = document.getElementById('deleteMarketData');
    const spinner = document.getElementById('updateSpinner');

    const summary = document.getElementById('marketSummaryCards');
    const dropdownGroup = dropdown.closest('.form-group');
    const searchHeading = dropdownGroup?.previousElementSibling;
    const actionGroup = analyzeMarketPriceButton.closest('.form-group');
    if (summary && dropdownGroup && actionGroup) {
        if (searchHeading) summary.parentNode.insertBefore(searchHeading, summary);
        summary.parentNode.insertBefore(dropdownGroup, summary);
        summary.parentNode.insertBefore(actionGroup, summary);
    }

    analyzeMarketPriceButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        fetch(`/taskle/get_market_data?keyword=${encodeURIComponent(searchWord)}`)
            .then(response => response.json())
            .then(data => {
                const prices = data.data.map(item => item.EndPrice).filter(price => !isNaN(price));
                const names = data.data.map(item => item.Name);
                const searchDay = data.searchDay;

                if (data.error) throw new Error(data.error);
                generateBarChart(prices, data.analysis?.summary?.histogram);
                generateWordCloud(names);
                renderMarketSummary(data.analysis?.summary || {});
                renderPriceTrend(data.analysis?.timeSeries || []);
                renderConditionStats(data.analysis?.conditionMarket || {});

                document.getElementById('searchDay').textContent = searchDay || '';
            })
            .catch(error => console.error('Error fetching market data:', error));
    });

    updateMarketDataButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        spinner.style.display = 'inline-block';
        updateMarketDataButton.disabled = true;
        fetch(`/taskle/update_market_data?keyword=${encodeURIComponent(searchWord)}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                alert(data.message || '相場データを更新しました');
                refreshSearchWordDropdown(searchWord);
                analyzeMarketPriceButton.click();
            })
            .catch(error => alert('更新に失敗しました: ' + error))
            .finally(() => {
                spinner.style.display = 'none';
                updateMarketDataButton.disabled = false;
            });
    });

    deleteMarketDataButton.addEventListener('click', () => {
        const searchWord = dropdown.value;
        if (!searchWord) {
            alert('検索ワードを選択してください');
            return;
        }
        if (!confirm('本当に削除しますか？')) return;
        fetch(`/taskle/delete_market_data?keyword=${encodeURIComponent(searchWord)}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                alert(data.message || '相場データを削除しました');
                refreshSearchWordDropdown();
                document.getElementById('priceChart').innerHTML = '';
                document.getElementById('wordcloud').innerHTML = '';
                document.getElementById('marketSummaryCards').innerHTML = '';
                document.getElementById('priceTrendChart').innerHTML = '';
                document.getElementById('conditionStats').innerHTML = '';
                document.getElementById('searchDay').textContent = '';
            })
            .catch(error => alert('削除に失敗しました: ' + error));
    });
});

function refreshSearchWordDropdown(selectedValue = "") {
    fetch('/taskle/get_search_words')
        .then(response => response.json())
        .then(data => {
            const dropdown = document.getElementById('searchWordDropdown');
            dropdown.innerHTML = '<option value="">選択してください</option>';
            data.searchWords.forEach(word => {
                const option = document.createElement('option');
                option.value = word;
                option.textContent = word;
                dropdown.appendChild(option);
            });
            if (selectedValue) dropdown.value = selectedValue;
        })
        .catch(error => console.error('Error fetching search words:', error));
}

function generateWordCloud(data) {
    const container = document.querySelector('.wordcloud-container');
    const width = container.offsetWidth || 800;
    const height = container.offsetHeight || 400;

    const wordCounts = {};
    data.forEach(item => {
        item.split(/\s+/).forEach(word => {
            if (word.length > 1) {
                wordCounts[word] = (wordCounts[word] || 0) + 1;
            }
        });
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


function calculateMedian(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}

function calculateStandardDeviation(numbers, mean) {
    const variance = numbers.reduce((sum, num) => sum + Math.pow(num - mean, 2), 0) / numbers.length;
    return Math.sqrt(variance);
}

function generateBarChart(prices, serverBins = null) {
    const chartContainer = document.getElementById('priceChart');
    chartContainer.innerHTML = '';

    if (!prices.length) return;
    const median = calculateMedian(prices);
    const fallbackBins = [
        { range: `(${Math.floor(median * 0)}円 - ${Math.floor(median * 0.2)}円)`, count: prices.filter(price => price >= median * 0 && price < median * 0.2).length },
        { range: `(${Math.floor(median * 0.2)}円 - ${Math.floor(median * 0.4)}円)`, count: prices.filter(price => price >= median * 0.2 && price < median * 0.4).length },
        { range: `(${Math.floor(median * 0.4)}円 - ${Math.floor(median * 0.6)}円)`, count: prices.filter(price => price >= median * 0.4 && price < median * 0.6).length },
        { range: `(${Math.floor(median * 0.6)}円 - ${Math.floor(median * 0.8)}円)`, count: prices.filter(price => price >= median * 0.6 && price < median * 0.8).length },
        { range: `(${Math.floor(median * 0.8)}円 - ${Math.ceil(median * 1.0)}円)`, count: prices.filter(price => price >= median * 0.8 && price <= median * 1.0).length },
        { range: `(${Math.ceil(median * 1.0)}円 - ${Math.ceil(median * 1.2)}円)`, count: prices.filter(price => price > median * 1.0 && price <= median * 1.2).length },
        { range: `(${Math.ceil(median * 1.2)}円 - ${Math.ceil(median * 1.4)}円)`, count: prices.filter(price => price > median * 1.2 && price <= median * 1.4).length },
        { range: `(${Math.ceil(median * 1.4)}円 - ${Math.ceil(median * 1.6)}円)`, count: prices.filter(price => price > median * 1.4 && price <= median * 1.6).length },
        { range: `(${Math.ceil(median * 1.6)}円 - ${Math.ceil(median * 1.8)}円)`, count: prices.filter(price => price > median * 1.6 && price <= median * 1.8).length },
        { range: `(${Math.ceil(median * 1.8)}円~)`, count: prices.filter(price => price > median * 1.8).length }
    ];
    const bins = Array.isArray(serverBins) && serverBins.length
        ? serverBins.map(bin => ({ range: `${bin.lower.toLocaleString()}～${bin.upper.toLocaleString()}円`, count: bin.count }))
        : fallbackBins;

    const margin = { top: 30, right: 50, bottom: 150, left: 60 };
    const width = 1300 - margin.left - margin.right;
    const height = 450 - margin.top - margin.bottom;

    const svg = d3.select(chartContainer)
        .append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleBand()
        .domain(bins.map(d => d.range))
        .range([0, width])
        .padding(0.1);

    const yScale = d3.scaleLinear()
        .domain([0, d3.max(bins, d => d.count) * 1.1])
        .range([height, 0]);

    svg.selectAll('.bar')
        .data(bins)
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', d => xScale(d.range))
        .attr('y', d => yScale(d.count))
        .attr('width', xScale.bandwidth())
        .attr('height', d => height - yScale(d.count))
        .attr('fill', 'steelblue');

    svg.selectAll('.label')
        .data(bins)
        .enter()
        .append('text')
        .attr('class', 'label')
        .attr('x', d => xScale(d.range) + xScale.bandwidth() / 2)
        .attr('y', d => yScale(d.count) - 15)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('fill', '#333')
        .text(d => `${d.count}個`);

    svg.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(xScale))
        .selectAll('text')
        .attr('transform', 'rotate(-45)')
        .style('text-anchor', 'end')
        .style('font-size', '14px');

    svg.append('g')
        .call(d3.axisLeft(yScale))
        .selectAll('text')
        .style('font-size', '14px');

    svg.append('text')
        .attr('x', width / 2)
        .attr('y', height + 150)
        .attr('text-anchor', 'middle')
        .style('font-size', '16px')
        .text('価格帯 (円)');

    svg.append('text')
        .attr('x', -height / 2)
        .attr('y', -40)
        .attr('transform', 'rotate(-90)')
        .attr('text-anchor', 'middle')
        .style('font-size', '16px')
        .text('商品数 (個)');
}

function formatYen(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toLocaleString()}円` : '—';
}

function renderMarketSummary(summary) {
    const values = [
        ['商品数', `${summary.count || 0}件`],
        ['中央値', formatYen(summary.median)],
        ['平均価格', formatYen(summary.mean)],
        ['価格変動', summary.coefficientOfVariation == null ? '—' : `${summary.coefficientOfVariation}%`],
        ['中央50%の幅', formatYen(summary.iqr)],
        ['外れ値候補', `${summary.outlierCount || 0}件`]
    ];
    document.getElementById('marketSummaryCards').innerHTML = values.map(([label, value]) => `
        <div class="col-6 col-lg-2"><div class="analysis-card">
            <div class="text-muted small">${label}</div><div class="value">${value}</div>
        </div></div>`).join('');
}

function renderConditionStats(market) {
    const rows = market.conditions || [];
    const target = document.getElementById('conditionStats');
    if (!rows.length) {
        target.innerHTML = '<p class="text-muted">状態別に集計できるデータがありません。</p>';
        return;
    }
    target.innerHTML = `<table class="table table-striped align-middle mb-0">
        <thead><tr><th>商品状態</th><th>件数</th><th>中央値</th></tr></thead>
        <tbody>${rows.map(row => `<tr><td>${row.label}</td><td>${row.count}件</td><td>${formatYen(row.medianPrice)}</td></tr>`).join('')}</tbody>
    </table>`;
}

function renderPriceTrend(series) {
    const target = document.getElementById('priceTrendChart');
    target.innerHTML = '';
    if (!series.length) {
        target.innerHTML = '<p class="text-muted">日付を解析できるデータがありません。</p>';
        return;
    }
    const data = series.slice(-20).map((item, index) => ({
        ...item,
        index,
        parsedDate: new Date(item.date),
    }));
    const margin = { top: 20, right: 30, bottom: 50, left: 75 };
    const width = 1000 - margin.left - margin.right;
    const height = 340 - margin.top - margin.bottom;
    const svg = d3.select(target).append('svg').attr('viewBox', '0 0 1000 340')
        .append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const x = d3.scalePoint()
        .domain(data.map(item => item.index))
        .range([0, width])
        .padding(data.length === 1 ? 0.5 : 0.35);
    const y = d3.scaleLinear().domain([0, d3.max(data, d => d.q3) * 1.08]).nice().range([height, 0]);
    svg.selectAll('.iqr-range').data(data).enter().append('rect')
        .attr('class', 'iqr-range')
        .attr('x', d => x(d.index) - Math.min(22, width / Math.max(data.length * 3, 1)))
        .attr('y', d => y(d.q3))
        .attr('width', Math.min(44, width / Math.max(data.length * 1.5, 1)))
        .attr('height', d => Math.max(3, y(d.q1) - y(d.q3)))
        .attr('rx', 4)
        .attr('fill', 'rgba(59,130,246,.28)');
    svg.append('path').datum(data).attr('fill', 'none').attr('stroke', '#dc2626').attr('stroke-width', 2.5)
        .attr('d', d3.line().x(d => x(d.index)).y(d => y(d.median)));
    svg.selectAll('.median-point').data(data).enter().append('circle').attr('class', 'median-point')
        .attr('cx', d => x(d.index)).attr('cy', d => y(d.median)).attr('r', 5).attr('fill', '#dc2626')
        .append('title').text(d => `${d.parsedDate.toLocaleString('ja-JP')}: ${d.median.toLocaleString()}円 (${d.count}件)`);
    svg.append('g').attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x).tickFormat(index => {
            const item = data[index];
            return item ? `更新${index + 1} ${item.parsedDate.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })}` : '';
        }))
        .selectAll('text').attr('transform', 'rotate(-25)').style('text-anchor', 'end');
    svg.append('g').call(d3.axisLeft(y).ticks(6).tickFormat(value => `${Number(value).toLocaleString()}円`));

    const recent = data.slice(-20).reverse();
    target.insertAdjacentHTML('beforeend', `
        <div class="table-responsive mt-3">
            <table class="table table-sm table-striped align-middle">
                <thead><tr><th>取得日時</th><th>件数</th><th>中央値</th><th>中央50%の価格帯</th></tr></thead>
                <tbody>${recent.map(item => `
                    <tr><td>${item.parsedDate.toLocaleString('ja-JP')}</td><td>${item.count}件</td>
                    <td>${formatYen(item.median)}</td><td>${formatYen(item.q1)} ～ ${formatYen(item.q3)}</td></tr>
                `).join('')}</tbody>
            </table>
        </div>`);
}
