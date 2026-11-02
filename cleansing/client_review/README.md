# Paket review client — data regional Salesforce

Folder ini digunakan untuk review dan konfirmasi client sebelum perubahan data dilakukan di Salesforce.

## File yang dibuka terlebih dahulu

1. `REVIEW_CLIENT_DATA_REGIONAL.xlsx` — file utama untuk mengisi keputusan client.
2. `PETUNJUK_REVIEW_CLIENT.md` — cara melakukan review.
3. `RINGKASAN_DATA_CLIENT.csv` — jumlah data per kelompok tindakan.
4. `KAMUS_ISTILAH.md` — penjelasan istilah dalam bahasa sederhana.

## File ZIP

- `CLIENT_REVIEW_CSV_DAN_PETUNJUK.zip` berisi petunjuk, ringkasan, dan seluruh CSV keputusan utama. Workbook tersedia sebagai file terpisah agar mudah dibuka.
- `CLIENT_REVIEW_PILIHAN_MAPPING.zip` berisi seluruh pilihan mapping lengkap untuk data yang belum jelas.

Pilihan mapping dipisahkan karena ukurannya besar. Client dapat memulai dari paket utama dan hanya membuka paket mapping jika membutuhkan pilihan tambahan.

## Cara client memberikan keputusan

Isi kolom berwarna kuning dalam workbook. Pilihan jawaban tersedia dalam dropdown.

Paket ini bukan file upload Salesforce. Setelah keputusan client selesai, hasil review perlu diproses menjadi file update, insert, dan pemindahan hubungan duplikat secara terpisah.

Belum ada data Salesforce yang diubah atau dihapus.
