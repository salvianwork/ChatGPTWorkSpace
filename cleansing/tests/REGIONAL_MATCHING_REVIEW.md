# Pencocokan regional untuk rekomendasi review

Aturan baru hanya mengubah daftar kandidat. Penetapan mapping, ID tujuan final,
status valid, update, dan duplikat tetap menggunakan pemeriksaan deterministik
sebelumnya. `Candidate_Target_Id` adalah ID usulan untuk review, bukan penetapan
mapping otomatis. `Similarity` tetap skor kemiripan karakter, bukan probabilitas.

Urutan kandidat: nama sama setelah normalisasi, alias terdaftar, nama inti
Kota/Kabupaten, lalu kemiripan teks. Kandidat dibatasi ke hierarki induk yang
sama. Jika induk tidak diketahui, hanya nama sama setelah normalisasi yang
boleh muncul; alias dan nama inti tidak dipakai untuk menebak provinsi.

Awalan administratif tetap disimpan dalam nama asli. Nama inti yang cocok
antara Kota dan Kabupaten diberi keterangan konflik jenis. Jika lebih dari
satu wilayah memiliki nama inti sama, semua kandidat nama inti dipertahankan
dan diberi keterangan ambigu. Maksimal tiga kandidat kemiripan teks ditambahkan;
bukti nama sama, alias, dan nama inti tidak dipotong oleh batas tersebut.

Alias tersimpan dalam `cleansing/scripts/regional_aliases.json`. Setiap entri
harus menyebut tingkat (0 provinsi, 1 kota/kabupaten, 2 kecamatan, 3 kelurahan),
provinsi, alias, dan nama target persis dalam master. Alias awal hanya
`Tangsel → Kota Tangerang Selatan` pada tingkat Kota/Kabupaten di Banten.
Penambahan alias harus diperiksa terhadap master dan konteks wilayah;
tidak ada pembentukan singkatan otomatis. Alias tidak dijalankan bila target
tidak tersedia di pool master dengan induk yang sama.

Temuan lintas tingkat tidak lagi menghapus kandidat pada tingkat yang sama.
Kandidat pada tingkat yang sama tampil lebih dahulu; temuan lintas tingkat
selalu tanpa ID tujuan kandidat. Workbook dan paket client yang telah ada
tidak diregenerasi oleh perubahan script ini.

## Pengujian

Dari root repository:

```sh
python -m unittest discover -s cleansing/tests -v
python cleansing/scripts/cleanse.py --output-dir /tmp/regional-trial
python cleansing/scripts/review_dan_terjemahkan.py --input-dir "$PWD" --output-dir /tmp/regional-trial
python cleansing/tests/check_regional_outputs.py /tmp/regional-baseline-output /tmp/regional-trial
```

Pembanding membutuhkan dua hasil pipeline lengkap yang sudah diterjemahkan.
Gunakan folder output berbeda untuk baseline dan trial; script penerjemahan
hanya menerima keluaran generator asli, bukan hasil terjemahan sebelumnya.
Script pembanding memeriksa seluruh CSV nonkandidat, bukti lintas tingkat,
serta rekomendasi pertama untuk record Banjar dan Tangsel yang dibahas.

## Hasil validasi pada snapshot repository

- 7 pengujian unit lulus.
- Pipeline generator dan penerjemahan lama serta baru selesai dengan sukses.
- Seluruh 28 CSV nonkandidat identik, termasuk 91.306 record sumber, ID,
  status mapping, usulan update, dan pemetaan duplikat.
- Kandidat review: 67.606 menjadi 71.502 baris. Urutan atau tujuan kandidat
  tingkat sama berubah untuk 2.882 record sumber.
- Bukti lintas tingkat identik selain nomor urut tampilan; semua ID kandidat
  lintas tingkat tetap kosong.
- Kandidat pertama Banjar Jawa Barat: Kota Banjar,
  `a1ofC00000EcXD8QAN`.
- Kandidat pertama Tangsel Banten: Kota Tangerang Selatan,
  `a1oJ40000009JP0IAM`.
- Seluruh workbook, ZIP, CSV sumber, dan keluaran client dalam repository
  tetap tidak berubah. Keluaran percobaan disimpan di `/tmp`.

## Kecamatan yang namanya ditemukan sebagai kelurahan

Jika kecamatan yang belum cocok mempunyai nama yang persis cocok setelah
normalisasi dengan kelurahan master dalam kabupaten/kota induk yang sudah
teridentifikasi, rekomendasikan kecamatan induk kelurahan tersebut untuk review.
Alasannya menyebut lokasi kelurahan dan dua kemungkinan: record memang dimaksudkan
sebagai kecamatan, atau sebenarnya kelurahan yang memerlukan koreksi tingkat.
Kandidat fuzzy yang hanya mirip ejaannya tidak ditampilkan untuk kasus ini.
Semua kecamatan induk yang cocok dipertahankan jika ambigu. Induk yang belum
diketahui atau berbeda tidak dipakai untuk membuat rekomendasi ini.

Ini tetap hipotesis maksud record, bukan kecocokan nama kecamatan. Karena itu,
skor kemiripan dikosongkan, status mapping tidak diubah, dan ID final client
menunggu keputusan. ID pada pilihan kandidat merujuk kecamatan yang diusulkan;
ID pada bukti `TEMUAN_LINTAS_TINGKAT` tetap kosong.

Contoh: Kecamatan Kingking pada Kabupaten Tuban mendapatkan rekomendasi
Kecamatan Tuban (`a1pJ40000008Y6BIAU`), disertai bukti
`Jawa Timur | Kab. Tuban | Tuban | Kingking` pada tingkat Kelurahan.
Bangilan tidak lagi direkomendasikan untuk record ini.

Validasi perluasan ini: 9 pengujian unit lulus. Dua pipeline lengkap berhasil;
seluruh 28 CSV nonkandidat identik. Rekomendasi tingkat sama berubah untuk 403
record; jumlah baris kandidat/informasi review berubah dari 71.502 ke 71.530.
Bukti lintas tingkat tetap sama selain nomor urut, dan seluruh ID kandidat
lintas tingkat tetap kosong. Banjar dan Tangsel mempertahankan rekomendasi utama.

Penerapan workbook memperbarui 2.536 sel pilihan/alasan pada 441 record
(termasuk perubahan rekomendasi untuk 403 record). Validasi workbook lulus:
15 sheet dengan urutan tetap, seluruh ID sumber dan input client tetap,
13 sheet lainnya identik, dropdown tetap, tanpa formula atau ID final baru.
Pilihan dan jumlah kandidat pada setiap record sesuai keluaran script.
