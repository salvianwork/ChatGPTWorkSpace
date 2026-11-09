# Paket review client — data regional Salesforce

Folder ini digunakan untuk review dan konfirmasi client sebelum perubahan data dilakukan di Salesforce.

## File yang dikirim ke client

Buka folder `Mandatory for Client` dan kirim kedua workbook di dalamnya:

1. `01_REVIEW_CLIENT_SEDERHANA.xlsx` — file utama; client cukup mengisi 14 keputusan dan mencatat pengecualian.
2. `02_REVIEW_CLIENT_DATA_REGIONAL.xlsx` — rincian lengkap jika client ingin memeriksa record tertentu.

## File pendukung tim data

- `MAPPING_ID_INVALID_KE_VALID.xlsx` digunakan setelah keputusan client untuk menyiapkan pemetaan ID.
- `CLIENT_REVIEW_PILIHAN_MAPPING.zip` hanya digunakan jika pilihan pada data belum jelas belum cukup.
- `CLIENT_REVIEW_CSV_DAN_PETUNJUK.zip` berisi seluruh paket, termasuk folder `Mandatory for Client` dan CSV referensi.

`PETUNJUK_REVIEW_CLIENT.md`, `RINGKASAN_DATA_CLIENT.csv`, dan `KAMUS_ISTILAH.md` dapat digunakan saat membutuhkan penjelasan tambahan.

Paket ini bukan file upload Salesforce. Setelah keputusan client selesai, hasil review perlu diproses menjadi file update, insert, dan pemindahan hubungan duplikat secara terpisah.

Belum ada data Salesforce yang diubah atau dihapus.
