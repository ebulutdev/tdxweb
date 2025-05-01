from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.image_processor import improved_mum_graph_analysis
from app.analyze import interpret_analysis, calculate_probabilities
from app.analyzehelper import trend_analysis_comment
import base64
from io import BytesIO

# FastAPI uygulamasını başlat
app = FastAPI()

# HTML şablonlarını templates/ klasöründen al
templates = Jinja2Templates(directory="templates")

# Ana sayfa - form ekranı
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def form_view(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Görseli yükle ve analiz et
@app.post("/upload", response_class=HTMLResponse)
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        # Görseli oku
        contents = await file.read()

        # Analiz fonksiyonunu çalıştır (dict döndürmesini bekliyoruz)
        result = improved_mum_graph_analysis(contents)

        # Hatalı string mesaj dönerse
        if isinstance(result, str):
            return templates.TemplateResponse("index.html", {
                "request": request,
                "error": result
            })

        # Orijinal ve analizli görselleri base64'e çevir
        base64_result = base64.b64encode(result['image_bytes']).decode()
        base64_input = base64.b64encode(contents).decode()

        # Yorumlayıcı analiz fonksiyonunu çağır
        yorumlar = interpret_analysis(result)
        probabilities = calculate_probabilities(result)
        trend_comment = trend_analysis_comment(result.get('trend_data', {}), result.get('clusters', []))

        # Hata ayıklama için log ekle
        print("CLUSTERS TYPE:", type(result.get('clusters')))
        print("CLUSTERS CONTENT:", result.get('clusters'))
        print("TREND_DATA TYPE:", type(result.get('trend_data')))
        print("TREND_DATA CONTENT:", result.get('trend_data'))
        for c in result.get('clusters', []):
            print("CLUSTER ITEM:", c)
            for k, v in c.items():
                print(k, type(v))
        print("MOST_TOUCHED_LEVELS TYPE:", type(result.get('most_touched_levels')))
        print("MOST_TOUCHED_LEVELS CONTENT:", result.get('most_touched_levels'))
        for lvl in result.get('most_touched_levels', []):
            print("LEVEL ITEM:", lvl)
            if hasattr(lvl, 'items'):
                for k, v in lvl.items():
                    print(k, type(v))
        print("YORUMLAR TYPE:", type(yorumlar))
        print("YORUMLAR CONTENT:", yorumlar)
        print("PROBABILITIES TYPE:", type(probabilities))
        print("PROBABILITIES CONTENT:", probabilities)
        for p in probabilities:
            print("PROB ITEM:", p)
            if hasattr(p, 'items'):
                for k, v in p.items():
                    print(k, type(v))

        return templates.TemplateResponse("index.html", {
            "request": request,
            "original_image": f"data:image/png;base64,{base64_input}",
            "analyzed_image": f"data:image/png;base64,{base64_result}",
            "direnc_y": result.get('direnc_y'),
            "destek_y": result.get('destek_y'),
            "most_touched_levels": result.get('most_touched_levels'),
            "clusters": result.get('clusters'),
            "yorumlar": yorumlar,
            "probabilities": probabilities,
            "trend_comment": trend_comment,
            "trend_data": result.get('trend_data')
        })

    except Exception as e:
        # Herhangi bir hata olursa detaylı mesaj ver
        return HTMLResponse(f"<h2>❌ Hata oluştu:</h2><pre>{str(e)}</pre>", status_code=500)
