/*
 * Pengaturan galeri foto SRTW 2026.
 * Ubah nilai di sini saja; file lain tidak perlu disentuh.
 */
window.SRTW_CONFIG = {
  eventName: 'She Runs The World 2026',

  // Alamat folder foto. Isinya tiga subfolder: thumb/, web/, full/
  // Selama demo: '/demo-photos'
  // Setelah foto di-upload ke R2: 'https://foto.domainkamu.id'
  photoBaseUrl: '/demo-photos',

  // Folder index hasil tools/build_index.py
  dataBaseUrl: '/data',

  // Link per BIB: true  -> /bib/10234
  //               false -> /?bib=10234
  //               'auto'-> /?bib= saat dibuka di localhost, /bib/ saat online
  prettyUrls: 'auto',

  // Versi foto yang dimasukkan ke ZIP "Download semua".
  // 'web' (sekitar 2048 px) jauh lebih ringan untuk HP dibanding 'full'.
  zipVariant: 'web',
  // Disimpan di website sendiri supaya ZIP tidak bergantung pada CDN luar
  jszipUrl: '/assets/jszip.min.js',

  // Link catatan waktu resmi. {bib} diganti nomor BIB.
  // Kosongkan ('') kalau belum ada. Hanya tampil untuk kategori di resultsCategories.
  resultsUrl: '',
  resultsCategories: ['10K'],

  // Link untuk minta foto dihapus, misalnya WhatsApp panitia:
  // 'https://wa.me/62812xxxxxxx?text=Halo%2C%20saya%20ingin%20minta%20foto%20dihapus'
  removalUrl: '',

  // Titik foto. id harus sama dengan kolom "point" di photos.csv
  points: [
    { id: 'village', label: 'Race Village', desc: 'Photo wall & warm up, 05.00–05.40' },
    { id: 'start', label: 'Start', desc: '10K 05.45, 5K 06.00' },
    { id: 'rute', label: 'Di Rute', desc: 'Sepanjang rute 5K & 10K' },
    { id: 'finish', label: 'Finish', desc: 'Plaza Timur, gate tutup 08.30' }
  ],

  // Jumlah foto per muatan di "Cari per titik foto"
  pageSize: 24,
  // Lebar rentang jam (menit) untuk filter jam di "Cari per titik foto"
  slotMinutes: 15
};
