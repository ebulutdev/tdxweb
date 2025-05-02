def main():
    print("Hissenin Olması Gereken Fiyatı Hesaplama Botu")
    print("-" * 50)
    hisse_adi = input("Hisse Adı: ")
    hisse_fiyati = float(input("Hisse Fiyatı: "))
    odenmis_sermaye = float(input("Ödenmiş Sermaye: "))
    net_kar = float(input("6/9 Aylık Net Kar: "))
    ozsermaye = float(input("Özsermaye: "))
    piyasa_degeri = float(input("Güncel Piyasa Değeri: "))
    fk_orani = float(input("F/K Oranı: "))
    pddd_orani = float(input("PD/DD Oranı: "))

    # 1) Cari F/K Oranına Göre
    fiyat_fk = (net_kar * fk_orani) / odenmis_sermaye

    # 2) Future's F/K Oranına Göre (örnek: F/K * 1.27)
    fiyat_future_fk = (net_kar * fk_orani * 1.27) / odenmis_sermaye

    # 3) PD/DD Oranına Göre
    fiyat_pddd = (ozsermaye * pddd_orani) / odenmis_sermaye

    # 4) Ödenmiş Sermayeye Göre
    fiyat_sermaye = piyasa_degeri / odenmis_sermaye

    # 5) Potansiyel Piyasa Değerine Göre (örnek: piyasa_degeri * 1.1)
    fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye

    # 6) Yıl Sonu Tahmini Özsermaye Karlılığına Göre (örnek: net_kar * 2)
    fiyat_ozsermaye_kar = (net_kar * 2) / odenmis_sermaye

    fiyatlar = [
        fiyat_fk,
        fiyat_future_fk,
        fiyat_pddd,
        fiyat_sermaye,
        fiyat_potansiyel,
        fiyat_ozsermaye_kar
    ]
    ortalama_fiyat = sum(fiyatlar) / len(fiyatlar)
    prim_potansiyeli = ((ortalama_fiyat - hisse_fiyati) / hisse_fiyati) * 100

    print("\n--- {} ---".format(hisse_adi.upper()))
    print(f"1) Cari F/K Oranına Göre Olması Gereken Fiyat: {fiyat_fk:.2f}")
    print(f"2) Future's F/K Oranına Göre Olması Gereken Fiyat: {fiyat_future_fk:.2f}")
    print(f"3) PD/DD Oranına Göre Olması Gereken Fiyat: {fiyat_pddd:.2f}")
    print(f"4) Ödenmiş Sermayeye Göre Olması Gereken Fiyat: {fiyat_sermaye:.2f}")
    print(f"5) Potansiyel Piyasa Değerine Göre Olması Gereken Fiyat: {fiyat_potansiyel:.2f}")
    print(f"6) Yıl Sonu Tahmini Özsermaye Karlılığına Göre Olması Gereken Fiyat: {fiyat_ozsermaye_kar:.2f}")
    print("-" * 50)
    print(f"6 yöntemin ortalamasına göre olması gereken fiyat: ₺{ortalama_fiyat:.2f}")
    print(f"Hissenin prim potansiyeli: %{prim_potansiyeli:.2f}")

if __name__ == '__main__':
    main() 