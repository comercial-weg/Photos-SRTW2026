#!/usr/bin/env python3
"""
Bangun index pencarian BIB untuk galeri foto SRTW.

Input:
  photos.csv        (wajib)  kolom: id, point, time, bibs
                    - id    : nama file foto tanpa .jpg, sama di thumb/, web/, full/
                    - point : id titik foto (village, start, rute, finish)
                    - time  : jam foto, format 06:49 (boleh kosong)
                    - bibs  : nomor BIB terbaca, pisahkan dengan spasi/koma/titik koma (boleh kosong)
  participants.csv  (opsional) kolom: bib, category   (contoh: 54326, 5K)
                    Tanpa file ini, kategori diambil dari digit pertama BIB (--category-prefix).
  removed.txt       (opsional) permintaan hapus, satu per baris:
                    - id foto (misalnya rute-aan00845)  -> foto disembunyikan dari galeri
                    - bib 54326                         -> tag BIB itu dihapus dari semua foto
                    Baris diawali # diabaikan.

Output (folder --out, default ./data):
  bib/<nomor>.json      satu file per BIB
  points/<titik>.json   semua foto per titik, termasuk yang BIB-nya tidak terbaca
  all.json              semua foto (untuk halaman depan), urut jam
  meta.json             jumlah foto, jumlah BIB, waktu update

Contoh:
  python3 tools/build_index.py --photos output/photos.csv --out site/data
  python3 tools/build_index.py --photos tools/sample/photos.csv \
      --participants tools/sample/participants.csv --out site/data
"""
import argparse
import csv
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone

ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')
POINT_RE = re.compile(r'^[a-z0-9_-]+$')


def clean_bib(value):
    return re.sub(r'\D', '', value or '')[:8]


def norm_time(value):
    m = re.match(r'^\s*(\d{1,2})[:.](\d{2})', value or '')
    return f'{int(m.group(1)):02d}:{m.group(2)}' if m else ''


def write_json(path, doc):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))


def main():
    ap = argparse.ArgumentParser(description='Bangun index BIB dari hasil OCR.')
    ap.add_argument('--photos', required=True, nargs='+',
                    help='CSV hasil OCR; boleh beberapa file (hasil dari beberapa komputer)')
    ap.add_argument('--participants', help='CSV peserta (bib, category)')
    ap.add_argument('--out', default='data', help='folder output (default: data)')
    ap.add_argument('--valid-ranges', default='',
                    help='rentang BIB sah per kategori, misalnya "5K=50001-54700,10K=10001-11999". '
                         'BIB di luar rentang dibuang (salah baca OCR) dan kategori diambil dari rentangnya')
    ap.add_argument('--only-registered', action='store_true',
                    help='buang BIB yang tidak ada di participants.csv (menyaring salah baca OCR)')
    ap.add_argument('--removed', help='daftar permintaan hapus (lihat keterangan di atas)')
    ap.add_argument('--category-prefix', default='1=10K,5=5K',
                    help='kategori dari awalan BIB bila tidak ada di participants.csv '
                         '(default: "1=10K,5=5K"; kosongkan untuk mematikan)')
    args = ap.parse_args()

    prefix_rules = []
    for rule in (args.category_prefix or '').split(','):
        if '=' in rule:
            pre, cat = (x.strip() for x in rule.split('=', 1))
            if pre and cat:
                prefix_rules.append((pre, cat))
    prefix_rules.sort(key=lambda r: -len(r[0]))

    ranges = []
    for part in (args.valid_ranges or '').split(','):
        m = re.match(r'^\s*([^=]+)=(\d+)-(\d+)\s*$', part)
        if m:
            ranges.append((m.group(1).strip(), int(m.group(2)), int(m.group(3))))
        elif part.strip():
            ap.error(f'--valid-ranges tidak dikenali: "{part}"')

    def range_category(bib):
        n = int(bib)
        for cat, lo, hi in ranges:
            if lo <= n <= hi:
                return cat
        return None

    def category_of(bib):
        if categories.get(bib):
            return categories[bib]
        if ranges:
            return range_category(bib)
        for pre, cat in prefix_rules:
            if bib.startswith(pre):
                return cat
        return None

    categories = {}
    if args.participants:
        with open(args.participants, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                bib = clean_bib(row.get('bib'))
                if bib:
                    categories[bib] = (row.get('category') or '').strip() or None

    if args.only_registered and not categories:
        ap.error('--only-registered butuh --participants berisi daftar BIB')
    dropped_unknown = defaultdict(int)  # BIB -> jumlah foto

    hidden_ids, hidden_bibs = set(), set()
    if args.removed:
        with open(args.removed, encoding='utf-8-sig') as f:
            for line in f:
                line = line.split('#', 1)[0].strip()
                if not line:
                    continue
                m = re.match(r'^bib\s+(\d+)$', line, re.I)
                if m:
                    hidden_bibs.add(clean_bib(m.group(1)))
                else:
                    hidden_ids.add(line[:-4] if line.lower().endswith('.jpg') else line)

    by_bib = defaultdict(list)
    seen_photos = []
    by_point = defaultdict(list)
    seen = set()
    total = skipped = untagged = 0

    rows = []
    for path in args.photos:
        with open(path, newline='', encoding='utf-8-sig') as f:
            rows += [(f'{os.path.basename(path)} baris {n}', row) for n, row in enumerate(csv.DictReader(f), start=2)]

    for n, row in rows:
        pid = (row.get('id') or '').strip()
        if pid.lower().endswith('.jpg'):
            pid = pid[:-4]
        if not pid or not ID_RE.match(pid):
            print(f'  {n}: id "{pid}" tidak valid (hanya huruf, angka, - dan _), dilewati', file=sys.stderr)
            skipped += 1
            continue
        if pid in seen:
            # bisa terjadi kalau foto diolah ulang; baris pertama yang dipakai
            print(f'  {n}: id "{pid}" dobel, dilewati', file=sys.stderr)
            skipped += 1
            continue
        seen.add(pid)
        if pid in hidden_ids:
            skipped += 1
            continue

        point = (row.get('point') or '').strip().lower()
        if point and not POINT_RE.match(point):
            print(f'  {n}: point "{point}" tidak valid, foto tetap masuk tanpa titik', file=sys.stderr)
            point = ''

        bibs = sorted({b for b in (clean_bib(x) for x in re.split(r'[\s,;|]+', row.get('bibs') or ''))
                       if b and b not in hidden_bibs})
        if args.only_registered:
            for b in bibs:
                if b not in categories:
                    dropped_unknown[b] += 1
            bibs = [b for b in bibs if b in categories]
        if ranges:
            for b in bibs:
                if not range_category(b):
                    dropped_unknown[b] += 1
            bibs = [b for b in bibs if range_category(b)]
        photo = {'id': pid, 'point': point, 'time': norm_time(row.get('time')), 'bibs': bibs}
        total += 1
        seen_photos.append(photo)
        if not bibs:
            untagged += 1
        if point:
            by_point[point].append(photo)
        for b in bibs:
            by_bib[b].append(photo)

    def order(p):
        return (p['time'] or '99:99', p['id'])

    out = args.out
    for sub in ('bib', 'points'):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    for bib, photos in by_bib.items():
        write_json(os.path.join(out, 'bib', f'{bib}.json'), {
            'bib': bib,
            'category': category_of(bib),
            'photos': sorted(photos, key=order),
        })

    for point, photos in by_point.items():
        write_json(os.path.join(out, 'points', f'{point}.json'), {
            'point': point,
            'photos': [{'id': p['id'], 'time': p['time'], 'bibs': p['bibs']} for p in sorted(photos, key=order)],
        })

    every = sorted((p for p in seen_photos), key=order)
    write_json(os.path.join(out, 'all.json'), {
        'photos': [{'id': p['id'], 'point': p['point'], 'time': p['time'], 'bibs': p['bibs']} for p in every],
    })

    write_json(os.path.join(out, 'meta.json'), {
        'totalPhotos': total,
        'totalBibs': len(by_bib),
        'untaggedPhotos': untagged,
        'points': {p: len(v) for p, v in sorted(by_point.items())},
        'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    })

    print(f'Selesai: {total} foto, {len(by_bib)} BIB, {untagged} foto tanpa BIB terbaca, {skipped} baris dilewati.')
    if dropped_unknown:
        top = sorted(dropped_unknown.items(), key=lambda kv: (-kv[1], kv[0]))
        print(f'{len(dropped_unknown)} BIB tidak terdaftar / di luar rentang dibuang (kemungkinan salah baca).')
        print('  BIB (jumlah foto), terbanyak dulu. BIB asli muncul di banyak foto; kalau ada yang')
        print('  sering muncul, berarti rentangnya terlalu sempit:')
        print('  ' + '  '.join(f'{b}({n})' for b, n in top[:40]) + ('  ...' if len(top) > 40 else ''))
    print(f'Titik: ' + ', '.join(f'{p}={len(v)}' for p, v in sorted(by_point.items())))
    print(f'Output: {os.path.abspath(out)}')


if __name__ == '__main__':
    main()
