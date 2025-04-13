let stockChart = null;

// Initialize the chart with empty data
function initializeChart() {
    const ctx = document.getElementById('stockChart').getContext('2d');
    stockChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Stock Price',
                data: [],
                borderColor: '#2962ff',
                backgroundColor: 'rgba(41, 98, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Stock Price Chart',
                    font: {
                        size: 16
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// Fetch stock data from the backend
async function fetchStockData(symbol) {
    try {
        const response = await fetch(`http://localhost:8000/stock/${symbol}`);
        if (!response.ok) {
            throw new Error('Failed to fetch stock data');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching stock data:', error);
        throw error;
    }
}

// Update the chart with new data
function updateChart(data, symbol) {
    if (!stockChart) {
        initializeChart();
    }

    const labels = data.map(item => new Date(item.timestamp).toLocaleDateString());
    const prices = data.map(item => item.price);

    stockChart.data.labels = labels;
    stockChart.data.datasets[0].data = prices;
    stockChart.data.datasets[0].label = `${symbol} Stock Price`;
    stockChart.options.plugins.title.text = `${symbol} Stock Price Chart`;
    stockChart.update();
}

// Handle search button click
document.getElementById('searchButton').addEventListener('click', async () => {
    const symbol = document.getElementById('stockSymbol').value.trim().toUpperCase();
    if (!symbol) {
        alert('Please enter a stock symbol');
        return;
    }

    const loadingIndicator = document.getElementById('loadingIndicator');
    loadingIndicator.style.display = 'block';

    try {
        const data = await fetchStockData(symbol);
        updateChart(data, symbol);
    } catch (error) {
        alert('Error fetching stock data. Please try again.');
    } finally {
        loadingIndicator.style.display = 'none';
    }
});

// Handle Enter key press in the input field
document.getElementById('stockSymbol').addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        document.getElementById('searchButton').click();
    }
});

// Initialize the chart when the page loads
document.addEventListener('DOMContentLoaded', initializeChart); 