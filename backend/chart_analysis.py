import cv2
import numpy as np
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Tuple, Dict
import io, base64

@dataclass
class PriceLevel:
    price: float
    strength: float
    type: str
    description: str

@dataclass
class CandlePattern:
    position: int
    type: str
    strength: float

class TechnicalAnalyzer:
    def __init__(self, img):
        self.img = img
        self.height, self.width = img.shape[:2]
        self.gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self.price_levels = []
        self.patterns = []
        self.swing_points = {}
        self.fib_levels = {}
        
    def detect_swing_points(self):
        """Tepe ve dip noktalarını tespit eder"""
        # Dikey projeksiyon histogramı
        projection = np.mean(self.gray, axis=1)
        smoothed = gaussian_filter1d(projection, sigma=3)
        
        # Tepe ve dip noktalarını bul
        peaks, _ = find_peaks(smoothed, distance=30, prominence=10)
        valleys, _ = find_peaks(-smoothed, distance=30, prominence=10)
        
        # En önemli swing noktalarını seç
        peak_values = [(p, smoothed[p]) for p in peaks]
        valley_values = [(v, smoothed[v]) for v in valleys]
        
        # En önemli tepe ve dipleri sırala
        peak_values.sort(key=lambda x: x[1], reverse=True)
        valley_values.sort(key=lambda x: x[1])
        
        self.swing_points = {
            "highs": peak_values[:3],  # En önemli 3 tepe
            "lows": valley_values[:3]   # En önemli 3 dip
        }
        
    def calculate_fibonacci_levels(self):
        """Fibonacci seviyelerini hesaplar"""
        if not self.swing_points:
            self.detect_swing_points()
            
        if self.swing_points["highs"] and self.swing_points["lows"]:
            high = self.height - min(p[0] for p in self.swing_points["highs"])
            low = self.height - max(p[0] for p in self.swing_points["lows"])
            
            range_price = high - low
            self.fib_levels = {
                "0": low,
                "0.236": low + range_price * 0.236,
                "0.382": low + range_price * 0.382,
                "0.5": low + range_price * 0.5,
                "0.618": low + range_price * 0.618,
                "0.786": low + range_price * 0.786,
                "1": high
            }
            
    def detect_support_resistance(self):
        """Destek ve direnç seviyelerini tespit eder"""
        # Yoğunluk haritası oluştur
        density_map = np.zeros(self.height)
        for i in range(self.width):
            black_pixels = np.where(self.gray[:, i] < 128)[0]
            density_map[black_pixels] += 1
            
        # Yoğunluk haritasını smoothle
        smoothed = gaussian_filter1d(density_map, sigma=5)
        
        # Önemli seviyeleri bul
        peaks, properties = find_peaks(smoothed, distance=30, prominence=5)
        
        # Seviyeleri güçlerine göre sırala
        levels = [(p, properties["prominences"][i]) for i, p in enumerate(peaks)]
        levels.sort(key=lambda x: x[1], reverse=True)
        
        # Destek ve direnç seviyelerini ayır
        for level, strength in levels[:6]:  # En güçlü 6 seviye
            price = self.height - level
            if strength > np.mean([l[1] for l in levels]):
                level_type = "Güçlü"
            else:
                level_type = "Zayıf"
                
            self.price_levels.append(PriceLevel(
                price=price,
                strength=strength,
                type="Destek" if level > self.height/2 else "Direnç",
                description=f"{level_type} {'Destek' if level > self.height/2 else 'Direnç'}"
            ))
            
    def analyze_current_position(self):
        """Mevcut fiyat pozisyonunu analiz eder"""
        # Son mumların pozisyonunu bul
        last_section = self.gray[:, -20:]
        current_position = self.height - np.mean(np.where(last_section < 128)[0])
        
        analysis = {
            "position": current_position,
            "warnings": [],
            "suggestions": [],
            "risk_level": "ORTA"
        }
        
        # Destek/Direnç yakınlığı kontrolü
        for level in self.price_levels:
            distance = abs(current_position - level.price)
            if distance < 20:
                if level.type == "Destek":
                    analysis["warnings"].append(f"⚠️ Fiyat güçlü destek bölgesinde ({level.price:.0f})")
                    analysis["suggestions"].append("💡 Destek bölgesinden alım fırsatı")
                else:
                    analysis["warnings"].append(f"⚠️ Fiyat güçlü direnç bölgesinde ({level.price:.0f})")
                    analysis["suggestions"].append("💡 Direnç bölgesinden satış fırsatı")
                    
        # Fibonacci yakınlığı kontrolü
        for level, price in self.fib_levels.items():
            if abs(current_position - price) < 20:
                analysis["warnings"].append(f"⚠️ Fiyat %{float(level)*100:.1f} Fibonacci seviyesinde")
                
        # Risk seviyesi belirleme
        nearest_support = min((abs(current_position - l.price) 
                             for l in self.price_levels if l.type == "Destek"), default=float('inf'))
        nearest_resistance = min((abs(current_position - l.price) 
                                for l in self.price_levels if l.type == "Direnç"), default=float('inf'))
                                
        if nearest_support < 20:
            analysis["risk_level"] = "DÜŞÜK"
        elif nearest_resistance < 20:
            analysis["risk_level"] = "YÜKSEK"
            
        return analysis
        
    def generate_report(self) -> str:
        """Analiz raporunu oluşturur"""
        self.detect_swing_points()
        self.calculate_fibonacci_levels()
        self.detect_support_resistance()
        current_analysis = self.analyze_current_position()
        
        report = []
        # Temel Bilgiler
        report.append("🎯 TEMEL ANALİZ RAPORU")
        report.append(f"Risk Seviyesi: {current_analysis['risk_level']}")
        report.append(f"Mevcut Pozisyon: {current_analysis['position']:.0f}")
        # Destek/Direnç Seviyeleri
        report.append("\n💪 DESTEK SEVİYELERİ:")
        for level in [l for l in self.price_levels if l.type == "Destek"]:
            report.append(f"   • {level.description}: {level.price:.0f} (Güç: {level.strength:.1f})")
        report.append("\n🛑 DİRENÇ SEVİYELERİ:")
        for level in [l for l in self.price_levels if l.type == "Direnç"]:
            report.append(f"   • {level.description}: {level.price:.0f} (Güç: {level.strength:.1f})")
        # Fibonacci Seviyeleri
        report.append("\n📐 FİBONACCİ SEVİYELERİ:")
        for level, price in self.fib_levels.items():
            report.append(f"   • %{float(level)*100:.1f}: {price:.0f}")
        # Uyarılar ve Öneriler
        if current_analysis["warnings"]:
            report.append("\n⚠️ UYARILAR:")
            for warning in current_analysis["warnings"]:
                report.append(f"   {warning}")
        if current_analysis["suggestions"]:
            report.append("\n💡 ÖNERİLER:")
            for suggestion in current_analysis["suggestions"]:
                report.append(f"   {suggestion}")
        # Genel Strateji
        report.append("\n📈 GENEL STRATEJİ:")
        if current_analysis["risk_level"] == "DÜŞÜK":
            report.append("   💡 Alım için uygun bölge, stop-loss ile pozisyon açılabilir")
        elif current_analysis["risk_level"] == "YÜKSEK":
            report.append("   💡 Riskli bölge, kar realizasyonu düşünülebilir")
        else:
            report.append("   💡 Trend yönünde pozisyon alınabilir")
        return "\n".join(report)
        
    def visualize(self):
        """Analizi görselleştirir"""
        fig, ax = plt.subplots(figsize=(15, 8))
        ax.imshow(cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB))
        
        # Destek/Direnç çizgileri ve değerleri
        for level in self.price_levels:
            # Çizgi rengi ve stili
            color = 'g' if level.type == "Destek" else 'r'
            alpha = min(level.strength / max(l.strength for l in self.price_levels), 0.8)
            
            # Yatay çizgi
            ax.axhline(y=self.height-level.price, color=color, alpha=alpha, linestyle='--')
            
            # Değer etiketi
            label = f"{level.type}: {level.price:.0f} (Güç: {level.strength:.1f})"
            ax.text(10, self.height-level.price, label, 
                   color=color, fontsize=8, 
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor=color))
            
        # Fibonacci seviyeleri
        for level, price in self.fib_levels.items():
            ax.axhline(y=self.height-price, color='blue', alpha=0.3, linestyle=':')
            ax.text(10, self.height-price, f"Fib {level}", 
                   color='blue', fontsize=8,
                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='blue'))
            
        # Swing noktaları
        for high, _ in self.swing_points["highs"]:
            ax.plot(self.width-1, high, 'r^', markersize=10)
        for low, _ in self.swing_points["lows"]:
            ax.plot(self.width-1, low, 'gv', markersize=10)
            
        # Grafik başlığı ve stil
        ax.set_title("Teknik Analiz Görselleştirmesi", pad=20)
        plt.tight_layout()
        
        # Görüntüyü base64'e çevir
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        encoded_img = base64.b64encode(buf.getvalue()).decode('utf-8')
        buf.close()
        plt.close()
        
        return encoded_img

def analyze_chart(img):
    """Gelişmiş teknik analiz ve yatırım tavsiyeleri"""
    analyzer = TechnicalAnalyzer(img)
    base_report = analyzer.generate_report()
    visualization = analyzer.visualize()
    
    class MarketAnalysis:
        def __init__(self):
            self.warnings = []
            self.opportunities = []
            self.risk_factors = []
            self.trend_analysis = []
            self.volume_signals = []
            self.pattern_signals = []
            
    analysis = MarketAnalysis()
    current_position = analyzer.analyze_current_position()
    
    def analyze_price_action():
        """Fiyat hareketlerini analiz eder"""
        position = current_position["position"]
        
        # Trend analizi
        if len(analyzer.swing_points["highs"]) >= 2 and len(analyzer.swing_points["lows"]) >= 2:
            last_high = analyzer.swing_points["highs"][0][0]
            prev_high = analyzer.swing_points["highs"][1][0]
            last_low = analyzer.swing_points["lows"][0][0]
            prev_low = analyzer.swing_points["lows"][1][0]
            
            if last_high > prev_high and last_low > prev_low:
                analysis.trend_analysis.append("📈 Yükselen trend devam ediyor")
            elif last_high < prev_high and last_low < prev_low:
                analysis.trend_analysis.append("📉 Düşen trend devam ediyor")
            else:
                analysis.trend_analysis.append("↔️ Yatay trend gözlemleniyor")
    
    def analyze_support_resistance():
        """Destek ve direnç analizini yapar"""
        position = current_position["position"]
        
        # Destek/Direnç kırılmaları
        for level in analyzer.price_levels:
            distance = abs(position - level.price)
            
            if distance < 5:  # Çok yakın
                if level.type == "Destek":
                    analysis.warnings.append(f"⚠️ KRITIK: Fiyat güçlü destek seviyesinde ({level.price:.0f})")
                    analysis.risk_factors.append("Destek kırılma riski yüksek")
                else:
                    analysis.warnings.append(f"⚠️ KRITIK: Fiyat güçlü direnç seviyesinde ({level.price:.0f})")
                    analysis.risk_factors.append("Direnç kırılma riski yüksek")
            
            elif distance < 20:  # Yakın
                if level.type == "Destek":
                    analysis.opportunities.append(f"💫 Potansiyel alım bölgesi: {level.price:.0f}")
                else:
                    analysis.opportunities.append(f"💫 Potansiyel satış bölgesi: {level.price:.0f}")
    
    def analyze_fibonacci_confluence():
        """Fibonacci uyumluluğunu analiz eder"""
        position = current_position["position"]
        
        fib_confluences = []
        for level, price in analyzer.fib_levels.items():
            # Fibonacci seviyelerinin destek/dirençlerle kesişimi
            for support_resistance in analyzer.price_levels:
                if abs(price - support_resistance.price) < 15:
                    fib_confluences.append({
                        "fib_level": level,
                        "price": price,
                        "type": support_resistance.type,
                        "strength": support_resistance.strength
                    })
        
        # Güçlü kesişim noktaları
        for conf in fib_confluences:
            if abs(position - conf["price"]) < 30:
                analysis.opportunities.append(
                    f"🎯 Güçlü {conf['type']} + Fibonacci %{float(conf['fib_level'])*100:.1f} kesişimi: {conf['price']:.0f}"
                )
    
    def analyze_volatility():
        """Volatilite analizi yapar"""
        # Son mumların yüksekliğini kontrol et
        last_candles = analyzer.gray[:, -20:]
        volatility = np.std([np.max(col) - np.min(col) for col in last_candles.T])
        
        if volatility > 20:
            analysis.warnings.append("⚠️ Yüksek volatilite tespit edildi - Risk yönetimi önemli!")
        elif volatility < 5:
            analysis.warnings.append("ℹ️ Düşük volatilite - Breakout fırsatları gözlemlenebilir")
    
    def generate_range_trading_scenarios():
        scenarios = []
        position = current_position["position"]

        # Destekleri ve dirençleri sırala
        supports = sorted([level for level in analyzer.price_levels if level.type == 'Destek'], key=lambda l: l.price)
        resistances = sorted([level for level in analyzer.price_levels if level.type == 'Direnç'], key=lambda l: l.price)

        # En yakın iki destek bul
        lower_supports = [s for s in supports if s.price < position]
        upper_supports = [s for s in supports if s.price > position]
        if lower_supports and upper_supports:
            s1 = lower_supports[-1]
            s2 = upper_supports[0]
            scenarios.append(
                f"🟢 Destek Arası Al-Sat: {s1.price:.0f} - {s2.price:.0f}\n"
                f"   • {s1.price:.0f} seviyesinden alım, {s2.price:.0f} seviyesinden satış.\n"
                f"   • Stop-loss: {s1.price-((s2.price-s1.price)*0.2):.0f}\n"
                f"   • Risk/Ödül oranı: {(s2.price-s1.price)/((s1.price-((s2.price-s1.price)*0.2))-s1.price):.2f}"
            )

        # En yakın iki direnç bul
        lower_resistances = [r for r in resistances if r.price < position]
        upper_resistances = [r for r in resistances if r.price > position]
        if lower_resistances and upper_resistances:
            r1 = lower_resistances[-1]
            r2 = upper_resistances[0]
            scenarios.append(
                f"🔴 Direnç Arası Al-Sat: {r1.price:.0f} - {r2.price:.0f}\n"
                f"   • {r2.price:.0f} seviyesinden satış, {r1.price:.0f} seviyesinden alım.\n"
                f"   • Stop-loss: {r2.price+((r2.price-r1.price)*0.2):.0f}\n"
                f"   • Risk/Ödül oranı: {(r2.price-r1.price)/((r2.price+((r2.price-r1.price)*0.2))-r2.price):.2f}"
            )

        return "\n\n".join(scenarios)
    
    def generate_enhanced_report():
        """Gelişmiş rapor oluşturur"""
        report_sections = [
            base_report,
            "\n🔄 TREND ANALİZİ:",
            "\n".join(f"   • {item}" for item in analysis.trend_analysis),
            
            "\n⚠️ RİSK FAKTÖRLERİ:" if analysis.risk_factors else "",
            "\n".join(f"   • {item}" for item in analysis.risk_factors),
            
            "\n🎯 FIRSATLAR:" if analysis.opportunities else "",
            "\n".join(f"   • {item}" for item in analysis.opportunities),
            
            "\n⚠️ UYARILAR:" if analysis.warnings else "",
            "\n".join(f"   • {item}" for item in analysis.warnings),
            
            "\n📊 YATIRIM TAVSİYELERİ:",
            generate_investment_advice()
        ]
        
        return "\n".join(filter(None, report_sections))
    
    def generate_investment_advice():
        """Yatırım tavsiyelerini oluşturur"""
        advice = []
        risk_level = current_position["risk_level"]
        position = current_position["position"]

        # En yakın güçlü destek ve dirençleri bul
        supports = [level for level in analyzer.price_levels if level.type == 'Destek']
        supports.sort(key=lambda l: abs(position - l.price))
        stop_loss = None
        for s in supports:
            if s.price < position:
                stop_loss = s.price
                break

        # Stop-loss çok uzaksa, alternatif öneri
        if stop_loss and abs(position - stop_loss) > position * 0.07:  # %7'den fazla uzaksa
            advice.append("   ⚠️ Stop-loss seviyesi mevcut fiyata uzak. Maksimum %5 kayıp ile manuel stop-loss belirleyin.")
            stop_loss = position * 0.95

        if risk_level == "DÜŞÜK":
            advice.append("   💚 Düşük riskli bölge - Kademeli alım düşünülebilir.")
            if stop_loss:
                advice.append(f"   📌 Stop-loss seviyesi: {stop_loss:.0f}")
            advice.append("   🎯 Hedef fiyat: En yakın güçlü direnç seviyesi veya %5-10 yukarısı.")
            advice.append("   📏 Pozisyon büyüklüğünü portföyünüzün %5-10'u ile sınırlayın.")
            advice.append("   ⚖️ Risk/Ödül oranı en az 2:1 olacak şekilde plan yapın.")
        elif risk_level == "YÜKSEK":
            advice.append("   ❌ Yüksek riskli bölge - Pozisyon almaktan kaçının.")
            advice.append("   💭 Düzeltme beklenmeli.")
        else:
            advice.append("   ⚖️ Orta riskli bölge - Kısmi pozisyon düşünülebilir.")
            if stop_loss:
                advice.append(f"   📌 Stop-loss seviyesi: {stop_loss:.0f}")
        # Hacim bazlı öneriler
        if analysis.volume_signals:
            advice.append("   📊 " + " | ".join(analysis.volume_signals))
        return "\n".join(advice)
    
    # Analizleri çalıştır
    analyze_price_action()
    analyze_support_resistance()
    analyze_fibonacci_confluence()
    analyze_volatility()
    
    # Gelişmiş raporu oluştur
    enhanced_report = generate_enhanced_report()
    range_scenarios = generate_range_trading_scenarios()
    
    if range_scenarios:
        enhanced_report += "\n\n🔄 ARALIKTA AL-SAT SENARYOLARI:\n" + range_scenarios
    
    return enhanced_report, visualization
