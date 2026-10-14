import json, urllib.request
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
def post(ep, body):
    r=urllib.request.Request("https://www.tefas.gov.tr"+ep, data=json.dumps(body).encode(), headers={"User-Agent":UA,"Content-Type":"application/json","Accept":"application/json, text/plain, */*"})
    with urllib.request.urlopen(r, timeout=40) as x: return json.loads(x.read())
out={}
try:
    b=post("/api/funds/fonGetiriBazliBilgiGetir", {"dil":"TR","fonTipi":"YAT","kurucuKodu":None,"sfonTurKod":None,"fonTurAciklama":None,"islem":1,"fonTurKod":None,"fonGrubu":None,"donemGetiri1a":"1","donemGetiri3a":"1","donemGetiri6a":"1","donemGetiri1y":"1","donemGetiriyb":"1","donemGetiri3y":"1","donemGetiri5y":"1","basTarih":None,"bitTarih":None,"calismaTipi":2,"getiriOrani":"1"})
    rows=b.get("resultList") or []
    out["liste_adet"]=len(rows); out["liste_ornek"]=rows[:2]
except Exception as e: out["liste_hata"]=repr(e)[:300]
try:
    b=post("/api/funds/fonFiyatBilgiGetir", {"fonKodu":"RBV","dil":"TR","periyod":1})
    rows=b.get("resultList") or []
    out["fiyat_adet"]=len(rows); out["fiyat_son"]=rows[-2:]
except Exception as e: out["fiyat_hata"]=repr(e)[:300]
json.dump(out, open("tefas_deneme.json","w"), ensure_ascii=False, indent=1)
