#!/usr/bin/env python3
"""
Uji beban sederhana: banyak pengunjung mencari BIB bersamaan. Tanpa library tambahan.

  python3 tools/load_test.py https://domainkamu.id --users 300 --minutes 3

Setiap "pengunjung" membuka halaman, config, index BIB acak, lalu thumbnail
foto-fotonya, lalu jeda 1-3 detik dan mengulang. Hasilnya: jumlah request,
error, dan waktu respons (p50/p95).

Jalankan dari internet biasa, bukan dari jaringan yang sama dengan server.
Jangan jalankan saat acara sedang ramai.
"""
import argparse
import json
import random
import re
import statistics
import threading
import time
import urllib.error
import urllib.request

lock = threading.Lock()
lat, errors, count = [], {}, [0]


def fetch(url):
    t = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'srtw-loadtest/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        body, code = b'', e.code
    except Exception as e:
        body, code = b'', type(e).__name__
    dt = time.time() - t
    with lock:
        count[0] += 1
        lat.append(dt)
        if code != 200:
            errors[code] = errors.get(code, 0) + 1
    return code, body


def user(site, data_url, photo_base, bibs, until):
    while time.time() < until:
        fetch(site + '/')
        fetch(site + '/config.js')
        code, body = fetch(f'{data_url}/bib/{random.choice(bibs)}.json')
        if code == 200 and photo_base:
            for p in json.loads(body).get('photos', [])[:15]:
                fetch(f'{photo_base}/thumb/{p["id"]}.jpg')
        time.sleep(random.uniform(1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('site')
    ap.add_argument('--users', type=int, default=200, help='pengunjung bersamaan (default 200)')
    ap.add_argument('--minutes', type=float, default=2, help='lama uji (default 2 menit)')
    args = ap.parse_args()
    site = args.site.rstrip('/')

    _, cfg = fetch(site + '/config.js')
    cfg = cfg.decode('utf-8', 'replace')

    def val(k):
        m = re.search(k + r"\s*:\s*'([^']*)'", cfg)
        return m.group(1) if m else ''

    photo_base = val('photoBaseUrl')
    photo_base = photo_base if photo_base.startswith('http') else site + photo_base
    data_base = val('dataBaseUrl') or '/data'
    data_url = data_base if data_base.startswith('http') else site + data_base

    _, meta = fetch(data_url + '/meta.json')
    bibs = set()
    for point in json.loads(meta or b'{}').get('points', {}):
        code, body = fetch(f'{data_url}/points/{point}.json')
        if code == 200:
            for p in json.loads(body)['photos']:
                bibs.update(p.get('bibs', []))
    bibs = sorted(bibs)
    if not bibs:
        raise SystemExit('Tidak menemukan BIB di index.')
    # Request persiapan di atas tidak ikut dihitung
    with lock:
        lat.clear(); errors.clear(); count[0] = 0

    print(f'{args.users} pengunjung, {args.minutes} menit, {len(bibs)} BIB, foto dari {photo_base}')
    until = time.time() + args.minutes * 60
    threads = [threading.Thread(target=user, args=(site, data_url, photo_base, bibs, until), daemon=True)
               for _ in range(args.users)]
    for i, t in enumerate(threads):
        t.start()
        if i % 20 == 19:
            time.sleep(0.5)  # naik bertahap
    started = time.time()
    while any(t.is_alive() for t in threads):
        time.sleep(10)
        with lock:
            n, e = count[0], sum(errors.values())
        print(f'  {time.time() - started:4.0f}s  {n} request  {e} error', flush=True)

    s = sorted(lat)
    p = lambda q: s[min(len(s) - 1, int(q * len(s)))] * 1000
    print(f'\nTotal {count[0]} request, {count[0] / (args.minutes * 60):.0f}/detik')
    print(f'Waktu respons: p50 {p(0.5):.0f} ms, p95 {p(0.95):.0f} ms, maks {s[-1] * 1000:.0f} ms')
    print(f'Error: {errors or "tidak ada"}')
    ok = not errors and p(0.95) < 2000
    print('LOLOS' if ok else 'PERLU DICEK: ada error atau p95 di atas 2 detik')


if __name__ == '__main__':
    main()
