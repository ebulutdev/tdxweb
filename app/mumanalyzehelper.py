from textwrap import dedent
import numpy as np

def interpret_analysis(result):
    yorumlar = []
    direnc = result.get('direnc_y')
    destek = result.get('destek_y')
    dokunulanlar = result.get('most_touched_levels', [])
    clusters = result.get('clusters', [])

    # Zayıf seviye analizi
    zayif_clusters = [c for c in clusters if c['label'] == 'Zayıf']
    for c in zayif_clusters:
        konum = "üst bölgede" if c['y1'] < (direnc + destek) / 2 else "alt bölgede"
        yakindaki_dokunma = sum(
            lvl['count']
            for lvl in dokunulanlar
            if abs(lvl['y'] - c['y1']) < 20 or abs(lvl['y'] - c['y2']) < 20
        )
        if yakindaki_dokunma == 0:
            yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. Bu bölgede hiç dokunma yok, fiyat bu seviyeleri kolayca geçebilir.")
        elif yakindaki_dokunma < 3:
            yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. Sadece {yakindaki_dokunma} kez dokunulmuş, bu seviyeler kırılgan olabilir.")
        else:
            yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. {yakindaki_dokunma} kez dokunulmuş olmasına rağmen direnç oluşturamamış.")

    # Trend yönü analizi
    if clusters and direnc and destek:
        orta_nokta = (direnc + destek) / 2
        ust_guclu = sum(1 for c in clusters if c['label'] == 'Bolge 1' and c['y1'] < orta_nokta)
        alt_guclu = sum(1 for c in clusters if c['label'] == 'Bolge 1' and c['y2'] > orta_nokta)
        ust_yogunluk = sum(c['strength'] for c in clusters if c['y1'] < orta_nokta)
        alt_yogunluk = sum(c['strength'] for c in clusters if c['y2'] > orta_nokta)

        if ust_guclu > alt_guclu and ust_yogunluk > alt_yogunluk * 1.5:
            yorumlar.append("Üst bölgede daha fazla güçlü bölge ve yoğunluk var. Aşağı yönlü baskı güçlü.")
        elif alt_guclu > ust_guclu and alt_yogunluk > ust_yogunluk * 1.5:
            yorumlar.append("Alt bölgede daha fazla güçlü bölge ve yoğunluk var. Yukarı yönlü baskı güçlü.")
        elif ust_guclu == alt_guclu and abs(ust_yogunluk - alt_yogunluk) < max(ust_yogunluk, alt_yogunluk) * 0.3:
            yorumlar.append("Güçlü bölgeler ve yoğunluk dengeli dağılmış. Yatay hareket olasılığı yüksek.")
        else:
            yorumlar.append("Güçlü bölgeler ve yoğunluk dengesiz dağılmış. Trend yönü belirsiz.")

    # En çok dokunulan seviye analizi
    if dokunulanlar and clusters:
        max_touch = max(dokunulanlar, key=lambda x: x['count'])
        closest_cluster = min(clusters, key=lambda c: min(abs(max_touch['y'] - c['y1']), abs(max_touch['y'] - c['y2'])))
        if abs(max_touch['y'] - closest_cluster['y1']) < 20 or abs(max_touch['y'] - closest_cluster['y2']) < 20:
            yorumlar.append(f"{max_touch['y']} seviyesine çok sık temas edilmiş ({max_touch['count']} kez) ve bu seviye güçlü bir bölgeye çok yakın. Burada sert bir fiyat hareketi beklenebilir.")
        else:
            yorumlar.append(f"{max_touch['y']} seviyesine çok sık temas edilmiş ({max_touch['count']} kez). Bu seviye psikolojik eşik olabilir.")

    # Destek/direnç güçlü bölgeye yakın mı
    if direnc and destek and clusters:
        guclu_bolgeler = [c for c in clusters if c['label'] == 'Bolge 1']
        if guclu_bolgeler:
            for c in guclu_bolgeler:
                if abs(c['y1'] - destek) < 30 or abs(c['y2'] - destek) < 30:
                    yorumlar.append(f"Güçlü bölge ({c['y1']}-{c['y2']}) desteğe çok yakın. Buradan yukarı yönlü tepki olasılığı yüksek.")
                elif abs(c['y1'] - direnc) < 30 or abs(c['y2'] - direnc) < 30:
                    yorumlar.append(f"Güçlü bölge ({c['y1']}-{c['y2']}) dirence çok yakın. Buradan aşağı yönlü tepki olasılığı yüksek.")
        else:
            yorumlar.append("Belirgin bir güçlü bölge yok, fiyat daha serbest hareket edebilir.")

    # Sıkışma
    if direnc and destek and abs(direnc - destek) < 50:
        yorumlar.append("Destek ve direnç çok yakın, fiyat sıkışmış. Yakında sert bir kırılım olabilir.")

    # Volatilite
    zayif_sayisi = sum(1 for c in clusters if c['label'] == 'Zayıf')
    if zayif_sayisi > len(clusters) // 2:
        yorumlar.append("Çok sayıda zayıf bölge var, fiyat dalgalı ve yönsüz olabilir.")

    return yorumlar


def calculate_probabilities(result, trend_data=None):
    direnc = result.get('direnc_y')
    destek = result.get('destek_y')
    dokunulanlar = result.get('most_touched_levels', [])
    clusters = result.get('clusters', [])

    probs = []
    total = 0
    belirsizlik = 0

    for lvl in dokunulanlar:
        if abs(lvl['y'] - direnc) < 10:
            probs.append({'type': 'Direnç (Yeşil Çizgi)', 'prob': 20, 'desc': f"Direnç seviyesi {direnc} üzerinde çok sık temas var ({lvl['count']} kez). Psikolojik eşik olabilir."})
            total += 20
        elif abs(lvl['y'] - destek) < 10:
            probs.append({'type': 'Destek (Kırmızı Çizgi)', 'prob': 20, 'desc': f"Destek seviyesi {destek} üzerinde çok sık temas var ({lvl['count']} kez). Aşağı kırılım riski olabilir."})
            total += 20
        elif lvl['count'] >= 5:
            probs.append({'type': 'Mor Çizgi (Psikolojik Eşik)', 'prob': 10, 'desc': f"{lvl['y']} seviyesi psikolojik eşik olabilir. ({lvl['count']} kez dokunulmuş)"})
            total += 10

    for c in clusters:
        if c['label'] in ['Bolge 1', 'Bolge 2', 'Bolge 3', 'Zayıf']:
            if abs(c['y1'] - destek) < 20 or abs(c['y2'] - destek) < 20:
                probs.append({'type': f'{c["label"]} (Destek Yakını)', 'prob': 15, 'desc': f"{c['label']} kutusu destek (kırmızı çizgi) yakınında. Yukarı tepki olasılığı var."})
                total += 15
            if abs(c['y1'] - direnc) < 20 or abs(c['y2'] - direnc) < 20:
                probs.append({'type': f'{c["label"]} (Direnç Yakını)', 'prob': 15, 'desc': f"{c['label']} kutusu direnç (yeşil çizgi) yakınında. Aşağı tepki olasılığı var."})
                total += 15

    if len(clusters) > 1:
        cluster_gaps = [clusters[i+1]['y1'] - clusters[i]['y2'] for i in range(len(clusters)-1)]
        if cluster_gaps:
            avg_gap = sum(cluster_gaps) / len(cluster_gaps)
            if avg_gap < 30:
                probs.append({'type': 'Fiyat Sıkışması (Bölgeler Yakın)', 'prob': 15, 'desc': 'Kümeler arası mesafe dar, fiyat sıkışıyor. Ani kırılım olabilir.'})
                total += 15

    if clusters:
        zayif_oran = sum(1 for c in clusters if c['label'] == 'Zayıf') / len(clusters)
        belirsizlik += zayif_oran * 20
        orta_nokta = (direnc + destek) / 2
        ust_guclu = sum(1 for c in clusters if c['label'] == 'Bolge 1' and c['y1'] < orta_nokta)
        alt_guclu = sum(1 for c in clusters if c['label'] == 'Bolge 1' and c['y2'] > orta_nokta)
        if ust_guclu == alt_guclu:
            belirsizlik += 15
        if belirsizlik > 0:
            belirsizlik_prob = min(30, belirsizlik)
            probs.append({'type': 'Belirsizlik', 'prob': belirsizlik_prob, 'desc': 'Grafikte belirsizlik sinyalleri var, dikkatli olunmalı.'})
            total += belirsizlik_prob

    if total > 0:
        for p in probs:
            p['prob'] = int(p['prob'] * 100 / total)

    return probs


def trend_analysis_comment(trend_data, clusters):
    values = trend_data.get('trend_values', [])
    n = len(values)
    if n < 10:
        return "Yeterli trend verisi yok. Lütfen daha net bir grafik yükleyin."

    # Doğrusal regresyon ile eğim
    x = np.arange(n)
    slope, intercept = np.polyfit(x, values, 1)
    degisim = values[-1] - values[0]
    ortalama = np.mean(values)
    volatilite = (max(values) - min(values)) / ortalama * 100 if ortalama else 0

    if slope < -0.1:
        ana_trend = "Aşağı yönlü güçlü bir trend var."
    elif slope > 0.1:
        ana_trend = "Yukarı yönlü güçlü bir trend var."
    else:
        ana_trend = "Yatay bir fiyat hareketi söz konusu."

    ekstra = (
        "Fiyat çok dar bir aralıkta sıkışmış." if volatilite < 2 else
        "Volatilite çok yüksek." if volatilite > 10 else
        "Volatilite normal seviyede."
    )

    return f"{ana_trend} (Eğim: {slope:.2f}) {ekstra}"
