document.addEventListener('DOMContentLoaded', () => {
    fetch('/taskle/get_search_words')
        .then(response => response.json())
        .then(data => {
            const dropdown = document.getElementById('searchWordDropdown');
            data.searchWords.forEach(word => {
                const option = document.createElement('option');
                option.value = word;
                option.textContent = word;
                dropdown.appendChild(option);
            });
        })
        .catch(error => console.error('Error fetching search words:', error));
});

document.addEventListener('DOMContentLoaded', () => {
    const dropdown = document.getElementById('searchWordDropdown');
    const analyzeMarketPriceButton = document.getElementById('analyzeMarketPrice');

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

                const chartContainer = document.getElementById('priceChartContainer');
                chartContainer.insertAdjacentHTML('beforeend', `<p>最終データ取得日: ${searchDay}</p>`);
            })
            .catch(error => console.error('Error fetching market data:', error));
    });
});

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
        { range: `(${Math.ceil(median * 1.45)}円~)`, count: prices.filter(price => price >= median * 1.45).length },
        { range: `(${Math.ceil(median * 1.30)}円 - ${Math.ceil(median * 1.45)}円)`, count: prices.filter(price => price >= median * 1.30 && price < median * 1.45).length },
        { range: `(${Math.ceil(median * 1.15)}円 - ${Math.ceil(median * 1.30)}円)`, count: prices.filter(price => price >= median * 1.15 && price < median * 1.30).length },
        { range: `(${Math.ceil(median * 1.00)}円 - ${Math.ceil(median * 1.15)}円)`, count: prices.filter(price => price >= median * 1.00 && price < median * 1.15).length },
        { range: `(${Math.floor(median * 0.95)}円 - ${Math.ceil(median * 1.00)}円)`, count: prices.filter(price => price >= median * 0.95 && price < median * 1.00).length },
        { range: `(${Math.floor(median * 0.85)}円 - ${Math.floor(median * 0.95)}円)`, count: prices.filter(price => price >= median * 0.85 && price < median * 0.95).length },
        { range: `(${Math.floor(median * 0.70)}円 - ${Math.floor(median * 0.85)}円)`, count: prices.filter(price => price >= median * 0.70 && price < median * 0.85).length },
        { range: `(${Math.floor(median * 0.55)}円 - ${Math.floor(median * 0.70)}円)`, count: prices.filter(price => price >= median * 0.55 && price < median * 0.70).length },
        { range: `(~${Math.floor(median * 0.55)}円)`, count: prices.filter(price => price < median * 0.55).length }
    ];


    const margin = { top: 30, right: 50, bottom: 120, left: 60 };
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
        .padding(0.15);

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
        .attr('y', height + 100)
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