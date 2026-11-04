# Hasil pemeriksaan data wilayah Salesforce

Paket ini membantu menentukan data yang perlu dipertahankan, diperbaiki, diperiksa, atau mungkin dibuat baru. Belum ada data Salesforce yang diubah atau dihapus.

## Mulai dari sini

1. Unduh dan ekstrak `Salesforce_cleansing_CSVs_and_scripts.zip`.
2. Buka `output/00_Start_Here/BACA_INI_DULU.md`.
3. Buka `output/00_Start_Here/KAMUS_ISTILAH.md` jika menemukan istilah yang belum jelas.
4. Lihat `Ringkasan_Mencapai_Jumlah_Master.csv` untuk memahami cara mencapai jumlah master.
5. Lihat `Ringkasan_Record_Salesforce_Lain.csv` untuk memahami data duplikat dan data lain yang masih perlu diperiksa.
6. Gunakan workbook `output/Salesforce_cleansing_review.xlsx` jika ingin membaca hasil dalam satu file Excel.

## Arti kelompok utama

- **Sudah benar**: tidak perlu diubah.
- **Perlu diperbaiki**: data sudah ada, tetapi nama atau hubungan ke wilayah induknya perlu diperbaiki.
- **Calon data baru**: lokasi ada di master, tetapi belum ditemukan data Salesforce yang dapat dipakai. Periksa lagi sebelum membuat data baru.
- **Perlu diperiksa sebelum membuat data baru**: data mungkin sudah ada, tetapi ID atau hubungan induknya belum pasti.
- **Data duplikat**: beberapa data mewakili lokasi yang sama. Pindahkan semua referensi sebelum menonaktifkan atau menghapus duplikat.
- **Data lain yang perlu diperiksa**: tentukan apakah data dapat diperbaiki, merupakan duplikat, berada pada tingkat wilayah yang salah, atau tidak termasuk dalam master.

## Urutan kerja

Kerjakan Provinsi terlebih dahulu, lalu Kota/Kabupaten, Kecamatan, dan Kelurahan.

1. Perbaiki data dari folder `01_Update_Proposals`.
2. Tangani duplikat dari folder `02_Duplicate_Handling`.
3. Selesaikan data yang belum jelas dari folder `03_Manual_Review`.
4. Periksa calon data baru dari folder `04_Master_Targets`.
5. Buat data baru hanya jika sudah dipastikan bahwa data tersebut belum ada.

## Catatan penting

Nama yang ditemukan pada tingkat wilayah lain hanya menjadi petunjuk. Contohnya, nama Madura ditemukan sebagai kelurahan di beberapa lokasi, tetapi hal tersebut tidak berarti record Kota/Kabupaten bernama Madura boleh otomatis diarahkan ke kelurahan tersebut.

File usulan masih memuat kolom penjelasan dan belum siap langsung diunggah. Setelah disetujui, buat file upload terpisah yang hanya berisi `Id` dan kolom Salesforce yang benar-benar perlu diubah. Kolom kosong berarti tidak diubah.

Data berasal dari snapshot 29 Oktober 2026. Pemeriksaan nama pada semua tingkat wilayah diperbarui pada 30 Oktober 2026.
