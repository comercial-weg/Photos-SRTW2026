#!/usr/bin/env python3
"""
Cari foto "aneh" untuk disembunyikan dari galeri: foto tanpa wajah dan tanpa BIB
terbaca (aspal, kaki, punggung, pemandangan, foto kabur). Tidak ada file yang
dihapus: skrip ini hanya membuat halaman review dan daftar kandidat.

  python3 tools/find_noface.py

Hasil:
  output/faces.csv        catatan deteksi per foto (dipakai ulang, jadi putaran
                          berikutnya hanya memeriksa foto baru)
  review_noface.html      buka di browser, centang/hapus centang, salin daftar
  noface_candidates.txt   daftar id kandidat (semua yang lolos aturan)

Mode otomatis (dipakai update_loop.sh): kandidat langsung disembunyikan lewat
removed_all.txt = removed.txt + kandidat, kecuali id yang ada di keep.txt.
Cek manual: review_noface.html hanya menampilkan kandidat yang belum pernah dicek.
Hapus centang foto yang layak tampil, salin daftar "layak tampil" ke keep.txt, lalu
  python3 tools/find_noface.py --combined removed_all.txt --mark-reviewed
supaya kandidat lainnya dicatat sudah dicek (reviewed.txt) dan tidak muncul lagi.
Foto tetap ada di R2.

Deteksi wajah memakai YuNet (OpenCV). Model ±230 KB diunduh otomatis sekali.
"""
import argparse
import csv
import html
import os
import sys
import time
import urllib.request

import cv2
import numpy as np

MODEL_URL = ('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/'
             'models/face_detection_yunet/face_detection_yunet_2023mar.onnx')
HERE = os.path.dirname(os.path.abspath(__file__))


def ensure_model(path):
    if os.path.exists(path) and os.path.getsize(path) > 100_000:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print('Mengunduh model deteksi wajah ...')
    urllib.request.urlretrieve(MODEL_URL, path + '.part')
    if os.path.getsize(path + '.part') < 100_000:
        sys.exit('Gagal mengunduh model wajah (file terlalu kecil). Coba lagi nanti.')
    os.replace(path + '.part', path)
    return path


def read_photos(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            pid = (r.get('id') or '').strip()
            if pid:
                rows.append({'id': pid, 'time': r.get('time', ''), 'bibs': (r.get('bibs') or '').strip()})
    seen, out = set(), []
    for r in rows:
        if r['id'] not in seen:
            seen.add(r['id'])
            out.append(r)
    return out


def load_cache(path):
    cache = {}
    if os.path.exists(path):
        with open(path, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                try:
                    cache[r['id']] = (int(r['faces']), float(r['sharp']), float(r['best']))
                except (KeyError, ValueError):
                    pass
    return cache


def analyse(det, img_path, max_side):
    img = cv2.imread(img_path)
    if img is None:
        return None
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    n = 0 if faces is None else len(faces)
    best = 0.0 if faces is None else float(max(f[-1] for f in faces))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(gray, (min(w, 1024), int(h * min(w, 1024) / w)), interpolation=cv2.INTER_AREA)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    return n, sharp, best


def write_review(path, cands, thumb_rel, total, reason_of):
    items = []
    for c in cands:
        pid = html.escape(c['id'])
        items.append(
            f'<label class="it"><input type="checkbox" checked value="{pid}">'
            f'<img loading="lazy" src="{thumb_rel}/{pid}.jpg" alt="">'
            f'<span>{pid}<br>{html.escape(c["time"])} · {html.escape(reason_of(c))}</span></label>')
    doc = f"""<!doctype html><meta charset="utf-8"><title>Review foto tanpa wajah</title>
<style>
body{{font:14px system-ui,sans-serif;margin:16px;background:#faf7f8;color:#2b1a24}}
.top{{position:sticky;top:0;background:#faf7f8;padding:8px 0 12px;z-index:2;border-bottom:1px solid #e8d6de}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:12px}}
.it{{display:block;background:#fff;border:3px solid #c9566f;border-radius:10px;overflow:hidden;cursor:pointer}}
.it:has(input:not(:checked)){{border-color:#ddd;opacity:.55}}
.it input{{position:absolute;margin:8px;transform:scale(1.4)}}
.it img{{width:100%;aspect-ratio:3/2;object-fit:cover;display:block;background:#eee}}
.it span{{display:block;padding:6px 8px;font-size:12px;color:#6b5560;word-break:break-all}}
textarea{{width:100%;height:70px;font:12px monospace}}
button{{padding:8px 14px;border:0;border-radius:8px;background:#3b1a2b;color:#fff;font-weight:700;cursor:pointer}}
</style>
<div class="top">
<b>{len(cands)}</b> foto baru yang disembunyikan dan belum dicek (dari {total} foto). Bingkai merah = tetap disembunyikan.
Klik foto yang <b>layak tampil</b> untuk menghapus centangnya.
<p><button type="button" onclick="all_(true)">Centang semua</button>
<button type="button" onclick="all_(false)">Hapus semua centang</button>
<button type="button" onclick="cp()">Salin daftar disembunyikan</button> <span id="n"></span></p>
<p id="srv" hidden><button type="button" id="save" style="background:#c9566f" onclick="save()">Simpan &amp; tandai semua sudah dicek</button>
<span id="msg"></span><br><small>Foto yang tidak dicentang masuk keep.txt (tampil lagi di galeri pada putaran update berikutnya).
Sisanya dicatat sudah dicek dan tetap disembunyikan.</small></p>
<p><b>Disembunyikan</b> (dicentang):</p><textarea id="out" readonly></textarea>
<p><b>Layak tampil</b> (tidak dicentang) &mdash; salin ke <code>keep.txt</code>:
<button type="button" onclick="cpk()">Salin daftar layak tampil</button></p><textarea id="keep" readonly></textarea>
</div>
<div class="grid">{''.join(items)}</div>
<script>
const boxes=[...document.querySelectorAll('input[type=checkbox]')];
function upd(){{const ids=boxes.filter(b=>b.checked).map(b=>b.value);
document.getElementById('out').value=ids.join('\\n');
document.getElementById('n').textContent=ids.length+' foto dicentang';
document.getElementById('keep').value=boxes.filter(b=>!b.checked).map(b=>b.value).join('\\n');}}
function cpk(){{const t=document.getElementById('keep');t.select();
try{{navigator.clipboard.writeText(t.value).catch(()=>document.execCommand('copy'));}}catch(e){{document.execCommand('copy');}}}}
function all_(v){{boxes.forEach(b=>b.checked=v);upd();}}
function cp(){{const t=document.getElementById('out');t.select();
try{{navigator.clipboard.writeText(t.value).catch(()=>document.execCommand('copy'));}}catch(e){{document.execCommand('copy');}}}}
boxes.forEach(b=>b.addEventListener('change',upd));upd();
if(location.protocol.startsWith('http'))document.getElementById('srv').hidden=false;
async function save(){{const btn=document.getElementById('save'),msg=document.getElementById('msg');
btn.disabled=true;msg.textContent=' Menyimpan...';
try{{const r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{keep:boxes.filter(b=>!b.checked).map(b=>b.value)}})}});
const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);
msg.textContent=' Tersimpan: '+d.kept+' foto layak tampil, '+d.reviewed+' dicatat sudah dicek. Memuat ulang...';
setTimeout(()=>location.reload(),1500);}}catch(e){{msg.textContent=' Gagal: '+e.message;btn.disabled=false;}}}}
</script>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='output', help='folder hasil process_photos (default: output)')
    ap.add_argument('--model', default=os.path.join(HERE, 'models', 'face_detection_yunet_2023mar.onnx'))
    ap.add_argument('--score', type=float, default=0.6, help='ambang keyakinan wajah 0-1 (default 0.6)')
    ap.add_argument('--max-side', type=int, default=2048, help='ukuran gambar yang diperiksa (default 2048)')
    ap.add_argument('--include-tagged', action='store_true',
                    help='ikutkan foto tanpa wajah yang BIB-nya terbaca (default: tidak)')
    ap.add_argument('--blur', type=float, default=0,
                    help='ikutkan juga foto ber-BIB yang ketajamannya di bawah angka ini (0 = mati)')
    ap.add_argument('--removed', default='removed.txt', help='foto yang sudah ada di sini tidak ditampilkan lagi')
    ap.add_argument('--keep', default='keep.txt', help='foto yang sudah dicek layak tampil, tidak pernah disembunyikan')
    ap.add_argument('--combined', default='', help='tulis removed + kandidat ke file ini (mode otomatis)')
    ap.add_argument('--reviewed', default='reviewed.txt', help='kandidat yang sudah dicek manual (tidak ditampilkan lagi di review)')
    ap.add_argument('--no-scan', action='store_true', help='jangan periksa foto baru, hanya susun ulang daftar/halaman')
    ap.add_argument('--mark-reviewed', action='store_true',
                    help='catat semua kandidat saat ini (selain keep.txt) sebagai sudah dicek; tidak memeriksa foto baru')
    ap.add_argument('--report', default='review_noface.html')
    ap.add_argument('--list', default='noface_candidates.txt')
    args = ap.parse_args()

    photos = read_photos(os.path.join(args.out, 'photos.csv'))
    cache_path = os.path.join(args.out, 'faces.csv')
    cache = load_cache(cache_path)
    # Hanya foto yang BIB-nya tidak terbaca yang bisa jadi kandidat, jadi hanya itu yang diperiksa
    # (kecuali --include-tagged). Foto ber-BIB tidak pernah disembunyikan otomatis.
    pool = photos if args.include_tagged else [p for p in photos if not p['bibs']]
    todo = [] if (args.mark_reviewed or args.no_scan) else [p for p in pool if p['id'] not in cache]
    print(f'{len(photos)} foto, {len(pool)} tanpa BIB terbaca'
          f'{" (semua diperiksa)" if args.include_tagged else ""}; '
          f'{len(pool) - len(todo)} sudah diperiksa, {len(todo)} diperiksa sekarang.')

    if todo:
        det = cv2.FaceDetectorYN.create(ensure_model(args.model), '', (320, 320), args.score, 0.3, 100)
        new_file = not os.path.exists(cache_path)
        with open(cache_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(['id', 'faces', 'sharp', 'best'])
            t0 = time.time()
            for i, p in enumerate(todo, 1):
                src = os.path.join(args.out, 'web', p['id'] + '.jpg')
                res = analyse(det, src, args.max_side)
                if res is None:
                    continue
                cache[p['id']] = res
                w.writerow([p['id'], res[0], f'{res[1]:.1f}', f'{res[2]:.3f}'])
                if i % 50 == 0 or i == len(todo):
                    f.flush()
                    left = (time.time() - t0) / i * (len(todo) - i) / 60
                    print(f'  {i}/{len(todo)} (sisa ~{left:.0f} menit)', flush=True)

    def read_ids(path):
        ids = set()
        if path and os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.split('#', 1)[0].strip()
                    if line and not line.lower().startswith('bib '):
                        ids.add(line[:-4] if line.lower().endswith('.jpg') else line)
        return ids

    already = read_ids(args.removed)
    keep = read_ids(args.keep)

    def reason(p):
        faces, sharp, _ = cache[p['id']]
        bits = ['tanpa wajah' if faces == 0 else f'{faces} wajah']
        bits.append('tanpa BIB' if not p['bibs'] else 'BIB ' + p['bibs'].replace(' ', ','))
        bits.append(f'tajam {sharp:.0f}')
        return ', '.join(bits)

    cands = []
    for p in photos:
        if p['id'] not in cache or p['id'] in already or p['id'] in keep:
            continue
        faces, sharp, _ = cache[p['id']]
        if faces == 0 and (not p['bibs'] or args.include_tagged):
            cands.append(p)
        elif args.blur and sharp < args.blur and not p['bibs']:
            cands.append(p)

    with open(args.list, 'w', encoding='utf-8') as f:
        f.write(''.join(c['id'] + '\n' for c in cands))
    if args.combined:
        manual = open(args.removed, encoding='utf-8').read() if os.path.exists(args.removed) else ''
        if manual and not manual.endswith('\n'):
            manual += '\n'
        with open(args.combined + '.part', 'w', encoding='utf-8') as f:
            f.write(manual + '# otomatis: tanpa wajah dan tanpa BIB (find_noface.py)\n')
            f.write(''.join(c['id'] + '\n' for c in cands))
        os.replace(args.combined + '.part', args.combined)
    reviewed = read_ids(args.reviewed)
    if args.mark_reviewed:
        new = [c['id'] for c in cands if c['id'] not in reviewed]
        with open(args.reviewed, 'a', encoding='utf-8') as f:
            f.write(''.join(i + '\n' for i in new))
        reviewed.update(new)
        print(f'{len(new)} kandidat dicatat sudah dicek (tetap disembunyikan).')
    to_review = [c for c in cands if c['id'] not in reviewed]
    thumb_rel = os.path.relpath(os.path.join(args.out, 'thumb'), os.path.dirname(os.path.abspath(args.report)))
    write_review(args.report, to_review, thumb_rel.replace(os.sep, '/'), len(photos), reason)

    checked = [p for p in pool if p['id'] in cache]
    noface = sum(1 for p in checked if cache[p['id']][0] == 0)
    print(f'Foto tanpa wajah: {noface} (dari {len(checked)} foto tanpa BIB yang diperiksa).')
    print(f'Kandidat disembunyikan: {len(cands)} '
          f'({"termasuk" if args.include_tagged else "tidak termasuk"} foto yang BIB-nya terbaca).')
    print(f'Belum dicek manual: {len(to_review)} foto. Review: buka {os.path.abspath(args.report)} di browser.')


if __name__ == '__main__':
    main()
