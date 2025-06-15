document.addEventListener('DOMContentLoaded', () => {
    refreshSearchWordDropdown();
    const dropdown = document.getElementById('searchWordDropdown');
    const analyzeMarketPriceButton = document.getElementById('analyzeMarketPrice');
    const updateMarketDataButton = document.getElementById('updateMarketData');
    const deleteMarketDataButton = document.getElementById('deleteMarketData');
    const spinner = document.getElementById('updateSpinner');

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

                generateBarChart(prices);
                generateWordCloud(names);

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

function generateBarChart(prices) {
    const chartContainer = document.getElementById('priceChart');
    chartContainer.innerHTML = '';

    const median = calculateMedian(prices);
    const bins = [
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