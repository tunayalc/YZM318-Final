# YZM318 Final - Orange Doğal Dil Workflow Aracı

Bu proje, Orange Data Mining içinde çalışan doğal dil tabanlı bir workflow oluşturma aracıdır.

Amacımız, kullanıcının yazdığı isteği okuyup Orange Canvas üzerinde gerekli node'ları otomatik oluşturmak, node'lar arasındaki bağlantıları kurmak, workflow'u çalıştırılabilir `.ows` dosyası olarak kaydetmek ve aynı akışın PNG görsel çıktısını üretmektir.

## Projenin Amacı

Orange Data Mining'de veri madenciliği akışları normalde node'lar elle eklenip birbirine bağlanarak hazırlanır. Bu projede bu süreci doğal dil ile yönetilebilir hale getirdik.

Kullanıcı prompt alanına veri dosyasını, hedef değişkeni ve yapmak istediği işlemleri yazar. Araç bu metinden gerekli bilgileri çıkarır, Orange widget kataloğunu kullanır ve uygun workflow'u Canvas üzerine yerleştirir.

Örnek istek:

```text
/Users/ytuna/Desktop/WA_Fn-UseC_-Telco-Customer-Churn.csv dosyasını aç.
Bir müşteri terk tahmin çalışması istiyorum.
Hedef değişkeni Churn olarak seç, customerID sütununu ayıkla.
Eksik değerleri doldur, veriyi normalize et.
Logistic Regression, Random Forest ve Gradient Boosting ile karşılaştırma yap.
Test and Score ile değerlendir, Confusion Matrix ve ROC Analysis çıktılarını göster.
```

Bu istekle kurulan temel akış:

```text
File -> Select Columns -> Impute -> Continuize -> Test and Score

Logistic Regression -> Test and Score
Random Forest       -> Test and Score
Gradient Boosting   -> Test and Score

Test and Score -> Confusion Matrix
Test and Score -> ROC Analysis
```

## Geliştirilen Araç

Araç bir Orange add-on'u olarak geliştirildi.

- Add-on paketi: `orange3-nl-workflow`
- Orange Canvas kategorisi: `Prompt Workflow`
- Widget adı: `Prompt Workflow Builder`
- Ana widget dosyası: `orange3-nl-workflow/orangecontrib/nlworkflow/widgets/ownlworkflow.py`

Widget açıldığında kullanıcı prompt alanına talimatını yazar. CSV yolu, hedef değişken ve çıkarılacak kolonlar prompttan çözümlenir. Arayüzde görünen dataset, target ve ignored columns alanları manuel seçim için değil, çözümlenen bilgiyi göstermek içindir.

## Özellikler

- Doğal dil promptundan Orange workflow planı üretir.
- OpenAI API anahtarını yalnızca yerel ortam değişkeninden okur.
- Orange registry üzerinden yüklü widget'ları ve channel bilgilerini okur.
- Hatalı node veya bağlantı oluşursa `.ows` üretmeden önce doğrulama hatası verir.
- Prompt içindeki CSV, TSV veya XLSX dosya yolunu bulur.
- Dosya adıyla veya “datasetten şu CSV'yi seç” gibi ifadelerle dataset arayabilir.
- Prompt üzerine eklenen yeni talimatları dikkate alır; son dataset, hedef ve kolon talimatı uygulanır.
- `scatter plot`, `box plot`, `data table` gibi ek istekleri workflow'a node olarak ekleyebilir.
- `Prompt Workflow Builder` node'u Canvas üzerinde kalır; tekrar üretim yapılınca yalnızca oluşturulan workflow bölümü yenilenir.
- Workflow'u `.ows` olarak kaydeder.
- Workflow'un PNG görsel çıktısını üretir.
- Oluşturulan `.ows` dosyası Orange içinde tekrar açılabilir.

## Repo İçeriği

- `orange3-nl-workflow/`: Geliştirilen Orange add-on kaynak kodu.
- `artifacts/workflows/`: Örnek `.ows` dosyaları ve PNG çıktıları.
- `artifacts/datasets/`: Demo veri dosyası.
- `patches/`: Yerel Orange çalıştırma uyumluluğu için küçük patch.

Bu repoya Portakal uygulaması eklenmemiştir. Teslim kapsamı Orange içinde çalışan doğal dil workflow aracıdır.

## Kurulum

Önce Orange ortamı aktif olmalıdır. Ardından add-on geliştirme modunda kurulur:

```bash
cd orange3-nl-workflow
python -m pip install -e ".[test]"
```

Orange Canvas'ı açmak için:

```bash
python -m Orange.canvas --no-splash --no-welcome
```

Canvas açıldıktan sonra sol taraftaki `Prompt Workflow` kategorisinden `Prompt Workflow Builder` widget'ı eklenir.

## OpenAI Ayarı

API anahtarı repoya yazılmaz. Local ortamda ortam değişkeni veya `.env` dosyası ile verilir:

```bash
export OPENAI_API_KEY="<openai-api-anahtarınız>"
```

`.env` örneği:

```text
OPENAI_API_KEY=<openai-api-anahtarınız>
OPENAI_MODEL=<kullanmak-istediğiniz-openai-modeli>
```

Belirli bir OpenAI seçimi koda sabitlenmemiştir. İstenirse yerel ortam ayarlarıyla değiştirilebilir.

## Test

Add-on testleri:

```bash
cd orange3-nl-workflow
python -m pytest -q tests
```

Son yerel doğrulamada testler başarılı çalışmıştır:

```text
13 passed
```

Üretilen workflow dosyaları ayrıca Orange doğrulama ve headless çalıştırma adımlarıyla kontrol edilmiştir.

## Örnek Çıktılar

- `artifacts/workflows/WA_Fn-UseC_-Telco-Customer-Churn-workflow.ows`
- `artifacts/workflows/WA_Fn-UseC_-Telco-Customer-Churn-workflow.png`
- `artifacts/workflows/self-test-extended.ows`
- `artifacts/workflows/self-test-extended.png`
