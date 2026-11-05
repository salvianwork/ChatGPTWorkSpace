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

## Kota/Kabupaten yang namanya ditemukan pada tingkat lebih rendah

Aturan hierarki juga berlaku bagi Kota/Kabupaten yang belum cocok: jika nama
sumber ditemukan persis sebagai kecamatan atau kelurahan master dalam provinsi
induk yang sudah diketahui, usulkan kota/kabupaten dari lokasi tersebut.
Alasan menyebut tingkat dan lokasi sebenarnya serta dua kemungkinan maksud
record. Nama persis, alias, dan nama inti yang sudah mempunyai kandidat tetap
dipertahankan; kandidat hierarki ditambahkan tanpa menduplikasi tujuan. Kandidat
yang hanya mirip ejaannya dihapus ketika bukti hierarki tersedia.

Jika beberapa kota/kabupaten cocok, pertahankan semua dan beri label ambigu.
Jangan menebak provinsi yang kosong atau memakai lokasi di provinsi berbeda.
Skor kemiripan untuk inferensi hierarki dikosongkan; ID final tetap menunggu
client. Ini juga mencakup record Kota/Kabupaten bernama seperti kelurahan,
tanpa mengubah aturan Kecamatan dari temuan Kelurahan sebelumnya.

Contoh Babelan: usulkan `Jawa Barat | Kab. Bekasi` dengan ID kandidat
`a1oJ40000009JMEIA2` dan bukti `Kecamatan: Jawa Barat | Kab. Bekasi | Babelan`.
Jika sebenarnya record dimaksudkan sebagai kecamatan, client perlu mengonfirmasi
koreksi tingkat wilayah. Kab. Sumedang tidak lagi menjadi kandidat untuk Babelan.

Validasi perluasan Kota/Kabupaten: 11 pengujian unit lulus dan kedua tahap
pipeline selesai. Seluruh 28 CSV nonkandidat identik terhadap versi sebelumnya;
rekomendasi tingkat sama berubah untuk 23 record. Baris kandidat/informasi review
berubah dari 71.530 ke 71.528. Bukti lintas tingkat sama selain nomor urut, dan
semua ID kandidat lintas tingkat tetap kosong. Banjar, Tangsel, dan Kingking
mempertahankan rekomendasi utama; Babelan merekomendasikan Kab. Bekasi.

Penerapan workbook: 211 sel jumlah/pilihan/alasan diperbarui pada 23 record.
Validasi semua baris kandidat dan pilihan tampilan lulus. Seluruh 15 sheet tetap
dengan urutan sama, jumlah record sumber tetap, 13 sheet lain identik, input
client dan dropdown tetap, tanpa formula atau ID final baru.

## Nama wilayah dengan keterangan induk setelah koma

Untuk rekomendasi review, nama seperti `Buay Pemaca, Ogan Komering Ulu Selatan`
dapat dibandingkan dengan `Buay Pemaca` hanya setelah suffix kabupatennya
cocok dengan induk yang sudah teridentifikasi. Nama sumber dan normalisasi
untuk mapping deterministik tidak diubah. Rekomendasi ini tetap memerlukan
konfirmasi client dan tidak mengisi ID final.

Aturan berlaku bagi Kota/Kabupaten, Kecamatan, dan Kelurahan. Jika terdapat
beberapa suffix setelah koma, urutannya harus sesuai induk langsung lalu
leluhurnya. Semua suffix harus cocok; suffix kosong, provinsi salah, jenis
Kota/Kabupaten bertentangan, atau induk yang tidak diketahui tidak boleh
diabaikan. Nama tanpa koma tidak dipotong berdasarkan kecocokan sebagian kata.

Skor `Kemiripan` tetap dihitung dari nama sumber lengkap. Kandidat nama yang
sama dengan keterangan induk cocok diprioritaskan berdasarkan bukti struktur,
meskipun skor teks mentah di bawah 50. Skor bukan probabilitas mapping benar.
14 pengujian unit mencakup kasus positif, batas wilayah, dan konflik suffix.

Validasi aturan koma: generator dan penerjemahan lama serta baru berhasil
selesai; seluruh 28 CSV nonkandidat identik. Tujuan atau urutan rekomendasi
berubah untuk 30 record; total baris kandidat/informasi review berubah dari
71.528 ke 71.548. Workbook memperbarui 265 sel jumlah/pilihan/alasan pada 114
record (termasuk penjelasan baru untuk kandidat yang tujuannya tetap sama).
Buay Pemaca direkomendasikan dengan ID kandidat `a1pfC00000DcH7xQAF` dalam
hierarki `Sumatra Selatan | Kab. Ogan Komering Ulu Selatan | Buay Pemaca`.

Validasi workbook lulus: semua 15 sheet dengan urutan sama, jumlah/urutan baris
sumber tetap, hanya kolom kandidat L:X dan daftar PILIHAN MAPPING diperbarui.
13 sheet lain identik, seluruh ID sumber dan input client tetap, dropdown
tetap, wrap text aktif, tanpa formula atau ID final baru. Semua kandidat
dan jumlah pilihan sesuai keluaran script; contoh sebelumnya tetap benar.

## Review lokasi yang cocok dan penjelasan ID

Semua record review yang lokasinya sudah cocok dengan master kini mempunyai
kandidat lokasi, termasuk yang ID canonical atau induknya belum terverifikasi.
Penambahan kandidat dilakukan sesudah keputusan deterministik selesai. Status
mapping, daftar update, duplikat, dan seluruh ID sumber tidak diubah oleh tahap
ini. Bila ID terkait sama dengan sumber, rekomendasi ditandai sebagai koreksi
record yang sama, bukan usulan pemindahan duplikat.

Setiap kandidat tingkat sama membawa empat field tambahan:

| Kolom | Arti |
|---|---|
| Jenis_Rekomendasi | Kandidat record tujuan, kecocokan lokasi perlu review, koreksi record yang sama, hipotesis tingkat wilayah, atau lokasi dengan induk sumber belum diketahui. |
| Status_Verifikasi_ID | ID terverifikasi, alternatif terverifikasi untuk review, konflik relasi, induk perlu konfirmasi, ID master berbeda hierarki/tidak ditemukan/ambigu, record tersedia belum terverifikasi, atau belum ada ID terverifikasi. |
| Alasan_Verifikasi_ID | Alasan ID belum dapat dipakai, konteks konflik/pemulihan induk sumber, dan apakah ID yang dibahas sama dengan sumber. |
| ID_Master_Perlu_Verifikasi | ID dari master atau record ekspor pada lokasi master tersebut yang masih perlu diverifikasi. Field ini bukan ID tujuan final dan bukan ID terverifikasi. Dapat berisi beberapa ID dipisahkan titik koma. |

ID pada `Id_Target_Kandidat` / `Pilihan_n_Id_Target` hanya diisi bila canonical
lama sudah terverifikasi, atau terdapat satu alternatif dengan nama persis,
seluruh hierarki cocok, tanpa konflik dan tanpa pemulihan induk/leluhur.
Alternatif diberi status `ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW`; keputusan
canonical dan pemindahan referensi tetap menunggu konfirmasi. Master ID yang
berkonflik tetap ditampilkan terpisah. Bila tidak ada ID sesuai hierarki,
field ID terverifikasi tetap kosong dengan penjelasan. ID Muara dari Papua
misalnya tidak boleh dipakai untuk Muara di Tapanuli Utara.

Kamus alias menambahkan jakbar. Untuk Kota/Kabupaten tanpa induk, hanya alias
atau usulan nama eksplisit dalam CSV yang menghasilkan satu lokasi master
unik yang dapat ditampilkan untuk review. Provinsi sumber tidak diisi atau
diasumsikan sudah benar. Bila alias dan usulan menunjuk lokasi berbeda, tidak
ada kandidat unik dari aturan ini.

Konteks kecamatan kini menerima nama kelurahan persis atau variasi terbatas
`nama sumber + Kota`, dalam kota/kabupaten yang sudah diketahui. Bukti variasi
tersebut diberi keterangan bahwa nama tidak cocok persis. Buntok Kota menjadi
bukti untuk Dusun Selatan, tanpa menggunakan substring bebas atau kabupaten
lain. Semua kecamatan yang cocok tetap ditampilkan bila ambigu.

### Penerapan workbook yang dapat diulang

Install dependency sesuai `cleansing/requirements.txt` jika belum tersedia.
`lxml` dipakai untuk mempertahankan XML sheet lain, style lama, dan dropdown.
Dari root repository, setelah generator dan penerjemahan selesai:

```sh
python cleansing/scripts/update_regional_client_workbook.py \
  --workbook 'cleansing/client_review/Mandatory for Client/02_REVIEW_CLIENT_DATA_REGIONAL.xlsx' \
  --candidates /tmp/regional-trial/03_Manual_Review/Review_candidates.csv \
  --backup /tmp/regional-before-apply.xlsx \
  --report /tmp/regional-apply-report.json

python cleansing/tests/check_client_review_workbook.py \
  /tmp/regional-before-apply.xlsx \
  'cleansing/client_review/Mandatory for Client/02_REVIEW_CLIENT_DATA_REGIONAL.xlsx' \
  /tmp/regional-trial/03_Manual_Review/Review_candidates.csv
```

Gunakan nama backup baru setiap penerapan. Tool menolak menimpa backup yang
sudah ada. Workbook sementara diperiksa sebagai ZIP sebelum mengganti file
asli. Hanya DATA BELUM JELAS dan PILIHAN MAPPING yang diperbarui.

DATA BELUM JELAS mempertahankan 32 kolom lama A:AF. Tambahan 12 kolom AG:AR
berisi empat field penjelasan untuk masing-masing Pilihan 1–3. Input client
Y:AF tetap pada posisi, nilai, dan format semula. PILIHAN MAPPING menambahkan
empat kolom Q:T setelah 16 kolom lama. Kolom tambahan memiliki wrap text;
filter diperluas mengikuti tambahan kolom/baris. Sheet lain tidak diubah.

### Validasi perluasan ini

- 22 pengujian unit lulus, mencakup variasi nama terbatas, konflik/provinsi
  kosong, ID master salah lokasi/tidak ada, alternatif ID aman dan ambigu,
  serta input helper yang tetap tidak dimutasi. Regresi pipeline memeriksa
  keenam contoh audit dan seluruh contoh yang dibahas sebelumnya.
- Pipeline final selesai; seluruh 28 CSV nonkandidat identik terhadap baseline.
  Semua keputusan mapping, update, duplikat, dan ID sumber tetap sama.
- Baris kandidat/informasi review berubah dari 71.548 menjadi 79.685.
  Urutan/tujuan kandidat tingkat sama berubah untuk 10.267 record pipeline.
- Workbook memperbarui 36.829 sel kandidat lama pada 10.237 record. Sebanyak
  180.869 sel metadata ditambahkan/diisi pada 25.070 record. Perbedaan jumlah
  record pipeline/workbook terjadi karena workbook menampilkan tiga pilihan
  pertama dan jumlah total, sedangkan pipeline menyimpan seluruh kandidat.
- Semua kandidat tingkat sama mempunyai status dan penjelasan ID. Dari 72.131
  baris kandidat tingkat sama, 5.271 slot memiliki satu alternatif ID yang
  lolos verifikasi hierarki untuk review; angka ini bukan jumlah record unik
  dan tidak berarti penetapan canonical atau ID final otomatis.
- Jakbar mengarah Kota Jakarta Barat dan Buntok ke Dusun Selatan. Martapura dan
  Lohong muncul sebagai lokasi cocok dengan ID sumber/master terpisah untuk
  verifikasi induk. Cintaasih menjelaskan konflik kota langsung versus lookup
  kecamatan. Hutanagodang mempertahankan Muara dan Purbatua; ID Muara Tapanuli
  Utara tetap kosong karena belum terverifikasi, disertai penjelasan.
- Validasi workbook membandingkan XML terlindungi dan semua nilai kandidat
  terhadap CSV, memeriksa tambahan kolom, 15 sheet dengan urutan tetap,
  jumlah/urutan record sumber, input client dan dropdown, serta tidak adanya
  formula atau ID final baru. 13 sheet lainnya identik.

Penerapan ulang pada workbook yang sudah diperbarui menghasilkan nol perubahan
sel kandidat maupun metadata; kolom tambahan tidak terduplikasi.

## Tampilan client yang disederhanakan (versi terbaru)

Bagian ini menggantikan susunan 44 kolom dan metadata terpisah pada bagian
sebelumnya. Aturan pencocokan, urutan kandidat, dan keputusan mapping tetap sama;
perubahan hanya pada penyajian workbook.

DATA BELUM JELAS sekarang mempunyai 35 kolom:

- A:K: informasi sumber dan penjelasan singkat yang mudah dibaca.
- L: jumlah rekomendasi.
- M:AA: tiga kelompok pilihan. Setiap kelompok hanya mempunyai Nama, Lokasi,
  ID Salesforce, Status, dan Catatan.
- AB:AI: delapan kolom input client yang semula berada di Y:AF. Nilai, style,
  nama kolom, serta pilihan dropdown tetap dipertahankan; posisi dropdown
  dipindahkan bersama kolom Keputusan_Client.

Setiap pilihan hanya mempunyai satu kolom ID. ID yang sesuai lokasi ditampilkan
lebih dahulu. Jika belum ada ID tersebut, ID yang masih perlu diperiksa tetap
ditampilkan dengan status yang jelas. Jika ada beberapa ID, semuanya disimpan
pada satu kolom dan statusnya meminta client memilih satu ID. Bila belum ada ID,
kolom ID kosong dan catatan menjelaskan pemeriksaan yang perlu dilakukan.
ID final tetap tidak diisi otomatis.

Kolom Jenis_Rekomendasi, Status_Verifikasi_ID, Alasan_Verifikasi_ID, dan
ID_Master_Perlu_Verifikasi tidak lagi diulang dalam workbook. Informasi yang
penting digabung menjadi Status dan Catatan di samping nama dan ID pilihan.
Informasi teknis lengkap tetap tersedia pada CSV pipeline untuk audit dan
pengujian, bukan ditampilkan sebagai kolom tambahan untuk client.

PILIHAN MAPPING berkurang dari 20 menjadi 12 kolom, dengan satu kelompok
Nama/Lokasi/ID/Status/Catatan pada setiap baris. Nama objek Salesforce juga
menggunakan sebutan yang mudah dibaca. Semua 79.685 baris tetap dipertahankan,
termasuk bukti nama di tingkat wilayah lain yang tetap tanpa ID rekomendasi.

Contoh kalimat pengganti:

> Nama dan lokasi rekomendasi sesuai master. Client perlu memastikan ID yang
> akan digunakan.

Status seperti "Hubungan wilayah perlu dicek", "Kabupaten/kota berbeda", dan
"ID belum dipastikan" menggantikan kode teknis yang panjang. Catatan tidak lagi
menggabungkan beberapa kalimat teknis yang menjelaskan hal yang sama. Bukti
nama, lokasi, provinsi, dan kemungkinan perbedaan tingkat wilayah tetap ada.

`regional_client_display.py` menjadi satu sumber untuk menyusun kalimat dan
kolom pada kedua sheet. Helper workbook menerima susunan lama 32/44 kolom
serta susunan baru 35 kolom. Pilihan dan format dropdown tidak diubah, hanya
referensi selnya. Workbook yang berisi formula pada kedua kelompok sumber/input
perlu ditinjau sebelum pemindahan kolom; helper menolak memindahkan formula
secara diam-diam. Workbook pada tugas ini tidak mempunyai formula tersebut.

Validasi versi ini: 29 pengujian unit lulus. Seluruh 79.685 catatan rekomendasi
lulus pemeriksaan bahasa sederhana. Validator workbook membandingkan setiap ID
sumber, nama sumber, nilai/style input client, dropdown, seluruh rekomendasi
terhadap CSV, jumlah/urutan baris dan sheet, serta 13 sheet lain yang tetap
identik. Kolom ID akhir tidak diisi otomatis dan tidak ada formula baru.

Penerapan ulang pada susunan baru menghasilkan nol perubahan nilai dan tidak
menambah kolom atau style. Semua jumlah dan urutan baris tetap sama. Pemeriksaan
seluruh sheet memastikan tidak ada formula yang bergantung pada kolom yang
dipindahkan. Pilihan dan format dropdown tetap sama setelah berpindah ke AB.

## Rekomendasi Bogor Timur, Bogor Barat, dan kasus serupa

Kota/Kabupaten tanpa provinsi sumber dapat memperoleh rekomendasi dari nama
kecamatan/kelurahan yang sama pada master, hanya bila semua bukti nama persis
tersebut mengarah ke satu kota/kabupaten. Jika bukti mengarah ke beberapa kota,
aturan ini tidak memilih salah satunya. Provinsi sumber tetap kosong dan perlu
konfirmasi client. Ini memperluas batasan lama yang menolak semua konteks anak
saat provinsi sumber kosong, tanpa mengubah lookup sumber atau mapping otomatis.

Contoh Bogor Timur (Kota/Kabupaten), `a1ofC0000004iFaQAI`: bukti master
`Jawa Barat | Kota Bogor | Bogor Timur` menghasilkan rekomendasi Kota Bogor,
ID `a1oJ40000009JOfIAM`. Catatan menyebut bahwa Bogor Timur merupakan kecamatan
dalam Kota Bogor dan meminta client memastikan tingkat serta provinsi sumber.

Kecamatan yang belum cocok dalam kabupaten/kota sumber juga dicari menurut
nama yang sama pada master kecamatan di kabupaten/kota lain pada provinsi yang
sama. Aturan ini tidak mencari ke provinsi lain dan tidak menggantikan kecocokan
nama yang sudah ada dalam kabupaten/kota sumber. Jika beberapa lokasi cocok,
semuanya ditampilkan dan client diminta memilih. Kandidat nama persis ini lebih
diutamakan daripada nama kecamatan yang hanya mirip ejaannya.

Contoh Bogor Barat (Kecamatan), `a1pJ40000008X21IAE`: data sumber masih tercatat
di Kab. Bogor, sedangkan master menemukan `Jawa Barat | Kota Bogor | Bogor Barat`.
Rekomendasi sekarang memakai lokasi tersebut dengan catatan perbedaan kota.
Karena belum ada ID utama yang terverifikasi untuk lokasi master itu, ID sumber
yang memang bernama Bogor Barat dapat ditampilkan sebagai ID yang perlu
konfirmasi untuk perbaikan kabupaten/kotanya. ID tersebut tidak dijadikan ID
tujuan terverifikasi atau ID final secara otomatis. Jika sudah tersedia ID
rekomendasi yang sesuai, ID itu tetap diprioritaskan. Peringatan untuk ID master
lain yang belum jelas tetap ditampilkan dan tidak disembunyikan oleh catatan kota.

Validasi versi ini:

- 34 pengujian unit lulus, termasuk provinsi kosong, nama di beberapa kota,
  nama di provinsi lain, larangan pencocokan sebagian kata, dan kecocokan
  dalam kota sumber yang harus dipertahankan.
- Generator dan penerjemahan selesai. Seluruh 28 CSV nonkandidat identik terhadap
  baseline: ID sumber, status mapping, usulan update, dan duplikat tetap sama.
- Rekomendasi tingkat sama berubah untuk 202 record. Workbook memperbarui 1.584
  sel kandidat pada 202 record. Jumlah baris kandidat/informasi review berubah
  dari 79.685 menjadi 79.741; jumlah dan urutan record sumber tidak berubah.
- Semua 79.741 penjelasan rekomendasi lulus pemeriksaan bahasa sederhana.
  Susunan 35 kolom DATA BELUM JELAS dan 12 kolom PILIHAN MAPPING tetap sama.
- Validator memeriksa setiap rekomendasi terhadap CSV, seluruh ID/nama sumber,
  nilai dan style input client, dropdown, urutan sheet, serta 13 sheet lain
  yang tetap identik. ID final tidak diisi otomatis.

Penerapan ulang pada hasil Bogor dan kasus serupa menghasilkan nol perubahan
sel tambahan. Tidak ada kolom baru atau formula baru. Semua rekomendasi pada
workbook sesuai CSV yang sudah divalidasi, termasuk Bogor Timur dan Bogor Barat.

## Rekomendasi yang berulang digabung

Kandidat dengan objek, ID sumber, dan seluruh lokasi master yang sama sekarang
hanya ditampilkan sekali. ID tujuan ditentukan dari lokasi master tersebut
setelah penggabungan, sehingga dua cara pencarian tidak lagi menghasilkan dua
pilihan untuk tujuan yang sama. Nama yang sama di lokasi berbeda tetap menjadi
pilihan terpisah. Tidak ada pencocokan sebagian nama untuk menghapus duplikasi.

Urutan tujuan yang berbeda tetap mengikuti kemunculan pertama sebelumnya.
Nomor pilihan dan Jumlah_Rekomendasi diperbarui. Contoh A, A menjadi A saja;
contoh A, A, B menjadi A, B. Jika ada kandidat berbeda berikutnya, kandidat itu
mengisi tempat yang tersedia di antara tiga pilihan yang ditampilkan. Slot
pilihan yang tidak terpakai dikosongkan. Jika penjelasan umum berulang dengan
bukti lokasi yang lebih jelas, bukti lokasi dipertahankan dalam satu catatan.

Contoh `a1ofC000002XjI9QAK` (kab bekasi) sekarang mempunyai satu rekomendasi:
`Jawa Barat | Kab. Bekasi`, ID `a1oJ40000009JMEIA2`. Pilihan 2 dan 3 kosong.
Sebelumnya tujuan tersebut muncul dua kali akibat kecocokan nama dan usulan nama.

PILIHAN MAPPING mengikuti daftar unik yang sama. Bukti nama dari Master dan
Salesforce pada tingkat wilayah lain tetap terpisah; yang digabung hanya
kandidat tujuan berulang. Tidak ada record sumber yang dihapus.

Input client tidak diubah otomatis. Bila pilihan client yang sudah diisi akan
menunjuk kandidat berbeda setelah daftar dirapikan, helper menghentikan proses
sebelum mengganti workbook dan menyebutkan ID sumber yang perlu diperiksa.
Pada workbook tugas ini, perapian berhasil tanpa mengubah input client.

Validasi versi ini:

- 40 pengujian unit lulus: duplikasi nama/usulan, pemadatan pilihan, urutan
  kecocokan utama, nama sama beda lokasi, bukti lokasi yang harus dipertahankan,
  serta perlindungan pilihan client yang sudah diisi.
- 20.088 baris kandidat berulang digabung pada 10.939 record. Sebelum perapian,
  4.974 record mempunyai duplikasi dalam tiga pilihan yang terlihat.
- Workbook memperbarui 33.336 sel rekomendasi pada 10.939 record. Jumlah baris
  PILIHAN MAPPING turun dari 79.741 ke 59.653 karena tujuan berulang digabung.
  Jumlah/urutan record sumber DATA BELUM JELAS tetap sama.
- Perbandingan seluruh sumber memastikan daftar tujuan dan ID yang berbeda
  tetap sama, dengan urutan kemunculan pertama yang sama. Setiap sumber tidak
  lagi mempunyai dua kandidat pada lokasi master yang sama.
- Seluruh 28 CSV nonkandidat identik: status mapping, ID sumber, keputusan
  update dan duplikat tidak berubah. Bukti lintas tingkat tetap sama selain
  nomor urut tampilan.
- Validator workbook memastikan tiga pilihan yang ditampilkan tidak berulang,
  semua nilai sesuai CSV, semua input client dan dropdown tetap, 13 sheet lain
  identik, tanpa formula atau ID final baru. Susunan 35/12 kolom tetap sama.

Penerapan ulang hasil daftar unik menghasilkan nol perubahan sel tambahan.
Perbandingan juga memastikan ID rekomendasi yang masih perlu konfirmasi tetap
tercakup; yang dihapus hanya pengulangannya, bukan tujuan atau ID yang berbeda.

## Petunjuk perbaikan hubungan wilayah di catatan rekomendasi

Catatan setiap rekomendasi sekarang menjelaskan tindakan pada provinsi,
kota/kabupaten, atau kecamatan yang terkait. Tidak ada kolom tambahan pada
workbook: petunjuk berada di Pilihan_1_Catatan, Pilihan_2_Catatan, dan
Pilihan_3_Catatan, serta Catatan_Rekomendasi pada PILIHAN MAPPING.

- Hubungan yang kosong: "Lengkapi kecamatan dengan Paseh, ID ...".
- ID yang berbeda dari lokasi rekomendasi: "Ubah kabupaten/kota menjadi ..., ID ...".
- Hubungan yang sudah sesuai: disebutkan agar client tidak mengubahnya.
- ID wilayah yang belum dipastikan: minta pemeriksaan; jangan menebak ID dari
  nama atau memakai ID lokasi lain.
- Bila ID rekomendasi sama dengan sumber dan nama cocok, petunjuk menyebutkan
  bahwa data yang sama dapat digunakan setelah client memastikan lokasinya.
- Bila ID rekomendasi berbeda, petunjuk selalu bersyarat pada pemilihan lokasi
  rekomendasi tersebut. Peringatan ID yang belum jelas dan kemungkinan perbedaan
  tingkat wilayah tetap dipertahankan.

Contoh sumber Legok Kidul `a1nJ4000000Kc2yIAC`, pada Pilihan_1_Catatan:

> Setelah client memastikan lokasi:
> • Lengkapi kecamatan dengan Paseh, ID a1pJ40000008XggIAE.
> • Kabupaten Sumedang sudah sesuai.
> • Gunakan ID sumber yang sama.

Petunjuk membaca ID yang benar-benar tercatat pada data sumber dan hanya
mengusulkan ID parent yang sudah lolos pemeriksaan seluruh lokasi pada master.
Kolom Id_Induk_Sekarang dan Id_Kota_Langsung_Sekarang tetap berisi kondisi saat
ini. Id_Induk_Final_Client tetap menjadi tempat keputusan client dan tidak
diisi otomatis. Kelurahan diperiksa untuk dua hubungan berbeda: kecamatan
langsung serta kota/kabupaten langsung. Kota/Kabupaten dan Kecamatan diperiksa
menurut tingkat wilayah di atasnya masing-masing. Provinsi tidak diberi parent.

`regional_parent_actions.py` menyusun petunjuk tanpa mengubah data sumber,
lookup, ID utama, atau keputusan mapping. Dua field tambahan hanya berada di
CSV internal: Petunjuk_Perbaikan_Wilayah dan Perlu_Perbaikan_Wilayah. Helper
memerlukan CSV terbaru dengan field tersebut agar petunjuk tidak hilang jika
workbook diterapkan ulang memakai keluaran lama.

Validasi versi ini:

- 47 pengujian unit lulus, termasuk hubungan kosong, hubungan berbeda, hubungan
  benar, ID parent belum ada, calon lokasi lain, jenis parent tiap tingkat,
  petunjuk bersyarat, dan peringatan ID yang tidak boleh dihilangkan.
- Generator/penerjemahan berhasil. Seluruh 28 CSV nonkandidat identik, dan semua
  field kandidat yang sudah ada juga identik. Nama, lokasi, urutan, ID, status
  rekomendasi, serta keputusan mapping tidak berubah.
- Semua 59.653 baris penjelasan rekomendasi lulus pemeriksaan bahasa sederhana.
  Workbook memperbarui 44.119 sel catatan pada 25.171 record, tanpa kolom baru.
- Jumlah/urutan record sumber dan semua sheet tetap sama. Input client,
  dropdown, ID sumber, dan 13 sheet lain tetap sama; tanpa formula atau ID
  final baru. Semua nilai workbook sesuai keluaran script.
- Penerapan ulang menghasilkan nol perubahan tambahan.

## Data wilayah benar dengan penetapan ID utama yang masih menunggu client

Lawang Agung `a1nJ4000000Kc3PIAS` sudah memiliki nama, kecamatan Pasemah Air
Keruh, dan hubungan langsung ke Kabupaten Empat Lawang yang sesuai master.
Data tersebut tidak memerlukan perubahan wilayah. Pilihan ID utama tetap
terpisah karena ID lain yang tercantum pada master memiliki hubungan wilayah
yang berbeda. ID lain tersebut tetap berada di DATA BELUM JELAS.

`regional_validity.py` menandai keadaan ini setelah pemeriksaan ID utama selesai,
tanpa mengubah Status, Tindakan, Id_Target, daftar perubahan, atau keputusan
mapping. Dua field keluaran internal ditambahkan:

- Status_Validasi_Wilayah: VALID_WILAYAH_MENUNGGU_ID_UTAMA.
- Status_Penetapan_ID_Utama: MENUNGGU_KONFIRMASI_CLIENT.

Syaratnya: nama persis sama dengan master, lokasi cocok persis, ID hubungan
wilayah saat ini sama dengan ID induk master yang sudah dipastikan, dan tidak
ada hubungan yang ditebak dari nama atau masalah hubungan yang belum selesai.
Kelurahan wajib cocok untuk kecamatan dan kota/kabupaten langsung sekaligus.
Data yang memerlukan perubahan nama, hubungan kosong/berbeda, atau hubungan
yang baru diperkirakan tetap diperiksa oleh client. Contohnya Legok Kidul
`a1nJ4000000Kc2yIAC` dan Cintaasih `a1nJ4000000KUKFIA4` tetap di DATA BELUM JELAS.

`reclassify_valid_regions.py` memindahkan data yang memenuhi syarat ke sheet
VALID sesuai tingkatnya. Kolom valid yang sudah ada tetap digunakan, dengan
penjelasan bahwa wilayah sudah sesuai dan ID utama masih menunggu konfirmasi
client. Keputusan dapat dicatat pada Catatan_Pemeriksaan. Baris rekomendasi
untuk data yang dipindahkan dihapus dari PILIHAN MAPPING. Bila salah satu
isian client di DATA BELUM JELAS sudah terisi, pemindahan ditunda sehingga
keputusan dan catatan client tidak hilang.

RINGKASAN memperbarui Sudah_Benar dan Data_Lain_Belum_Jelas. Kolom tambahan
Valid_Menunggu_ID_Utama menunjukkan bagian dari Sudah_Benar yang masih
memerlukan konfirmasi ID utama; angka ini bukan tambahan jumlah record.
Tidak ada ID final client atau ID utama yang ditetapkan otomatis.

Hasil pada data saat ini:

- 1.059 kelurahan dipindahkan, termasuk Lawang Agung. Tidak ada isian client
  yang menghalangi pemindahan pada workbook ini.
- VALID KELURAHAN: 46.246 menjadi 47.305 data.
- DATA BELUM JELAS: 27.187 menjadi 26.128 data.
- PILIHAN MAPPING: 59.653 menjadi 58.594 baris penjelasan.
- Seluruh field lama pada 28 CSV nonkandidat identik; seluruh 59.653 baris
  kandidat internal identik. Hanya dua field status wilayah di atas ditambahkan
  pada keluaran pipeline. CSV sumber dan workbook master tidak diubah.
- 51 pengujian unit lulus. `check_valid_region_reclassification.py` memeriksa
  seluruh record sumber, ID, hubungan wilayah, urutan data tersisa, data valid
  lama, ringkasan, input client beserta format/dropdown, dan ketiadaan formula.
- Workbook dapat dibuka, jumlah dan urutan 15 sheet tetap sama, 11 sheet lain
  identik. Selain workbook regional, tidak ada workbook/ZIP/CSV sumber yang
  diubah.
- Penerapan ulang menghasilkan nol perubahan nilai sel atau format dan nol
  pemindahan tambahan. Tidak ada rekomendasi yang kembali untuk data yang
  sudah dipindahkan. Catatan client pada sheet VALID tetap dipertahankan.
- Simulasi dengan catatan client terisi pada Lawang Agung menunda satu
  pemindahan tersebut, memindahkan 1.058 data lainnya, dan mempertahankan
  catatan, ID, format, dropdown, serta urutan seluruh data yang tersisa.

Contoh pemeriksaan workbook setelah menjalankan generator dan penerjemah:

```sh
python cleansing/tests/check_valid_region_reclassification.py \
  /tmp/regional-valid-before.xlsx \
  'cleansing/client_review/Mandatory for Client/02_REVIEW_CLIENT_DATA_REGIONAL.xlsx' \
  /tmp/regional-valid-new
```

## Nama provinsi tidak dijadikan saran kabupaten berdasarkan kemiripan teks

Record Kota/Kabupaten Lampung `a1oJ40000009gGfIAI` sebelumnya mendapat saran
Kab. Lampung Barat, Kab. Lampung Timur, dan Kab. Lampung Utara. Ketiganya hanya
mirip secara teks. Nama Lampung sendiri sudah ditemukan sebagai provinsi pada
master dan ekspor Salesforce; tidak ada bukti bahwa record tersebut dimaksudkan
sebagai salah satu kabupaten itu.

Generator sekarang memberikan daftar provinsi master ke `ranked_candidates`.
Untuk sumber Kota/Kabupaten dengan nama persis sama setelah normalisasi dengan
nama provinsi master, kandidat yang hanya berdasarkan kemiripan teks tidak
ditampilkan. Pemeriksaan memakai seluruh nama provinsi master, sehingga tetap
berlaku bila hubungan provinsi pada sumber berbeda. Bukti yang lebih kuat tetap
dipertahankan: nama sama, alias terdaftar, nama inti administratif yang sama,
keterangan induk yang sudah dicocokkan, serta konteks lokasi persis dari master.
Contohnya Bengkulu tetap dapat mengarah ke Kota Bengkulu; tidak semua nama yang
sama dengan provinsi harus dikosongkan jika bukti kota/kabupatennya tersedia.

Pada data saat ini, lima saran dihapus untuk tiga sumber:

- Lampung `a1oJ40000009gGfIAI`: tiga kabupaten Lampung di atas.
- Bali `a1oJ40000009VymIAE`: Kab. Bangli.
- Papua `a1ofC00000504n7QAA`: Kab. Jayapura.

Ketiganya tetap berada di DATA BELUM JELAS. Jumlah_Rekomendasi menjadi nol;
Pilihan_1 sampai Pilihan_3 kosong. Temuan Provinsi dari Master dan Salesforce
tetap ditampilkan agar client mengonfirmasi tingkat wilayah. Tidak ada ID
provinsi yang otomatis dimasukkan sebagai ID tujuan kota/kabupaten. ID sumber,
nama sumber, hubungan wilayah, dan kolom keputusan client tidak diubah.

Validasi pipeline mencocokkan seluruh field lama pada 28 CSV nonkandidat dan
memastikan hanya lima baris saran tersebut yang dihapus dari CSV kandidat;
baris lain identik kecuali nomor urut bukti pada sumber yang terpengaruh.
Jumlah kandidat internal sesudah penerjemahan: 59.653 menjadi 59.648.
Keputusan mapping, data valid, duplikat, usulan perbaikan, serta bukti lintas
tingkat tidak berubah. Ada 55 pengujian unit, termasuk penahanan saran Lampung,
normalisasi nama provinsi, perbedaan provinsi sumber, mempertahankan kecocokan
kota yang kuat, dan mempertahankan saran biasa untuk nama selain provinsi.

Pemeriksaan workbook menggunakan `check_client_review_workbook.py`; kandidat
untuk 1.059 record yang sudah dipindahkan ke sheet VALID tetap dikecualikan
dari PILIHAN MAPPING agar tidak muncul kembali. Jumlah record sumber dan urutan
sheet/baris sumber tetap; hanya rekomendasi pada tiga sumber dan rincian terkait
di PILIHAN MAPPING yang diperbarui.

Hasil penerapan: 28 sel rekomendasi pada tiga sumber berubah; DATA BELUM JELAS
tetap 26.128 record dan 35 kolom. PILIHAN MAPPING menjadi 58.589 baris, berkurang
lima saran tersebut. Workbook dapat dibuka; kolom lain, input client, dropdown,
dan 13 sheet lain tetap sama. Teks rekomendasi tetap memakai wrap. Jumlah dan
urutan 15 sheet tidak berubah; tidak ada formula atau ID final otomatis baru.

## Alasan ID kosong dan ID sumber yang sama diperjelas

`regional_id_explanations.py` menambahkan penjelasan untuk rekomendasi yang
belum mempunyai ID, wilayah di atasnya belum mempunyai ID utama, atau memakai
ID sumber yang sama tetapi masih perlu pemeriksaan hubungan wilayah.
Pemeriksaan membaca nama dan ID hubungan yang benar-benar tercatat pada file
Salesforce. Lokasi hasil perkiraan dari nama atau kolom lama tidak digunakan
sebagai bukti bahwa hubungan utama sudah benar.

Penjelasan ditampilkan pada kolom Pilihan_1_Catatan sampai Pilihan_3_Catatan di
DATA BELUM JELAS dan Catatan_Rekomendasi di PILIHAN MAPPING. Tidak ada kolom
workbook baru. Field Penjelasan_ID_Client hanya ditambahkan pada CSV kandidat
internal, dan helper penerapan memerlukan field tersebut agar penjelasan tidak
hilang ketika dijalankan dengan keluaran lama.

Keadaan yang dijelaskan mencakup:

- Nama rekomendasi ada di master, tetapi nama yang sama pada tingkat tersebut
  belum ditemukan dalam file Salesforce. Minta penelusuran nama/ID lain;
  pembuatan data tetap memerlukan keputusan client setelah pemeriksaan data lama.
- Data bernama sama ditemukan, tetapi hubungan wilayahnya berbeda, kosong,
  atau belum dapat dipastikan. Tampilkan lokasi yang diperlukan dan kondisi
  hubungan setiap ID yang ditemukan. Maksimal tiga data ditampilkan; sisanya
  dinyatakan sebagai +N data bernama sama lainnya.
- Beberapa data cocok dengan lokasi, tetapi penetapan ID utama belum selesai.
  Penjelasan meminta client memilih setelah memeriksa data tersebut.
- ID sumber ditampilkan kembali karena data yang sama masih perlu diperiksa
  atau diperbaiki. Kondisi saat ini dijelaskan sebelum petunjuk perbaikan,
  termasuk kecamatan kosong, ID hubungan yang tidak ditemukan, dan penggunaan
  data kota/kabupaten duplikat. Instruksi mempertahankan ID tidak diulang.

Contoh Jangga Dolok `a1pJ40000008XEvIAM`: rekomendasi kecamatan Lumban Julu
tetap ditampilkan dengan kolom ID kosong. Catatan menjelaskan bahwa kabupaten
yang diperlukan adalah Sumatra Utara | Kab. Toba, sedangkan ID Lumban Julu
`a1pJ40000008XSDIA2` yang ditemukan masih terhubung ke Kab. Tapanuli Utara.
ID itu hanya disebut sebagai bahan pemeriksaan dan tidak otomatis menjadi ID
tujuan. Informasi Jangga Dolok sebagai kelurahan pada master tetap ditampilkan.
Keterangan hubungan Kab. Toba yang sudah sesuai diperjelas sebagai kondisi
data sumber, sehingga tidak terbaca sebagai persetujuan terhadap ID kecamatan.

Contoh lain: Penarik `a1nJ4000000KcG8IAK` dijelaskan memiliki kolom kecamatan
utama yang kosong; Maju Makmur `a1nJ4000000KcG4IAK` masih menunjuk Batulicin;
Jangga Toruan `a1nfC00000VFAI6QAP` memerlukan pemeriksaan ID kecamatan serta
peralihan hubungan dari data Toba duplikat ke ID utama Kab. Toba.

Seluruh 65 pengujian unit lulus, termasuk perbedaan kabupaten, hubungan kosong,
ID yang tidak ditemukan, beberapa ID yang cocok, batas tiga data, konteks beda
tingkat, ID sumber yang sama, dan pemisahan kondisi data sumber dari ID tujuan.
Perbandingan pipeline memastikan seluruh field lama pada 28 CSV nonkandidat
dan 59.648 baris kandidat identik. Nama/lokasi rekomendasi, urutan, seluruh ID,
status, hasil mapping, serta temuan lintas tingkat tidak diubah. Penjelasan
tidak mengubah jumlah rekomendasi atau mengisi ID final client secara otomatis.

Validasi workbook: 21.661 sel catatan pada 17.444 sumber diperbarui di DATA
BELUM JELAS, serta 27.303 sel Catatan_Rekomendasi di PILIHAN MAPPING. Pemeriksaan
seluruh sel membatasi perubahan hanya pada tiga kolom catatan pilihan dan
satu kolom catatan mapping tersebut. DATA BELUM JELAS tetap 26.128 sumber;
PILIHAN MAPPING tetap 58.589 baris. Sebanyak 5.634 ID pilihan pertama tetap
kosong dan 2.019 sumber tetap tidak mempunyai rekomendasi. Jumlah/urutan 15
sheet tetap, 13 sheet lain identik, input dan format client serta dropdown
terjaga, teks memakai wrap, dan tidak ada formula baru. Workbook dapat dibuka.
