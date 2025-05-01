// API URL'sini belirle
const BASE_URL = "https://tdx-combined-service.onrender.com";

async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim(); 
    if (message === "") return;

    appendMessage("Siz", message);
    input.value = "";
    appendMessage("TDX Bot", "Analiz yapılıyor...");

    let symbol = message;
    let detayli = false;

    if (message.toLowerCase().includes("detaylı")) { 
        detayli = true;
        const words = message.split(" ");
        symbol = words[words.length - 1];
        console.log("Detaylı analiz isteği:", symbol, detayli);
    }
    
    // Remove .IS suffix if present
    symbol = symbol.replace('.IS', '').toUpperCase();
    
    try {
        const response = await fetch(`${BASE_URL}/chatbot?symbol=${symbol}&detay=${detayli}`);

        if (!response.ok) {
            const errorDetails = await response.text();
            console.error("API Hatası:", errorDetails);
            updateLastBotMessage("API isteğinde hata oluştu. Lütfen sunucuyu kontrol edin.");
            return;
        }

        const data = await response.json();
        if (!data.response) {
            throw new Error('Chatbot yanıtı boş geldi');
        }
        updateLastBotMessage(data.response.replace(/\n/g, "<br>"));
    } catch (error) {
        console.error("İstek gönderilirken hata oluştu:", error);
        updateLastBotMessage("Bir hata oluştu. Sunucuya ulaşılamıyor olabilir.");
    }
}

function appendMessage(sender, message) {
    const chatDisplay = document.getElementById("chat-display");
    const messageDiv = document.createElement("div");
    messageDiv.setAttribute('data-sender', sender);
    messageDiv.innerHTML = `<strong>${sender}:</strong> ${message}`;
    chatDisplay.appendChild(messageDiv);
    chatDisplay.scrollTop = chatDisplay.scrollHeight;
}

function updateLastBotMessage(newText) {
    const chatDisplay = document.getElementById("chat-display");
    const messages = chatDisplay.querySelectorAll("div");
    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        lastMessage.innerHTML = `<strong>TDX Bot:</strong> ${newText}`;
    }
}

function toggleChatbot() {
    const panel = document.getElementById("chatbot-panel");
    if (panel.style.display === "none" || panel.style.display === "") {
        panel.style.display = "flex";
    } else {
        panel.style.display = "none";
    }
}

let isDragging = false, offsetX, offsetY;

function startDrag(e) {
    const panel = document.getElementById("chatbot-panel");
    isDragging = true;
    offsetX = e.clientX - panel.offsetLeft;
    offsetY = e.clientY - panel.offsetTop;

    document.onmousemove = function(e) {
        if (isDragging) {
            panel.style.left = (e.clientX - offsetX) + "px";
            panel.style.top = (e.clientY - offsetY) + "px";
            panel.style.bottom = "auto";
            panel.style.right = "auto";
        }
    };

    document.onmouseup = function() {
        isDragging = false;
        document.onmousemove = null;
        document.onmouseup = null;
    };
}

function toggleMenu() {
    const navLinks = document.getElementById("navLinks");
    navLinks.classList.toggle("active");
}

function smoothScroll(target, duration) {
    const targetElement = document.querySelector(target);
    const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset;
    const startPosition = window.pageYOffset;
    const distance = targetPosition - startPosition;
    let startTime = null;

    function animation(currentTime) {
        if (startTime === null) startTime = currentTime;
        const timeElapsed = currentTime - startTime;
        const run = ease(timeElapsed, startPosition, distance, duration);
        window.scrollTo(0, run);
        if (timeElapsed < duration) requestAnimationFrame(animation);
    }

    function ease(t, b, c, d) {
        t /= d / 2;
        if (t < 1) return c / 2 * t * t + b;
        t--;
        return -c / 2 * (t * (t - 2) - 1) + b;
    }

    requestAnimationFrame(animation);
}

document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = link.getAttribute('href');
            if (target !== '#') {
                smoothScroll(target, 1000);
            }
            document.getElementById('navLinks').classList.remove('active');
        });
    });

    document.getElementById("chatbot-panel").style.display = "none";
});

// Chart Configuration and Functions
let stockChart;

async function updateChart() {
    const symbol = document.getElementById('stockSymbol').value;
    const activeTimeframe = document.querySelector('.timeframe-btn.active') || 
                        document.querySelector('[data-timeframe="6mo"]');
    
    if (!activeTimeframe) {
        console.error('Timeframe butonu bulunamadı');
        return;
    }

    let period = activeTimeframe.dataset.timeframe;
    let interval = activeTimeframe.dataset.interval;

    if (period === '1mo') {
        interval = '1d';
    } else if (period === '3mo') {
        interval = '1d';
    } else if (period === '6mo' || period === '1y') {
        interval = '1wk';
    } else if (period === '2y') {
        interval = '1wk';
    } else {
        period = '6mo';
        interval = '1wk';
    }

    try {
        document.getElementById('currentPrice').textContent = 'Yükleniyor...';
        document.getElementById('closePrice').textContent = 'Yükleniyor...';
        document.getElementById('priceChange').textContent = '...';
        document.getElementById('volume').textContent = '...';

        // Remove .IS suffix if present and convert to uppercase
        let formattedSymbol = symbol.replace('.IS', '').toUpperCase();

        const response = await fetch(`${BASE_URL}/stock-data?symbol=${formattedSymbol}&period=${period}&interval=${interval}`);

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Veri alınamadı: ${formattedSymbol}`);
        }
        
        const data = await response.json();

        if (!data || !data.success || !data.prices || data.prices.length === 0) {
            throw new Error('Geçerli veri bulunamadı');
        }

        // Update price information
        document.getElementById('currentPrice').textContent = data.current.toFixed(2);
        document.getElementById('closePrice').textContent = data.close.toFixed(2);
        document.getElementById('priceChange').textContent = `${data.change > 0 ? '+' : ''}${data.change.toFixed(2)}%`;
        document.getElementById('volume').textContent = data.volume.toLocaleString();

        // Update chart
        const chartData = {
            labels: data.timestamps.map(ts => new Date(ts)),
            datasets: [{
                label: `${formattedSymbol} Fiyat`,
                data: data.prices,
                borderColor: '#2ecc71',
                backgroundColor: 'rgba(46, 204, 113, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.1
            }]
        };

        if (window.myChart) {
            window.myChart.destroy();
        }

        const ctx = document.getElementById('priceChart').getContext('2d');
        window.myChart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: period === '1mo' || period === '3mo' ? 'day' : 'week',
                            displayFormats: {
                                day: 'dd MMM',
                                week: 'dd MMM yyyy'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Tarih'
                        }
                    },
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Fiyat (TL)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y.toFixed(2)} TL`;
                            }
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error('Veri alınırken bir hata oluştu:', error);
        document.getElementById('currentPrice').textContent = 'Hata';
        document.getElementById('closePrice').textContent = 'Hata';
        document.getElementById('priceChange').textContent = 'Hata';
        document.getElementById('volume').textContent = 'Hata';
        
        // Show error message to user
        const errorMessage = document.createElement('div');
        errorMessage.className = 'alert alert-danger';
        errorMessage.textContent = `Veri alınırken bir hata oluştu: ${error.message}`;
        
        // Remove any existing error messages
        const existingErrors = document.querySelectorAll('.alert-danger');
        existingErrors.forEach(err => err.remove());
        
        // Add the new error message
        document.querySelector('.chart-container').prepend(errorMessage);
        
        // Destroy chart if it exists
        if (window.myChart) {
            window.myChart.destroy();
            window.myChart = null;
        }
    }
}

// Timeframe butonları için event listener
document.querySelectorAll('.timeframe-btn').forEach(button => {
    button.addEventListener('click', (e) => {
        // Aktif butonu güncelle
        const activeButton = document.querySelector('.timeframe-btn.active');
        if (activeButton) {
            activeButton.classList.remove('active');
        }
        e.target.classList.add('active');
        // Grafiği güncelle
        updateChart();
    });
});

// Sayfa yüklendiğinde ilk grafiği çiz
document.addEventListener('DOMContentLoaded', () => {
    // Canvas kontrolü
    const canvas = document.getElementById('priceChart');
    if (!canvas) {
        console.error('Canvas elementi bulunamadı');
        return;
    }

    // İlk timeframe butonu kontrolü
    const defaultTimeframe = document.querySelector('[data-timeframe="6mo"]');
    if (!defaultTimeframe) {
        console.error('Varsayılan timeframe butonu bulunamadı');
        return;
    }

    // Varsayılan timeframe'i aktif yap
    if (!document.querySelector('.timeframe-btn.active')) {
        defaultTimeframe.classList.add('active');
    }

    updateChart();
});

// Enter tuşu ile arama yapma
document.getElementById('stockSymbol').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        updateChart();
    }
});
