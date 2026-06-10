# Orange3 NL Workflow

`orange3-nl-workflow`, Orange Canvas içinde çalışan `Prompt Workflow Builder` widget'ını ekleyen bir Orange add-on'udur.

Bu add-on'un amacı, kullanıcının doğal dilde yazdığı veri madenciliği isteğini Orange workflow'una çevirmektir. Araç Orange'ın kendi registry, scheme ve `.ows` yazma mekanizmalarını kullanarak node'ları oluşturur, bağlantıları kurar ve çıktı dosyalarını üretir.

## Widget Bilgisi

- Category: `Prompt Workflow`
- Widget: `Prompt Workflow Builder`
- Entry point: `orange.widgets`
- Ana dosya: `orangecontrib/nlworkflow/widgets/ownlworkflow.py`

## Kullanıcı Akışı

1. Orange Canvas açılır.
2. `Prompt Workflow` kategorisinden `Prompt Workflow Builder` eklenir.
3. Kullanıcı prompt alanına doğal dil talimatını yazar.
4. `Generate` butonuna basılır.
5. Araç dataset bilgisini prompttan çözer.
6. Workflow Canvas üzerine çizilir.
7. `.ows` ve PNG çıktısı oluşturulur.

CSV, target ve ignored columns alanları manuel giriş alanı değildir. Bu alanlar prompttan çözülen bilgiyi kullanıcıya göstermek için kullanılır.

## Örnek Prompt

```text
/Users/ytuna/Desktop/WA_Fn-UseC_-Telco-Customer-Churn.csv dosyasını aç.
Bir müşteri terk tahmin çalışması istiyorum.
Hedef değişkeni Churn olarak seç, customerID sütununu ayıkla.
Eksik değerleri doldur, veriyi normalize et.
Logistic Regression, Random Forest ve Gradient Boosting ile karşılaştırma yap.
Test and Score ile değerlendir, Confusion Matrix ve ROC Analysis çıktılarını göster.
```

## Oluşturulan Temel Akış

```text
File -> Select Columns -> Impute -> Continuize -> Test and Score
Logistic Regression -> Test and Score
Random Forest -> Test and Score
Gradient Boosting -> Test and Score
Test and Score -> Confusion Matrix
Test and Score -> ROC Analysis
```

## Prompt Davranışı

Widget prompt alanının son halini dikkate alır.

- Yeni dataset veya dosya belirtilirse onu kullanır.
- Dosya adıyla dataset arayabilir.
- “Datasetten telco customer churn CSV'yi seç” gibi ifadeleri çözümleyebilir.
- Son hedef değişken talimatını uygular.
- `scatter plot`, `box plot`, `data table` gibi ek node isteklerini workflow'a ekleyebilir.
- Generate tekrar çalıştırıldığında önceki oluşturulmuş node'lar temizlenir ve yenileri eklenir.
- `Prompt Workflow Builder` node'u Canvas üzerinde korunur.

## Mimari

- `core/planner.py`: OpenAI çağrısı ve yerel akış üretimi.
- `core/models.py`: Workflow plan veri yapıları.
- `core/registry.py`: Orange widget registry kataloğu.
- `core/validation.py`: Node ve channel doğrulama.
- `core/compiler.py`: Workflow planını Orange Scheme ve `.ows` dosyasına dönüştürme.
- `core/exporter.py`: `.ows` dosyasından PNG/SVG görsel üretimi.
- `core/canvas.py`: Canvas'a ekleme, açma ve headless çalıştırma yardımcıları.
- `core/dataset_resolver.py`: Prompttan dataset yolu veya dosya adı çözümleme.
- `core/recipes.py`: Sınıflandırma ve churn akışı oluşturma.
- `core/settings.py`: Bilinen widget ayarlarını Orange ayar mekanizmasıyla paketleme.

## OpenAI Ayarı

API anahtarı repoya eklenmez. Local ortamda ortam değişkeni olarak verilir:

```bash
export OPENAI_API_KEY="<openai-api-anahtarınız>"
```

`.env` kullanılacaksa:

```text
OPENAI_API_KEY=<openai-api-anahtarınız>
OPENAI_MODEL=<kullanmak-istediğiniz-openai-modeli>
```

Belirli bir OpenAI seçimi koda sabitlenmemiştir. Yerel ortam ayarlarıyla değiştirilebilir.

## Kurulum

```bash
python -m pip install -e ".[test]"
```

Orange Canvas:

```bash
python -m Orange.canvas --no-splash --no-welcome
```

## Test

```bash
python -m pytest -q tests
```

Son yerel doğrulamada testler başarılıdır:

```text
13 passed
```
