async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (message === "") return;

    appendMessage("Siz", message);
    input.value = "";
    appendMessage("TDX Bot", "Analiz yapılıyor...");

    // API URL'sini oluştur
    let apiUrl = "http://localhost:8001/chatbot";  // Port değiştirildi
    let symbol = message;
    let detayli = false;

    // "detaylı analiz yap" veya "detaylı" kelimelerini kontrol et
    if (message.toLowerCase().includes("detaylı")) {
        detayli = true;
        // Sembolü ayıkla (son kelimeyi al)
        const words = message.split(" ");
        symbol = words[words.length - 1];
        console.log("Detaylı analiz isteği:", symbol, detayli);
    }
    
    // Sembolün sonunda .IS yoksa ekle
    if (!symbol.toUpperCase().endsWith(".IS")) {
        symbol = symbol + ".IS";
    }
    
    // URL'yi parametrelere göre oluştur
    apiUrl += `?symbol=${symbol}&detay=${detayli}`;
    console.log("API URL:", apiUrl);

    try {
        const response = await fetch(apiUrl);

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
                          document.querySelector('[data-timeframe="6mo"]'); // Varsayılan 6 ay
    
    if (!activeTimeframe) {
        console.error('Timeframe butonu bulunamadı');
        return;
    }

    // Period ve interval ayarları
    let period = activeTimeframe.dataset.timeframe;
    let interval = activeTimeframe.dataset.interval;

    // THYAO gibi BIST hisseleri için yfinance sınırlı veri dönüyor
    // Örneğin 1mo+1d bazen çalışmıyor, onun yerine güvenli kombinasyonlar:
    if (period === '1mo') {
        interval = '1d'; // bazı hisselerde çalışmıyor!
    } else if (period === '3mo') {
        interval = '1d';
    } else if (period === '6mo' || period === '1y') {
        interval = '1wk';
    } else if (period === '2y') {
        interval = '1wk';
    } else {
        // default fallback
        period = '6mo';
        interval = '1wk';
    }

    try {
        // Loading durumunu göster
        document.getElementById('currentPrice').textContent = 'Yükleniyor...';
        document.getElementById('closePrice').textContent = 'Yükleniyor...';
        document.getElementById('priceChange').textContent = '...';
        document.getElementById('volume').textContent = '...';

        // Symbol kontrolü ve .IS ekleme
        let formattedSymbol = symbol.toUpperCase();
        if (!formattedSymbol.endsWith('.IS')) {
            formattedSymbol += '.IS';
        }

        const response = await fetch(`http://localhost:8001/stock-data?symbol=${formattedSymbol}&period=${period}&interval=${interval}`);


        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Veri alınamadı: ${errorText}`);
        }
        
        const data = await response.json();

        // Veri kontrolü
        if (!data || !data.prices || data.prices.length === 0) {
            throw new Error('Geçerli veri bulunamadı');
        }

        // Mevcut grafik varsa yok et
        if (stockChart) {
            stockChart.destroy();
        }

        // Grafik verilerini hazırla
        const chartData = {
            labels: data.timestamps.map(ts => {
                const date = new Date(ts);
                if (interval === '1d') {
                    return date.toLocaleDateString('tr-TR', { 
                        day: '2-digit',
                        month: '2-digit'
                    });
                } else {
                    return date.toLocaleDateString('tr-TR', { 
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric'
                    });
                }
            }),
            datasets: [{
                label: formattedSymbol,
                data: data.prices,
                borderColor: '#2ecc71',
                backgroundColor: 'rgba(46, 204, 113, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.1
            }]
        };

        // Grafik ayarları
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        bodyFont: {
                            size: 14
                        },
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return `Fiyat: ${context.parsed.y.toFixed(2)} TL`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Tarih'
                        },
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Fiyat (TL)'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        };

        // Canvas kontrolü
        const canvas = document.getElementById('stockChart');
        if (!canvas) {
            throw new Error('Canvas elementi bulunamadı');
        }

        const ctx = canvas.getContext('2d');
        stockChart = new Chart(ctx, config);

        // Bilgileri güncelle
        if (data.current) document.getElementById('currentPrice').textContent = data.current.toFixed(2) + ' TL';
        if (data.close) document.getElementById('closePrice').textContent = data.close.toFixed(2) + ' TL';
        if (data.change) {
            const priceChangeElement = document.getElementById('priceChange');
            const change = parseFloat(data.change);
            priceChangeElement.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
            priceChangeElement.style.color = change >= 0 ? '#2ecc71' : '#e74c3c';
        }
        if (data.volume) document.getElementById('volume').textContent = parseInt(data.volume).toLocaleString('tr-TR');

    } catch (error) {
        console.error('Hata:', error);
        alert('Veri alınırken bir hata oluştu: ' + error.message);
        
        // Hata durumunda bilgileri sıfırla
        document.getElementById('currentPrice').textContent = '0.00';
        document.getElementById('closePrice').textContent = '0.00';
        document.getElementById('priceChange').textContent = '0.00%';
        document.getElementById('volume').textContent = '0';
        
        // Mevcut grafik varsa temizle
        if (stockChart) {
            stockChart.destroy();
            stockChart = null;
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
    const canvas = document.getElementById('stockChart');
    if (!canvas) {
        console.error('Canvas elementi bulunamadı');
        return;
    }

    // İlk timeframe butonu kontrolü
    const defaultTimeframe = document.querySelector('[data-timeframe="5d"]');
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
