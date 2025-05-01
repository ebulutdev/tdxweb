def interpret_analysis(result):
    """
    image_processor.py çıktısını alır ve insan-diliyle senaryo/yorum üretir.
    result: {
        'direnc_y': int,
        'destek_y': int,
        'most_touched_levels': [{'y': int, 'count': int}, ...],
        'clusters': [{'y1': int, 'y2': int, 'strength': int, 'label': str}, ...]
    }
    """
    yorumlar = []
    direnc = result.get('direnc_y')
    destek = result.get('destek_y')
    dokunulanlar = result.get('most_touched_levels', [])
    clusters = result.get('clusters', [])

    # Zayıf seviye analizi
    zayif_clusters = [c for c in clusters if c['label'] == 'Zayıf']
    if zayif_clusters:
        for c in zayif_clusters:
            # Zayıf seviyenin konumuna göre yorum
            if c['y1'] < (direnc + destek) / 2:
                konum = "üst bölgede"
            else:
                konum = "alt bölgede"
            
            # Zayıf seviyenin yakınındaki dokunma sayısı
            yakindaki_dokunma = 0
            for lvl in dokunulanlar:
                if abs(lvl['y'] - c['y1']) < 20 or abs(lvl['y'] - c['y2']) < 20:
                    yakindaki_dokunma += lvl['count']
            
            if yakindaki_dokunma == 0:
                yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. Bu bölgede hiç dokunma yok, fiyat bu seviyeleri kolayca geçebilir.")
            elif yakindaki_dokunma < 3:
                yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. Sadece {yakindaki_dokunma} kez dokunulmuş, bu seviyeler kırılgan olabilir.")
            else:
                yorumlar.append(f"{c['y1']}-{c['y2']} arası {konum} zayıf bölge var. {yakindaki_dokunma} kez dokunulmuş olmasına rağmen direnç oluşturamamış.")

    # Trend yönü analizi - daha detaylı karşılaştırma
    if clusters and direnc and destek:
        orta_nokta = (direnc + destek) / 2
        
        # Üst ve alt bölgelerdeki güçlü bölgeleri say
        ust_guclu = sum(1 for c in clusters if c['label'] == 'Güçlü Bölge' and c['y1'] < orta_nokta)
        alt_guclu = sum(1 for c in clusters if c['label'] == 'Güçlü Bölge' and c['y2'] > orta_nokta)
        
        # Üst ve alt bölgelerdeki toplam yoğunluk
        ust_yogunluk = sum(c['strength'] for c in clusters if c['y1'] < orta_nokta)
        alt_yogunluk = sum(c['strength'] for c in clusters if c['y2'] > orta_nokta)
        
        # Trend yönü belirleme
        if ust_guclu > alt_guclu and ust_yogunluk > alt_yogunluk * 1.5:
            yorumlar.append("Üst bölgede daha fazla güçlü bölge ve yoğunluk var. Aşağı yönlü baskı güçlü.")
        elif alt_guclu > ust_guclu and alt_yogunluk > ust_yogunluk * 1.5:
            yorumlar.append("Alt bölgede daha fazla güçlü bölge ve yoğunluk var. Yukarı yönlü baskı güçlü.")
        elif ust_guclu == alt_guclu and abs(ust_yogunluk - alt_yogunluk) < max(ust_yogunluk, alt_yogunluk) * 0.3:
            yorumlar.append("Güçlü bölgeler ve yoğunluk dengeli dağılmış. Yatay hareket olasılığı yüksek.")
        else:
            yorumlar.append("Güçlü bölgeler ve yoğunluk dengesiz dağılmış. Trend yönü belirsiz.")

    # En çok dokunulan seviye ve güçlü bölgeye yakınlığı
    if dokunulanlar and clusters:
        max_touch = max(dokunulanlar, key=lambda x: x['count'])
        closest_cluster = min(clusters, key=lambda c: min(abs(max_touch['y']-c['y1']), abs(max_touch['y']-c['y2'])))
        if abs(max_touch['y'] - closest_cluster['y1']) < 20 or abs(max_touch['y'] - closest_cluster['y2']) < 20:
            yorumlar.append(f"{max_touch['y']} seviyesine çok sık temas edilmiş ({max_touch['count']} kez) ve bu seviye güçlü bir bölgeye çok yakın. Burada sert bir fiyat hareketi beklenebilir.")
        else:
            yorumlar.append(f"{max_touch['y']} seviyesine çok sık temas edilmiş ({max_touch['count']} kez). Bu seviye psikolojik eşik olabilir.")

    # Destek/direnç ve güçlü bölge yakınlığı
    if direnc and destek and clusters:
        guclu_bolgeler = [c for c in clusters if c['label'] == 'Güçlü Bölge']
        if guclu_bolgeler:
            for c in guclu_bolgeler:
                if abs(c['y1'] - destek) < 30 or abs(c['y2'] - destek) < 30:
                    yorumlar.append(f"Güçlü bölge ({c['y1']}-{c['y2']}) desteğe çok yakın. Buradan yukarı yönlü tepki olasılığı yüksek.")
                elif abs(c['y1'] - direnc) < 30 or abs(c['y2'] - direnc) < 30:
                    yorumlar.append(f"Güçlü bölge ({c['y1']}-{c['y2']}) dirence çok yakın. Buradan aşağı yönlü tepki olasılığı yüksek.")
        else:
            yorumlar.append("Belirgin bir güçlü bölge yok, fiyat daha serbest hareket edebilir.")

    # Sıkışma ve kırılım senaryosu
    if direnc and destek and abs(direnc - destek) < 50:
        yorumlar.append("Destek ve direnç çok yakın, fiyat sıkışmış durumda. Yakında sert bir kırılım olabilir.")

    # Volatilite yorumu
    if clusters:
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
    belirsizlik = 0  # Belirsizlik skoru

    # --- Renkli Çizgi ve Bölge Senaryoları ---
    for lvl in dokunulanlar:
        if abs(lvl['y'] - direnc) < 10:
            probs.append({
                'type': 'Direnç (Yeşil Çizgi)',
                'prob': 20,
                'desc': f"Yeşil çizgiyle (direnç) gösterilen {direnc} seviyesine çok sık dokunulmuş ({lvl['count']} kez). Psikolojik eşik ve yukarı kırılım riski artıyor."
            })
            total += 20
        elif abs(lvl['y'] - destek) < 10:
            probs.append({
                'type': 'Destek (Kırmızı Çizgi)',
                'prob': 20,
                'desc': f"Kırmızı çizgiyle (destek) gösterilen {destek} seviyesine çok sık dokunulmuş ({lvl['count']} kez). Psikolojik eşik ve aşağı kırılım riski artıyor."
            })
            total += 20
        elif lvl['count'] >= 5:
            renk = 'Mor' if lvl['y'] > (direnc + destek) / 2 else 'Mor'
            probs.append({
                'type': f'{renk} Çizgi (En Çok Dokunulan Seviye)',
                'prob': 10,
                'desc': f"{renk} çizgiyle gösterilen {lvl['y']} seviyesi psikolojik eşik olabilir. ({lvl['count']} kez dokunulmuş)"
            })
            total += 10

    # Bölge kutuları (Bolge 1, Bolge 2, Bolge 3, Zayıf) destek/direnç yakınında mı?
    for c in clusters:
        if c['label'] in ['Bolge 1', 'Bolge 2', 'Bolge 3', 'Zayıf']:
            if abs(c['y1'] - destek) < 20 or abs(c['y2'] - destek) < 20:
                probs.append({
                    'type': f'{c["label"]} (Destek Yakını)',
                    'prob': 15,
                    'desc': f"{c['label']} kutusu destek (kırmızı çizgi) yakınında. Buradan yukarı tepki olasılığı yüksek."
                })
                total += 15
            if abs(c['y1'] - direnc) < 20 or abs(c['y2'] - direnc) < 20:
                probs.append({
                    'type': f'{c["label"]} (Direnç Yakını)',
                    'prob': 15,
                    'desc': f"{c['label']} kutusu direnç (yeşil çizgi) yakınında. Buradan aşağı tepki olasılığı yüksek."
                })
                total += 15

    # Sıkışma ve ani kırılım (küme aralığına göre)
    if len(clusters) > 1:
        cluster_gaps = [clusters[i+1]['y1'] - clusters[i]['y2'] for i in range(len(clusters)-1)]
        avg_gap = sum(cluster_gaps) / len(cluster_gaps)
        if avg_gap < 30:
            probs.append({'type': 'Fiyat Sıkışması (Bölgeler Yakın)', 'prob': 15, 'desc': 'Kümeler arası mesafe çok dar (bölgeler yakın), fiyat sıkışıyor. Yakında ani kırılım olabilir.'})
            total += 15

    # Belirsizlik analizi (orijinalden)
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

    # Normalize et (toplam 100 olacak şekilde)
    if total > 0:
        for p in probs:
            p['prob'] = int(p['prob'] * 100 / total)

    # Eğer sadece belirsizlik varsa, açıklamayı detaylandır
    if len(probs) == 1 and probs[0]['type'] == 'Belirsizlik':
        probs[0]['desc'] = (
            "Grafikte anlamlı güçlü/zayıf bölge, destek/direnç veya dokunulan seviye tespit edilemedi. "
            "Bu nedenle yalnızca belirsizlik senaryosu sunulmuştur. "
            "Bu durum genellikle veri yetersizliği, aşırı gürültü veya net bir trend olmamasından kaynaklanır. "
            "Farklı bir grafik yükleyin veya görselin kalitesini artırın."
        )
    return probs
