#!/usr/bin/env python3
"""
Olah foto asli SRTW menjadi bahan galeri: baca BIB (OCR), buat 3 ukuran foto,
dan tulis photos.csv untuk tools/build_index.py.

Struktur input (satu subfolder per titik foto; nama folder bebas asal mengandung
kata kuncinya, misalnya "01 Race Village", "START", "Finish - Andi"):

  originals/
    village/   (kata kunci: village, photo wall, warm)
    start/     (kata kunci: start)
    rute/      (kata kunci: rute, route, course, km)
    finish/    (kata kunci: finish)

Output:

  output/
    thumb/<id>.jpg   sisi pendek 480 px, untuk grid
    web/<id>.jpg     sisi panjang 2048 px, untuk pratinjau dan ZIP
    full/<id>.jpg    salinan file asli, untuk tombol download
    photos.csv       id, point, time, bibs  -> masukan build_index.py
    ocr_detail.csv   semua bacaan OCR + skor, untuk cek kualitas

Script bisa dihentikan dan dijalankan lagi: foto yang sudah ada di photos.csv
dilewati.

Contoh:
  pip install -r tools/requirements.txt
  python3 tools/process_photos.py --src originals --out output --workers 2
  python3 tools/process_photos.py --src originals --out output --limit 100   # uji dulu
"""
import argparse
import csv
import multiprocessing as mp
import os
import re
import shutil
import sys
import time

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 200_000_000

POINT_KEYWORDS = [
    ('village', ('village', 'photo wall', 'photowall', 'warm')),
    ('start', ('start',)),
    ('finish', ('finish',)),
    ('rute', ('rute', 'route', 'course', 'km')),
]
EXTS = ('.jpg', '.jpeg')
CSV_FIELDS = ['id', 'point', 'time', 'bibs']
DETAIL_FIELDS = ['id', 'bib', 'conf', 'accepted']

# Diisi per proses worker
_ocr = None
_cfg = None


def detect_point(rel_path, default):
    parts = rel_path.replace('\\', '/').lower().split('/')[:-1]
    for part in parts:
        for point, keys in POINT_KEYWORDS:
            if any(k in part for k in keys):
                return point
    return default


def make_id(rel_path):
    stem = os.path.splitext(rel_path.replace('\\', '/'))[0]
    slug = re.sub(r'[^A-Za-z0-9]+', '-', stem).strip('-').lower()
    return slug[-80:].strip('-')


def exif_time(img, offset_min):
    exif = img.getexif()
    raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal, DateTime
    m = re.search(r'(\d{1,2}):(\d{2}):\d{2}\s*$', str(raw or ''))
    if not m:
        return ''
    total = (int(m.group(1)) * 60 + int(m.group(2)) + offset_min) % (24 * 60)
    return f'{total // 60:02d}:{total % 60:02d}'


def resized(img, long_side=None, short_side=None):
    w, h = img.size
    if long_side:
        scale = long_side / max(w, h)
    else:
        scale = short_side / min(w, h)
    if scale >= 1:
        return img.copy()
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def save_jpeg(img, path, quality):
    tmp = path + '.part'
    img.save(tmp, 'JPEG', quality=quality, optimize=True, progressive=True)
    os.replace(tmp, path)


def init_worker(cfg):
    global _ocr, _cfg
    _cfg = cfg
    if not cfg['no_ocr']:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()


def ocr_bibs(img):
    import numpy as np
    pattern = re.compile(r'(?<!\d)(' + _cfg['bib_regex'] + r')(?!\d)')
    found = {}

    def run(part):
        result, _ = _ocr(np.array(part))
        for _box, text, conf in result or []:
            t = text.replace(' ', '').translate(str.maketrans('OoIl', '0011'))
            for bib in pattern.findall(t):
                found[bib] = max(float(conf), found.get(bib, 0.0))

    # 1) Foto utuh diperkecil: cepat, menangkap BIB yang besar
    run(resized(img, long_side=2000))
    # 2) Potongan resolusi penuh: menangkap BIB kecil di foto kerumunan
    w, h = img.size
    rows, cols = (3, 2) if h >= w else (2, 3)
    tw, th, ov = w / cols, h / rows, 0.15
    for r in range(rows):
        for c in range(cols):
            box = (max(0, int((c - ov) * tw)), max(0, int((r - ov) * th)),
                   min(w, int((c + 1 + ov) * tw)), min(h, int((r + 1 + ov) * th)))
            run(img.crop(box))
    return found


def process(task):
    rel, pid, point = task
    src = os.path.join(_cfg['src'], rel)
    out = _cfg['out']
    try:
        with Image.open(src) as raw:
            shot_time = exif_time(raw, _cfg['time_offset'])
            img = ImageOps.exif_transpose(raw).convert('RGB')
        save_jpeg(resized(img, short_side=480), os.path.join(out, 'thumb', pid + '.jpg'), 78)
        save_jpeg(resized(img, long_side=2048), os.path.join(out, 'web', pid + '.jpg'), 82)
        full = os.path.join(out, 'full', pid + '.jpg')
        shutil.copyfile(src, full + '.part')
        os.replace(full + '.part', full)
        reads = {} if _cfg['no_ocr'] else ocr_bibs(img)
        bibs = sorted(b for b, c in reads.items() if c >= _cfg['min_conf'])
        return {'ok': True, 'id': pid, 'point': point, 'time': shot_time, 'bibs': bibs, 'reads': reads}
    except Exception as exc:  # foto rusak tidak boleh menghentikan semuanya
        return {'ok': False, 'id': pid, 'rel': rel, 'error': f'{type(exc).__name__}: {exc}'}


def load_done(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline='', encoding='utf-8') as f:
        return {row['id'] for row in csv.DictReader(f)}


def open_csv(path, fields):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    f = open(path, 'a', newline='', encoding='utf-8')
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()
    return f, w


def main():
    ap = argparse.ArgumentParser(description='OCR BIB + resize foto SRTW.')
    ap.add_argument('--src', required=True, help='folder foto asli')
    ap.add_argument('--out', default='output', help='folder hasil (default: output)')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help='jumlah proses sekaligus (default: setengah jumlah core)')
    ap.add_argument('--point', default='', help='titik foto untuk file yang foldernya tidak dikenali')
    ap.add_argument('--bib-regex', default=r'[15]\d{4}',
                    help='pola nomor BIB (default: 5 digit diawali 1 atau 5)')
    ap.add_argument('--min-conf', type=float, default=0.7,
                    help='skor OCR minimum agar BIB dipakai (default: 0.7)')
    ap.add_argument('--time-offset', type=int, default=0,
                    help='koreksi jam kamera dalam menit, misalnya -7 kalau jam kamera 7 menit lebih cepat')
    ap.add_argument('--limit', type=int, default=0, help='olah maksimal N foto baru (untuk uji)')
    ap.add_argument('--no-ocr', action='store_true', help='hanya resize, tanpa OCR')
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)
    for sub in ('thumb', 'web', 'full'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    photos_csv = os.path.join(out, 'photos.csv')
    detail_csv = os.path.join(out, 'ocr_detail.csv')
    done = load_done(photos_csv)

    tasks, ids, unknown_point = [], {}, 0
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for name in sorted(files):
            if name.startswith('.') or not name.lower().endswith(EXTS):
                continue
            rel = os.path.relpath(os.path.join(root, name), src)
            pid = make_id(rel)
            if pid in ids:
                print(f'PERINGATAN: "{rel}" dan "{ids[pid]}" menghasilkan id sama, yang kedua dilewati', file=sys.stderr)
                continue
            ids[pid] = rel
            if pid in done:
                continue
            point = detect_point(rel, args.point)
            if not point:
                unknown_point += 1
            tasks.append((rel, pid, point))
    if args.limit:
        tasks = tasks[:args.limit]

    print(f'{len(ids)} foto ditemukan, {len(done)} sudah diolah, {len(tasks)} akan diolah dengan {args.workers} proses.')
    if unknown_point:
        print(f'PERINGATAN: {unknown_point} foto tidak punya titik foto (nama folder tidak dikenali, --point kosong). '
              'Foto tetap bisa dicari dengan BIB, tapi tidak muncul di "Cari per titik foto".', file=sys.stderr)
    if not tasks:
        return

    cfg = {'src': src, 'out': out, 'bib_regex': args.bib_regex, 'min_conf': args.min_conf,
           'time_offset': args.time_offset, 'no_ocr': args.no_ocr}
    pf, pw = open_csv(photos_csv, CSV_FIELDS)
    df, dw = open_csv(detail_csv, DETAIL_FIELDS)
    started, n, tagged, failed = time.time(), 0, 0, []
    try:
        with mp.get_context('spawn').Pool(args.workers, initializer=init_worker, initargs=(cfg,)) as pool:
            for res in pool.imap_unordered(process, tasks):
                n += 1
                if not res['ok']:
                    failed.append(res)
                    print(f'  GAGAL {res["rel"]}: {res["error"]}', file=sys.stderr)
                    continue
                pw.writerow({'id': res['id'], 'point': res['point'], 'time': res['time'], 'bibs': ' '.join(res['bibs'])})
                for bib, conf in sorted(res['reads'].items()):
                    dw.writerow({'id': res['id'], 'bib': bib, 'conf': f'{conf:.2f}',
                                 'accepted': 'ya' if conf >= args.min_conf else 'tidak'})
                pf.flush()
                df.flush()
                tagged += bool(res['bibs'])
                elapsed = time.time() - started
                eta = elapsed / n * (len(tasks) - n)
                print(f'  [{n}/{len(tasks)}] {res["id"]}  {res["point"] or "-"}  {res["time"] or "--:--"}  '
                      f'BIB: {" ".join(res["bibs"]) or "-"}  (sisa ~{eta / 60:.0f} menit)', flush=True)
    except KeyboardInterrupt:
        print('\nDihentikan. Jalankan perintah yang sama untuk melanjutkan.', file=sys.stderr)
    finally:
        pf.close()
        df.close()

    ok = n - len(failed)
    print(f'Selesai: {ok} foto diolah, {tagged} dengan BIB terbaca, {len(failed)} gagal, '
          f'{(time.time() - started) / 60:.1f} menit.')
    print(f'Langkah berikutnya: python3 tools/build_index.py --photos {photos_csv} --out site/data')


if __name__ == '__main__':
    main()
