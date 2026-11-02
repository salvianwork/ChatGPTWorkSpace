# Petunjuk review client

## Tujuan review

Client diminta mengonfirmasi tiga jenis keputusan utama:

1. Data yang perlu diubah.
2. Data yang perlu dibuat baru.
3. Data yang perlu diarahkan atau dipetakan ke data lain.

## Cara review yang sederhana

Gunakan `Mandatory for Client/01_REVIEW_CLIENT_SEDERHANA.xlsx` sebagai file utama. Isi 14 baris pada lembar `KEPUTUSAN UTAMA`. Jika hanya beberapa record yang berbeda dari keputusan umum, masukkan record tersebut pada lembar `PENGECUALIAN`. Client tidak perlu mengisi seluruh daftar rinci satu per satu.

Workbook rinci dan workbook mapping ID digunakan sebagai referensi oleh tim data atau saat client ingin memeriksa record tertentu.

## Workbook mapping ID

Gunakan `MAPPING_ID_INVALID_KE_VALID.xlsx` untuk mengisi keputusan `Id_Invalid` harus diarahkan ke `Id_Valid_Final_Client` mana. Workbook tersebut menyatukan data duplikat dan data yang belum jelas. Kolom berwarna kuning perlu diisi oleh client. Jumlah data transaksi yang menggunakan ID invalid harus dihitung dari ekspor transaksi sebelum migrasi dilakukan.

## Data yang sudah sesuai master

Folder `05_DATA_SUDAH_SESUAI_MASTER` dan lembar workbook yang namanya diawali `VALID` berisi record yang sudah cocok dengan master. Data ini disediakan sebagai dasar pemeriksaan jumlah dan tidak memerlukan keputusan client.

Jumlahnya adalah 38 Provinsi, 54 Kota/Kabupaten, 6.081 Kecamatan, dan 46.246 Kelurahan.

## Cara mengisi workbook

Gunakan `Mandatory for Client/02_REVIEW_CLIENT_DATA_REGIONAL.xlsx`. Isi kolom berwarna kuning pada setiap lembar yang perlu ditinjau. Lembar yang namanya diawali `VALID` hanya untuk dibaca.

### Data yang perlu diubah

Pilihan `Keputusan_Client`:

- `SETUJU_UBAH`: nama atau hubungan induk yang diusulkan disetujui.
- `TOLAK_PERUBAHAN`: data tidak boleh diubah sesuai usulan.
- `PERLU_DISKUSI`: keputusan belum dapat diberikan.

### Calon data baru

Pilihan `Keputusan_Client`:

- `SETUJU_BUAT_DATA_BARU`: client sudah memastikan data belum ada.
- `DATA_SUDAH_ADA`: client mengetahui record Salesforce yang seharusnya digunakan.
- `TIDAK_PERLU_DIBUAT`: lokasi tidak perlu dibuat di Salesforce.
- `PERLU_DISKUSI`: keputusan belum jelas.

Jika memilih `DATA_SUDAH_ADA`, isi `Id_Data_Lama_Jika_Sudah_Ada`.

### Data duplikat

Pilihan `Keputusan_Client`:

- `SETUJU_GABUNGKAN`: gunakan ID tujuan yang diusulkan.
- `BUKAN_DUPLIKAT`: kedua record dianggap berbeda.
- `GUNAKAN_ID_TUJUAN_LAIN`: gunakan ID tujuan lain dan isi kolom ID final.
- `PERLU_DISKUSI`: keputusan belum jelas.

### Data yang belum jelas

Pilihan `Keputusan_Client`:

- `PILIH_KANDIDAT_1`, `PILIH_KANDIDAT_2`, atau `PILIH_KANDIDAT_3`.
- `MASUKKAN_ID_LAIN`: client mengetahui ID tujuan yang benar.
- `BUAT_DATA_BARU`: client sudah memastikan data belum ada.
- `DATA_DI_LUAR_MASTER`: data tidak termasuk dalam master regional.
- `PERLU_DISKUSI`: keputusan belum jelas.

Jika memilih kandidat, periksa nama, susunan wilayah, ID tujuan, dan alasannya. Jika kandidat berasal dari tingkat wilayah lain, gunakan hanya sebagai petunjuk.

## Setelah review selesai

Kembalikan workbook yang sudah diisi. Hasilnya akan digunakan untuk membuat file update, insert, dan pemindahan hubungan duplikat secara terpisah.

Jangan mengunggah workbook atau CSV dalam folder ini langsung ke Salesforce.
