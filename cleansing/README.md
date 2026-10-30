# Tinjauan cleansing data wilayah Salesforce

Paket ini berisi usulan dan bahan tinjauan, bukan perubahan yang sudah diterapkan ke Salesforce. Snapshot data: 29 Oktober 2026. Penelusuran lintas tingkat dan penerjemahan diperbarui pada 30 Oktober 2026.

## Mulai di sini

1. Unduh dan ekstrak `Salesforce_cleansing_CSVs_and_scripts.zip`.
2. Buka `output/README.md` untuk panduan 27 CSV berdasarkan kegunaan.
3. Buka workbook terpisah `output/Salesforce_cleansing_review.xlsx` untuk melihat ringkasan dan kandidat tinjauan dalam Bahasa Indonesia.

Di dalam ZIP, CSV dikelompokkan menjadi ringkasan, usulan update, penanganan duplikat, tinjauan manual, target master, seluruh record, analisis gap awal, dan audit. Nama file/folder tetap dipertahankan agar mudah ditelusuri ke versi sebelumnya.

## Penelusuran lintas tingkat

Nama yang belum cocok ditelusuri pada provinsi, kota/kabupaten, kecamatan, dan kelurahan dalam master dan ekspor Salesforce. Temuan master dibedakan dari kemunculan dalam ekspor yang belum terverifikasi. Pencarian memakai nama yang sama setelah normalisasi, bukan kecocokan sebagian kata.

Dalam `Review_candidates.csv`, baris `Jenis_Bukti = TEMUAN_LINTAS_TINGKAT` hanya berisi alasan dan bukti lokasi; `Id_Target_Kandidat` selalu kosong. Jika nama tidak ditemukan pada objek asal tetapi ditemukan pada tingkat lain, saran kemiripan lama diganti oleh bukti lintas tingkat. Kemunculan nama yang sama tidak membuktikan bahwa lokasi tersebut sama, khususnya jika provinsi berbeda.

Contoh: Madura pada objek kota/kabupaten ditemukan sebagai nama kelurahan di beberapa provinsi dalam master, bukan sebagai kota/kabupaten valid di Jawa Timur. Ini tidak membenarkan pemetaan otomatis ke kelurahan tersebut.

## Bahasa dan kompatibilitas

Judul kolom laporan, status, alasan, catatan, panduan, serta workbook diterjemahkan ke Bahasa Indonesia. ID, nama wilayah, nama file/folder, dan nama API Salesforce (`Id`, `Name`, `Provinsi__c`, `Kota_Kabupaten__c`, `Kecamatan__c`) dipertahankan. Skema JSON audit teknis dipertahankan. Padanan judul kolom tersedia dalam panduan penggunaan.

Keputusan pada 8.595 usulan update dan 3.105 pemetaan duplikat tidak diubah oleh penelusuran ini. Semua 91.306 record sumber tetap tercakup. Kasus yang memerlukan konfirmasi tetap memerlukan tinjauan.

## Sebelum menerapkan

Tinjau dalam urutan provinsi → kota/kabupaten → kecamatan → kelurahan. File usulan memuat kolom audit dan bukan file Data Loader siap pakai. Siapkan file terpisah yang hanya berisi Id dan kolom API yang disetujui. Kolom usulan kosong berarti tidak diubah, bukan dikosongkan di Salesforce. Untuk duplikat, verifikasi dan pindahkan semua referensi sebelum menonaktifkan record sumber. Target master yang belum terverifikasi bukan daftar insert otomatis.

## Menghasilkan ulang

Gunakan versi dependensi dalam `requirements.txt`, lalu jalankan dari root repository:

```bash
python cleansing/scripts/cleanse.py --input-dir . --output-dir cleansing/output
python cleansing/scripts/review_dan_terjemahkan.py --input-dir . --output-dir cleansing/output
```

Generator menghasilkan data dasar, kemudian tahap kedua menelusuri nama lintas tingkat dan menerjemahkan keluaran. Tidak ada koneksi atau perubahan ke Salesforce. Rincian validasi penelusuran tersedia di `output/07_Audit/Laporan_tinjauan_bahasa.md` dalam ZIP.
