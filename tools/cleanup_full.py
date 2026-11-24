#!/usr/bin/env python3
"""
Hemat disk: hapus output/full/<id>.jpg yang sudah ada di R2 dengan ukuran sama.

  python3 tools/cleanup_full.py            # hapus
  python3 tools/cleanup_full.py --dry-run  # hanya hitung

File di R2 tidak disentuh (upload memakai rclone copy, bukan sync). Id yang dihapus
dicatat di output/full_uploaded.txt supaya process_photos.py tidak mengolah ulang.
originals/ sengaja tidak dihapus: kalau dihapus, rclone akan men-download ulang dari Drive.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', default=os.path.join(HERE, 'event.json'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding='utf-8'))
    out = cfg.get('out', 'output')
    full_dir = os.path.join(out, 'full')
    remote = f'{cfg["r2_remote"]}:{cfg["r2_bucket"]}/full'

    local = {}
    for name in os.listdir(full_dir) if os.path.isdir(full_dir) else []:
        if name.lower().endswith('.jpg'):
            local[name] = os.path.getsize(os.path.join(full_dir, name))
    if not local:
        print('output/full kosong, tidak ada yang perlu dihapus.')
        return

    try:
        res = subprocess.run(['rclone', 'lsf', remote, '--format', 'sp', '--separator', '|', '--files-only'],
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f'Gagal membaca daftar file di R2, tidak ada yang dihapus: {exc}')
    in_r2 = {}
    for line in res.stdout.splitlines():
        size, _, name = line.partition('|')
        if name:
            in_r2[name] = int(size)

    ok = [n for n, s in local.items() if in_r2.get(n) == s]
    freed = sum(local[n] for n in ok)
    print(f'output/full: {len(local)} file, {len(ok)} sudah ada di R2 dengan ukuran sama '
          f'({freed / 1024**3:.1f} GiB), {len(local) - len(ok)} belum.')
    if args.dry_run or not ok:
        return
    with open(os.path.join(out, 'full_uploaded.txt'), 'a', encoding='utf-8') as f:
        f.write(''.join(n[:-4] + '\n' for n in ok))
        f.flush()
        os.fsync(f.fileno())
    for n in ok:
        os.remove(os.path.join(full_dir, n))
    print(f'Dihapus dari disk: {len(ok)} file, {freed / 1024**3:.1f} GiB dibebaskan.')


if __name__ == '__main__':
    main()
