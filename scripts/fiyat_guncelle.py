"""Portföy Defteri fiyat güncelleyici.

Her çalıştığında fiyatlar.json dosyasını yeniler:
  - kur:    TCMB günlük kurlarından USD döviz alış (https://www.tcmb.gov.tr/kurlar/today.xml)
  - altin:  ons altın (gold-api.com) x TCMB USD kuru ile hesaplanan gram altın,
            çeyrek/yarım/tam/Cumhuriyet için serbest piyasadaki ortalama oranlar.
  - piyasa: Borsa İstanbul hisseleri (TradingView, 15 dk gecikmeli), ABD hisse/ETF'leri (TradingView),
            TEFAS yatırım fonlarının son fiyatları (tefas.gov.tr).
Bir kaynağa ulaşılamazsa o bölümün önceki değeri korunur. Sadece Python standart kütüphanesi kullanılır.
"""
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

DOSYA = "fiyatlar.json"
ONS_GRAM = 31.1034768
# Serbest piyasa fiyatlarının gram altına oranı (14 Ekim 2026, Bloomberg HT alış fiyatlarından).
ORANLAR = {"ceyrek": 1.600, "yarim": 3.190, "tam": 6.503, "cumhuriyet": 6.400}
TR = timezone(timedelta(hours=3))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def getir(url, data=None, headers=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=40) as r:
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


def tradingview(pazar, adet, siralama):
    govde = {
        "columns": ["name", "close"],
        "options": {"lang": "en"},
        "range": [0, adet],
        "sort": {"sortBy": siralama, "sortOrder": "desc"},
        "markets": [pazar],
    }
    cevap = json.loads(getir(f"https://scanner.tradingview.com/{pazar}/scan", json.dumps(govde).encode(),
                             {"Content-Type": "application/json", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}))
    sonuc = {}
    for satir in cevap.get("data", []):
        ad, fiyat = satir["d"][0], satir["d"][1]
        if isinstance(fiyat, (int, float)) and fiyat > 0 and ad and ad not in sonuc:
            sonuc[str(ad).upper()] = round(float(fiyat), 4)
    if len(sonuc) < 50:
        raise ValueError(f"{pazar}: çok az sonuç ({len(sonuc)})")
    return sonuc


def tefas():
    bugun = datetime.now(TR).date()
    for geri in range(0, 8):
        g = bugun - timedelta(days=geri)
        tarih = g.strftime("%d.%m.%Y")
        form = urllib.parse.urlencode({"fontip": "YAT", "sfontur": "", "fonkod": "", "fongrup": "", "bastarih": tarih,
                                       "bittarih": tarih, "fonturkod": "", "fonunvantip": "", "kurucukod": ""}).encode()
        ham = getir("https://www.tefas.gov.tr/api/DB/BindHistoryInfo", form, {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.tefas.gov.tr", "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx"})
        veri = json.loads(ham).get("data") or []
        fiyatlar = {}
        for s in veri:
            kod, fiyat = s.get("FONKODU"), s.get("FIYAT")
            if kod and isinstance(fiyat, (int, float)) and fiyat > 0:
                fiyatlar[kod.upper()] = round(float(fiyat), 6)
        if len(fiyatlar) > 100:
            return fiyatlar, g.isoformat()
    raise ValueError("TEFAS verisi bulunamadı")


def main():
    try:
        with open(DOSYA, encoding="utf-8") as f:
            eski = json.load(f)
    except Exception:
        eski = {}
    yeni = dict(eski)
    simdi = datetime.now(TR)
    zaman = simdi.isoformat(timespec="minutes")

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
        altin["zaman"] = zaman
        yeni["altin"] = altin
    except Exception as e:
        print("Altın okunamadı, önceki fiyatlar korunuyor:", e)

    piyasa = dict(eski.get("piyasa") or {})
    for anahtar, is_ in (("bist", lambda: tradingview("turkey", 1500, "market_cap_basic")),
                         ("abd", lambda: tradingview("america", 3000, "Value.Traded"))):
        try:
            piyasa[anahtar] = is_()
            piyasa[anahtar + "Zaman"] = zaman
            print(anahtar, len(piyasa[anahtar]), "fiyat")
        except Exception as e:
            print(anahtar, "okunamadı, önceki fiyatlar korunuyor:", e)
    try:
        fon, fon_tarih = tefas()
        piyasa["fon"] = fon
        piyasa["fonTarih"] = fon_tarih
        print("fon", len(fon), "fiyat,", fon_tarih)
    except Exception as e:
        print("TEFAS okunamadı, önceki fiyatlar korunuyor:", e)
    piyasa["kaynak"] = {"bist": "TradingView (15 dk gecikmeli)", "abd": "TradingView", "fon": "TEFAS"}
    yeni["piyasa"] = piyasa

    karsilastir = lambda d: json.dumps({k: {kk: vv for kk, vv in (v or {}).items() if "aman" not in kk} for k, v in d.items() if k in ("kur", "altin", "piyasa")}, sort_keys=True)
    if karsilastir(yeni) == karsilastir(eski):
        print("Değişiklik yok.")
        return
    yeni["zaman"] = zaman
    with open(DOSYA, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, separators=(",", ":"))
    print("Güncellendi. Boyut:", len(json.dumps(yeni, ensure_ascii=False)), "bayt")


if __name__ == "__main__":
    main()
