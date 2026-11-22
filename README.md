# Galeri Foto She Runs The World 2026

Website untuk mencari foto lari dengan nomor BIB. Tidak ada server atau database: halaman, index BIB, dan foto semuanya file statis yang dilayani CDN Cloudflare, jadi aman untuk ribuan pengunjung bersamaan.

```
Google Drive ──► originals/<titik>/ ──► process_photos.py ──► output/thumb, web, full ──► upload_r2.sh ──► R2
(foto asli)                              (OCR BIB + resize)   output/photos.csv
                                                                   │
                                                                   ▼
                                                            build_index.py ──► site/data ──► Cloudflare Pages
```

## Isi repo

```
site/                   SEMUA yang di-deploy ke Cloudflare Pages
  index.html, 404.html
  config.js             semua pengaturan
  _redirects            /bib/54326 diarahkan ke index.html
  _headers              aturan cache
  assets/               style.css, app.js, logo
  data/                 index pencarian (hasil build_index.py)
  pilot-photos/         uji coba 50 foto asli CAM AAN (thumb, web 2048 px, full 4000 px)
tools/                  TIDAK di-deploy
  process_photos.py     OCR BIB + 3 ukuran foto + photos.csv
  build_index.py        photos.csv -> site/data
  upload_r2.sh          upload output/ ke R2 dengan rclone
  run_pipeline.py       SATU perintah: download Drive -> OCR -> index -> upload R2
  event.json            pengaturan run_pipeline (titik per fotografer, rentang BIB, R2)
  check_live.py         cek galeri online sebelum link disebar
  load_test.py          uji beban (banyak pencarian bersamaan)
  requirements.txt
  sample/               contoh photos.csv dan participants.csv
```

Folder `originals/` dan `output/` tidak masuk git (lihat `.gitignore`).

## Coba di komputer sendiri

```bash
cd site
python3 -m http.server 8000
```

Buka http://localhost:8000. Data bawaan adalah uji coba 50 foto asli dari CAM AAN: cari BIB **54326**, **52501**, atau **10785**. Di localhost link BIB berformat `/?bib=54326`; setelah online otomatis jadi `/bib/54326`.

## Cara cepat (satu perintah)

Sekali saja: pasang Python 3.10–3.13 dan [rclone](https://rclone.org/install/), buat remote rclone `gdrive` (Google Drive) dan `r2` (langkah 4), lalu:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
```

Isi `tools/event.json`: titik foto per fotografer (`point_map`), rentang BIB, nama bucket. Lalu dari folder utama repo:

```bash
python3 tools/run_pipeline.py --download --upload
```

Perintah ini mengambil foto dari Drive, menjalankan OCR + resize, membangun index ke `site/data`, dan meng-upload foto ke R2. Kalau terputus, jalankan perintah yang sama lagi: yang sudah selesai dilewati. Setelah selesai, commit dan push `site/data`, lalu Cloudflare akan deploy otomatis.

Kalau hanya mengubah rentang BIB atau daftar hapus: `python3 tools/run_pipeline.py --index-only`.

### Foto menyusul (misalnya besok ada upload baru)

Jalankan perintah yang sama lagi di **laptop yang sama**. Hanya foto baru yang di-download, di-OCR, dan di-upload; index dibangun ulang dalam beberapa detik. Syaratnya:

- **Jangan hapus folder `output/`** (berisi `photos.csv` = catatan foto yang sudah diolah, plus hasil thumb/web/full). Folder `originals/` boleh dihapus kalau disk penuh, tapi rclone akan men-download ulang semuanya di putaran berikutnya.
- Kalau ada file hasil yang hilang atau rusak (misalnya laptop mati di tengah proses), foto itu otomatis diolah ulang.
- Setelah selesai, commit dan push `site/data` lagi supaya website ter-update.

Bagian di bawah menjelaskan tiap langkah secara terpisah.

## Langkah dari foto asli sampai online

### 1. Ambil foto asli

Kumpulkan foto ke `originals/`, satu subfolder per titik foto. Nama folder bebas asal mengandung kata kuncinya:

| Titik | Kata kunci nama folder | id di config.js |
|---|---|---|
| Race Village | `village`, `photo wall`, `warm` | `village` |
| Start | `start` | `start` |
| On Race | `rute`, `route`, `course`, `km` | `rute` |
| Finish | `finish` | `finish` |

Dari Google Drive, paling cepat dengan [rclone](https://rclone.org/drive/) (buat remote `gdrive` sekali dengan `rclone config`):

```bash
rclone copy "gdrive:Foto SRTW 2026" originals --drive-shared-with-me --transfers 8 --progress
```

Hapus `--drive-shared-with-me` kalau foldernya ada di Drive Anda sendiri.

Folder "ALL PHOTO EVENT" disusun per fotografer (`CAM AAN`, `CAM DANDI`, `CAM BIBIN`), bukan per titik. Petakan fotografer ke titik foto saat menjalankan script di langkah 2, misalnya:

```bash
python3 tools/process_photos.py --src originals --out output \
  --point-map "CAM AAN=rute" --point-map "CAM DANDI=finish" --point-map "CAM BIBIN=start"
```

File `.DS_Store` dan `._*` dari Mac otomatis dilewati.

### 2. OCR dan resize

Butuh Python 3.10–3.13 (teruji di 3.13). Di Windows, ganti `source .venv/bin/activate` dengan `.venv\Scripts\activate`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt

# uji 100 foto dulu, lalu cek output/ocr_detail.csv
python3 tools/process_photos.py --src originals --out output --limit 100

# semua foto (bisa dihentikan dengan Ctrl+C lalu dijalankan lagi)
python3 tools/process_photos.py --src originals --out output
```

Yang dilakukan script untuk setiap foto:

- `thumb/` sisi pendek 480 px (±60–80 KB), `web/` sisi panjang 2048 px kualitas 85 (±0,3 MB) untuk pratinjau dan ZIP, `full/` salinan file asli (4–7 MB) untuk tombol unduh per foto. Ukuran pratinjau bisa diubah dengan `--web-size` dan `--web-quality`.
- Jam diambil dari EXIF kamera. Kalau jam kamera meleset, pakai `--time-offset` (menit, misalnya `--time-offset -7`).
- BIB dibaca dua kali: foto utuh 2000 px, lalu 4 potongan dari versi 4000 px untuk BIB kecil di kerumunan.
- Hanya angka yang cocok dengan pola BIB (`--bib-regex`, default 5 digit diawali 1 atau 5) dan berskor minimal 0,7 (`--min-conf`) yang dipakai sebagai tag. Lebih baik foto tidak tertandai daripada salah orang; foto itu tetap bisa ditemukan lewat "Cari per titik foto".
- Semua bacaan beserta skornya dicatat di `output/ocr_detail.csv` untuk dicek.

Kecepatan (diukur di komputer 4 core, termasuk resize dan salin file): sekitar 3,4 detik per foto dengan 2 proses (default). Perkiraan: 3.000 foto ≈ 3 jam, 6.000 ≈ 6 jam, 10.000 ≈ 9,5 jam. Lebih dari 2 proses tidak membantu, karena satu proses OCR sudah memakai banyak core.

Hasil uji pada 4 foto asli (22 November 2026): 11 BIB terbaca benar, 0 salah orang; 1 bacaan salah (skor 0,59) tersaring oleh ambang 0,7.

**Supaya lebih cepat, bagi ke beberapa laptop.** Setiap laptop memegang salinan `originals/` yang sama (atau minimal folder fotografernya) dan mengolah satu fotografer:

```bash
# laptop 1
python3 tools/process_photos.py --src originals --out output-aan --only "CAM AAN" --point-map "CAM AAN=rute"
# laptop 2
python3 tools/process_photos.py --src originals --out output-dandi --only "CAM DANDI" --point-map "CAM DANDI=finish"
```

Lalu gabungkan di satu komputer: salin isi `thumb/`, `web/`, `full/` dari semua folder output ke satu `output/`, dan bangun index dari semua CSV sekaligus:

```bash
python3 tools/build_index.py --photos output-aan/photos.csv output-dandi/photos.csv --out site/data
```

### 3. Bangun index

```bash
python3 tools/build_index.py --photos output/photos.csv --out site/data
```

Kategori 5K/10K diambil dari digit pertama BIB (1xxxx = 10K, 5xxxx = 5K). Kalau perlu, pakai `--participants peserta.csv` (kolom `bib,category`) atau ubah aturannya dengan `--category-prefix "1=10K,5=5K"`.

**Saring salah baca dengan rentang BIB** (5K dari panitia: 50000–54700; 10K tidak ada datanya, jadi sementara 10000–11999 berdasarkan BIB yang terlihat di 50 foto uji coba):

```bash
python3 tools/build_index.py --photos output/photos.csv --out site/data \
  --valid-ranges "5K=50000-54700,10K=10001-11999"
```

BIB di luar rentang dibuang dan kategori diambil dari rentangnya. Script mencetak BIB yang dibuang beserta jumlah fotonya. Setelah semua foto diproses, cek daftar itu: kalau ada nomor 12xxx atau lebih yang muncul di banyak foto, berarti itu BIB 10K asli, jadi lebarkan rentang 10K lalu jalankan ulang (cukup build_index, OCR tidak perlu diulang). Kalau daftar BIB peserta lengkap tersedia, `--participants peserta.csv --only-registered` lebih ketat lagi. Pada uji 50 foto, sekitar 2 dari 119 tag ternyata salah baca (misalnya `15438`, yang bukan nomor peserta). Opsi ini membuang BIB yang tidak terdaftar.

### 4. Upload foto ke R2

Persiapan sekali di Cloudflare dashboard:

1. **R2** > buat bucket `srtw-photos`.
2. Bucket > **Settings > Custom Domains** > sambungkan subdomain, misalnya `foto.domainkamu.id`. Domainnya harus dikelola di Cloudflare. Jangan pakai alamat `r2.dev` untuk acara, kecepatannya dibatasi.
3. Bucket > **Settings > CORS Policy** (wajib supaya download dan ZIP berfungsi):

   ```json
   [
     {
       "AllowedOrigins": ["https://domainkamu.id"],
       "AllowedMethods": ["GET", "HEAD"],
       "AllowedHeaders": ["*"],
       "MaxAgeSeconds": 86400
     }
   ]
   ```

4. Domain > **Caching > Cache Rules** > hostname sama dengan `foto.domainkamu.id`, **Eligible for cache**, Edge TTL 1 bulan.
5. **R2 > Manage API Tokens** > buat token Object Read & Write, lalu `rclone config` > remote baru bernama `r2`, tipe `s3`, provider `Cloudflare`, isi Access Key, Secret, dan endpoint `https://<account_id>.r2.cloudflarestorage.com`.

Upload:

```bash
tools/upload_r2.sh output srtw-photos
```

Sekitar 35 GB (original ±30 GB + web dan thumbnail ±4 GB untuk ±8.000 foto), kira-kira 4 jam di internet upload 20 Mbps. Aman dijalankan ulang. Upload bisa dimulai sambil OCR masih berjalan (jalankan ulang di akhir untuk sisa fotonya).

Di Windows tanpa bash, jalankan tiga perintah `rclone copy` yang ada di dalam `tools/upload_r2.sh` satu per satu.

### 5. Deploy website ke Cloudflare Pages

1. Di `site/config.js`:
   - `photoBaseUrl` diganti ke `https://foto.domainkamu.id`
   - `resultsUrl` diisi link catatan waktu 10K (`{bib}` diganti nomor BIB), atau biarkan kosong
2. Di `site/index.html`, ganti alamat `https://photos-srtw2026.dodi-wahyono.workers.dev` di `og:url` dan `og:image` dengan domain baru, supaya preview link di WhatsApp (gambar `assets/og.jpg`) tetap muncul.
3. Hapus `site/pilot-photos/` dan baris `/pilot-photos/*` di `site/_headers`.
4. Deploy, pilih salah satu:
   - **Cloudflare Workers dari GitHub (yang dipakai sekarang):** Workers & Pages > Create > Import a repository > pilih repo ini. Pengaturan ada di `wrangler.jsonc` (folder `site`, 404 dari `404.html`), deploy command `npx wrangler deploy`. Setiap push ke `main` otomatis deploy.
   - **Cloudflare Pages dari GitHub:** Workers & Pages > Create > Pages > Connect to Git > pilih repo ini. Framework preset: None, build command kosong, **build output directory: `site`**. Setiap push ke `main` otomatis deploy.
   - **Dari terminal:** `npx wrangler pages deploy site --project-name srtw-photos`
5. Tab **Custom domains** > sambungkan `domainkamu.id`.

Pages membatasi 20.000 file per deploy. Index untuk 5.000 peserta sekitar 5.000 file, jadi aman. Foto **jangan** dimasukkan ke Pages; foto tetap di R2.

### 6. Permintaan hapus foto

Tulis di `removed.txt` (satu per baris):

```
rute-aan00845      # sembunyikan satu foto dari galeri
bib 54326          # hapus tag BIB ini dari semua foto
```

Lalu bangun ulang index dan deploy:

```bash
python3 tools/build_index.py --photos output/photos.csv --removed removed.txt --out site/data
```

Untuk menghapus file fotonya juga: `rclone delete r2:srtw-photos --include "*/rute-aan00845.jpg"`, lalu purge cache domain foto di Cloudflare.

### 7. Cek sebelum link disebar

```bash
python3 tools/check_live.py https://domainkamu.id
python3 tools/load_test.py https://domainkamu.id --users 300 --minutes 3
```

`check_live.py` memeriksa og:image, photoBaseUrl, link `/bib/`, index, foto di R2, CORS, dan cache CDN, lalu menandai yang belum beres dengan `!!`. `load_test.py` mensimulasikan ratusan pengunjung mencari BIB bersamaan dan melaporkan error serta waktu respons.

## Pengaturan di site/config.js

| Kunci | Isi |
|---|---|
| `photoBaseUrl` | alamat R2, misalnya `https://foto.domainkamu.id` |
| `resultsUrl` | link catatan waktu resmi, `{bib}` diganti nomor BIB; kosongkan kalau belum ada |
| `resultsCategories` | kategori yang punya timing resmi (`['10K']`) |
| `points` | daftar titik foto; `id` harus sama dengan kolom `point` di photos.csv |
| `zipVariant` | `web` (disarankan) atau `full` untuk isi ZIP |

## Checklist sebelum link disebar

- [ ] `photoBaseUrl` mengarah ke domain R2, bukan `/pilot-photos`
- [ ] CORS R2 berisi domain website yang benar
- [ ] Cache rule domain foto aktif
- [ ] Coba 3–5 BIB asli: grid, pratinjau, download satu foto, dan ZIP
- [ ] Coba buka link `/bib/<nomor>` langsung dari WhatsApp di HP
- [ ] `og:image` sudah URL lengkap
- [ ] `resultsUrl` sudah diisi (kalau ada)
- [ ] `python3 tools/check_live.py <alamat>` lolos semua
- [ ] `python3 tools/load_test.py <alamat>` lolos
