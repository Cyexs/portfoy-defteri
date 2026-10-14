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
