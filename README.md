# Veri Merkezi CFD Programı

Ubuntu üzerinde çalışan, veri merkezi / server odası **soğuk koridor – sıcak
koridor** ısıl-akış (CFD) analizini uçtan uca yöneten bir web uygulaması.
Oda, kabin (rack) ve koridor bilgilerini girip, odaya ait teknik çizim
PDF'lerini yükleyerek bu verilerden otomatik olarak çalıştırılabilir bir
**OpenFOAM** CFD case'i üretir.

## Neden OpenFOAM (Ansys Fluent / Abaqus-CFD yerine)?

Ansys Fluent ve Abaqus/CFD ticari, lisanslı yazılımlardır ve bu programın
onları otomatik kuramaz/çalıştıramaz. Bunun yerine bu proje, aynı
mühendislik iş akışını (**geometri → mesh → sınır şartları → çözüm →
sonuç**) Ubuntu'da tamamen açık kaynak ve lisanssız çalışan **OpenFOAM**
çözücüsü (`buoyantSimpleFoam`) ile hayata geçirir. Üretilen case yapısı
(blockMeshDict, sınır şartları, ısı kaynakları vb.) kavramsal olarak
Fluent/Abaqus'taki "zone tanımla / sınır şartı ata / çöz" mantığını izler.

## Modelleme yaklaşımı

- **Oda**: uzunluk (X), genişlik (Y), yükseklik (Z) ve **döşeme yüksekliği**
  (raised floor / yükseltilmiş döşeme plenum yüksekliği — CFD hacminin
  kendisine dahil edilmez, mühendislik özetinde referans olarak tutulur).
- **Kabinler (rack)**: konum, boyut, IT güç yükü (kW). Kabinler katı geometri
  olarak mesh'e işlenmez; ayak izlerine karşılık gelen hücre bölgeleri
  (`cellSet` + `fvOptions` ile `scalarSemiImplicitSource`) üzerinden ısı
  kaynağı olarak modellenir. Bu, oda ölçekli soğuk/sıcak koridor analizlerinde
  hesap maliyetini makul tutan, yaygın kullanılan basitleştirilmiş bir
  yaklaşımdır.
- **Koridorlar**: soğuk koridor (perfore döşeme fayanslarından üflenen
  soğutulmuş hava — CFD'de `soguk_giris` inlet sınırı) ve sıcak koridor
  (dönüş havası bölgesi). Kapatma (containment) bilgisi tutulur ve
  mühendislik özetinde uyarı üretir.
- **Mesh**: döşeme izdüşümü fayans boyutuna göre bir sütun ızgarasına
  bölünür; her sütun döşemeden tavana tek bir yapılandırılmış (structured)
  hex blok olarak mesh'lenir. Taban yüzü soğuk koridor altındaysa `inlet`,
  değilse `wall` (duvar) olarak işaretlenir. Tavan tamamı dönüş/egzoz
  (`tavan_donus`, outlet) olarak alınır.
- **Çözücü**: `buoyantSimpleFoam` (kaldırma kuvvetli, sıkıştırılabilir,
  kararlı hal), k-epsilon türbülans modeli.

## Kurulum (Ubuntu)

```bash
git clone <bu-repo>
cd foam
chmod +x scripts/install_ubuntu.sh
./scripts/install_ubuntu.sh
```

Bu betik hem Python bağımlılıklarını (bir `.venv` içinde) hem de OpenFOAM'ı
(`openfoam.org` apt deposundan) kurar. OpenFOAM olmadan da uygulama tam
işlevseldir; yalnızca "mesh oluştur" ve "çöz" adımları OpenFOAM ister.

Sadece web uygulamasını (OpenFOAM olmadan) denemek isterseniz:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
source .venv/bin/activate
# OpenFOAM kuruluysa, mesh/çöz adımlarından önce ortamı yükleyin:
source /opt/openfoam11/etc/bashrc   # (kurulu sürüme göre)
./run.sh
```

Tarayıcıda `http://localhost:8000` adresini açın.

## Kullanım akışı

1. **Proje** oluşturun (bir veri merkezi sahası).
2. Proje içinde **oda** oluşturun: boyutlar, döşeme yüksekliği, fayans
   boyutu, CRAC üfleme sıcaklığı/debisi.
3. Oda sayfasında **kabinleri** (rack) ve **koridorları** (soğuk/sıcak, konum,
   kapatma tipi) girin.
4. Varsa kat planı / teknik çizim **PDF**'ini yükleyin (referans/dokümantasyon
   olarak odaya eklenir ve tarayıcıda görüntülenir).
5. **"Yeni CFD case üret"** ile OpenFOAM case dosyaları otomatik üretilir; alt
   kısımda mühendislik özeti (toplam IT yükü, tahmini koridor ΔT, eksik
   koridor/kapatma uyarıları) gösterilir.
6. OpenFOAM kuruluysa **"Mesh oluştur"** (`blockMesh` + `checkMesh` +
   `topoSet`) ve **"Çöz"** (`buoyantSimpleFoam`) butonlarıyla analizi
   doğrudan arayüzden çalıştırabilirsiniz; log çıktısı sayfada gösterilir.
7. Sonuçları görselleştirmek için case dizinindeki `case.foam` dosyasını
   ParaView (`paraFoam`) ile açın (bu depoya dahil değildir, ayrıca
   kurulmalıdır: `sudo apt install paraview`).

## Sınırlamalar

- PDF yükleme, kat planlarından ölçüleri **otomatik okumaz** — teknik çizimler
  görsel/CAD tabanlı olduğundan güvenilir otomatik çıkarım yapılamaz; PDF
  yalnızca referans belge olarak saklanır, veriler formdan girilir.
- Kabinler ısı kaynağı olarak modellenir; kabin gövdesinin hava akışına fiziksel
  direnci (blokaj) mesh'e işlenmez.
- Tüm tavan tek bir dönüş/egzoz yüzeyi olarak alınır; ayrı dönüş ızgaraları
  modellenmez.
- Büyük odalarda (küçük fayans boyutu + büyük alan) blok sayısı sınırlıdır
  (varsayılan üst sınır 3000 blok); gerekirse fayans boyutunu büyütün.

## Testler

```bash
source .venv/bin/activate
pip install pytest
pytest tests/ -v
```

## Dizin yapısı

```
app/
  main.py              FastAPI uygulaması ve tüm HTTP rotaları
  models.py            SQLAlchemy veri modeli (Proje/Oda/Kabin/Koridor/Belge/CfdRun)
  cfd/
    geometry.py         oda+kabin+koridor -> mesh ızgarası + rack ısı bölgeleri
    case_generator.py   OpenFOAM case dosyalarını üretir
    runner.py           blockMesh/checkMesh/topoSet/buoyantSimpleFoam çalıştırıcı
  templates/            Jinja2 HTML sayfaları
  static/                CSS
scripts/install_ubuntu.sh   Ubuntu kurulum betiği
tests/                  pytest birim testleri
```
