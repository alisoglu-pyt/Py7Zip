# Py7-Zip

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-Tkinter-FF6F00)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-0078D4)]()
[![Languages](https://img.shields.io/badge/Languages-10-success)]()
[![License](https://img.shields.io/badge/License-LGPL--2.1-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-orange)]()

**Python + Tkinter ile yazılmış modern, çok dilli ve çapraz platform arşiv yöneticisi.**

Py7-Zip, [mcmilk/7-Zip](https://github.com/mcmilk/7-Zip) deposundaki 7-Zip C++
kaynak ağacından (codec'ler, arşiv biçimleri ve dosya yöneticisi) esinlenerek
geliştirilmiş **bağımsız bir Python yeniden yazımıdır**. Amaç; 7-Zip'in tanıdık
kullanım deneyimini, **saf Python** bir motor ve **Windows Gezgini tarzı
klasik-modern** bir Tkinter arayüzüyle sunmaktır.

> 7-Zip'in C++ çekirdeği (LZMA/LZMA2, BCJ, AES-256 vb.) satır satır Python'a
> çevrilmedi. Arşiv işlemleri için `py7zr` ve Python standart kütüphanesi
> (`zipfile`, `tarfile`, `gzip`, `bz2`, `lzma`) kullanılır.

---

## Ekran görüntüleri

<p align="center">
  <img src="/screenshot.png" alt="Py7-Zip ana pencere" width="760">
</p>

<p align="center">
  <img src="/screenshot-progress.png" alt="Py7-Zip ana pencere Koyu Tema" width="360">
  
</p>

---

## Öne çıkan özellikler

- 🎨 **Klasik-modern arayüz** — Windows Gezgini / 7-Zip görünümü, açık gri araç
  çubuğu, renkli simgeler, ayrıntı listesi; isteğe bağlı nötr koyu tema.
- 🌍 **10 dil** — Türkçe, English, Deutsch, Français, Español, Português,
  中文, 한국어, Azərbaycanca, Türkmençe. Dil çalışma anında değiştirilir.
- 🗂 **Geniş biçim desteği** — 7z, zip, tar, tar.gz, tar.bz2, tar.xz, gz, bz2, xz.
- 📦 **Oluşturma** — sıkıştırma düzeyi ve yöntem seçimi (LZMA2, LZMA, Deflate,
  BZip2, PPMD, Copy; zip için Deflate/Store/BZip2/LZMA).
- 🔐 **7z AES-256** — parola ve isteğe bağlı dosya adı şifreleme.
- 🧩 **Parçalı arşivler** — MB veya GB cinsinden parça boyutu;
  `arsiv.7z.001`, `.002`, … biçiminde 7-Zip uyumlu çoklu cilt.
- 📊 **İlerleme penceresi** — yüzde göstergesi, işlenen dosya adı ve İptal.
- 📤 **Çıkarma** — tümü/seçilenler, üzerine yazma, arşiv adıyla alt klasör.
- ➕ **Ekleme / silme** — 7z, zip ve tar ailelerinde arşiv güncelleme.
- 🧪 **Arşiv testi** — CRC/bütünlük kontrolü.
- 👁 **Önizleme** — metin/görsel önizleme, harici uygulamayla açma.
- 🔎 **Gezinme** — dosya sistemi ve arşiv içi klasörler, geri/ileri, arama,
  sıralanabilir sütunlar, bağlam menüsü.
- ⌨️ **Klavye kısayolları** — `Ctrl+O`, `Ctrl+N`, `Ctrl+E`, `Ctrl+A`, `Ctrl+F`,
  `F5`, `Backspace`, `Enter`, `Delete`, `Alt+Enter`, `Ctrl+Q`.
- 💾 **Kalıcı ayarlar** — dil, tema, son klasörler, sıralama, pencere boyutu
  (`%APPDATA%\Py7Zip\settings.json` veya `~/.config/py7zip/settings.json`).

---

## Desteklenen biçimler

| Biçim | Listele | Çıkar | Oluştur | Ekle | Sil | Şifre |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 7z | ✅ | ✅ | ✅ | ✅¹ | ✅¹ | ✅ AES-256 |
| zip | ✅ | ✅ | ✅ | ✅ | ✅ | okuma ✅ / yazma ❌² |
| tar | ✅ | ✅ | ✅ | ✅¹ | ✅¹ | ❌ |
| tar.gz / tar.bz2 / tar.xz | ✅ | ✅ | ✅ | ✅¹ | ✅¹ | ❌ |
| gz / bz2 / xz | ✅ | ✅ | ✅ (tek dosya) | ❌ | ❌ | ❌ |
| Parçalı `.001` ciltleri | ✅ | ✅ | ✅ | ❌³ | ❌³ | ✅ (7z) |

¹ 7z ve sıkıştırılmış tar güncellemeleri, güvenilirlik için arşivi geçici
klasöre açıp yeniden oluşturur. Büyük arşivlerde bu işlem zaman alabilir.  
² Python'un `zipfile` modülü yazarken parola şifrelemesi desteklemez; parola
korunan zip arşivleri **okunabilir**.  
³ Parçalı arşivlerde ekleme/silme desteklenmez; parçalar `.001` dosyası
seçilerek açılır.

---

## Parçalı (çoklu cilt) arşivler

“Yeni Arşiv” penceresinde **Parçalara böl (çoklu cilt)** seçeneğini işaretleyin
ve parça boyutunu **MB** veya **GB** olarak girin.

- Parçalar: `arsiv.7z.001`, `arsiv.7z.002`, …
- Açmak için `.001` dosyasını seçin; Py7-Zip ciltleri otomatik birleştirir.
- 7z ve zip ciltleri resmî 7-Zip ile doğrudan açılabilir.
- `tar.gz` gibi iç içe biçimlerde 7-Zip önce gzip katmanını çıkarır.

---

## Diller

| Kod | Dil | Kod | Dil |
|---|---|---|---|
| `tr` | Türkçe | `pt` | Português |
| `en` | English | `zh` | 中文 |
| `de` | Deutsch | `ko` | 한국어 |
| `fr` | Français | `az` | Azərbaycanca |
| `es` | Español | `tk` | Türkmençe |

Dil; **Görünüm → Dil**, **Araçlar → Ayarlar** veya komut satırından
`--lang de` / `--lang zh` / … ile değiştirilebilir.

---

## Kurulum ve çalıştırma

Gereksinimler: **Python 3.9+** ve Tkinter.
(Windows'ta resmî Python kurulumuyla gelir; Debian/Ubuntu'da `sudo apt install python3-tk`.)

```bash
git clone <depo-adresi>
cd Py7Zip

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

python -m pip install -r requirements.txt
python -m py7zip
```

Bir arşiv veya klasörle başlatmak için:

```bash
python -m py7zip "C:\yol\arsiv.7z"
python -m py7zip --lang en --theme light
```

---

## Windows derlemesi

```powershell
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

Tek dosya EXE:

```powershell
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1 -OneFile
```

| Mod | Çıktı |
|---|---|
| onedir (varsayılan) | `dist\Py7Zip\Py7Zip.exe` |
| onefile (`-OneFile`) | `dist\Py7Zip.exe` |

Betik bağımlılıkları kurar, ikonu üretir ve `build\py7zip.spec` ile
PyInstaller'ı çalıştırır. `build\build_windows.bat` dosyasına çift tıklayarak
da derleyebilirsiniz.

---

## Linux derlemesi

Linux derlemesi **Linux üzerinde** çalıştırılmalıdır (PyInstaller çapraz
derleme yapmaz):

```bash
bash build/linux/build_linux.sh
# bağımlılık kurmadan:
bash build/linux/build_linux.sh --no-install
```

Çıktılar (`dist/`):

| Ürün | Dosya |
|---|---|
| PyInstaller paketi | `Py7Zip/` (çalıştırılabilir: `Py7Zip/Py7Zip`) |
| Taşınabilir arşiv | `py7zip-1.2.0-linux-x86_64.tar.gz` |
| Debian paketi | `py7zip_1.2.0_amd64.deb` (`dpkg-deb` varsa) |
| AppImage | `Py7Zip-1.2.0-x86_64.AppImage` (`appimagetool` varsa) |

AppImage üretmek için `appimagetool` `PATH` üzerinde olmalıdır:
<https://github.com/AppImage/appimagetool/releases>.

---

## Testler

```bash
python tests/smoke_test.py          # motor: tüm biçimler, parça, şifreleme
python tests/dialogs_smoke_test.py  # diyaloglar
python tests/ui_smoke_test.py       # arayüz, dil geçişleri, ilerleme
python -m py7zip --selftest         # paketlenmiş öz-test
```

Paketlenmiş uygulamada:

```powershell
dist\Py7Zip\Py7Zip.exe --selftest      # Windows
./dist/Py7Zip/Py7Zip --selftest        # Linux
```

`--selftest`; 7z/zip/tar/gz işlemlerini, AES-256 şifrelemeyi, parçalı arşivleri,
10 dili, ilerleme raporlamayı ve kendini arşivleme korumasını doğrular.

---

## Proje yapısı

```
py7zip/
├── __init__.py          Sürüm bilgisi
├── __main__.py          python -m py7zip
├── main.py              CLI / giriş noktası
├── i18n.py              Çeviri çekirdeği
├── locales/             de, fr, es, pt, zh, ko, az, tk
├── settings_store.py    JSON ayar kalıcılığı
├── utils.py             Biçimlendirme ve işletim sistemi yardımcıları
├── engine/
│   ├── formats.py       Biçim kaydı, parça algılama
│   ├── entries.py       Normalize arşiv öğeleri
│   └── archive.py       py7zr + stdlib arşiv motoru
├── ui/
│   ├── theme.py         Klasik-modern açık/koyu tema
│   ├── icons.py         Bağımlılıksız vektörel simgeler
│   ├── widgets.py       Durum çubuğu, kenar çubuğu, araç ipuçları
│   ├── progress.py      Yüzde göstergeli ilerleme penceresi
│   ├── preview.py       Metin/görsel önizleme
│   ├── dialogs.py       Yeni arşiv, çıkarma, ayarlar, parola, özellikler
│   └── main_window.py   Ana pencere ve eylemler
└── resources/icon.png   Uygulama simgesi

build/
├── py7zip.spec          PyInstaller tanımı
├── launcher.py          Paketleme giriş noktası
├── make_icon.py         PNG/ICO üretici
├── build_windows.ps1    Windows derleme
├── build_windows.bat    Windows çift tık
└── linux/
    ├── build_linux.sh   Linux + tar.gz/deb/AppImage
    └── py7zip.desktop   Masaüstü girdisi

tests/                   Motor, diyalog, arayüz ve ekran görüntüsü testleri
```

---

## Sınırlamalar

- RAR, ISO, CAB, MSI gibi biçimler **desteklenmez** (7-Zip'in C++ codec'leri
  gerekir).
- zip yazarken parola şifrelemesi yoktur.
- 7z ve sıkıştırılmış tar arşivlerinde ekleme/silme, arşivi yeniden oluşturur.
- Parçalı arşivlerde ekleme/silme desteklenmez.
- 7-Zip uyumluluğu için 7z yöntem listesinde **Brotli/Zstd sunulmaz**.
- Arşiv kaynak klasörün içine oluşturulursa geçici klasörde üretilip taşınır;
  böylece arşiv kendisini eklemez.
- Görsel önizleme JPEG/WebP için `pillow` kurulduğunda genişler.

---

## Geliştirici

**Bekir Alişoğlu**  
📧 [alisoglu@yahoo.com](mailto:alisoglu@yahoo.com)

---

## Lisans

Bu proje **GNU LGPL-2.1** altında dağıtılır. Ayrıntılar için
[`LICENSE`](LICENSE) dosyasına bakın. `py7zr` ve diğer üçüncü taraf
bileşenler kendi lisanslarına tabidir.

---

## English summary

**Py7-Zip** is an independent, pure-Python re-imagining of the 7-Zip desktop
experience, built with Tkinter. It uses `py7zr` and the standard library for
archive operations and supports 7z, zip, tar, tar.gz/bz2/xz, gz, bz2 and xz.
The UI ships in **10 languages**, offers a classic Windows Explorer-style
light theme (plus a neutral dark theme), archive browsing, creation,
extraction, add/delete, integrity testing, a preview pane, a percentage-based
progress window and **multi-volume archives** (`.001`, `.002`, …).

```bash
pip install -r requirements.txt
python -m py7zip
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

```bash
# Linux (run on Linux)
bash build/linux/build_linux.sh
```

**Developer:** Bekir Alişoğlu — [alisoglu@yahoo.com](mailto:alisoglu@yahoo.com)  
**License:** LGPL-2.1
