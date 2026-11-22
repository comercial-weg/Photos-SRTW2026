#!/usr/bin/env python3
"""
Satu perintah untuk seluruh proses, memakai pengaturan di tools/event.json.

  python3 tools/run_pipeline.py                 # OCR + resize + index (foto sudah ada di originals/)
  python3 tools/run_pipeline.py --download      # ambil dulu foto dari Google Drive (rclone)
  python3 tools/run_pipeline.py --upload        # sesudahnya upload ke R2 (rclone)
  python3 tools/run_pipeline.py --download --upload   # semuanya
  python3 tools/run_pipeline.py --index-only    # hanya bangun ulang index (mis. setelah ubah rentang BIB)

Aman dijalankan berulang: foto yang sudah diolah dan file yang sudah ter-upload dilewati.
Jalankan dari folder utama repo.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))


def run(cmd, label):
    print(f'\n=== {label} ===\n$ ' + ' '.join(f'"{c}"' if ' ' in c else c for c in cmd), flush=True)
    code = subprocess.call(cmd)
    if code != 0:
        sys.exit(f'Langkah "{label}" gagal (kode {code}). Perbaiki lalu jalankan perintah yang sama lagi.')


def need_rclone():
    if not shutil.which('rclone'):
        sys.exit('rclone belum terpasang. Lihat https://rclone.org/install/ lalu jalankan lagi.')


def main():
    ap = argparse.ArgumentParser(description='Jalankan seluruh proses galeri foto.')
    ap.add_argument('--config', default=os.path.join(TOOLS, 'event.json'))
    ap.add_argument('--download', action='store_true', help='ambil foto dari Google Drive dulu')
    ap.add_argument('--upload', action='store_true', help='upload hasil ke R2 di akhir')
    ap.add_argument('--index-only', action='store_true', help='lewati OCR, hanya bangun index')
    ap.add_argument('--limit', type=int, default=0, help='olah maksimal N foto baru (uji coba)')
    args = ap.parse_args()

    with open(args.config, encoding='utf-8') as f:
        cfg = json.load(f)
    py = sys.executable

    if args.download:
        need_rclone()
        cmd = ['rclone', 'copy', f'{cfg["drive_remote"]}:{cfg["drive_folder"]}', cfg['src'],
               '--transfers', '8', '--progress', '--exclude', '.DS_Store', '--exclude', '._*']
        if cfg.get('drive_shared_with_me'):
            cmd.append('--drive-shared-with-me')
        run(cmd, 'Download foto dari Google Drive')

    if not args.index_only:
        cmd = [py, os.path.join(TOOLS, 'process_photos.py'), '--src', cfg['src'], '--out', cfg['out'],
               '--workers', str(cfg.get('workers', 2))]
        for folder, point in (cfg.get('point_map') or {}).items():
            cmd += ['--point-map', f'{folder}={point}']
        if cfg.get('default_point'):
            cmd += ['--point', cfg['default_point']]
        if args.limit:
            cmd += ['--limit', str(args.limit)]
        run(cmd, 'OCR BIB + resize foto')

    cmd = [py, os.path.join(TOOLS, 'build_index.py'), '--photos', os.path.join(cfg['out'], 'photos.csv'),
           '--out', cfg['site_data']]
    if cfg.get('valid_ranges'):
        cmd += ['--valid-ranges', cfg['valid_ranges']]
    if cfg.get('participants'):
        cmd += ['--participants', cfg['participants'], '--only-registered']
    if cfg.get('removed') and os.path.exists(cfg['removed']):
        cmd += ['--removed', cfg['removed']]
    run(cmd, 'Bangun index pencarian')

    if args.upload:
        need_rclone()
        headers = ['--header-upload', 'Cache-Control: public, max-age=2592000, immutable',
                   '--header-upload', 'Content-Type: image/jpeg']
        for sub, transfers in (('thumb', '32'), ('web', '32'), ('full', '16')):
            run(['rclone', 'copy', os.path.join(cfg['out'], sub), f'{cfg["r2_remote"]}:{cfg["r2_bucket"]}/{sub}',
                 '--transfers', transfers, '--checkers', '32', '--progress'] + headers, f'Upload {sub}/ ke R2')

    print('\nSelesai. Langkah berikutnya:')
    print(f'  1. Cek daftar BIB yang dibuang di atas (kalau ada nomor yang muncul di banyak foto, lebarkan valid_ranges).')
    print(f'  2. Commit dan push folder {cfg["site_data"]} supaya website ter-update:')
    print(f'       git add {cfg["site_data"]} && git commit -m "Update index foto" && git push')
    if not args.upload:
        print('  3. Upload foto ke R2: python3 tools/run_pipeline.py --index-only --upload')


if __name__ == '__main__':
    main()
