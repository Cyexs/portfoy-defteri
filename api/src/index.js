// Portföy Defteri API: keeps the Anthropic key on the server and caps daily use.
// POST /yorum  {cihaz, ozet, soru}      -> streamed plain-text commentary
// POST /oku    {cihaz, gorseller:[{tip, veri}]} -> {varliklar:[...]} read from screenshots
// GET  /durum?cihaz=...                 -> remaining uses today
import { DurableObject } from 'cloudflare:workers';

const MODEL_YORUM = 'claude-sonnet-5-5';
const MODEL_OKU = 'claude-haiku-5-5';
const ANTHROPIC = 'https://api.anthropic.com/v1/messages';

const AI_TALIMAT = `Sen Türkçe konuşan, dikkatli bir portföy asistanısın. Aşağıdaki kişisel portföyü yorumla.
Kişinin yatırım hedefi uzun vade, risk toleransı orta (aksi belirtilmedikçe). Bugünün haberlerine, bilançolara veya canlı fiyatlara erişimin yok; yalnızca verilen sayılarla ve genel bilginle konuş, bilmediğin güncel bir rakamı uydurma.
Biçim: kısa başlıklar için "## " ile başlayan satırlar, maddeler için "- ", vurgu için **kalın**. Toplam 350-450 kelime.
Bölümler:
## Genel tablo (2-3 cümle)
## Güçlü yanlar
## Dikkat edilmesi gerekenler (yoğunlaşma, aynı işi yapan fonlar, kur ve enflasyon etkisi, zarardaki pozisyonlar gibi olgusal gözlemler)
## Bu ayki ekleme (hedef dağılıma göre aylık tutarın nasıl bölünebileceği, rakamlarla)
## İncelemeye değer eklemeler (2-4 öneri: varlık türü veya örnek araç; her birinin neden uygun olabileceği ve riski)
Kesin "al/sat" deme; "incelemeye değer" gibi ifadeler kullan. En sona tek satır: "Bu bir yatırım tavsiyesi değildir; karar sana aittir."
Portföy dışındaki konularda (kod, ödev, genel sohbet) yardım etme; kibarca yalnızca portföy hakkında konuşabileceğini söyle.`;

const OKU_TALIMAT = `Bu görüntüler bir yatırım uygulamasının (çoğunlukla Midas) portföy ekranından. Görünen her varlığı oku.
Sadece şu JSON'u döndür: {"varliklar":[{"kod":"THYAO","ad":"Türk Hava Yolları","grup":"bist","birim":"TL","adet":2,"fiyat":283.0,"maliyet":300.0}]}
Kurallar:
- Sayıları nokta ondalıklı JSON sayısı yaz. Ekranda Türkçe biçim olabilir: "1.234,56" = 1234.56, "0,2050" = 0.205.
- "fiyat" birim fiyat (güncel), "maliyet" birim başına ortalama maliyettir. Toplam pozisyon tutarını fiyat yerine yazma.
- "birim": ABD hisseleri ve ETF'ler (fiyat $ ile) için "USD", diğerleri "TL".
- "grup": ABD hisse/ETF → "kuresel"; Borsa İstanbul hisseleri ve hisse senedi fonları → "bist"; kira sertifikası, para piyasası, borçlanma araçları fonları → "kira"; altın veya kıymetli maden fonları → "altin". Emin değilsen fon adına göre tahmin et.
- Ekranda görünmeyen bir alanı uydurma; null yaz. Grup başlıklarını (ör. "ABD Hisseleri") varlık sayma.
- Aynı kod birden fazla görüntüde varsa bir kez yaz.
- Görüntü bir portföy ekranı değilse {"varliklar":[]} döndür.`;

const GORSEL_TIPLERI = ['image/jpeg', 'image/png', 'image/webp'];

/* ---------- daily counters: one Durable Object per Istanbul day ---------- */
export class Sayac extends DurableObject {
  // Atomically checks every limit and, only if all pass, counts the use.
  async harca(anahtarlar, limitler) {
    const simdi = await this.ctx.storage.get(anahtarlar);
    for (const k of anahtarlar) if ((simdi.get(k) || 0) >= limitler[k]) return { ok: false, asilan: k };
    const yeni = {};
    for (const k of anahtarlar) yeni[k] = (simdi.get(k) || 0) + 1;
    await this.ctx.storage.put(yeni);
    if (!(await this.ctx.storage.getAlarm())) await this.ctx.storage.setAlarm(Date.now() + 2 * 864e5);
    return { ok: true };
  }
  async geriVer(anahtarlar) {
    const simdi = await this.ctx.storage.get(anahtarlar);
    const yeni = {};
    for (const k of anahtarlar) yeni[k] = Math.max(0, (simdi.get(k) || 0) - 1);
    await this.ctx.storage.put(yeni);
  }
  async oku(anahtarlar) {
    const m = await this.ctx.storage.get(anahtarlar);
    return Object.fromEntries(anahtarlar.map(k => [k, m.get(k) || 0]));
  }
  async alarm() { await this.ctx.storage.deleteAll(); }
}

const gun = () => new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10); // Europe/Istanbul, no DST
const sayi = (v, d) => { const n = parseInt(v, 10); return Number.isFinite(n) && n >= 0 ? n : d; };
function limitler(env) {
  return { yorum: sayi(env.GUNLUK_YORUM, 3), oku: sayi(env.GUNLUK_OKU, 5), toplam: sayi(env.GUNLUK_TOPLAM, 60) };
}
async function ipOzeti(req) {
  const ip = req.headers.get('CF-Connecting-IP') || 'yok';
  const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('pd:' + ip));
  return [...new Uint8Array(h)].slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
}
// Each device gets the per-person limit; an IP gets three times that (shared Wi-Fi), and the whole app has a daily ceiling.
async function hakAnahtarlari(req, env, tur, cihaz) {
  const L = limitler(env), ip = await ipOzeti(req);
  const keys = [`c:${tur}:${cihaz}`, `i:${tur}:${ip}`, 'toplam'];
  return { keys, lim: { [keys[0]]: L[tur], [keys[1]]: L[tur] * 3, toplam: L.toplam } };
}
const sayacStub = (env) => env.SAYAC.get(env.SAYAC.idFromName(gun()));

/* ---------- http helpers ---------- */
function cors(req, env) {
  const izinli = String(env.IZINLI_KAYNAK || '').split(',').map(s => s.trim()).filter(Boolean);
  const o = req.headers.get('Origin') || '';
  return {
    'Access-Control-Allow-Origin': izinli.includes(o) ? o : izinli[0] || '',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin'
  };
}
const json = (req, env, body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(req, env), ...extra } });
const hata = (req, env, status, kod, mesaj) => json(req, env, { hata: kod, mesaj }, status);
const cihazGecerli = (c) => typeof c === 'string' && /^[a-zA-Z0-9-]{8,64}$/.test(c);

async function anthropic(env, body) {
  return fetch(env.ANTHROPIC_URL || ANTHROPIC, {
    method: 'POST',
    headers: { 'x-api-key': env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify(body)
  });
}

/* ---------- routes ---------- */
async function yorum(req, env) {
  let b; try { b = await req.json(); } catch { return hata(req, env, 400, 'gecersiz', 'İstek okunamadı.'); }
  if (!cihazGecerli(b.cihaz)) return hata(req, env, 400, 'gecersiz', 'Cihaz kimliği eksik.');
  const ozet = String(b.ozet || '').slice(0, 8000), soru = String(b.soru || '').trim().slice(0, 300);
  if (ozet.length < 20) return hata(req, env, 400, 'gecersiz', 'Portföy bilgisi eksik.');
  const { keys, lim } = await hakAnahtarlari(req, env, 'yorum', b.cihaz);
  const st = sayacStub(env), h = await st.harca(keys, lim);
  if (!h.ok) return h.asilan === 'toplam'
    ? hata(req, env, 503, 'kapasite', 'Bugünkü toplam yorum kapasitesi doldu. Yarın tekrar dene.')
    : hata(req, env, 429, 'limit', 'Bugünkü yorum hakkın doldu (günde ' + limitler(env).yorum + '). Yarın tekrar dene.');

  const input = AI_TALIMAT + (soru ? '\n\nKişinin sorusu (önce buna odaklan, sonra kısaca diğer bölümlere değin; toplam 300 kelimeyi geçme): ' + soru : '') + '\n\nPORTFÖY:\n' + ozet;
  const r = await anthropic(env, { model: MODEL_YORUM, max_tokens: 1400, stream: true, messages: [{ role: 'user', content: input }] });
  if (!r.ok || !r.body) {
    await st.geriVer(keys);
    return hata(req, env, 502, 'servis', r.status === 429 || r.status === 529 ? 'Claude şu an yoğun; biraz sonra tekrar dene.' : 'Yorum oluşturulamadı; tekrar dene.');
  }
  // Turn Anthropic's SSE into plain text so the app can append chunks as they arrive.
  const enc = new TextEncoder(), dec = new TextDecoder();
  let tampon = '';
  const donustur = new TransformStream({
    transform(chunk, ctl) {
      tampon += dec.decode(chunk, { stream: true });
      let i;
      while ((i = tampon.indexOf('\n\n')) >= 0) {
        const olay = tampon.slice(0, i); tampon = tampon.slice(i + 2);
        const veri = olay.split('\n').find(l => l.startsWith('data:'));
        if (!veri) continue;
        try { const j = JSON.parse(veri.slice(5)); if (j.type === 'content_block_delta' && j.delta && j.delta.type === 'text_delta') ctl.enqueue(enc.encode(j.delta.text)); } catch {}
      }
    }
  });
  const kalan = Math.max(0, lim[keys[0]] - ((await st.oku([keys[0]]))[keys[0]]));
  return new Response(r.body.pipeThrough(donustur), { headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store', 'X-Kalan': String(kalan), 'Access-Control-Expose-Headers': 'X-Kalan', ...cors(req, env) } });
}

async function oku(req, env) {
  let b; try { b = await req.json(); } catch { return hata(req, env, 400, 'gecersiz', 'İstek okunamadı.'); }
  if (!cihazGecerli(b.cihaz)) return hata(req, env, 400, 'gecersiz', 'Cihaz kimliği eksik.');
  const g = Array.isArray(b.gorseller) ? b.gorseller.slice(0, 4) : [];
  if (!g.length || g.some(x => !GORSEL_TIPLERI.includes(x.tip) || typeof x.veri !== 'string' || x.veri.length > 2_000_000))
    return hata(req, env, 400, 'gorsel', 'Görüntü okunamadı; JPG ya da PNG ekran görüntüsü seç.');
  const { keys, lim } = await hakAnahtarlari(req, env, 'oku', b.cihaz);
  const st = sayacStub(env), h = await st.harca(keys, lim);
  if (!h.ok) return h.asilan === 'toplam'
    ? hata(req, env, 503, 'kapasite', 'Bugünkü toplam kapasite doldu. Yarın tekrar dene ya da varlıkları elle ekle.')
    : hata(req, env, 429, 'limit', 'Bugünkü görüntü okuma hakkın doldu (günde ' + limitler(env).oku + '). Varlıkları elle ekleyebilirsin.');

  const content = [...g.map(x => ({ type: 'image', source: { type: 'base64', media_type: x.tip, data: x.veri } })), { type: 'text', text: OKU_TALIMAT }];
  const r = await anthropic(env, { model: MODEL_OKU, max_tokens: 3000, messages: [{ role: 'user', content }] });
  if (!r.ok) { await st.geriVer(keys); return hata(req, env, 502, 'servis', 'Görüntü okunamadı; biraz sonra tekrar dene.'); }
  const j = await r.json();
  const metin = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  const m = metin.match(/\{[\s\S]*\}/);
  let sonuc = null; try { sonuc = m ? JSON.parse(m[0]) : null; } catch {}
  if (!sonuc || !Array.isArray(sonuc.varliklar)) return hata(req, env, 422, 'okunamadi', 'Görüntüden varlık listesi çıkarılamadı; daha net bir ekran görüntüsü dene.');
  return json(req, env, { varliklar: sonuc.varliklar.slice(0, 100) });
}

async function durum(req, env) {
  const cihaz = new URL(req.url).searchParams.get('cihaz');
  const L = limitler(env);
  if (!cihazGecerli(cihaz)) return json(req, env, { yorum: L.yorum, oku: L.oku });
  const s = await sayacStub(env).oku([`c:yorum:${cihaz}`, `c:oku:${cihaz}`]);
  return json(req, env, { yorum: Math.max(0, L.yorum - s[`c:yorum:${cihaz}`]), oku: Math.max(0, L.oku - s[`c:oku:${cihaz}`]) });
}

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(req, env) });
    if (!env.ANTHROPIC_API_KEY) return hata(req, env, 503, 'ayar', 'Sunucu henüz ayarlanmadı.');
    try {
      if (req.method === 'POST' && pathname === '/yorum') return await yorum(req, env);
      if (req.method === 'POST' && pathname === '/oku') return await oku(req, env);
      if (req.method === 'GET' && pathname === '/durum') return await durum(req, env);
      if (req.method === 'GET' && pathname === '/') return json(req, env, { ad: 'Portföy Defteri API', durum: 'çalışıyor' });
      return hata(req, env, 404, 'yok', 'Böyle bir adres yok.');
    } catch (e) {
      return hata(req, env, 500, 'sunucu', 'Beklenmeyen bir hata oldu; tekrar dene.');
    }
  }
};
