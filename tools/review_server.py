#!/usr/bin/env python3
"""
Halaman cek manual foto tanpa wajah, dengan tombol simpan langsung.

  python3 tools/review_server.py        lalu buka http://localhost:8800

Tombol "Simpan & tandai semua sudah dicek":
  - foto yang TIDAK dicentang ditambahkan ke keep.txt (tampil lagi di galeri),
  - sisanya dicatat di reviewed.txt (tetap disembunyikan, tidak muncul lagi di review).
Galeri ikut berubah pada putaran update_loop.sh berikutnya.
Server hanya bisa dibuka dari PC ini sendiri (127.0.0.1). Hentikan dengan Ctrl+C.
"""
import argparse
import http.server
import json
import os
import re
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, 'find_noface.py')
ID_RE = re.compile(r'^[A-Za-z0-9._-]+$')


def run_tool(*extra):
    res = subprocess.run([sys.executable, TOOL, '--combined', 'removed_all.txt', *extra],
                         capture_output=True, text=True)
    return res.returncode, (res.stdout + res.stderr).strip()


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ('/', '/review_noface.html'):
            run_tool('--no-scan')
            self.path = '/review_noface.html'
            return super().do_GET()
        if path.startswith('/output/thumb/') and path.endswith('.jpg') and '..' not in path:
            return super().do_GET()
        self.send_error(404)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != '/save':
            return self.send_error(404)
        if self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
            return self.send_error(403)
        try:
            n = int(self.headers.get('Content-Length', '0'))
            data = json.loads(self.rfile.read(min(n, 5_000_000)) or b'{}')
            keep = [i for i in data.get('keep', []) if isinstance(i, str) and ID_RE.match(i)]
        except (ValueError, AttributeError):
            return self.send_json(400, {'error': 'data tidak valid'})
        if keep:
            with open('keep.txt', 'a', encoding='utf-8') as f:
                f.write(''.join(i + '\n' for i in keep))
        code, out = run_tool('--mark-reviewed')
        if code != 0:
            return self.send_json(500, {'error': out[-300:]})
        m = re.search(r'(\d+) kandidat dicatat sudah dicek', out)
        print(f'Disimpan: {len(keep)} ke keep.txt, {m.group(1) if m else 0} dicatat sudah dicek.', flush=True)
        self.send_json(200, {'kept': len(keep), 'reviewed': int(m.group(1)) if m else 0})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8800)
    args = ap.parse_args()
    if not os.path.exists(os.path.join('output', 'photos.csv')):
        sys.exit('Jalankan dari folder repo (yang berisi output/photos.csv).')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Halaman review: http://localhost:{args.port}   (Ctrl+C untuk berhenti)', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
