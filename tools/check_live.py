#!/usr/bin/env python3
"""
Cek galeri yang sudah online sebelum link disebar. Tanpa library tambahan.

  python3 tools/check_live.py https://domainkamu.id
  python3 tools/check_live.py https://domainkamu.id --bib 54326

Yang dicek: halaman utama, config.js, og:image, link /bib/<nomor>, index BIB,
foto di R2 (thumb, web, full), CORS untuk tombol download/ZIP, dan cache CDN.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

UA = 'srtw-check/1.0'
results = []


def get(url, origin=None, method='GET'):
    headers = {'User-Agent': UA}
    if origin:
        headers['Origin'] = origin
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read() if method == 'GET' else b''
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, b''
    except Exception as e:  # jaringan, DNS, TLS
        return 0, {}, str(e).encode()


def check(ok, label, detail=''):
    results.append(ok)
    print(f'  [{"OK" if ok else "!!"}] {label}' + (f' -- {detail}' if detail else ''))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('site', help='alamat website, misalnya https://domainkamu.id')
    ap.add_argument('--bib', help='BIB yang pasti punya foto (default: diambil dari index)')
    args = ap.parse_args()
    site = args.site.rstrip('/')

    print('Website')
    status, _, body = get(site + '/')
    html = body.decode('utf-8', 'replace')
    check(status == 200, 'halaman utama terbuka', f'HTTP {status}')
    m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    check(bool(m and m.group(1).startswith('http')), 'og:image memakai URL lengkap (preview WhatsApp)',
          m.group(1) if m else 'tidak ada')

    status, _, body = get(site + '/config.js')
    cfg = body.decode('utf-8', 'replace')
    check(status == 200, 'config.js terbuka', f'HTTP {status}')

    def cfg_value(key):
        mm = re.search(key + r"\s*:\s*'([^']*)'", cfg)
        return mm.group(1) if mm else ''

    photo_base = cfg_value('photoBaseUrl')
    data_base = cfg_value('dataBaseUrl') or '/data'
    check(photo_base.startswith('https://') and 'r2.dev' not in photo_base,
          'photoBaseUrl mengarah ke domain foto sendiri', photo_base or 'kosong')
    check(bool(cfg_value('removalUrl')), 'removalUrl (minta hapus foto) sudah diisi')
    check(bool(cfg_value('resultsUrl')), 'resultsUrl (catatan waktu 10K) sudah diisi', 'boleh kosong kalau memang belum ada')

    status, _, _ = get(site + '/bib/12345')
    check(status == 200, 'link /bib/<nomor> diarahkan ke halaman utama', f'HTTP {status}')
    status, _, _ = get(site + '/halaman-yang-tidak-ada-xyz')
    check(status == 404, 'halaman tidak dikenal memberi 404', f'HTTP {status}')

    print('Index')
    data_url = data_base if data_base.startswith('http') else site + data_base
    status, _, body = get(data_url + '/meta.json')
    meta = json.loads(body or b'{}') if status == 200 else {}
    check(status == 200, 'meta.json terbuka',
          f'{meta.get("totalPhotos", "?")} foto, {meta.get("totalBibs", "?")} BIB, update {meta.get("updatedAt", "?")}')

    bib = args.bib
    photo = None
    if not bib:
        for point in (meta.get('points') or {}):
            st, _, b = get(f'{data_url}/points/{point}.json')
            if st == 200:
                tagged = [p for p in json.loads(b)['photos'] if p.get('bibs')]
                if tagged:
                    bib = tagged[0]['bibs'][0]
                    break
    if bib:
        status, _, body = get(f'{data_url}/bib/{bib}.json')
        doc = json.loads(body or b'{}') if status == 200 else {}
        check(status == 200 and bool(doc.get('photos')), f'index BIB {bib} terbuka', f'{len(doc.get("photos", []))} foto')
        photo = (doc.get('photos') or [None])[0]
        if photo:
            check(not photo['id'].startswith('srtw26-'), 'index berisi foto asli, bukan data demo', photo['id'])
    else:
        check(False, 'menemukan BIB contoh untuk dicek')

    print('Foto (R2)')
    if photo and photo_base.startswith('http'):
        for variant in ('thumb', 'web', 'full'):
            url = f'{photo_base.rstrip("/")}/{variant}/{photo["id"]}.jpg'
            status, h, _ = get(url, method='HEAD')
            check(status == 200 and 'image' in h.get('content-type', ''), f'{variant}/ tersedia',
                  f'HTTP {status}, {h.get("content-type", "-")}, {int(h.get("content-length", 0)) // 1024} KB')
        url = f'{photo_base.rstrip("/")}/web/{photo["id"]}.jpg'
        status, h, _ = get(url, origin=site)
        allow = h.get('access-control-allow-origin', '')
        check(allow in ('*', site), 'CORS mengizinkan website (tombol download dan ZIP)', allow or 'header tidak ada')
        get(url)
        status, h, _ = get(url)
        cache = h.get('cf-cache-status', '-')
        check(cache in ('HIT', 'REVALIDATED', 'UPDATING'), 'foto dilayani dari cache CDN',
              f'cf-cache-status {cache}; kalau MISS/DYNAMIC terus, cek cache rule')
    else:
        check(False, 'cek foto dilewati', 'photoBaseUrl belum diisi atau tidak ada BIB contoh')

    bad = results.count(False)
    print(f'\n{len(results) - bad}/{len(results)} cek lolos.' + (' Perbaiki yang bertanda !! sebelum link disebar.' if bad else ' Siap disebar.'))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
