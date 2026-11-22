#!/usr/bin/env bash
# Upload hasil tools/process_photos.py ke Cloudflare R2 dengan rclone.
#
# Persiapan sekali: buat remote rclone bernama "r2" (lihat README, bagian R2).
# Pemakaian:
#   tools/upload_r2.sh                    # folder output, bucket srtw-photos
#   tools/upload_r2.sh output srtw-photos
#
# Aman dijalankan ulang: rclone hanya mengirim file yang belum ada atau berubah.
set -euo pipefail

OUT="${1:-output}"
BUCKET="${2:-srtw-photos}"
REMOTE="${R2_REMOTE:-r2}"

for sub in thumb web full; do
  if [ ! -d "$OUT/$sub" ]; then
    echo "Folder $OUT/$sub tidak ada. Jalankan tools/process_photos.py dulu." >&2
    exit 1
  fi
done

# Nama foto tidak pernah berubah, jadi boleh di-cache lama oleh browser dan CDN
HEADERS=(--header-upload "Cache-Control: public, max-age=2592000, immutable"
         --header-upload "Content-Type: image/jpeg")

# thumb dan web dulu supaya grid dan pratinjau cepat siap; full paling besar
echo "== thumb ==" && rclone copy "$OUT/thumb" "$REMOTE:$BUCKET/thumb" --transfers 32 --checkers 32 "${HEADERS[@]}" --progress
echo "== web =="   && rclone copy "$OUT/web"   "$REMOTE:$BUCKET/web"   --transfers 32 --checkers 32 "${HEADERS[@]}" --progress
echo "== full =="  && rclone copy "$OUT/full"  "$REMOTE:$BUCKET/full"  --transfers 16 --checkers 32 "${HEADERS[@]}" --progress

echo "Selesai. Cek jumlah file:"
for sub in thumb web full; do
  printf '  %-5s lokal %6s  R2 %6s\n' "$sub" \
    "$(find "$OUT/$sub" -name '*.jpg' | wc -l | tr -d ' ')" \
    "$(rclone lsf "$REMOTE:$BUCKET/$sub" --files-only | wc -l | tr -d ' ')"
done
