# Baca ini dulu

Tujuannya adalah memastikan setiap lokasi dalam master mempunyai satu data Salesforce yang benar.

## Arti angka dalam ringkasan

- **Sudah benar**: tidak perlu diubah.
- **Perlu diperbaiki**: data sudah ada, tetapi nama atau hubungan ke induknya perlu diperbaiki.
- **Calon data baru**: lokasi ada di master, tetapi belum ditemukan data Salesforce yang dapat dipakai. Periksa lagi sebelum membuat data baru.
- **Perlu diperiksa sebelum membuat data baru**: data mungkin sudah ada, tetapi ID atau hubungan induknya belum pasti. Jangan membuat data baru sebelum pemeriksaan selesai.
- **Data duplikat**: pindahkan seluruh referensi ke data yang dipertahankan sebelum menonaktifkan atau menghapus duplikat.

Gunakan `Ringkasan_Mencapai_Jumlah_Master.csv` untuk melihat cara mencapai jumlah master. Gunakan `Ringkasan_Record_Salesforce_Lain.csv` untuk melihat duplikat dan data lain yang masih perlu diperiksa.

Urutan kerja: perbaiki data utama, tangani duplikat, selesaikan data yang belum jelas, lalu buat data baru yang benar-benar belum ada. Kerjakan dari Provinsi, Kota/Kabupaten, Kecamatan, lalu Kelurahan.

Tidak ada file dalam paket ini yang boleh langsung diunggah tanpa pemeriksaan.
