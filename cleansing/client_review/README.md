# Paket review client — data regional Salesforce

Folder ini digunakan untuk review dan konfirmasi client sebelum perubahan data dilakukan di Salesforce.

## File yang dibuka terlebih dahulu

1. `REVIEW_CLIENT_DATA_REGIONAL.xlsx` — file utama untuk melihat data dan mengisi keputusan client.
2. `MAPPING_ID_INVALID_KE_VALID.xlsx` — file khusus untuk menentukan ID invalid harus diarahkan ke ID valid mana sebelum hubungan data transaksi dipindahkan.
3. `PETUNJUK_REVIEW_CLIENT.md` — cara melakukan review.
4. `RINGKASAN_DATA_CLIENT.csv` — jumlah data per kelompok tindakan.
5. `KAMUS_ISTILAH.md` — penjelasan istilah dalam bahasa sederhana.

Workbook sekarang mempunyai empat lembar yang namanya diawali `VALID`. Lembar tersebut menjelaskan record yang sudah sesuai master dan tidak memerlukan keputusan client.

## File ZIP

- `CLIENT_REVIEW_CSV_DAN_PETUNJUK.zip` adalah paket utama. Paket ini berisi petunjuk, CSV keputusan, workbook mapping ID, dan folder `05_DATA_SUDAH_SESUAI_MASTER`.
- `CLIENT_REVIEW_PILIHAN_MAPPING.zip` hanya referensi tambahan jika pilihan dalam folder `04_DATA_BELUM_JELAS` belum cukup.

Client dapat memulai dari workbook atau paket utama. ZIP pilihan mapping tidak perlu dibuka pada review awal.

Paket ini bukan file upload Salesforce. Setelah keputusan client selesai, hasil review perlu diproses menjadi file update, insert, dan pemindahan hubungan duplikat secara terpisah.

Belum ada data Salesforce yang diubah atau dihapus.
