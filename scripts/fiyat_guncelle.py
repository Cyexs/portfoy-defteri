"""Portföy Defteri fiyat güncelleyici.

Her çalıştığında fiyatlar.json dosyasını yeniler:
  - kur:   TCMB günlük kurlarından USD döviz alış (https://www.tcmb.gov.tr/kurlar/today.xml)
  - altin: ons altın (gold-api.com) x TCMB USD kuru ile hesaplanan gram altın,
           çeyrek/yarım/tam/Cumhuriyet için serbest piyasadaki ortalama oranlar.
Bir kaynağa ulaşılamazsa o bölümün önceki değeri korunur. Sadece Python standart kütüphanesi kullanılır.
"""
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

DOSYA = "fiyatlar.json"
ONS_GRAM = 31.1034768
# Serbest piyasa fiyatlarının gram altına oranı (14 Ekim 2026, Bloomberg HT alış fiyatlarından).
ORANLAR = {"ceyrek": 1.600, "yarim": 3.190, "tam": 6.503, "cumhuriyet": 6.400}
TR = timezone(timedelta(hours=3))


def getir(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PortfoyDefteri fiyat guncelleyici)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def tcmb_usd():
    kok = ET.fromstring(getir("https://www.tcmb.gov.tr/kurlar/today.xml"))
    tarih = kok.attrib.get("Date")  # AA/GG/YYYY
    ay, gun, yil = tarih.split("/")
    for c in kok.findall("Currency"):
        if c.attrib.get("CurrencyCode") == "USD":
            deger = float(c.findtext("ForexBuying"))
            if deger > 0:
                return {"usdtry": round(deger, 4), "kaynak": "TCMB döviz alış", "tarih": f"{yil}-{ay.zfill(2)}-{gun.zfill(2)}"}
    raise ValueError("USD bulunamadı")


def ons_usd():
    veri = json.loads(getir("https://api.gold-api.com/price/XAU"))
    fiyat = float(veri["price"])
    if fiyat <= 0:
        raise ValueError("geçersiz ons fiyatı")
    return fiyat


def main():
    try:
        with open(DOSYA, encoding="utf-8") as f:
            eski = json.load(f)
    except Exception:
        eski = {}
    yeni = dict(eski)
    simdi = datetime.now(TR)

    try:
        yeni["kur"] = tcmb_usd()
    except Exception as e:
        print("TCMB okunamadı, önceki kur korunuyor:", e)

    try:
        ons = ons_usd()
        usd = (yeni.get("kur") or {}).get("usdtry")
        if not usd:
            raise ValueError("kur yok")
        gram = ons / ONS_GRAM * usd
        altin = {"gram": round(gram, 2), "ons_usd": round(ons, 2)}
        for k, oran in ORANLAR.items():
            altin[k] = round(gram * oran, 2)
        altin["kaynak"] = "Ons altın × TCMB kuru (yaklaşık)"
        altin["zaman"] = simdi.isoformat(timespec="minutes")
        yeni["altin"] = altin
    except Exception as e:
        print("Altın okunamadı, önceki fiyatlar korunuyor:", e)

    karsilastir = lambda d: json.dumps({k: {kk: vv for kk, vv in (v or {}).items() if kk != "zaman"} for k, v in d.items() if k in ("kur", "altin")}, sort_keys=True)
    if karsilastir(yeni) == karsilastir(eski):
        print("Değişiklik yok.")
        return
    with open(DOSYA, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, indent=1)
    print("Güncellendi:", json.dumps(yeni, ensure_ascii=False))


if __name__ == "__main__":
    main()
