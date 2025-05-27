from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yfinance as yf
from datetime import datetime, timedelta
import time
import sqlite3
import json
import re
import random
from difflib import get_close_matches
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from random import uniform

# Download required NLTK data (if not already downloaded)
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
from nltk.corpus import stopwords

app = Flask(__name__)

# Rate Limiter ayarları
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# SQLite veritabanı bağlantısı
def get_db():
    db = sqlite3.connect('stocks_cache.db')
    db.row_factory = sqlite3.Row
    return db

# Veritabanı tablosunu oluştur
def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS stock_cache (
                symbol TEXT PRIMARY KEY,
                data TEXT,
                timestamp DATETIME
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT UNIQUE,
                answer TEXT
            )
        ''')
        db.commit()

# Veritabanını başlat
init_db()

# Selamlama kalıpları
GREETINGS = [
    "Merhaba! Size nasıl yardımcı olabilirim?",
    "Hoş geldiniz! Hangi hisse senedi hakkında bilgi almak istersiniz?",
    "Selam! Borsa verilerini sorgulamak için hazırım.",
    "Merhaba! Hangi hisse senedinin durumunu öğrenmek istersiniz?"
]

# Teşekkür kalıpları
THANKS = [
    "Rica ederim! Başka bir sorunuz var mı?",
    "Ne demek, yardımcı olabildiysem ne mutlu bana!",
    "Rica ederim! Başka bir hisse senedi hakkında bilgi almak isterseniz sorabilirsiniz.",
    "Rica ederim! Başka nasıl yardımcı olabilirim?"
]

# Sık sorulanlar için hazır yanıtlar (Veritabanından çekilecek)
def load_faq_from_db():
    db = get_db()
    cursor = db.execute('SELECT question, answer FROM faq')
    faq_data = {row['question']: row['answer'] for row in cursor.fetchall()}
    db.close()
    return faq_data

FAQ_ANSWERS = load_faq_from_db()

# Duygu analizi anahtar kelimeleri ve yanıtları
SENTIMENTS = [
    (['korkuyorum', 'endişeliyim', 'panik', 'kaygılıyım', 'üzgünüm', 'moralim bozuk'],
     "Endişelenmeyin, borsada duygularınızı kontrol etmek çok önemli. Sakin kalın ve planınıza sadık kalın. Unutmayın, her düşüş bir fırsat olabilir!"),
    (['heyecanlıyım', 'mutluyum', 'çok iyi hissediyorum', 'kazandım'],
     "Harika! Duygularınızı yönetmek ve başarılarınızı kutlamak önemli. Yine de yatırım kararlarınızı mantıkla vermeye devam edin!"),
    (['zarardayım', 'kaybettim', 'zarar ettim'],
     "Zarar etmek borsanın bir parçası. Önemli olan ders çıkarmak ve duygusal kararlar vermemek. Portföyünüzü çeşitlendirmeyi unutmayın.")
]

# Kişisel hatırlatıcılar ve uyarılar
REMINDERS = [
    (['portföy'], "Portföyünüzü çeşitlendirmeyi unutmayın! Farklı sektörlerden ve risk seviyelerinden varlıklar bulundurmak, riskinizi azaltmanıza yardımcı olabilir."),
    (['araştırma', 'araştırmadan'], "Yatırım yaparken kendi araştırmanızı yapmalısınız. Şirketlerin finansal durumlarını, sektörlerini ve gelecekteki potansiyellerini değerlendirin."),
    (['haber', 'gündem'], "Piyasa haberlerini ve gündemi takip etmek önemlidir. Ekonomik gelişmeler, şirket haberleri ve politik olaylar yatırım kararlarınızı etkileyebilir."),
    (['vergi'], "Yatırımlarınızdan elde ettiğiniz gelirler vergiye tabi olabilir. Vergi mevzuatını takip edin ve gerekirse bir uzmana danışın.")
]

# Ekstra finansal terimler ve açıklamalar
DEFAULT_FAQ = {
    # Genel Borsa Bilgileri
    "tdx nedir": "TDX, Türkiye'nin gelişmiş borsa analiz ve veri platformudur. Kullanıcılarına anlık veri, analiz ve yapay zeka destekli öneriler sunar.",
    "tdx ne işe yarar": "TDX, yatırımcılara hisse senedi analizleri, portföy takibi ve yapay zeka destekli öneriler sunarak borsada daha bilinçli kararlar almanıza yardımcı olur.",
    "borsa nedir": "Borsa, hisse senetleri ve diğer menkul kıymetlerin alınıp satıldığı organize bir piyasadır.",
    "hisse senedi nedir": "Hisse senedi, bir şirketin sermayesindeki payı temsil eden ve sahibine o şirketin kârından pay alma hakkı veren bir menkul kıymettir.",
    "yatırım nedir": "Yatırım, gelecekte getiri elde etmek amacıyla yapılan harcamalardır. Borsada hisse senedi almak bir yatırımdır.",
    "tdx nedir": "TDX, Türkiye'nin gelişmiş borsa analiz ve veri platformudur. Kullanıcılarına anlık veri, analiz ve yapay zeka destekli öneriler sunar.",
    "tdx ne işe yarar": "TDX, yatırımcılara hisse senedi analizleri, portföy takibi ve yapay zeka destekli öneriler sunarak borsada daha bilinçli kararlar almalarına yardımcı olur.",
    "tdx hangi analizleri sunuyor": "TDX, hem temel analiz hem de teknik analiz araçları sunar. Ayrıca, yapay zeka destekli analizler ve öneriler de mevcuttur.",
    "tdx yapay zeka": "TDX, yapay zeka algoritmaları ile piyasaları analiz ederek yatırımcılara potansiyel fırsatları ve riskleri gösterir.",
    "tdx risk yönetimi": "TDX, yatırımcılara portföylerini analiz ederek risk düzeylerini belirleme ve risk yönetimi stratejileri geliştirme konusunda yardımcı olur.",
    "tdx piyasa verileri": "TDX, anlık piyasa verilerini ve geçmiş verileri sunarak yatırımcılara kapsamlı bir piyasa görünümü sağlar.",
    "tdx endeksler": "TDX, BIST 100, BIST 30 gibi tüm önemli endekslerin verilerini ve analizlerini sunar.",
    "tdx halka arz": "TDX, yaklaşan halka arzları takip etmenize ve analiz etmenize yardımcı olur.",
    "tdx forex": "TDX, forex piyasası hakkında temel bilgiler ve analiz araçları sunar.",
    "tdx kripto": "TDX, kripto paralar hakkında temel bilgiler ve piyasa verileri sunar.",
    "tdx üyelik": "TDX'e üye olarak anlık piyasa verilerine, analizlere ve yapay zeka destekli önerilere erişebilirsiniz.",
    "tdx ücretli mi": "TDX'in farklı üyelik seçenekleri bulunmaktadır. Bazı özellikler ücretsizken, daha gelişmiş analizler ve verilere erişim için ücretli üyelik gerekmektedir.",
    "tdx mobil uygulama": "TDX'in mobil uygulaması, iOS ve Android platformlarında mevcuttur. Borsayı her yerden takip edebilir ve işlem yapabilirsiniz.",
    "tdx destek hattı": "TDX destek hattına web sitemiz veya mobil uygulamamız üzerinden ulaşabilirsiniz. Her türlü sorunuz ve teknik yardım için size yardımcı olmaktan mutluluk duyarız.",
    "tdx portföy takibi": "TDX ile portföyünüzü kolayca takip edebilir, performansınızı analiz edebilir ve risk yönetimi stratejileri geliştirebilirsiniz.",
    "tdx hisse önerileri": "TDX, yapay zeka destekli algoritmalar sayesinde size kişiselleştirilmiş hisse senedi önerileri sunar.",
    "tdx alarm": "TDX'te belirli bir hisse senedinin fiyatı belirli bir seviyeye ulaştığında alarm kurabilirsiniz.",
    "tdx grafik": "TDX, gelişmiş grafik araçları ile hisse senedi fiyat hareketlerini detaylı bir şekilde analiz etmenize olanak tanır.",
    "tdx eğitim": "TDX, borsa ve yatırım konularında eğitim materyalleri ve rehberler sunar.",
    "tdx analiz raporları": "TDX, uzman analistler tarafından hazırlanan detaylı analiz raporlarına erişmenizi sağlar.",
    "tdx temel analiz": "TDX, şirketlerin finansal tablolarını ve temel göstergelerini analiz etmenize yardımcı olacak araçlar sunar.",
    "tdx teknik analiz": "TDX, teknik analiz araçları ve göstergeleri ile hisse senedi fiyat hareketlerini analiz etmenize yardımcı olur.",
    "tdx veri": "TDX, kapsamlı piyasa verilerine ve geçmiş verilere erişmenizi sağlar.",
    "tdx haberler": "TDX, finansal piyasalarla ilgili güncel haberleri ve gelişmeleri takip etmenize yardımcı olur.",
    "tdx avantajları": "TDX, kullanıcı dostu arayüzü, kapsamlı analiz araçları ve yapay zeka destekli önerileri ile yatırım yapmanızı kolaylaştırır.",
    "tdx kimler kullanabilir": "TDX, hem yeni başlayan hem de deneyimli yatırımcılar için uygundur.",
    "tdx nasıl başlarım": "TDX'e üye olarak hemen başlayabilirsiniz. Ücretsiz deneme sürümümüzü kullanarak platformu keşfedebilirsiniz.",
    "tdx iletişim": "TDX ile ilgili sorularınız için web sitemizdeki iletişim formunu kullanabilir veya destek hattımızı arayabilirsiniz.",
    "tdx güvenlik": "TDX, kullanıcı verilerinin güvenliğini en üst düzeyde sağlamak için gelişmiş güvenlik önlemleri kullanır.",

    # Hisse Önerileri ve Analiz
    "günlük hisse öner": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "günlük hisse önerisi": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hisse öner": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hisse önerisi": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hangi hisseleri almam lazım": "Yatırım tavsiyesi veremem, ancak portföyünüzü çeşitlendirmek ve riskleri azaltmak için farklı sektörlerden güçlü şirketleri inceleyebilirsiniz.",
    "nasıl hisse seçilir": "Hisse seçerken şirketin finansal durumu, sektör analizi, büyüme potansiyeli, teknik göstergeler ve güncel haberler dikkate alınmalıdır.",
    "günlük hisse öner": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "günlük hisse önerisi": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hisse öner": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hisse önerisi": "TDX AI hisse tavsiyesi kısmında size özel günlük analizlere ulaşabilirsiniz.",
    "hangi hisseleri almam lazım": "Yatırım tavsiyesi veremem, ancak portföyünüzü çeşitlendirmek ve riskleri azaltmak için farklı sektörlerden güçlü şirketleri inceleyebilirsiniz.",
    "nasıl hisse seçilir": "Hisse seçerken şirketin finansal durumu, sektör analizi, büyüme potansiyeli, teknik göstergeler ve güncel haberler dikkate alınmalıdır.",
    "tdx ile nasıl hisse seçilir": "TDX'in sunduğu temel analiz, teknik analiz ve yapay zeka destekli analiz araçlarını kullanarak hisse senedi seçimi yapabilirsiniz.",
    "tdx hisse filtreleme": "TDX'in gelişmiş filtreleme araçları ile belirli kriterlere uyan hisse senetlerini kolayca bulabilirsiniz.",
    "tdx hisse karşılaştırma": "TDX ile farklı hisse senetlerini karşılaştırabilir, performanslarını ve finansal verilerini analiz edebilirsiniz.",
    "tdx portföy çeşitlendirme": "TDX, portföyünüzü çeşitlendirmenize yardımcı olacak farklı yatırım araçları ve stratejiler sunar.",
    "tdx yatırım stratejileri": "TDX'te farklı yatırım stratejileri hakkında bilgi edinebilir ve kendi stratejinizi oluşturabilirsiniz.",
    "tdx uzun vadeli yatırım": "TDX, uzun vadeli yatırımcılar için temel analiz araçları ve şirket analiz raporları sunar.",
    "tdx kısa vadeli yatırım": "TDX, kısa vadeli yatırımcılar için teknik analiz araçları ve anlık piyasa verileri sunar.",
    "tdx al sat sinyalleri": "TDX, yapay zeka destekli al-sat sinyalleri ile yatırım kararlarınıza yardımcı olur.",
    "tdx borsa yorumları": "TDX, uzman analistlerin borsa yorumlarını ve piyasa analizlerini takip etmenizi sağlar.",
    "tdx sektörel analiz": "TDX, farklı sektörlerin performansını analiz etmenize ve yatırım yapabileceğiniz sektörleri belirlemenize yardımcı olur.",
    "tdx hisse senedi performansı": "TDX, hisse senetlerinin geçmiş performanslarını ve gelecekteki potansiyellerini analiz etmenize yardımcı olur.",
    "tdx yatırımcı eğitimi": "TDX, yatırımcıların bilgi ve becerilerini geliştirmelerine yardımcı olacak eğitimler ve seminerler düzenler.",
    "tdx risk analizi": "TDX, yatırım yapmadan önce risklerinizi analiz etmenize ve risk toleransınıza uygun yatırım kararları almanıza yardımcı olur.",
    "tdx nasıl kullanılır": "TDX'i kullanmak için öncelikle üye olmanız ve ardından platformun sunduğu araçları ve analizleri keşfetmeniz gerekmektedir. Eğitim bölümümüz size bu konuda yardımcı olacaktır.",
    "tdx ücretli üyelik avantajları": "TDX'in ücretli üyelikleri, daha detaylı analizlere, özel raporlara ve öncelikli desteğe erişmenizi sağlar.",
    # Teknik ve Temel Analiz
    "macd nedir": "MACD (Moving Average Convergence Divergence), iki hareketli ortalamanın birbirinden uzaklaşmasını ve yakınlaşmasını ölçen popüler bir teknik analiz göstergesidir. Al-sat sinyalleri üretmek için kullanılır.",
    "rsi nedir": "RSI (Relative Strength Index), bir hissenin aşırı alım veya aşırı satımda olup olmadığını gösteren teknik analiz göstergesidir. 70 üzeri aşırı alım, 30 altı aşırı satım olarak yorumlanır.",
    "teknik analiz nedir": "Teknik analiz, geçmiş fiyat hareketleri ve işlem hacmi verilerini kullanarak gelecekteki fiyat hareketlerini tahmin etmeye çalışan bir analiz yöntemidir.",
    "temel analiz nedir": "Temel analiz, bir şirketin finansal tabloları, yönetimi, sektörü ve ekonomik koşulları inceleyerek hisse değerini belirlemeye çalışan analiz yöntemidir.",
    "bollinger bandı nedir": "Bollinger Bandı, bir hissenin fiyatının hareketli ortalamasının üstünde ve altında çizilen iki bant ile volatiliteyi ölçen bir teknik analiz göstergesidir.",
    "fibonacci nedir": "Fibonacci düzeltme seviyeleri, fiyat hareketlerinde olası destek ve direnç noktalarını belirlemek için kullanılan teknik analiz aracıdır.",
    "hacim analizi nedir": "Hacim analizi, bir hissenin işlem hacmine bakarak fiyat hareketlerinin gücünü ve sürdürülebilirliğini analiz etmeye yarar.",
    "destek nedir": "Destek, bir hissenin düşüşünü durdurabileceği düşünülen fiyat seviyesidir.",
    "direnç nedir": "Direnç, bir hissenin yükselişini durdurabileceği düşünülen fiyat seviyesidir.",
    "hareketli ortalama nedir": "Hareketli ortalama, belirli bir zaman dilimindeki fiyatların ortalamasını alarak fiyat hareketlerindeki kısa vadeli dalgalanmaları yumuşatan bir teknik analiz aracıdır.",
    
    "tdx macd": "TDX, hisse senetleri için MACD analizini kolayca yapmanızı sağlar ve al-sat sinyalleri üretmenize yardımcı olur.",
    "tdx rsi": "TDX ile hisse senetlerinin RSI değerlerini takip edebilir ve aşırı alım/satım bölgelerini belirleyebilirsiniz.",
    "tdx teknik analiz araçları": "TDX, teknik analiz için birçok araç sunar: MACD, RSI, Bollinger Bandı, Fibonacci Düzeltme Seviyeleri, Hacim Analizi ve daha fazlası.",
    "tdx temel analiz raporları": "TDX, şirketlerin finansal durumlarını gösteren temel analiz raporlarına erişmenizi sağlar.",
    "tdx bollinger bandı": "TDX'te Bollinger Bandı göstergesini kullanarak hisse senedinin volatilite durumunu analiz edebilirsiniz.",
    "tdx fibonacci": "TDX, Fibonacci düzeltme seviyelerini kullanarak olası destek ve direnç noktalarını belirlemenize yardımcı olur.",
    "tdx hacim": "TDX, hisse senedinin işlem hacmini analiz ederek fiyat hareketlerinin gücünü değerlendirmenize olanak tanır.",
    "tdx destek direnç": "TDX'in grafik araçları ile hisse senetlerinin destek ve direnç seviyelerini belirleyebilirsiniz.",
    "tdx hareketli ortalamalar": "TDX, farklı periyotlardaki hareketli ortalamaları kullanarak trendleri belirlemenize yardımcı olur.",
    "tdx grafik analizi": "TDX'in gelişmiş grafik araçları ile detaylı teknik analizler yapabilirsiniz.",
    "tdx bilanço analizi": "TDX, şirketlerin bilançolarını detaylı bir şekilde incelemenize ve temel analiz yapmanıza olanak tanır.",
    "tdx gelir tablosu": "TDX, şirketlerin gelir tablolarını analiz etmenize ve karlılıklarını değerlendirmenize yardımcı olur.",
    "tdx nakit akışı": "TDX, şirketlerin nakit akış tablolarını inceleyerek finansal sağlıklarını değerlendirmenize olanak tanır.",
    "tdx oran analizleri": "TDX, finansal oran analizleri yaparak şirketlerin performansını değerlendirmenize yardımcı olur (örneğin, FK, PD/DD, vb.).",
    "tdx sektör karşılaştırması": "TDX ile farklı sektörlerdeki şirketleri karşılaştırabilir ve yatırım için en uygun sektörleri belirleyebilirsiniz.",
    # Alım-Satım Stratejileri
    "al sat yapmak için nelere bakmak lazım": "Al-sat yaparken teknik analiz (ör. MACD, RSI, hareketli ortalamalar), temel analiz (şirketin finansalları), haber akışı ve piyasa trendleri gibi birçok faktöre bakmak gerekir.",
    "alırken nelere bakmam lazım": "Bir hisse alırken şirketin bilançosu, karlılığı, borçluluk oranı, sektör durumu ve teknik göstergeler gibi birçok faktöre dikkat edilmelidir.",
    "hisse alırken nelere bakılır": "Hisse alırken temel analiz (şirketin mali durumu), teknik analiz (grafik ve göstergeler), sektör ve piyasa koşulları göz önünde bulundurulmalıdır.",
    "stop loss nedir": "Stop loss, zarar durdur emridir. Belirli bir fiyat seviyesine gelindiğinde otomatik satış yapılmasını sağlar.",
    "kâr-zarar nasıl hesaplanır": "Kâr veya zarar, satış fiyatından alış fiyatı çıkarılarak ve lot adediyle çarpılarak hesaplanır. (Kâr/Zarar = (Satış Fiyatı - Alış Fiyatı) x Lot)",

    # Temel Kavramlar
    "temettü nedir": "Temettü, şirketlerin kârlarından ortaklarına dağıttığı paydır. Hisse sahipleri temettü ödemesi alabilir.",
    "bedelli sermaye artırımı nedir": "Bedelli sermaye artırımı, şirketin yeni hisse ihraç ederek ortaklardan para toplamasıdır.",
    "bedelsiz sermaye artırımı nedir": "Bedelsiz sermaye artırımı, şirketin iç kaynaklarını kullanarak sermayesini artırmasıdır. Yatırımcıya ek hisse verilir, para talep edilmez.",
    "endeks nedir": "Endeks, belirli bir grup hissenin performansını ölçen göstergedir. (Örn: BIST 100)",
    "portföy çeşitlendirme nedir": "Portföy çeşitlendirme, riskleri azaltmak için farklı sektör ve varlıklara yatırım yapmaktır.",
    "yatırım fonu nedir": "Yatırım fonu, birçok yatırımcının parasını bir araya getirerek profesyonel yöneticiler tarafından yönetilen portföylerdir.",
    "bist 100 nedir": "BIST 100, Borsa İstanbul'da işlem gören en büyük 100 şirketin performansını gösteren endekstir.",
    "halka arz nedir": "Halka arz, bir şirketin hisselerini ilk kez borsada satışa sunmasıdır.",
    "lot nedir": "Borsada işlem gören hisse senetlerinin standart alım satım birimidir.",

    # Psikoloji ve Risk Yönetimi
    "yatırımcı psikolojisi hakkında ipuçları": "Duygularınızı kontrol edin, panik yapmayın, planlı hareket edin ve uzun vadeli düşünün. Borsada sabır ve disiplin çok önemlidir.",
    "risk yönetimi nedir": "Risk yönetimi, yatırım yaparken olası kayıpları en aza indirmek için alınan önlemlerdir.",
    "portföy nasıl oluşturulur": "Portföy oluştururken risk toleransınızı, yatırım hedeflerinizi ve zaman ufkunuzu dikkate alın. Farklı sektörlerden hisse senetleri, tahviller ve diğer varlıkları içeren bir portföy oluşturmak riskleri azaltır.",

    # Sektör Bazlı Hisseler (Örnekler - Güncel veriler için araştırma yapın)
    "bist 100 önemli hisseler": "BIST 100 endeksinde yer alan önemli hisseler, genellikle piyasa değeri yüksek, işlem hacmi fazla ve sektörlerinde lider konumda olan şirketlerin hisseleridir. Örnek olarak bankacılık sektöründen Garanti, Akbank; sanayi sektöründen Tüpraş, Arçelik; telekomünikasyon sektöründen Türk Telekom sayılabilir.",
    "bist 30 en iyi hisseler": "BIST 30 endeksi, BIST 100 içindeki en büyük 30 şirketi kapsar. Bu endeksteki hisseler genellikle daha likit ve daha istikrarlıdır. Örnek olarak bankacılık, enerji ve sanayi sektörlerinden hisseler yer alır.",
    "ulaşım hisseleri": "Ulaşım sektöründe THYAO (Türk Hava Yolları), PGSUS (Pegasus), TTRAK (Türk Traktör) gibi hisseler bulunmaktadır. Bu hisseler, turizm ve lojistik sektörlerindeki gelişmelere duyarlıdır.",
    "teknoloji hisseleri": "Teknoloji sektöründe ASELS, VESTL (Vestel), INDES (Index Bilgisayar) gibi hisseler bulunmaktadır. Bu hisseler, teknolojik yenilikler ve dijitalleşme trendlerinden etkilenir.",
    "bankacılık hisseleri": "Bankacılık sektöründe AKBNK (Akbank), GARAN (Garanti Bankası), ISCTR (İş Bankası) gibi büyük bankaların hisseleri yer alır. Bu hisseler, faiz oranları ve ekonomik büyüme gibi faktörlerden etkilenir.",
    "enerji hisseleri": "Enerji sektöründe TUPRS (Tüpraş), PETKM (Petkim), AKSA (Aksa Enerji) gibi şirketlerin hisseleri bulunmaktadır. Bu hisseler, petrol fiyatları ve enerji politikalarından etkilenir.",

    #Ek Soru Kalıpları
    "hangi sektörlere yatırım yapmalıyım": "Yatırım yapacağınız sektörler, risk toleransınıza, yatırım hedeflerinize ve piyasa koşullarına bağlıdır. Büyüme potansiyeli yüksek sektörleri (örneğin, teknoloji, yenilenebilir enerji) veya daha istikrarlı sektörleri (örneğin, gıda, perakende) tercih edebilirsiniz.",
    "büyük yatırımcılar hangi hisseleri alıyor": "Büyük yatırımcıların (kurumsal yatırımcılar, fonlar) hangi hisseleri aldığına dair kesin bilgilere ulaşmak zordur, ancak genellikle büyük piyasa değerine sahip, likit ve istikrarlı şirketlerin hisselerini tercih ettikleri bilinir. Ayrıca, büyüme potansiyeli yüksek ve gelecek vaat eden sektörlerdeki şirketlere de yatırım yapabilirler.",
    "en çok kazandıran hisseler hangileri": "Geçmişte en çok kazandıran hisseler, gelecekte de aynı performansı gösterecekleri anlamına gelmez. En çok kazandıran hisseleri belirlemek için piyasa koşullarını, sektör trendlerini ve şirketlerin finansal performansını sürekli olarak takip etmek gerekir.",
    "uzun vadeli yatırım için hangi hisseleri önerirsiniz": "Uzun vadeli yatırım için genellikle sağlam temellere sahip, istikrarlı büyüme gösteren ve temettü ödemesi yapan şirketlerin hisseleri önerilir. Örnek olarak, büyük bankalar, enerji şirketleri ve telekomünikasyon şirketleri sayılabilir.",
    "dolar bazında hisse almak mantıklı mı": "Dolar bazında hisse almak, TL'nin değer kaybettiği dönemlerde cazip olabilir. Ancak, kur riskini de göz önünde bulundurmak gerekir. Dolar bazında hisse alırken, şirketin dolar cinsinden gelirleri ve giderleri, borçluluk durumu ve sektördeki rekabet koşulları gibi faktörler dikkate alınmalıdır.",
     "merhaba": "Merhaba! Ben TDX Borsa Botu, bugün çok neşeliyim. Bana hemen hangi hisseyi soracağını söyle, zaman kaybetmeyelim!",
    "merhaba nasılsın": "Nasılsın mı? Ben bir botum, duygularım yok. Ama piyasalar hareketli, bu beni heyecanlandırıyor! Hadi hisse konuşalım.",
    "nasılsın": "Eh, bir borsa botu için olabilecek en iyisiyim. Veriler akıyor, grafikler yükseliyor... Sizin için hangi hisseyi inceleyebilirim?",
    "naber": "Naber mi? Bende her şey tıkırında. Borsada fırsatlar bitmez, yeter ki doğru hisseyi bulalım. Ne arıyorsun?",
    "selam": "Selam! Lafı dolandırmayalım, hemen hisselere geçelim. Ne öğrenmek istiyorsun?",
    "iyi misin": "İyiyim, teşekkürler! Ama asıl önemli olan senin portföyün nasıl? Yardımcı olabileceğim bir hisse var mı?",
    "hey": "Hey! Vakit nakittir derler. Hangi hisse seni ilgilendiriyor?",
    "günaydın": "Günaydın! Piyasalar açılıyor ,hala uyuyor musun ? hangi hisseyi mercek altına alalım?",
    "iyi akşamlar": "İyi akşamlar! Günün kapanışını değerlendirmek için harika bir zaman. Hangi hisseler radarında?",
    "nası gidiyor": "Nasıl gittiği önemli değil, önemli olan nasıl gideceği! Hangi hissenin geleceğini merak ediyorsun?",
    
    "hangi sektörlere yatırım yapmalıyım": "Yatırım yapacağınız sektörler, risk toleransınıza, yatırım hedeflerinize ve piyasa koşullarına bağlıdır. Büyüme potansiyeli yüksek sektörleri (örneğin, teknoloji, yenilenebilir enerji) veya daha istikrarlı sektörleri (örneğin, gıda, perakende) tercih edebilirsiniz.",
    "büyük yatırımcılar hangi hisseleri alıyor": "Büyük yatırımcıların (kurumsal yatırımcılar, fonlar) hangi hisseleri aldığına dair kesin bilgilere ulaşmak zordur, ancak genellikle büyük piyasa değerine sahip, likit ve istikrarlı şirketlerin hisselerini tercih ettikleri bilinir. Ayrıca, büyüme potansiyeli yüksek ve gelecek vaat eden sektörlerdeki şirketlere de yatırım yapabilirler.",
    "en çok kazandıran hisseler hangileri": "Geçmişte en çok kazandıran hisseler, gelecekte de aynı performansı gösterecekleri anlamına gelmez. En çok kazandıran hisseleri belirlemek için piyasa koşullarını, sektör trendlerini ve şirketlerin finansal performansını sürekli olarak takip etmek gerekir.",
    "uzun vadeli yatırım için hangi hisseleri önerirsiniz": "Uzun vadeli yatırım için genellikle sağlam temellere sahip, istikrarlı büyüme gösteren ve temettü ödemesi yapan şirketlerin hisseleri önerilir. Örnek olarak, büyük bankalar, enerji şirketleri ve telekomünikasyon şirketleri sayılabilir.",
    "dolar bazında hisse almak mantıklı mı": "Dolar bazında hisse almak, TL'nin değer kaybettiği dönemlerde cazip olabilir. Ancak, kur riskini de göz önünde bulundurmak gerekir. Dolar bazında hisse alırken, şirketin dolar cinsinden gelirleri ve giderleri, borçluluk durumu ve sektördeki rekabet koşulları gibi faktörler dikkate alınmalıdır.",

    "hangi hisseler düşecek": "Keşke düşecek hisseleri bilsem! Ama o zaman borsa botu değil, kahin olurdum. TDX ile analiz yaparak kendi tahminlerini oluşturabilirsin.",
    "en güvenli hisseler hangileri": "En güvenli hisse diye bir şey yoktur, en iyi analiz edilmiş hisse vardır. TDX ile şirketlerin finansal sağlığını kontrol et ve riskini minimize et.",
    "hangi hisse zengin eder": "Zengin edecek hisse arıyorsan, piyangoya baksan daha iyi! Borsada kısa yoldan zengin olmak yerine, uzun vadeli ve bilinçli yatırım yapmak daha mantıklı.",
    "temettü veren hisseler alınır mı": "Temettü veren hisseler güzeldir, ama tek başına yeterli değil. Şirketin genel performansını ve gelecekteki büyüme potansiyelini de değerlendirmek lazım. TDX bu konuda sana yardımcı olabilir.",
    "hangi hisse alınmaz": "Alınmaması gereken hisseleri belirlemek için TDX'teki risk analiz araçlarını kullanabilirsin. Borçlu, karlılığı düşük ve geleceği belirsiz şirketlerden uzak durmakta fayda var.",
    "bu hisse yükselir mi": "Bu hisse yükselir mi sorusunun cevabını ben veremem, ama TDX'teki teknik ve temel analiz araçları sana bu konuda fikir verebilir.",
    "piyasa ne zaman düzelir": "Piyasanın ne zaman düzeleceğini kimse bilemez. Ama TDX ile piyasayı sürekli takip ederek hazırlıklı olabilirsin.",
    "hangi banka hissesi alınır": "Hangi banka hissesinin alınacağına karar vermek için TDX'teki bankacılık sektörü analizlerini inceleyebilirsin. Bankaların karlılık, büyüme ve risk durumlarını karşılaştır.",
    "hangi enerji hissesi alınır": "Enerji sektörü hareketli bir sektör. TDX ile farklı enerji şirketlerinin finansal performanslarını ve projelerini inceleyerek karar verebilirsin.",
    "hangi teknoloji hissesi alınır": "Teknoloji hisseleri geleceğin yıldızları olabilir, ama riskli de olabilirler. TDX ile teknoloji şirketlerinin inovasyon potansiyellerini ve rekabet güçlerini analiz et.",
    "hisseler neden düşüyor": "Hisseler birçok nedenle düşebilir: ekonomik belirsizlikler, şirket sorunları, yatırımcı panikleri... TDX ile piyasayı takip ederek nedenleri anlamaya çalışabilirsin.",
    "hisseler neden yükseliyor": "Hisseler de birçok nedenle yükselebilir: iyi şirket haberleri, sektör büyümesi, yatırımcı ilgisi... TDX ile piyasayı takip ederek nedenleri anlamaya çalışabilirsin.",
    "hangi yatırımcıyı takip etmeliyim": "Yatırımcı tavsiyesi almak yerine, kendi analizlerini yapmayı öğren. TDX sana bu konuda yardımcı olabilir. Kendi kararlarını kendin ver!",
    "borsa kumar mı": "Borsa kumar değildir, ama kumar gibi oynanabilir. Bilgi ve analizle yatırım yapmak, kumar oynamaktan çok farklıdır. TDX ile bilinçli yatırım yapabilirsin.",
    
    "piyasalar nasıl": "Piyasalar her zamanki gibi hareketli ve öngörülemez. Ama TDX ile piyasaları yakından takip edebilir ve fırsatları yakalayabilirsin.",
    "bugün ne alalım": "Bugün ne alalım sorusu yerine, 'Bugün hangi analizleri yapmalıyım?' diye sormalısın. TDX'te analiz araçlarımız seni bekliyor!",
    "hangi hisse ucuz": "Ucuz hisse diye bir şey yoktur, potansiyeli olan hisse vardır. TDX ile hisselerin değerini analiz edebilir ve potansiyel fırsatları bulabilirsin.",
    "ne yapmalıyım": "Ne yapman gerektiğini ben söyleyemem, ama TDX'i kullanarak doğru kararlar vermen için gereken tüm araçlara sahipsin.",
}
# Veritabanına varsayılan SSS'leri ekle
def populate_default_faq():
    db = get_db()
    for question, answer in DEFAULT_FAQ.items():
        try:
            db.execute('INSERT INTO faq (question, answer) VALUES (?, ?)', (question, answer))
        except sqlite3.IntegrityError:
            # Soru zaten varsa atla
            pass
    db.commit()
    db.close()

# Uygulama başladığında varsayılan SSS'leri yükle
with app.app_context():
    populate_default_faq()
    FAQ_ANSWERS = load_faq_from_db()

def extract_stock_symbol(text):
    # Sadece .IS ile bitenleri hisse kodu olarak al
    pattern = r'([A-Z]{2,5}\.IS)'
    match = re.search(pattern, text.upper())
    if match:
        return match.group(1)
    return None

# Global sembol sorgu zamanları (bellekte tutulur)
symbol_last_query = {}

def get_stock_data(symbol, max_retries=5, base_delay=3, max_delay=30, min_symbol_interval=15):
    """
    Hisse senedi verilerini getirir, önce veritabanında kontrol eder,
    sonra Yahoo Finance API'sini kullanır. API sınırına takılmamak için
    bekleme süreleri, exponential backoff, random jitter ve yeniden deneme mekanizması içerir.
    Ayrıca aynı sembole çok sık sorgu yapılmasını engeller.
    """
    global symbol_last_query
    now = datetime.now()
    # Sembole özel minimum sorgu aralığı kontrolü
    last_time = symbol_last_query.get(symbol)
    if last_time and (now - last_time).total_seconds() < min_symbol_interval:
        raise Exception(f"Bu hisseye çok sık sorgu yapıldı. Lütfen {min_symbol_interval} saniye bekleyin.")
    for attempt in range(max_retries):
        try:
            # Önce veritabanından kontrol et
            with get_db() as db:
                cursor = db.execute(
                    'SELECT data, timestamp FROM stock_cache WHERE symbol = ?',
                    (symbol,)
                )
                result = cursor.fetchone()
                if result:
                    # Veri 5 dakikadan eski mi kontrol et
                    cache_time = datetime.strptime(result['timestamp'], '%Y-%m-%d %H:%M:%S')
                    if now - cache_time < timedelta(minutes=5):
                        return json.loads(result['data'])

            # Veritabanında yoksa veya süresi geçmişse yeni veri çek
            stock = yf.Ticker(symbol)
            info = stock.info

            # API'den veri çekildiyse veritabanına kaydet
            stock_data = {
                'price': info.get('regularMarketPrice'),
                'change': info.get('regularMarketChangePercent'),
                'open_price': info.get('open'),
                'prev_close': info.get('previousClose'),
                'volume': info.get('regularMarketVolume'),
                'day_high': info.get('dayHigh'),
                'day_low': info.get('dayLow'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
                'marketCap': info.get('marketCap'),
                'shortName': info.get('shortName'),
                'longName': info.get('longName'),
                'recommendationKey': info.get('recommendationKey'),
                'numberOfAnalystOpinions': info.get('numberOfAnalystOpinions'),
                'targetMeanPrice': info.get('targetMeanPrice'),
                'targetHighPrice': info.get('targetHighPrice'),
                'targetLowPrice': info.get('targetLowPrice'),
                'earningsPerShare': info.get('epsCurrentYear')
            }
            with get_db() as db:
                db.execute(
                    'INSERT OR REPLACE INTO stock_cache (symbol, data, timestamp) VALUES (?, ?, ?)',
                    (symbol, json.dumps(stock_data), now.strftime('%Y-%m-%d %H:%M:%S'))
                )
                db.commit()
            # Sorgu zamanını güncelle
            symbol_last_query[symbol] = now
            return stock_data

        except Exception as e:
            # API rate limit veya forbidden hatası ise uzun bekle
            err_str = str(e).lower()
            if any(x in err_str for x in ['rate limit', 'forbidden', '429', '403']):
                wait_time = max_delay
                print(f'API rate limit/engeli: {e}, {wait_time}s bekleniyor...')
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = uniform(0, 2)
                total_delay = delay + jitter
                print(f"API hatası: {e}, {total_delay:.1f} sn sonra tekrar denenecek... (Deneme {attempt+1}/{max_retries})")
                time.sleep(total_delay)
            else:
                print(f"API hatası (son deneme): {e}")
                raise Exception(f"Veri alınamadı: {str(e)}")

def generate_response(user_message, stock_data=None):
    # Selamlama kontrolü
    if any(word in user_message.lower() for word in ['merhaba', 'selam', 'hey']):
        return random.choice(GREETINGS)
    
    # Teşekkür kontrolü
    if any(word in user_message.lower() for word in ['teşekkür', 'sağol', 'eyvallah']):
        return random.choice(THANKS)
    
    # Hisse senedi verisi varsa formatla
    if stock_data:
        change_emoji = "📈" if stock_data.get('change') and stock_data.get('change') > 0 else "📉"
        def safe(val, digits=2):
            return f"{val:.{digits}f}" if isinstance(val, (int, float)) and val is not None else "Veri yok"
        response = f"""
        {change_emoji} <b>{stock_data.get('shortName', user_message)} ({user_message})</b> için güncel bilgiler:<br>
        <b>💰 Güncel Fiyat:</b> {safe(stock_data.get('price'))} TL<br>
        <b>{change_emoji} Değişim:</b> {safe(stock_data.get('change'))}%<br>
        <b>🔓 Açılış:</b> {safe(stock_data.get('open_price'))} TL<br>
        <b>🔒 Önceki Kapanış:</b> {safe(stock_data.get('prev_close'))} TL<br>
        <b>📊 Hacim:</b> {safe(stock_data.get('volume'), 0)}<br>
        <b>Gün İçi:</b> En Yüksek: {safe(stock_data.get('day_high'))} TL, En Düşük: {safe(stock_data.get('day_low'))} TL<br>
        <b>52 Hafta:</b> En Yüksek: {safe(stock_data.get('fiftyTwoWeekHigh'))} TL, En Düşük: {safe(stock_data.get('fiftyTwoWeekLow'))} TL<br>
        <b>Piyasa Değeri:</b> {safe(stock_data.get('marketCap'), 0)} TL<br>
        <b>Analist Tavsiyesi:</b> {stock_data.get('recommendationKey', 'Veri yok').capitalize()}<br>
        <b>Analist Sayısı:</b> {stock_data.get('numberOfAnalystOpinions', 'Veri yok')}<br>
        <b>Ortalama Hedef Fiyat:</b> {safe(stock_data.get('targetMeanPrice'))} TL<br>
        <b>En Yüksek Hedef Fiyat:</b> {safe(stock_data.get('targetHighPrice'))} TL<br>
        <b>En Düşük Hedef Fiyat:</b> {safe(stock_data.get('targetLowPrice'))} TL<br>
        <b>Hisse Başına Kâr (EPS):</b> {safe(stock_data.get('earningsPerShare'))}<br>
        <br>
        Başka bir hisse senedi hakkında bilgi almak ister misiniz?
        """
        return response
    
    return "Üzgünüm, anlayamadım. Lütfen bir hisse senedi kodu girin (örn: THYAO.IS)"

def check_faq(user_message):
    msg = user_message.lower()
    for key, answer in FAQ_ANSWERS.items():
        if key in msg or msg in key:
            return answer
    return None

def find_similar_faq(user_message):
    msg = user_message.lower()
    # Önce kısmi eşleşme kontrolü
    for key in FAQ_ANSWERS:
        if key in msg or msg in key:
            return [key]
    # Sonra anahtar kelime geçenleri topla
    matches = [key for key in FAQ_ANSWERS if any(word in msg for word in key.split())]
    if not matches:
        close = get_close_matches(msg, FAQ_ANSWERS.keys(), n=1, cutoff=0.7)  # Eşiği yükselttik
        if close:
            matches = close
    return matches

# Duygu analizi fonksiyonu (VADER ile)
def analyze_sentiment(user_message):
    analyzer = SentimentIntensityAnalyzer()
    vs = analyzer.polarity_scores(user_message)
    compound_score = vs['compound']

    if compound_score >= 0.05:
        return "Yatırımlarınızla ilgili olumlu duygularınız olduğunu görüyorum. Başarılarınızın devamını dilerim!"
    elif compound_score <= -0.05:
        return "Yatırımlarınızla ilgili endişeli olduğunuzu anlıyorum. Sakin kalmaya ve planınıza sadık kalmaya çalışın."
    else:
        return None

# Hatırlatıcı fonksiyonu
def check_reminders(user_message):
    msg = user_message.lower()
    for keywords, response in REMINDERS:
        if any(word in msg for word in keywords):
            return response
    return None

# Stop loss ve kâr-zarar hesaplama fonksiyonu
def calculate_from_message(user_message):
    # %10 stop loss örneği
    match = re.search(r'%\s*(\d{1,2})\s*stop\s*loss', user_message.lower())
    if match:
        percent = int(match.group(1))
        return f"Örneğin 100 TL'den aldığınız bir hisse için %{percent} stop loss seviyesi: {100 - 100 * percent / 100:.2f} TL olur. (Stop loss: Alış fiyatı - (%{percent} x alış fiyatı))"
    # Kâr-zarar hesaplama
    match = re.search(r'(\d+[\.,]?\d*)\s*(tl)?\s*al(dım|ış)?[\s,;]+(\d+[\.,]?\d*)\s*(tl)?\s*sat(ar)?sam', user_message.lower())
    if match:
        buy = float(match.group(1).replace(',', '.'))
        sell = float(match.group(4).replace(',', '.'))
        profit = sell - buy
        percent = (profit / buy) * 100
        return f"{buy:.2f} TL'den alıp {sell:.2f} TL'den satarsanız kâr/zararınız: {profit:.2f} TL (%{percent:.2f}) olur. (Vergi ve komisyonlar hariçtir.)"
    return None

# Soru cevaplama fonksiyonu (TF-IDF ile)
def answer_question(user_message):
    # SSS verilerini ve soruları al
    questions = list(FAQ_ANSWERS.keys())
    answers = list(FAQ_ANSWERS.values())

    # Soruları ve kullanıcı mesajını birleştir
    corpus = questions + [user_message]

    # TF-IDF vektörleştirici oluştur
    vectorizer = TfidfVectorizer(stop_words=stopwords.words('turkish'))
    tfidf_matrix = vectorizer.fit_transform(corpus)

    # Kullanıcı mesajının vektörünü al
    user_vector = tfidf_matrix[-1]

    # SSS sorularının vektörlerini al
    question_vectors = tfidf_matrix[:-1]

    # Kullanıcı mesajı ile SSS soruları arasındaki benzerlikleri hesapla
    similarity_scores = cosine_similarity(user_vector, question_vectors)

    # En benzer sorunun indeksini al
    best_match_index = similarity_scores.argmax()

    # En benzer sorunun benzerlik skorunu al
    best_match_score = similarity_scores[0, best_match_index]

    # Eğer benzerlik skoru belirli bir eşiğin üzerindeyse, cevabı döndür
    if best_match_score > 0.2:  # Eşik değerini ayarlayabilirsiniz
        return answers[best_match_index]
    else:
        return "Üzgünüm, bu konuda size yardımcı olamıyorum. Lütfen sorunuzu farklı şekilde ifade edin."

@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'response': random.choice(GREETINGS)})
    
    # Duygu analizi
    sentiment = analyze_sentiment(user_message)
    if sentiment:
        return jsonify({'response': sentiment})
    # Hatırlatıcılar
    reminder = check_reminders(user_message)
    if reminder:
        return jsonify({'response': reminder})
    # Hesaplama
    calc = calculate_from_message(user_message)
    if calc:
        return jsonify({'response': calc})
    # Selamlama veya teşekkür ise insansı cevap ver
    if any(word in user_message.lower() for word in ['merhaba', 'selam', 'hey']):
        return jsonify({'response': random.choice(GREETINGS)})
    if any(word in user_message.lower() for word in ['teşekkür', 'sağol', 'eyvallah']):
        return jsonify({'response': random.choice(THANKS)})

    try:
        symbol = extract_stock_symbol(user_message)
        if symbol:
            try:
                stock_data = get_stock_data(symbol)
            except Exception as e:
                if 'çok sık sorgu' in str(e).lower():
                    return jsonify({'response': 'Bu hisseye çok sık sorgu yaptınız. Lütfen birkaç saniye sonra tekrar deneyin.'})
                raise
            if stock_data['price'] is None:
                return jsonify({'response': 'Üzgünüm, bu hisse kodu için veri bulunamadı. Lütfen kodu kontrol edin veya başka bir hisse deneyin.'})
            response = generate_response(symbol, stock_data)
        else:
            # Önce tam/kısmi eşleşme
            faq_answer = check_faq(user_message)
            if faq_answer:
                return jsonify({'response': faq_answer})
            # Soru cevaplama
            question_answer = answer_question(user_message)
            if question_answer:
                return jsonify({'response': question_answer})
            # Sonra benzerlik
            similar = find_similar_faq(user_message)
            if similar:
                suggestion = f'Bunu mu demek istediniz: <b>{similar[0]}</b>?<br><br>{FAQ_ANSWERS[similar[0]]}'
                return jsonify({'response': suggestion})
            response = "Lütfen bir hisse kodu girin (örn: THYAO.IS) veya bir soru sorun :)"
        return jsonify({'response': response})
    except Exception as e:
        if '404' in str(e):
            return jsonify({'response': 'Üzgünüm, bu hisse kodu için veri bulunamadı. Lütfen kodu kontrol edin veya başka bir hisse deneyin.'})
        return jsonify({'response': f'❌ Üzgünüm, bir hata oluştu: {str(e)}'})

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'response': '⚠️ Çok fazla istek gönderdiniz. Lütfen biraz bekleyin ve tekrar deneyin.'
    }), 429

if __name__ == '__main__':
    app.run(debug=True)