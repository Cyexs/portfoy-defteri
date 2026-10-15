# Portföy Defteri

Midas portföyünü, aylık eklemelerini, dolar kurunu ve altın fiyatlarını takip eden kişisel portföy uygulaması.
Telefonda "Ana ekrana ekle" ile uygulama gibi kurulur, internet yokken de açılır. Veriler sadece o telefonda saklanır.

## Yayınlama (bir kez, ~5 dakika)

1. **Depo oluştur:** github.com → sağ üstte **+** → **New repository** → ad: `portfoy-defteri`, **Public** seç → **Create repository**.
2. **Dosyaları yükle:** Açılan sayfada **uploading an existing file** bağlantısına tıkla. Bu klasördeki her şeyi (`.github` klasörü dahil) sürükleyip bırak → **Commit changes**.
   - `.github` klasörü görünmüyorsa gizli dosyaları göster: Mac'te Finder'da `Cmd + Shift + .`, Windows'ta Dosya Gezgini → Görünüm → **Gizli öğeler**.
3. **Siteyi aç:** Depoda **Settings → Pages** → *Source*: **Deploy from a branch** → Branch: **main**, klasör: **/(root)** → **Save**.
   1–2 dakika sonra adresin hazır: `https://KULLANICI-ADIN.github.io/portfoy-defteri/`
4. **Fiyat güncelleyiciyi başlat:** Depoda **Actions** sekmesi → (istenirse workflow'ları etkinleştir) → **Fiyatları güncelle** → **Run workflow**.
   Bundan sonra her saat kendiliğinden çalışır.

## Telefona kurma

- **iPhone:** Adresi **Safari**'de aç → alttaki **Paylaş** → **Ana Ekrana Ekle**.
- **Android:** Adresi **Chrome**'da aç → sağ üstte **⋮** → **Ana ekrana ekle** (veya **Uygulamayı yükle**).

## Verilerini taşımak

claude.ai'deki Portföy Defteri'nde **Geçmiş → Yedek indir**, sonra yüklediğin uygulamada **Geçmiş → Yedekten yükle**.
Telefon değiştirmeden önce de aynı şekilde yedek al.

## Fiyatlar nereden geliyor?

- **Dolar kuru:** TCMB günlük kurları, döviz alış (TCMB her iş günü 15:30'da yayımlar).
- **Altın:** Uluslararası ons fiyatı × TCMB kuru ile hesaplanan gram altın; çeyrek, yarım, tam ve Cumhuriyet altını serbest piyasadaki ortalama oranlarla hesaplanır. Kuyumcu fiyatından biraz farklı olabilir.
- `scripts/fiyat_guncelle.py` dosyayı günceller, `.github/workflows/fiyatlar.yml` onu her saat çalıştırır.
- GitHub, depoda uzun süre hiç işlem olmazsa saatlik görevi durdurabilir. Fiyatlar güncellenmezse **Actions** sekmesinden görevi tekrar etkinleştir.

## Bu sürümde olmayanlar

Ekran görüntüsünden varlık okuma Claude'a bağlı olduğu için yalnızca claude.ai sürümünde çalışır. Burada varlıklar elle eklenir.

## Claude yorumu (API)

Uygulamadaki Claude yorumu ve ekran görüntüsü okuma, `api/` klasöründeki küçük bir Cloudflare Worker üzerinden çalışır.
Anthropic API anahtarı bu sunucuda gizli durur; uygulamanın içinde görünmez.

- **Model:** yorum için Claude Sonnet 5.5, ekran görüntüsü okuma için Claude Haiku 5.5.
- **Sınırlar (İstanbul saatine göre günlük):** kişi başı 3 yorum ve 5 görüntü okuma; tüm uygulama için toplam 60 istek.
  Değiştirmek için `api/wrangler.toml` içindeki `GUNLUK_YORUM`, `GUNLUK_OKU`, `GUNLUK_TOPLAM`.
- **Maliyet:** bir yorum en fazla ~2 sent, bir görüntü okuma 1 sentin altında. Toplam sınır her gün dolsa bile ayda en fazla ~30 $ eder; gerçek kullanımda çok daha az.
  Asıl güvence, Anthropic Console'da koyacağın aylık harcama sınırıdır.
- **Gizlilik:** sunucu portföy verisini, görüntüleri ve soruları saklamaz; kayıt (log) kapalıdır. Günlük sayaç için sadece
  rastgele cihaz kimliği ve IP'nin tek yönlü özeti tutulur, iki gün içinde silinir.

### Kurulum (bir kez, ~15 dakika)

1. **Anthropic API anahtarı:** https://console.anthropic.com → hesap aç → **Billing** → kredi yükle (en az 5 $) →
   **Limits** → aylık harcama sınırı koy (ör. 10 $) → **API Keys** → **Create Key** → anahtarı kopyala.
2. **Cloudflare hesabı:** https://dash.cloudflare.com → ücretsiz hesap aç → soldan **Workers & Pages** → bir kez aç
   (workers.dev alt alan adını seçmeni isterse seç).
   - **Account ID:** Workers & Pages sayfasının sağında **Account ID** → kopyala.
   - **API token:** sağ üstte profil → **My Profile** → **API Tokens** → **Create Token** → **Edit Cloudflare Workers** şablonu →
     **Use template** → **Continue to summary** → **Create Token** → kopyala.
3. **GitHub sırları:** bu depoda **Settings → Secrets and variables → Actions → New repository secret**, üç tane ekle:
   `ANTHROPIC_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`.
4. **Yayınla:** **Actions** → **API'yi yayınla** → **Run workflow**. 1–2 dakika sonra depoda `api.json` oluşur;
   uygulamayı yenileyince Yorum sekmesi ve "Görüntüden" düğmesi çalışır.

`api/` klasöründe bir değişiklik yapıldığında API kendiliğinden yeniden yayınlanır.
Anahtarı değiştirmek için GitHub'daki `ANTHROPIC_API_KEY` sırrını güncelleyip **API'yi yayınla**'yı yeniden çalıştır.
