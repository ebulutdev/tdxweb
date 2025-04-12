async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (message === "") return;

    appendMessage("Siz", message);
    input.value = "";
    appendMessage("TDX Bot", "Analiz yapılıyor...");

    // API URL'sini oluştur
    let apiUrl = "https://tdx-api.onrender.com/chatbot";
    let symbol = message;
    let detayli = false;

    // "detaylı analiz yap THYAO.IS" yazıldıysa, sembolü ayıkla ve detay parametresi ekle
    if (message.toLowerCase().startsWith("detaylı analiz yap")) {
        const parts = message.split(" ");
        symbol = parts[parts.length - 1];
        detayli = true;
    }

    // URL'yi parametrelere göre oluştur
    apiUrl += `?symbol=${symbol}`;
    if (detayli) {
        apiUrl += `&detay=true`;
    }

    try {
        const response = await fetch(apiUrl, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        });

        if (!response.ok) {
            const errorDetails = await response.text();
            console.error("API Hatası:", errorDetails);
            updateLastBotMessage("API isteğinde hata oluştu. Lütfen sunucuyu kontrol edin.");
            return;
        }

        const data = await response.json();
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
