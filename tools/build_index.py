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
    ap.add_argument('--photos', required=True, help='CSV hasil OCR')
    ap.add_argument('--participants', help='CSV peserta (bib, category)')
    ap.add_argument('--out', default='data', help='folder output (default: data)')
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

    def category_of(bib):
        if categories.get(bib):
            return categories[bib]
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
    by_point = defaultdict(list)
    seen = set()
    total = skipped = untagged = 0

    with open(args.photos, newline='', encoding='utf-8-sig') as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            pid = (row.get('id') or '').strip()
            if pid.lower().endswith('.jpg'):
                pid = pid[:-4]
            if not pid or not ID_RE.match(pid):
                print(f'  baris {n}: id "{pid}" tidak valid (hanya huruf, angka, - dan _), dilewati', file=sys.stderr)
                skipped += 1
                continue
            if pid in seen:
                print(f'  baris {n}: id "{pid}" dobel, dilewati', file=sys.stderr)
                skipped += 1
                continue
            seen.add(pid)
            if pid in hidden_ids:
                skipped += 1
                continue

            point = (row.get('point') or '').strip().lower()
            if point and not POINT_RE.match(point):
                print(f'  baris {n}: point "{point}" tidak valid, foto tetap masuk tanpa titik', file=sys.stderr)
                point = ''

            bibs = sorted({b for b in (clean_bib(x) for x in re.split(r'[\s,;|]+', row.get('bibs') or ''))
                           if b and b not in hidden_bibs})
            photo = {'id': pid, 'point': point, 'time': norm_time(row.get('time')), 'bibs': bibs}
            total += 1
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

    write_json(os.path.join(out, 'meta.json'), {
        'totalPhotos': total,
        'totalBibs': len(by_bib),
        'untaggedPhotos': untagged,
        'points': {p: len(v) for p, v in sorted(by_point.items())},
        'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    })

    print(f'Selesai: {total} foto, {len(by_bib)} BIB, {untagged} foto tanpa BIB terbaca, {skipped} baris dilewati.')
    print(f'Titik: ' + ', '.join(f'{p}={len(v)}' for p, v in sorted(by_point.items())))
    print(f'Output: {os.path.abspath(out)}')


if __name__ == '__main__':
    main()
