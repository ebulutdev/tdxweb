async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (message === "") return;

    appendMessage("Siz", message);
    input.value = "";
    appendMessage("TDX Bot", "Analiz yapılıyor...");

    try {
        // FastAPI tabanlı hisse analiz botuna istek gönder
        const response = await fetch(`http://127.0.0.1:8000/predict/${message}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        });

        if (!response.ok) {
            const errorDetails = await response.text();
            console.error("API Hatası:", errorDetails);
            updateLastBotMessage("API isteğinde hata oluştu. Lütfen sunucunuzu kontrol edin.");
            return;
        }

        const data = await response.json();
        const aiMessage = formatBotResponse(data);
        updateLastBotMessage(aiMessage);
    } catch (error) {
        console.error("İstek gönderilirken hata oluştu:", error);
        updateLastBotMessage("Bir hata oluştu. Lütfen sunucuya bağlanıp bağlanmadığınızı kontrol edin.");
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

function formatBotResponse(data) {
    return `
    📊 <strong>${data.symbol}</strong> Analizi:
    
    💰 Mevcut Fiyat: ${data.mevcut_fiyat}
    📈 MA5: ${data.ma_5}
    📉 MA10: ${data.ma_10}
    🎯 RSI: ${data.rsi}
    
    ⬇️ Destek: ${data.destek}
    ⬆️ Direnç: ${data.direnc}
    
    ⚠️ Risk Oranı: ${data.risk_orani}
    💫 Kar Oranı: ${data.kar_orani}
    
    🔮 Tahmin: ${data.tahmin}
    
    💡 Yorum: ${data.yorum}
    `;
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

// Smooth Scroll fonksiyonu
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

// Navigasyon bağlantıları için smooth scroll
document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = link.getAttribute('href');
            if (target !== '#') {
                smoothScroll(target, 1000);
            }
            // Mobil menüyü kapat
            const navLinks = document.getElementById('navLinks');
            navLinks.classList.remove('active');
        });
    });

    // Sayfa yüklendiğinde chatbot'u gizle
    const panel = document.getElementById("chatbot-panel");
    panel.style.display = "none";
});
