import json, re, urllib.request
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(u, data=None, h=None):
    hh={"User-Agent":UA,"Accept-Language":"tr-TR,tr;q=0.9"}; hh.update(h or {})
    with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=hh), timeout=40) as r:
        return r.status, r.headers.get("content-type",""), r.read()
out={}
for u in ["https://www.getmidas.com/midasin-kulaklari/","https://www.getmidas.com/feed/","https://www.getmidas.com/wp-json/wp/v2/posts?per_page=3","https://www.getmidas.com/midasin-kulaklari/midas-ile-gun-sonu-jpm-akbnk-gs-cvkmd-unh-fonet-p-813836"]:
    try:
        s,ct,b=get(u); t=b.decode("utf-8","replace")
        info={"status":s,"ct":ct,"len":len(t),"basi":t[:300]}
        info["next_data"]= "__NEXT_DATA__" in t
        info["nuxt"]= "__NUXT__" in t
        m=re.findall(r'https?://[^"\'\s]+(?:api|json|graphql)[^"\'\s]*', t)[:15]
        info["api_url_ornek"]=m
        i=t.find("-p-813836") if "kulaklari/" in u and u.endswith("/") else -1
        if i>0: info["link_cevresi"]=t[max(0,i-1500):i+300]
        for kw in ["THYAO","AKBNK","%","degisim","change"]:
            j=t.find(kw)
            if j>0 and u.endswith("813836"): info["k_"+kw]=t[max(0,j-400):j+400]
        out[u]=info
    except Exception as e:
        out[u]={"hata":repr(e)[:300]}
try:
    body={"columns":["name","close","change","price_earnings_ttm","return_on_equity","market_cap_basic","dividends_yield_current","description"],"options":{"lang":"tr"},"range":[0,3],"sort":{"sortBy":"market_cap_basic","sortOrder":"desc"},"markets":["turkey"]}
    s,ct,b=get("https://scanner.tradingview.com/turkey/scan", json.dumps(body).encode(), {"Content-Type":"application/json","Origin":"https://www.tradingview.com","Referer":"https://www.tradingview.com/"})
    out["tv"]=json.loads(b)
except Exception as e: out["tv"]={"hata":repr(e)[:300]}
json.dump(out, open("sonda.json","w"), ensure_ascii=False, indent=1)
