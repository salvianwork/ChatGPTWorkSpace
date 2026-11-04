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
