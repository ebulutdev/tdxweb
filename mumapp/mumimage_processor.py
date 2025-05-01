import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import scipy.ndimage

def improved_mum_graph_analysis(image_bytes):
    # Görseli byte dizisinden OpenCV formatına çevir
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # Grafik bölgesini kırp (üst, alt, sol, sağ boşlukları çıkar)
    crop_top = int(h * 0.18)
    crop_bottom = int(h * 0.92)
    crop_left = int(w * 0.08)
    crop_right = int(w * 0.97)
    cropped_img = img[crop_top:crop_bottom, crop_left:crop_right]

    # Mumları tespit etmek için renk maskeleri oluştur (kırmızı ve yeşil mumlar)
    hsv = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
    green = cv2.inRange(hsv, (36, 50, 50), (89, 255, 255))
    mask = red1 | red2 | green

    # Maskeleme sonucunda mum piksel koordinatlarını al
    coords = np.column_stack(np.where(mask > 0))
    if coords.shape[0] == 0:
        return "Mum çubukları tespit edilemedi."

    # En yüksek ve en düşük mum pikselini bul (y koordinatına göre)
    top = tuple(coords[coords[:, 0].argmin()][::-1])
    bottom = tuple(coords[coords[:, 0].argmax()][::-1])
    top_global = (top[0] + crop_left, top[1] + crop_top)
    bottom_global = (bottom[0] + crop_left, bottom[1] + crop_top)

    # En yüksek ve en düşük seviyeye yatay çizgi çiz
    cv2.line(img, (0, top_global[1]), (w, top_global[1]), (0, 255, 0), 2)  # yeşil = direnç
    cv2.putText(img, 'Direnç', (10, top_global[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.line(img, (0, bottom_global[1]), (w, bottom_global[1]), (0, 0, 255), 2)  # kırmızı = destek
    cv2.putText(img, 'Destek', (10, bottom_global[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # Sık dokunulan seviye analizleri için dokunma sayısı haritası oluştur
    touch_counts = {}
    y_tolerance = 3  # yakın seviyeler gruplanır
    for y in coords[:, 0]:
        found = False
        for key in list(touch_counts.keys()):
            if abs(y - key) <= y_tolerance:
                touch_counts[key] += 1
                found = True
                break
        if not found:
            touch_counts[y] = 1

    # En çok temas edilen ilk 4 yatay seviye → SeviyeX sayısı olarak yazılır
    most_touched = sorted(touch_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    most_touched_levels = []
    for y_local, count in most_touched:
        y_global = int(y_local + crop_top)
        color = (255, 0, 255) if y_global > h // 2 else (255, 165, 0)
        cv2.line(img, (0, y_global), (w, y_global), color, 1)
        cv2.putText(img, f'Seviyex{count}', (w - 160, y_global - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        most_touched_levels.append({
            'y': int(y_global),
            'count': int(count)
        })

    # Yoğunluk analizi için dikey (y ekseni) yoğunluk haritası oluştur
    density_map = np.zeros((cropped_img.shape[0],), dtype=int)
    for y in coords[:, 0]:
        density_map[y] += 1

    # Sadece üst %25 yoğunlukta olan seviyeleri kümeye al
    threshold = np.percentile(density_map, 75)
    clusters = []
    in_cluster = False
    cluster_start = 0
    for y in range(len(density_map)):
        if density_map[y] >= threshold and not in_cluster:
            in_cluster = True
            cluster_start = y
        elif density_map[y] < threshold and in_cluster:
            in_cluster = False
            cluster_end = y
            density_sum = np.sum(density_map[cluster_start:cluster_end])  # kümelenmiş bölgedeki mum yoğunluğu
            clusters.append((cluster_start, cluster_end, density_sum))  # (başlangıç_y, bitiş_y, toplam yoğunluk)

    # Kümeler içinde en yoğunu referans alarak göreceli yoğunluk renklerini ayarla
    cluster_results = []
    if clusters:
        max_density = max([c[2] for c in clusters])

    for i, (start, end, strength) in enumerate(clusters):
        y1 = start + crop_top
        y2 = end + crop_top
        norm_strength = strength / max_density if clusters else 0

        # Göreceli yoğunluğa göre renk ve etiket seçimi
        if norm_strength > 0.75:
            label = "Bolge 1"
        elif norm_strength > 0.5:
            label = "Bolge 2"
        elif norm_strength > 0.3:
            label = "Bolge 3"
        else:
            label = "Zayıf"

        # Kümeyi grafik üzerinde kutu olarak çiz ve üzerine etiket yaz
        cv2.rectangle(img, (crop_left, y1), (crop_right, y2), (0, 255, 255), 2)
        cv2.putText(img, f"{label} ({strength})", (crop_left + 5, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cluster_results.append({
            'y1': int(y1),
            'y2': int(y2),
            'strength': int(strength),
            'label': label
        })

    # Sonuç görüntüyü PIL Image olarak PNG byte'ına çevir ve döndür
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    # X ekseni: Gerçek mum sayısı
    num_mum = len(coords)
    trend_labels = [str(i+1) for i in range(num_mum)]

    # Y ekseni: crop_top + y_raw (fiyat gibi) -> TERSLE!
    y_raw = coords[:, 0]
    y_fiyat = h - (crop_top + y_raw)

    # Outlier temizliği
    low, high = np.percentile(y_fiyat, [2, 98])
    y_filtered = np.clip(y_fiyat, low, high)

    # Hareketli ortalama
    window = 10
    y_smooth = scipy.ndimage.uniform_filter1d(y_filtered, size=window, mode='nearest')

    # Çizgi seviyelerini al
    direnc_y = int(top_global[1])
    destek_y = int(bottom_global[1])
    mor_y = [lvl['y'] for lvl in most_touched_levels]
    sari_y = []
    for c in cluster_results:
        sari_y.append(c['y1'])
        sari_y.append(c['y2'])

    # Her pencere için ortalama y (veya y_smooth)
    window = 30
    y_values = coords[:, 0]
    pencere_ort = []
    for i in range(0, len(y_values), max(1, len(y_values)//window)):
        window_y = y_values[i:i+max(1, len(y_values)//window)]
        if len(window_y) > 0:
            pencere_ort.append(np.mean(window_y) + crop_top)

    # Her pencere için uzaklıkları hesapla
    uzaklik_direnc = [abs(y - direnc_y) for y in pencere_ort]
    uzaklik_destek = [abs(y - destek_y) for y in pencere_ort]
    uzaklik_mor = [min([abs(y - m) for m in mor_y]) if mor_y else 0 for y in pencere_ort]
    uzaklik_sari = [min([abs(y - s) for s in sari_y]) if sari_y else 0 for y in pencere_ort]

    trend_data = {
        "labels": [str(i) for i in range(len(pencere_ort))],
        "uzaklik_direnc": uzaklik_direnc,
        "uzaklik_destek": uzaklik_destek,
        "uzaklik_mor": uzaklik_mor,
        "uzaklik_sari": uzaklik_sari
    }

    return {
        'image_bytes': image_bytes,
        'direnc_y': int(top_global[1]),
        'destek_y': int(bottom_global[1]),
        'most_touched_levels': most_touched_levels,
        'clusters': cluster_results,
        'trend_data': trend_data
    }
