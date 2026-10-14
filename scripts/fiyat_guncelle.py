"""Portföy Defteri fiyat güncelleyici.

Her çalıştığında fiyatlar.json dosyasını yeniler:
  - kur:    TCMB günlük kurlarından USD döviz alış (https://www.tcmb.gov.tr/kurlar/today.xml)
  - altin:  ons altın (gold-api.com) x TCMB USD kuru ile hesaplanan gram altın,
            çeyrek/yarım/tam/Cumhuriyet için serbest piyasadaki ortalama oranlar.
  - piyasa: Borsa İstanbul hisseleri (TradingView, 15 dk gecikmeli), ABD hisse/ETF'leri (TradingView),
            TEFAS yatırım fonlarının son fiyatları (tefas.gov.tr), günlük % değişimler.
  - oneriler: kriterlere uyan "incelemeye değer" BIST hisseleri ve kira/altın fonları.
  - haberler: Midas'ın son haber başlıkları (getmidas.com RSS) ve başlıkta geçen hisse kodları.
Bir kaynağa ulaşılamazsa o bölümün önceki değeri korunur. Sadece Python standart kütüphanesi kullanılır.
"""
import json
import os
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


def tradingview(pazar, adet, siralama, oranlar=False):
    kolonlar = ["name", "close", "change"]
    if oranlar:
        kolonlar += ["price_earnings_ttm", "return_on_equity", "market_cap_basic", "dividends_yield_current", "description"]
    govde = {"columns": kolonlar, "options": {"lang": "tr"}, "range": [0, adet],
             "sort": {"sortBy": siralama, "sortOrder": "desc"}, "markets": [pazar]}
    cevap = json.loads(getir(f"https://scanner.tradingview.com/{pazar}/scan", json.dumps(govde).encode(),
                             {"Content-Type": "application/json", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}))
    fiyat, degisim, satirlar = {}, {}, []
    for satir in cevap.get("data", []):
        d = satir["d"]
        ad, f, ch = d[0], d[1], d[2]
        if isinstance(f, (int, float)) and f > 0 and ad:
            kod = str(ad).upper()
            if kod in fiyat:
                continue
            fiyat[kod] = round(float(f), 4)
            if isinstance(ch, (int, float)):
                degisim[kod] = round(float(ch), 2)
            if oranlar:
                satirlar.append(d)
    if len(fiyat) < 50:
        raise ValueError(f"{pazar}: çok az sonuç ({len(fiyat)})")
    return fiyat, degisim, satirlar


def bist_onerileri(satirlar):
    """Büyük şirketler (piyasa değerine göre ilk 150) içinde F/K 0-12 ve özsermaye kârlılığı %15 üstü olanlar."""
    adaylar = []
    for d in satirlar[:150]:
        kod, f, ch, fk, roe, pd, tv, ad = d
        if isinstance(fk, (int, float)) and isinstance(roe, (int, float)) and 0 < fk < 12 and roe > 15:
            adaylar.append({"kod": kod, "ad": (ad or "")[:40], "fk": round(fk, 1), "roe": round(roe, 1),
                            "temettu": round(tv, 1) if isinstance(tv, (int, float)) else None})
    adaylar.sort(key=lambda x: -x["roe"])
    return adaylar[:8]


def tefas_post(yol, govde):
    ham = getir("https://www.tefas.gov.tr" + yol, json.dumps(govde).encode(),
                {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*"})
    return json.loads(ham).get("resultList") or []


def tefas():
    """TEFAS'taki tüm yatırım fonlarının son fiyatı. 2026'daki yeni API fon başına çalışıyor;
    o yüzden günde bir kez, az sayıda paralel istekle çekiyoruz."""
    from concurrent.futures import ThreadPoolExecutor
    liste = tefas_post("/api/funds/fonGetiriBazliBilgiGetir", {
        "dil": "TR", "fonTipi": "YAT", "kurucuKodu": None, "sfonTurKod": None, "fonTurAciklama": None, "islem": 1,
        "fonTurKod": None, "fonGrubu": None, "donemGetiri1a": "1", "donemGetiri3a": "1", "donemGetiri6a": "1",
        "donemGetiri1y": "1", "donemGetiriyb": "1", "donemGetiri3y": "1", "donemGetiri5y": "1",
        "basTarih": None, "bitTarih": None, "calismaTipi": 2, "getiriOrani": "1"})
    kodlar = sorted({r["fonKodu"].upper() for r in liste if r.get("fonKodu")})
    if len(kodlar) < 100:
        raise ValueError(f"fon listesi çok kısa ({len(kodlar)})")

    def bir_fon(kod):
        try:
            satirlar = tefas_post("/api/funds/fonFiyatBilgiGetir", {"fonKodu": kod, "dil": "TR", "periyod": 1})
            satirlar = [r for r in satirlar if isinstance(r.get("fiyat"), (int, float)) and r["fiyat"] > 0]
            if not satirlar:
                return None
            son = max(satirlar, key=lambda r: r.get("tarih") or "")
            return kod, round(float(son["fiyat"]), 6), son.get("tarih")
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=6) as havuz:
        sonuclar = [x for x in havuz.map(bir_fon, kodlar) if x]
    fiyatlar = {k: f for k, f, _ in sonuclar}
    tarihler = sorted({t for _, _, t in sonuclar if t})
    if len(fiyatlar) < 100:
        raise ValueError(f"çok az fon fiyatı ({len(fiyatlar)}/{len(kodlar)})")
    def getiri(r):
        for k in ("getiri1y", "getiriyb", "getiri6a"):
            if isinstance(r.get(k), (int, float)):
                return r[k]
        return None
    def sec(kosul, adet=5):
        sec_ = [r for r in liste if r.get("tefasDurum") and kosul((r.get("fonUnvan") or "").upper(), (r.get("fonTurAciklama") or "").upper())
                and r.get("fonKodu", "").upper() in fiyatlar and getiri(r) is not None]
        sec_.sort(key=lambda r: -getiri(r))
        return [{"kod": r["fonKodu"].upper(), "ad": (r.get("fonUnvan") or "")[:70], "getiri1y": r.get("getiri1y"), "getiriyb": r.get("getiriyb"),
                 "getiri1a": r.get("getiri1a"), "risk": r.get("riskDegeri")} for r in sec_[:adet]]
    oneri = {"kira": sec(lambda u, t: "KİRA SERTİFİKA" in u), "altin": sec(lambda u, t: "ALTIN" in u and "HİSSE" not in u)}
    return fiyatlar, (tarihler[-1] if tarihler else None), oneri


HABER_DISI = {"BIST", "TCMB", "ABD", "FED", "USD", "EUR", "TRY", "GSYH", "TÜFE", "TUFE", "KAP", "SPK", "CEO", "IPO", "ETF", "MIDAS", "AB", "BM", "IMF", "OPEC", "NATO", "AI", "GDP", "CPI", "PMI", "ECB", "BOJ", "THE", "AND", "FOR"}


def midas_haberleri(bist, abd):
    """Midas RSS'inden son haber başlıkları. Haber metnini saklamıyoruz; başlık, bağlantı, tarih ve başlıkta geçen hisseler."""
    import re
    from email.utils import parsedate_to_datetime
    kok = ET.fromstring(getir("https://www.getmidas.com/feed/"))
    haberler = []
    for item in kok.iter("item"):
        baslik = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not baslik or not link.startswith("https://www.getmidas.com/"):
            continue
        try:
            tarih = parsedate_to_datetime(item.findtext("pubDate")).astimezone(TR).isoformat(timespec="minutes")
        except Exception:
            tarih = None
        ozet = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        hisseler = []
        def ekle(kod, min_uzunluk):
            if len(kod) < min_uzunluk or kod in HABER_DISI or any(h[0] == kod for h in hisseler):
                return
            if kod in bist:
                hisseler.append([kod, "bist"])
            elif kod in abd:
                hisseler.append([kod, "abd"])
        for kod in re.findall(r"\b[A-ZÇĞİÖŞÜ0-9]{2,6}\b", baslik):
            ekle(kod, 2)
        for kod in re.findall(r"\b[A-Z]{4,6}\b", ozet):
            if len(hisseler) >= 6:
                break
            if kod in bist:
                ekle(kod, 4)
        haberler.append({"b": baslik[:160], "u": link, "t": tarih, "h": hisseler[:6]})
        if len(haberler) >= 25:
            break
    if not haberler:
        raise ValueError("RSS'te haber bulunamadı")
    return haberler


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

    hatalar = {}
    piyasa = dict(eski.get("piyasa") or {})
    oneriler = dict(eski.get("oneriler") or {})
    for anahtar, pazar, adet, siralama in (("bist", "turkey", 1500, "market_cap_basic"), ("abd", "america", 3000, "Value.Traded")):
        try:
            fiyat, degisim, satirlar = tradingview(pazar, adet, siralama, oranlar=(anahtar == "bist"))
            piyasa[anahtar] = fiyat
            piyasa[anahtar + "D"] = degisim
            piyasa[anahtar + "Zaman"] = zaman
            if anahtar == "bist":
                oneriler["bist"] = bist_onerileri(satirlar)
            print(anahtar, len(fiyat), "fiyat")
        except Exception as e:
            print(anahtar, "okunamadı, önceki fiyatlar korunuyor:", e)
            hatalar[anahtar] = str(e)[:200]
    bugun = simdi.date().isoformat()
    if piyasa.get("fonGun") != bugun or os.environ.get("TEFAS_ZORLA"):
        try:
            fon, fon_tarih, fon_oneri = tefas()
            oneriler.update(fon_oneri)
            piyasa["fon"] = fon
            piyasa["fonTarih"] = fon_tarih
            piyasa["fonGun"] = bugun
            print("fon", len(fon), "fiyat,", fon_tarih)
        except Exception as e:
            print("TEFAS okunamadı, önceki fiyatlar korunuyor:", e)
            hatalar["fon"] = (type(e).__name__ + ": " + str(e))[:200]
    else:
        print("Fon fiyatları bugün zaten alındı.")
    piyasa["kaynak"] = {"bist": "TradingView (15 dk gecikmeli)", "abd": "TradingView", "fon": "TEFAS"}
    yeni["piyasa"] = piyasa
    yeni["oneriler"] = oneriler
    try:
        yeni["haberler"] = midas_haberleri(piyasa.get("bist") or {}, piyasa.get("abd") or {})
        yeni["haberZaman"] = zaman
        print("haber", len(yeni["haberler"]))
    except Exception as e:
        print("Haberler okunamadı:", e)
        hatalar["haber"] = str(e)[:200]
    yeni["hatalar"] = hatalar

    temiz = lambda v: {kk: vv for kk, vv in v.items() if "aman" not in kk} if isinstance(v, dict) else v
    karsilastir = lambda d: json.dumps({k: temiz(v) for k, v in d.items() if k in ("kur", "altin", "piyasa", "hatalar", "oneriler", "haberler")}, sort_keys=True, ensure_ascii=False)
    if karsilastir(yeni) == karsilastir(eski):
        print("Değişiklik yok.")
        return
    yeni["zaman"] = zaman
    with open(DOSYA, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, separators=(",", ":"))
    print("Güncellendi. Boyut:", len(json.dumps(yeni, ensure_ascii=False)), "bayt")


if __name__ == "__main__":
    main()
