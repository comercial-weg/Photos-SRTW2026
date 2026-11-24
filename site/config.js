/*
 * Pengaturan galeri foto SRTW 2026.
 * Ubah nilai di sini saja; file lain tidak perlu disentuh.
 */
window.SRTW_CONFIG = {
  eventName: 'She Runs The World 2026',

  // Alamat folder foto. Isinya tiga subfolder: thumb/, web/, full/
  // Uji coba 50 foto asli (CAM AAN): '/pilot-photos' (unduh per foto = 4000 px; versi final = file asli dari R2)
  // Setelah foto di-upload ke R2: 'https://foto.domainkamu.id'
  photoBaseUrl: 'https://foto.sherunstheworld.id',

  // Folder index hasil tools/build_index.py
  dataBaseUrl: '/data',

  // Link per BIB: true  -> /bib/54326
  //               false -> /?bib=54326
  //               'auto'-> /?bib= saat dibuka di localhost, /bib/ saat online
  prettyUrls: 'auto',

  // Versi foto yang dimasukkan ke ZIP "Download semua".
  // 'web' (2048 px, ±0,3 MB per foto) jauh lebih ringan untuk HP dibanding 'full' (file asli 4-7 MB).
  zipVariant: 'web',
  // Disimpan di website sendiri supaya ZIP tidak bergantung pada CDN luar
  jszipUrl: '/assets/jszip.min.js',

  // Link catatan waktu resmi. {bib} diganti nomor BIB.
  // Kosongkan ('') kalau belum ada. Hanya tampil untuk kategori di resultsCategories.
  resultsUrl: '',
  resultsCategories: ['10K'],

  // Titik foto. id harus sama dengan kolom "point" di photos.csv
  points: [
    { id: 'village', label: 'Race Village', desc: 'Photo wall & warm up, 05.00–05.40' },
    { id: 'start', label: 'Start', desc: '10K 05.45, 5K 06.00' },
    { id: 'rute', label: 'On Race', desc: 'Sepanjang rute 5K & 10K' },
    { id: 'finish', label: 'Finish', desc: 'Plaza Timur, gate tutup 08.30' }
  ],

  // Halaman depan langsung menampilkan semua foto (urut jam)
  showAllOnHome: true,

  // Label titik foto (Race Village/Start/On Race/Finish) di kartu, pratinjau, dan tombol pilihan titik
  showPointLabels: false,
  // Daftar foto: foto dengan BIB terbaca tampil dulu, foto tanpa BIB di halaman akhir
  taggedFirst: true,
  // Baris filter jam (05.00–05.15, dst.) di daftar foto
  showTimeFilter: false,

  // Jumlah nomor halaman berurutan yang ditampilkan di bawah daftar foto
  pagerWindow: 10,

  // Jumlah foto per halaman di daftar foto
  pageSize: 20,
  // Lebar rentang jam (menit) untuk filter jam di "Cari per titik foto"
  slotMinutes: 15
};
