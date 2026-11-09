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

## Daikin: pisahkan perbaikan Parent dengan ID data tetap

`daikin_parent_review.py` memindahkan semua kasus dengan ID rekomendasi pertama
sama dengan ID sumber dari DATA BELUM JELAS ke PERBAIKAN PARENT - ID TETAP pada
Daikin_Cleansing_Data_Regional.xlsx. Setelah pemisahan awal 4.841 sumber,
perluasan memindahkan 4.159 sumber tambahan: 64 kecamatan dan 4.095 kelurahan.
Sheet Parent kini memuat 9.000 sumber (200 kecamatan dan 8.800 kelurahan).
DATA BELUM JELAS menjadi 17.128 sumber: 67 kota/kabupaten, 781 kecamatan,
dan 16.280 kelurahan. Tidak ada rekomendasi ke ID sumber sendiri yang tersisa
pada DATA BELUM JELAS. Jumlah dan urutan 15 sheet tetap pada perluasan ini.
Workbook asli 02_REVIEW_CLIENT_DATA_REGIONAL.xlsx tidak diperbarui.

Pemindahan tidak lagi mensyaratkan semua ID Parent sudah tersedia, satu lokasi
rekomendasi saja, atau nama sumber sama persis. ID rekomendasi dan lokasi
pertama diperiksa terhadap Review_candidates.csv. Seluruh kandidat sejenis
diperiksa agar pilihan lain tidak hilang karena Daikin hanya menampilkan
rekomendasi pertama. ID Parent yang belum diketahui dibiarkan kosong. Jika
ada beberapa lokasi, ID dan nama Parent usulan dikosongkan seluruhnya; lokasi
pertama tetap ditampilkan sebagai bahan review dan seluruh pilihan tersedia
di PILIHAN MAPPING. Jika nama berbeda, nama sumber dipertahankan dan nama
usulan dijelaskan di Catatan Perbaikan. ID Parent yang diisi berasal dari
inventaris target dan diperiksa kembali terhadap lokasi data sumber tujuan.
Baris dengan isian Tim Daikin tetap dilindungi; seluruh isian pada 4.159
baris tambahan saat ini masih kosong.

Sheet Parent menampilkan ID data sekali, Parent saat ini, Parent usulan,
Lokasi Rekomendasi Untuk Review, dan tindakan perbaikan/konfirmasi. Kolom
Lokasi Parent Dari Pencocokan serta Lokasi Kota Dari Pencocokan mempertahankan
konteks hasil pencocokan dari workbook sebelumnya; kolom tersebut bukan bukti
bahwa hubungan yang tercatat saat ini sudah benar. Nama dan ID Parent saat ini
tetap ditampilkan terpisah. Catatan kondisi sumber dan bukti beda tingkat
dipertahankan. Status Review membedakan Parent belum pasti, lokasi dan Parent
belum pasti, nama perlu dikonfirmasi, serta usulan lengkap yang menunggu
konfirmasi Tim Daikin. Seluruh keputusan dan ID final tetap kosong. Dropdown
keputusan berisi SETUJU_UBAH,
TOLAK_PERUBAHAN, dan PERLU_DISKUSI. Tidak ada perubahan Salesforce otomatis.

Contoh: Penarik a1nJ4000000KcG8IAK diusulkan untuk melengkapi Parent kecamatan
dengan a1pJ40000008Xi7IAE. Maju Makmur a1nJ4000000KcG4IAK diusulkan mengganti
Parent Batulicin dengan Kecamatan Penarik yang sama. ID kedua kelurahan tetap
dipertahankan. Legok Kidul a1nJ4000000Kc2yIAC juga dipindahkan untuk melengkapi
Parent Kecamatan Paseh. Jangga Toruan a1nfC00000VFAI6QAP kini juga dipindahkan,
dengan ID Parent Lumban Julu tetap kosong karena belum dapat dipastikan.
Hutagurgur (Huta Gurgur) a1nfC00000VF9uNQAT berstatus Parent masih perlu
dikonfirmasi; ID Parent Dolok Sanggul kosong, tetapi usulan ID kabupaten
a1oJ40000009JMgIAM tetap ditampilkan. Citamiang a1pJ40000008X7QIAU mempunyai
beberapa lokasi sehingga seluruh ID Parent usulan kosong. Tambun utara
a1pJ40000008ZWAIA2 mempertahankan nama sumber dan menjelaskan nama usulan
Tambun Utara, dengan status Nama masih perlu dikonfirmasi.

4.159 baris tambahan dikelompokkan secara berurutan tanpa tumpang tindih:
3.058 masih mempunyai lebih dari satu kandidat lokasi, 995 belum mempunyai
semua ID Parent usulan, dan 106 juga memerlukan perubahan nama. Baris ini
belum dinyatakan valid atau disetujui otomatis. Sebanyak 5.634 ID rekomendasi
pertama pada DATA BELUM JELAS tetap kosong; di antaranya
2.019 sumber tidak mempunyai rekomendasi lokasi sama sekali.

RINGKASAN, PETUNJUK, dan KAMUS ISTILAH diperbarui. RINGKASAN menampilkan
Perbaikan Parent ID Tetap sebagai kelompok terpisah. Seluruh 91.306 ID sumber
tetap ada tepat satu kali pada sheet pengelompokan sumber. PILIHAN MAPPING
tetap 58.589 baris sebagai bukti baca untuk kedua sheet; bukan antrean input
review tambahan. Sepuluh sheet lain identik secara byte. Seluruh sel, gaya,
urutan, serta isian Tim Daikin pada baris DATA BELUM JELAS yang tidak
dipindahkan identik dengan sebelumnya. Dropdown dan rentang filter mengikuti
jumlah baris baru. Seluruh 4.841 baris Parent sebelumnya, termasuk urutan,
nilai, gaya dan isian reviewnya, identik; hanya judul kolom lokasi pada header
diubah agar jelas merupakan rekomendasi yang masih perlu diperiksa.
Tidak ada formula baru; seluruh teks pada sheet Parent memakai wrap.

80 pengujian unit lulus, termasuk 15 pengujian pemisahan ID tetap, Parent
kosong, beberapa lokasi, perubahan nama, dan perlindungan isian review.
Pemeriksaan workbook dilakukan dengan:

```sh
python cleansing/tests/check_daikin_parent_review.py \
  /tmp/daikin-before-all-same-id.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/regional-id-explanation-final
```

Helper mendukung susunan awal 14 sheet atau 15 sheet yang sudah memiliki
sheet Parent. Jalankan setelah pipeline regional dan penerjemahan selesai:

```sh
python cleansing/scripts/daikin_parent_review.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/regional-id-explanation-final \
  --backup /tmp/daikin-before-all-same-id.xlsx \
  --report /tmp/daikin-all-same-id-report.json
```

Helper memerlukan lokasi backup baru dan memeriksa kesesuaian pipeline dengan
rekomendasi workbook. Jika sheet Parent sudah ada, baris lama dipertahankan
dan baris tambahan diletakkan di akhir. Jika tidak ada sumber tambahan yang
memenuhi kriteria, workbook tidak ditulis ulang.

## Daikin: satu baris per hubungan dan relasi master lengkap

Tahap tampilan `daikin_relation_rows.py` dijalankan sesudah pemisahan seluruh
ID tetap di atas. Sheet PERBAIKAN PARENT - ID TETAP berubah dari 9.000 baris
data/24 kolom menjadi 12.570 baris hubungan/19 kolom. Jumlah ID unik tetap
9.000: 200 kecamatan dan 8.800 kelurahan. Terdapat 3.570 ID dengan dua hubungan
yang perlu diperiksa. Baris terdiri atas 200 Parent Kabupaten/Kota, 8.543
Parent Kecamatan, dan 3.827 Kabupaten/Kota Langsung. ID data boleh berulang
di dalam sheet ini, tetapi pasangan ID data dan jenis hubungan harus unik.
Tidak ada sumber yang pindah ke kelompok review lain. RINGKASAN tetap memakai
9.000 ID unik dan judul kolomnya diperjelas; tidak menjumlahkan 12.570 baris
hubungan sebagai jumlah data.

Kolom Id/Nama Relasi Sekarang dan Id/Nama Relasi Usulan dipakai bersama untuk
setiap jenis hubungan. Hubungan yang sudah sesuai tidak mendapat baris
tambahan dan tetap dijelaskan di catatan. ID relasi final mengikuti jenis
hubungannya; keputusan, catatan, PIC dan tanggal review tetap dipertahankan.
Nama kota saat ini diambil dari ekspor berdasarkan ID sumber, bukan ditebak
dari lokasi hasil pencocokan. Kolom Lokasi Relasi Dari Pencocokan diberi label
terpisah karena konteks tersebut belum membuktikan hubungan saat ini benar.
Catatan sumber dan temuan lintas tingkat dipertahankan utuh pada setiap baris.

Kolom J, Relasi Master yang Seharusnya, berisi provinsi hingga nama data:
provinsi | kabupaten/kota | kecamatan [| kelurahan]. Setiap lokasi diperiksa
terhadap Master_target_inventory.csv; tidak ada lokasi yang dibuat atau
ditebak. Untuk 3.058 ID dengan beberapa lokasi, semua pilihan ditampilkan
dengan bullet dan penanda Lokasi masih perlu dikonfirmasi. ID relasi usulan
tetap kosong untuk lokasi yang belum dipastikan. Contoh Hutagurgur (Huta
Gurgur) a1nfC00000VF9uNQAT sekarang mempunyai dua baris: Parent Kecamatan
Dolok Sanggul dengan ID usulan kosong dan Kabupaten/Kota Langsung dengan ID
usulan a1oJ40000009JMgIAM. Relasi master pada keduanya adalah Sumatra Utara |
Kab. Humbang Hasundutan | Dolok Sanggul | Hutagurgur (Huta Gurgur).

Dropdown keputusan berpindah ke O2:O12571, ID Relasi Final Tim Daikin berada
di kolom P. Filter mencakup A1:S12571; teks tetap wrap dan header dibekukan.
PETUNJUK dan KAMUS ISTILAH menjelaskan format baris hubungan. Jumlah dan
urutan 15 sheet tidak berubah; sebelas sheet lain, seluruh gaya serta shared
strings identik secara byte. Workbook asli 02_REVIEW_CLIENT_DATA_REGIONAL.xlsx
dan workbook lain tidak diperbarui. Seluruh 91.306 ID sumber tetap ada dalam
kelompoknya; jumlah dihitung setelah ID berulang per hubungan disatukan.
Tidak ada formula atau ID final otomatis baru.

88 pengujian unit lulus, termasuk 8 pengujian relasi master, dua hubungan,
hubungan yang sudah sesuai, nama kota dari ekspor, ID yang belum tersedia,
dan pemeliharaan jawaban review. Pemeriksaan workbook untuk format terbaru:

```sh
python cleansing/tests/check_daikin_relation_rows.py \
  /tmp/daikin-before-relation-rows.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/regional-id-explanation-final
```

Untuk membangun format ini dari hasil tahap ID tetap 24 kolom:

```sh
python cleansing/scripts/daikin_relation_rows.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/regional-id-explanation-final \
  --backup /tmp/daikin-before-relation-rows.xlsx \
  --report /tmp/daikin-relation-rows-report.json
```

Helper memerlukan lokasi backup baru dan menolak penerapan ulang pada sheet
yang sudah memakai format 19 kolom. Pemeriksa pemisahan ID tetap sebelumnya
berlaku untuk tahap antara 24 kolom; pemeriksa relasi ini berlaku untuk hasil
tampilan terakhir.

## Finalisasi Daikin: Madura dan kolom penghitung teknis

`regional_matching.py` menahan kandidat kota/kabupaten yang hanya berdasarkan
kemiripan huruf untuk nama kawasan Madura. Madura a1oJ40000009JPKIA2 sebelumnya
mendapat Kab. Madiun a1oJ40000009JPJIA2 (skor 53,33) dan Kota Madiun
a1ofC00000EcXDLQA3 (skor 50). Kesamaan provinsi Jawa Timur dan huruf tersebut
tidak membuktikan wilayah yang sama. Kecocokan nama yang kuat dan penggunaan
Madura sebagai kelurahan tetap diperbolehkan; aturan ini tidak menaikkan batas
kemiripan seluruh nama atau menghapus saran nama lain yang sah.

`finalize_daikin_review.py` adalah tahap tampilan terakhir setelah branding,
pemisahan ID tetap, dan format baris hubungan. Tahap internal tetap dapat
memakai jumlah kandidat untuk pengolahan, tetapi kolom Jumlah Rekomendasi
Ditampilkan tidak dikeluarkan pada file final Tim Daikin. Jalankan finalisasi
setiap kali membentuk ulang file Daikin agar kolom tidak muncul kembali.

Rekomendasi pertama Madura dikosongkan dan alasan konfirmasinya diperjelas.
Dua saran Madiun di PILIHAN MAPPING dihapus; dua temuan lintas tingkat Madura
tetap sama, dengan nomor urut menjadi 1 dan 2. DATA BELUM JELAS tetap 17.128
data dengan 23 kolom. ID rekomendasi pertama kosong menjadi 5.635, terdiri
dari 3.615 rekomendasi lokasi tanpa ID dan 2.020 data tanpa rekomendasi.
PILIHAN MAPPING menjadi 58.587 baris. Dropdown keputusan bergeser dari R ke Q
dengan pilihan yang sama. Seluruh ID sumber, kolom final Tim Daikin, gaya,
dan nilai lain tetap terjaga. Tiga belas sheet lain identik secara byte,
termasuk RINGKASAN dan 12.570 baris hubungan Parent untuk 9.000 ID unik.
Jumlah/urutan 15 sheet tetap dan tidak ada formula baru. Workbook asli,
CSV sumber, workbook lain, dan ZIP tidak diperbarui.

90 pengujian unit lulus. Pemeriksaan final membandingkan setiap nilai dan gaya
sel yang dipertahankan, dropdown, metadata, dua kandidat yang dihapus, temuan
lintas tingkat, dan integritas workbook:

```sh
python cleansing/scripts/finalize_daikin_review.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --backup /tmp/daikin-before-madura-final.xlsx \
  --report /tmp/daikin-madura-final-report.json
python cleansing/tests/check_daikin_final_review.py \
  /tmp/daikin-before-madura-final.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx'
```

Finalisasi memerlukan path backup baru dan melindungi isian review Madura yang
sudah diisi dari perubahan pilihan secara diam-diam. Pemeriksa tahap baris
hubungan sebelumnya tetap dipakai sebelum finalisasi; pemeriksa ini dipakai
untuk file final 23 kolom pada DATA BELUM JELAS.

## Rename dengan ID tetap untuk nama yang memuat keterangan Parent setelah koma

`regional_rename.py` memeriksa nama kecamatan/kelurahan yang mempunyai
keterangan Parent setelah koma. Bagian nama harus cocok dengan satu lokasi
master di seluruh Parent yang sesuai; setiap keterangan setelah koma harus
sesuai urutan Parent sebenarnya. ID Parent sumber wajib sama dengan ID Parent
master yang sudah dipastikan. Untuk kelurahan, hubungan kabupaten/kota
langsung juga wajib benar. Data dengan hubungan kosong, konflik, atau
hasil perkiraan tidak memenuhi syarat. Beberapa sumber untuk lokasi yang
sama, normalisasi nama master yang ambigu, atau ID master lain yang masih
bermasalah tetap memerlukan review.

`candidate_id_review` dapat mengusulkan ID sumber tersebut untuk rename
tanpa mengubah pemilihan ID utama otomatis, `_path`, atau mapping data anak.
Rekomendasi dengan kecocokan nama dan keterangan Parent yang lengkap tidak
lagi diikuti saran kemiripan huruf yang tidak terkait. Seratus pengujian unit
lulus, termasuk 10 pengujian nama dengan koma, Parent salah/kosong, pemulihan
hubungan, beberapa ID, ID master konflik, hubungan kota langsung, dan
perlindungan terhadap perubahan input.

Penerapan pertama menemukan 11 kecamatan di Sumatra Selatan: Belimbing,
Bunga Mayang, Cempaka, Kandis, Lais, Martapura, Mesuji, Purwodadi, Sungai
Pinang, Tanjung Raja, dan Ujan Mas, masing-masing pada kabupaten sumbernya.
Contoh Belimbing a1pJ40000008X0WIAU: nama Belimbing, Muara Enim diusulkan
menjadi Belimbing, ID tetap, dan Parent a1oJ40000009JPgIAM tetap. Relasi
master Sumatra Selatan | Kab. Muara Enim | Belimbing. Data bernama sama di
kabupaten/provinsi lain tidak menjadi dasar untuk kasus tersebut.

`daikin_qualified_renames.py` memindahkan 11 sumber dari DATA BELUM JELAS ke
PERUBAHAN KECAMATAN sebagai usulan perubahan Nama saja. Data dengan isian
review yang sudah diisi ditunda, termasuk calon insert yang sudah mempunyai
jawaban Tim Daikin. Lokasi yang sama dikeluarkan dari CALON DATA BARU agar
tidak diusulkan dibuat ulang. Sebanyak 29 baris bukti mapping untuk sumber
yang sudah dipindahkan dihapus dari antrean PILIHAN MAPPING; baris lainnya
identik. Tidak ada ID final yang diisi otomatis.

Hasil akhir: PERUBAHAN KECAMATAN 619 data, DATA BELUM JELAS 17.117 data,
CALON DATA BARU 20.511 lokasi, dan PILIHAN MAPPING 58.558 baris. RINGKASAN
mengikuti perubahan kelompok tersebut. Data valid, duplikat, dan sheet
PERBAIKAN PARENT - ID TETAP tidak berubah. Semua 91.306 ID sumber tetap ada
tepat satu kali pada kelompoknya, setelah ID per hubungan disatukan.
Seluruh input, gaya, dropdown, urutan baris tersisa dan urutan 15 sheet
terjaga. Workbook asli, CSV sumber, ZIP dan workbook lainnya tidak berubah.

Perbandingan dua eksekusi pipeline ke direktori sementara membuktikan
26 CSV nonkandidat identik secara byte. Hanya Review_candidates.csv berubah:
52.092 menjadi 52.004 kandidat (88 saran fuzzy dihapus pada nama dengan
keterangan Parent yang sudah cocok). Sebelas kandidat mendapatkan ID sumber
sebagai usulan rename dan penjelasan ID diperbarui. Tidak ada kandidat lokasi
baru atau perubahan mapping anak otomatis.

Tahap ini dijalankan sesudah finalisasi Daikin, dengan direktori pipeline
asli berkolom bahasa Inggris dari `cleanse.py` sebelum penerjemahan:

```sh
python cleansing/scripts/daikin_qualified_renames.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/qualified-rename-after \
  --backup /tmp/daikin-before-qualified-renames.xlsx \
  --report /tmp/daikin-qualified-renames-report.json
python cleansing/tests/check_daikin_qualified_renames.py \
  /tmp/daikin-before-qualified-renames.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/qualified-rename-after
```

Pemeriksa terbaru memvalidasi proposal rename, ID Parent yang sama,
penghapusan calon insert terkait, seluruh ID sumber, isian review, nilai
dan gaya baris lain, dropdown, ringkasan, formula dan integritas workbook.

## Empat perbaikan rekomendasi dan penjelasan review

Nama provinsi pada master dapat mempunyai alias dalam tanda kurung, misalnya
Aceh (NAD). `province_name_forms` mengenali Aceh dan NAD untuk menahan usulan
kota/kabupaten yang hanya berasal dari kemiripan huruf. Kecocokan kuat pada
tingkat kota/kabupaten tetap dipertahankan. Aceh a1ofC000000MuErQAK tidak
lagi direkomendasikan ke Kab. Aceh Jaya/Barat/Besar. Temuan provinsi dari
Master dan ekspor Salesforce ditambahkan sebagai informasi tanpa ID tujuan;
temuan kelurahan yang sudah ada dipertahankan.

`parenthesized_name_core` mengenali variasi ejaan dalam tanda kurung pada
tingkat kecamatan/kelurahan. Nama inti harus cocok dengan tepat satu nama
master pada Parent yang sama. Nama literal lengkap pada master tetap
diutamakan. Keterangan arah/wilayah seperti Barat, Utara, Pesisir atau Induk
tidak dibuang sebagai alias ejaan, termasuk bentuk kata yang disambung.
Parent yang belum diketahui tidak ditebak. ID master tetap dipilih melalui
pemeriksaan ID yang sudah ada; Source ID dan pilihan ID utama tidak diganti
otomatis.

Penerapan memperbarui 36 rekomendasi alias pada DATA BELUM JELAS. Kulisusu
(Kalingsusu/Kalisusu) a1pJ40000008XNrIAM kini mempunyai rekomendasi Sulawesi
Tenggara | Kab. Buton Utara | Kulisusu, ID a1pfC00000DcH4HQAV, sesuai master.
Kulisusu Barat dan Utara tidak lagi menjadi usulan untuk sumber ini. Ini
tetap rekomendasi yang perlu diperiksa, bukan instruksi mengganti ID tanpa
persetujuan. Kasus yang ID lokasinya belum dapat dipastikan tetap kosong,
dengan alasan dan penjelasan alias yang tetap ditampilkan.

Sebanyak 2.679 baris PILIHAN MAPPING diperjelas menjadi Nama persis belum
ditemukan; ada kandidat, hanya bila sumber tersebut mempunyai kandidat
pada tingkat yang sama. Bukti lintas tingkat saja tidak dianggap kandidat
mapping. `clarify_no_exact_rows` juga diterapkan pada pembentukan workbook
regional agar penjelasan lama tidak muncul kembali.

Status pada 12.570 baris hubungan Parent kini menjelaskan ketersediaan ID
relasi pada baris tersebut. Ada 5.153 baris ID tersedia menunggu konfirmasi,
107 ID tersedia dengan nama data perlu konfirmasi, 1.208 ID relasi belum
pasti, dan 6.102 lokasi serta ID relasi belum pasti. Pada 254 baris yang ID
relasinya sudah tersedia tetapi hubungan lain belum pasti, catatan
ketergantungan ditambahkan. Tidak ada keputusan, ID final, Parent, relasi
master, atau bukti lama yang dihapus.

Jumlah DATA BELUM JELAS tetap 17.117: 11.492 memiliki ID rekomendasi, 3.604
memiliki lokasi rekomendasi dengan ID kosong, dan 2.021 belum mempunyai
rekomendasi. Total ID rekomendasi kosong 5.625. PILIHAN MAPPING menjadi
58.547 baris; 49 usulan lama pada 37 sumber terkait digantikan 36 kandidat
alias dan dua bukti provinsi. Dua belas sheet lain, termasuk RINGKASAN,
tetap identik secara byte. Seluruh 91.306 ID sumber tetap terjaga; 15 sheet serta urutannya
tetap, dan tidak ada formula baru. Workbook asli dan CSV sumber tidak berubah.

110 pengujian unit lulus. Sebanyak 26 keluaran CSV nonkandidat identik dengan
baseline; hanya kandidat review yang berubah. Terapkan tahap ini setelah
finalisasi/rename dengan direktori keluaran mentah `cleanse.py`:

```sh
python cleansing/scripts/daikin_review_clarity.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/review-clarity-final \
  --backup /tmp/daikin-before-review-clarity.xlsx \
  --report /tmp/daikin-review-clarity-report.json
python cleansing/tests/check_daikin_review_clarity.py \
  /tmp/daikin-before-review-clarity.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/review-clarity-final
```

Pemeriksaan mencocokkan sumber/Parent/jawaban review sebelum dan sesudah,
seluruh kandidat serta bukti yang tidak terkait, label konfirmasi, status per
hubungan, gaya, dropdown, jumlah/urutan sheet, dan integritas workbook.

## 8 November 2026 — bukti lengkap dan alur review yang lebih jelas

Tahap `daikin_review_readability.py` diterapkan pada workbook Daikin sesudah
`daikin_review_clarity.py`. Workbook asli `02_REVIEW_CLIENT_DATA_REGIONAL.xlsx`,
workbook lain, CSV sumber, ZIP, serta README tidak diubah.

Perubahan isi review:

- Tujuh rekomendasi pertama yang hanya mirip tetapi berbeda penanda wilayah
  dikosongkan, misalnya Misool Utara ke Misool Selatan dan Sei Kera Hilir ke
  Sei Kera Hulu. Pada PILIHAN MAPPING, 97 alternatif seperti ini menjadi bukti
  dengan ID kosong. Sebanyak 46 pilihan yang sama pada relasi master sheet
  Parent dihapus; lokasi tetap tersedia sebagai bukti pada PILIHAN MAPPING.
  Seluruh ID relasi usulan tetap. Nama inti Misool dan Rumbai yang benar-benar
  ada pada master ditampilkan sebagai bukti tambahan, tanpa menetapkan ID.
- Ada 855 data tanpa rekomendasi yang namanya ditemukan pada master, termasuk
  819 data yang sebelumnya tidak memiliki rincian bukti. Lokasi master ditulis
  di Alasan Belum Jelas dan PILIHAN MAPPING: maksimum tiga lokasi, disertai
  jumlah lokasi lainnya. Bukti ini bukan rekomendasi ID. Contoh Sukarindik:
  master Jawa Barat | Kota Tasikmalaya | Bungursari | Sukarindik, sementara
  informasi Parent sumber mengarah ke lokasi berbeda.
- Sebanyak 424 data dengan ID rekomendasi pertama kosong kini menjelaskan
  bahwa kandidat lain ber-ID mewakili pilihan berbeda. Tidak ada promosi
  alternatif berdasarkan ketersediaan ID. Contoh Hutanagodang: usulan Muara
  tetap tanpa ID; ID kandidat Purbatua tidak menggantikannya.
- Catatan pada 12.570 baris Parent disederhanakan menjadi ID tetap, hubungan
  yang diperiksa, tindakan, dan konfirmasi yang diperlukan. Alasan khusus ID
  relasi kosong tetap ditampilkan. Instruksi lama yang menyalin usulan pertama
  berulang kali dihapus. Baris hubungan lain pada ID yang sama tetap dirujuk.

Alur dan tampilan:

- Semua kolom input Tim Daikin berwarna kuning, dengan tanggal memakai format
  tanggal. Kolom ID/nama dibekukan di sheet review. Catatan memakai wrap text
  dan tinggi baris disesuaikan; sel sangat panjang dapat dibaca lewat formula
  bar atau F2, sesuai PETUNJUK.
- Pilihan keputusan memakai bahasa sederhana. Gunakan rekomendasi 1 hanya
  tersedia jika ada satu ID. Sebanyak 710 data yang memuat beberapa ID pada
  satu lokasi diminta memilih satu lewat Gunakan ID lain dan Id Target Final.
  Tidak ada ID yang dipilih otomatis.
- Pada Parent, Setujui usulan hanya tersedia jika ID usulan ada. Gunakan ID
  final tersedia untuk hasil konfirmasi lain. ID final harus satu ID Salesforce
  berukuran 15 atau 18 karakter, tanpa spasi/titik koma. Sel yang masih wajib
  diisi setelah keputusan dipilih ditandai merah, termasuk PIC dan tanggal.
  Warna adalah alat bantu kelengkapan review, bukan persetujuan otomatis.
- VALID KELURAHAN mempunyai lima kolom tambahan M–Q untuk 1.059 data yang
  menunggu ID utama: keputusan, ID utama final, catatan, PIC, tanggal. Isian
  hanya ditandai kuning pada kelompok tersebut. Data valid dan ID yang ada
  tidak dipindahkan atau diubah. Jumlah Master/Calon Data Baru diberi satuan
  lokasi; Menunggu ID Utama dijelaskan sebagai bagian dari Sudah Benar.
- PDF dan PowerPoint diperbarui, masing-masing dua halaman/slide, memakai
  angka dari workbook yang sama. Footer memuat hash Excel untuk mencocokkan
  sumber. Grafik menghitung ID Salesforce unik; calon lokasi baru terpisah.

Hasil: DATA BELUM JELAS tetap 17.117 data: 11.485 memuat ID rekomendasi,
3.604 mempunyai lokasi rekomendasi tetapi ID kosong, dan 2.028 belum memiliki
rekomendasi. Total sel ID rekomendasi kosong 5.632. Kelompok ber-ID mencakup
710 data yang memerlukan pilihan satu ID final. PILIHAN MAPPING bertambah
857 baris bukti menjadi 59.404; 855 bukti nama sama dan dua bukti nama inti.
Seluruh sheet utama mempertahankan jumlah/urutan record. Tetap 15 sheet,
91.306 ID sumber unik, dan 9.000 ID sumber pada 12.570 baris hubungan Parent.

117 pengujian unit lulus. Validator independen membandingkan semua baris:
ID/nama/Parent sumber, usulan Parent, jawaban review, kandidat yang tidak
terkait, lokasi master sebenarnya, dropdown sesuai ketersediaan ID, format
input, serta jumlah dan urutan sheet. Tidak ada formula sel baru; rumus
kelengkapan hanya dipakai pada validasi input dan conditional formatting.
Regenerasi pipeline menghasilkan 26 CSV nonkandidat identik secara byte;
hanya kandidat review yang berbeda. Penerjemahan menghasilkan 855 bukti
`NAMA_SAMA_LOKASI_LAIN` tanpa ID kandidat, terpisah dari temuan lintas tingkat.

```sh
python cleansing/scripts/daikin_review_readability.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/daikin-readability/pipeline \
  --backup /tmp/daikin-before-readability.xlsx \
  --report /tmp/daikin-readability-report.json
python cleansing/tests/check_daikin_review_readability.py \
  /tmp/daikin-before-readability.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/daikin-readability/pipeline
python cleansing/scripts/build_daikin_review_slides.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --output-dir /tmp/daikin-slides
```

Tahap workbook menolak layout yang sudah memiliki kolom input ID utama;
jangan diterapkan dua kali atau pada workbook yang sudah diisi tanpa review.
Tahap tidak menghubungi atau mengubah Salesforce.

## 9 November 2026 — gabungkan Parent ke PERUBAHAN

`merge_daikin_changes.py` diterapkan setelah tahap keterbacaan. Seluruh data
pada PERBAIKAN PARENT - ID TETAP digabung menurut objek ke PERUBAHAN
KECAMATAN dan PERUBAHAN KELURAHAN. Ketiga sheet PERUBAHAN sekarang memakai
19 kolom yang sama, satu baris per nama atau hubungan. Sheet Parent beserta
relasi paket, filter, dan daftar judulnya dihapus; jumlah sheet menjadi 14.
Urutan sheet yang dipertahankan tidak berubah.

| Sheet | ID data unik | Baris review |
| --- | ---: | ---: |
| PERUBAHAN KOTA | 458 | 458 |
| PERUBAHAN KECAMATAN | 819 | 830 |
| PERUBAHAN KELURAHAN | 16.329 | 20.039 |
| Total | 17.606 | 21.327 |

Perhitungan baris: 8.606 usulan lama menjadi 8.625 baris setelah perubahan
nama/Parent/kabupaten-kota langsung yang digabung dalam satu record dipisah.
Sebanyak 12.570 hubungan dari 9.000 ID data Parent dipindahkan. Konfirmasi nama
yang sebelumnya melekat pada 132 data Parent menjadi 132 baris Nama tersendiri.
Nama usulan pada 23 kasus yang memiliki beberapa nama master tetap kosong;
nama atau lokasi tidak dipilih otomatis. Keputusan Parent tidak diwariskan
menjadi persetujuan nama.

Format utama:

- B Id Data tetap menjadi ID Salesforce yang diperiksa.
- D Bagian yang Diubah membedakan Nama, Parent Provinsi, Parent Kabupaten/Kota,
  Parent Kecamatan, dan Kabupaten/Kota Langsung.
- E/H Nilai Sekarang/Nilai Usulan berisi nama untuk baris Nama, atau ID relasi
  untuk baris hubungan. F/I menampilkan nama relasi agar ID mudah dipahami.
- G Konteks Lokasi Sekarang membedakan informasi dari relasi Salesforce
  sebenarnya dengan konteks hasil pencocokan. Informasi yang tidak lengkap
  ditandai; tidak ditebak dari lokasi rekomendasi.
- J Relasi Master yang Seharusnya tetap menunjukkan provinsi hingga data.
  Semua lokasi berasal dari bukti yang sudah ada sebelum penggabungan.
- K Status Konfirmasi menjelaskan apakah nilai tersedia atau nama/lokasi/ID
  masih perlu dipastikan. L mempertahankan alasan khusus ID kosong dan tindakan.
- N–S adalah isian kuning: keputusan, nilai final, lokasi final, catatan, PIC,
  tanggal. Nama dan hubungan diputuskan per baris. Untuk hubungan, nilai final
  dibatasi satu ID Salesforce 15/18 karakter tanpa spasi/titik koma; baris Nama
  menerima nama. Lokasi Final wajib ketika lokasi masih perlu dikonfirmasi.
  Tolak usulan/Perlu diskusi memerlukan catatan. PIC serta tanggal diperlukan
  ketika ada keputusan. Sel merah membantu melihat isian belum lengkap.

Setujui usulan tersedia pada 13.991 baris yang memiliki satu nilai usulan dan
lokasi cukup jelas. Sebanyak 7.310 hubungan yang ID usulannya kosong tetap
kosong. Dengan 23 baris Nama tanpa usulan, total nilai usulan kosong 7.333.
Ada 6.128 baris yang memerlukan konfirmasi lokasi; kelompok ini dapat beririsan
dengan nilai kosong. Seluruh isian final/keputusan pada file ini tetap kosong,
tidak diisi atau disetujui otomatis.

RINGKASAN menggabungkan 9.000 ID Parent ke Perubahan untuk Direview (ID Unik),
sehingga 8.606 menjadi 17.606. Kolom ringkasan Parent terpisah dihapus. Jumlah
master, valid, calon lokasi baru, duplikat, belum jelas, dan subset menunggu ID
utama tetap. PETUNJUK dan KAMUS ISTILAH diperbarui. PDF/PPT tetap dua halaman /
slide; grafik sekarang empat kelompok Salesforce, dengan 17.606 data perubahan
(21.327 baris review) sebagai satu kelompok. Panduan menunjukkan kolom baru dan
contoh dua hubungan Hutagurgur yang diputuskan secara terpisah.

Validasi independen mencocokkan setiap nilai sebelum/sesudah, meliputi ID data,
nama sumber, ID relasi saat ini/usulan, alasan ID kosong, lokasi master, bukti
lintas tingkat, dan jawaban review. Seluruh 91.306 ID sumber tetap ada dan
kelompok utamanya saling terpisah. Belimbing tetap memakai ID
`a1pJ40000008X0WIAU` dengan usulan nama Belimbing. Dua hubungan Hutagurgur tetap
terpisah, dengan ID usulan Parent Kecamatan kosong dan ID Kabupaten/Kota
Langsung `a1oJ40000009JMgIAM`.

Delapan sheet berikut identik secara byte: seluruh VALID, CALON DATA BARU,
DATA DUPLIKAT, DATA BELUM JELAS, PILIHAN MAPPING. Gaya dan shared strings tetap
mengacu pada indeks semula; hanya jumlah pemakaian string disesuaikan.
Referensi worksheet dan defined names diperiksa agar tidak menunjuk sheet
yang dihapus. Tidak ada formula sel baru. Workbook asli 02, workbook lain,
CSV sumber, README, serta ZIP tetap tidak berubah. 125 pengujian unit lulus.
Workbook lengkap berhasil dibuka dan diekspor melalui LibreOffice ke salinan
uji terpisah. PDF dan PowerPoint masing-masing dua halaman/slide; seluruh teks
terekspor tanpa terpotong dan hash sumbernya cocok dengan Excel hasil merge.

```sh
python cleansing/scripts/merge_daikin_changes.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --source-dir . \
  --backup /tmp/daikin-before-merge-changes.xlsx \
  --report /tmp/daikin-merge-changes-report.json
python cleansing/tests/check_merged_daikin_changes.py \
  /tmp/daikin-before-merge-changes.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx'
python cleansing/scripts/build_daikin_review_slides.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --output-dir /tmp/daikin-merged-slides
```

Tahap hanya menerima struktur 15 sheet sebelum penggabungan dan menolak
penerapan ulang pada hasil 14 sheet. CSV dibaca untuk nama serta konteks relasi
saat ini; tidak ditulis. Pembuatan file upload tetap proses terpisah sesudah
review dan persetujuan Tim Daikin.

## 9 November 2026 — struktur bukti master dan perbaikan file Excel

Tahap `polish_daikin_workbook.py` diterapkan setelah penggabungan Parent.
Temuan lintas tingkat pada DATA BELUM JELAS dan PERUBAHAN menampilkan struktur
langsung dengan pemisah ` | `, tanpa awalan Provinsi/Kota/Kecamatan/Kelurahan.
Master dan ekspor Salesforce tetap menjadi dua bagian berbeda. Bukti dari
Master tidak digunakan untuk mengisi lokasi Salesforce yang belum diketahui.
Maksimum tiga lokasi ditampilkan per sumber/tingkat, dengan jumlah lokasi
lainnya. Tingkat wilayah tetap tersedia sebagai metadata pada PILIHAN MAPPING.

Bukti pendukung yang sudah digunakan oleh mesin rekomendasi sekarang juga
masuk ke temuan Master. Pengambilan bukti memeriksa bahwa seluruh path ada
pada master dan ID rekomendasinya berkaitan dengan Parent pada path tersebut.
Bukti untuk rekomendasi yang sedang ditampilkan didahulukan pada daftar lokasi.
Tidak dilakukan pencocokan sebagian nama secara umum. Variasi Buntok menjadi
Buntok Kota dibatasi pada konteks rekomendasi yang sudah tersedia; Buntok Baru
di kabupaten lain tidak ditambahkan ke bukti untuk kasus ini.

Contoh Buntok `a1pJ40000008X4aIAE`:

```text
• Hasil Master:
  - Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota
  Keterangan: variasi nama “Buntok” → “Buntok Kota”.
```

Master tersebut melengkapi temuan Salesforce yang lokasinya masih belum
lengkap. Rekomendasi tetap Kecamatan Dusun Selatan dengan ID
`a1pfC00000DcGqWQAV` dan lokasi kecamatan tiga tingkat. Struktur lengkap empat
tingkat ditampilkan di catatan sebagai bukti. Baris bukti Master tambahan
pada PILIHAN MAPPING tidak mempunyai ID tujuan. Jumlah baris bukti menjadi
59.405; jumlah dan urutan record pada semua sheet lainnya tetap.

Sebanyak 467 data mempunyai bukti struktur master dari rekomendasi. Ada 453
catatan rekomendasi yang diperjelas memakai path lengkap untuk pilihan yang
sedang ditampilkan. Penjelasan khusus ID kosong/konflik tetap dipertahankan,
termasuk peringatan yang sebelumnya berada pada paragraf pertama. Total
2.102 sel temuan lintas tingkat diperbarui. Judul lima kolom menjadi
Rekomendasi Nama, Rekomendasi Lokasi, Rekomendasi ID Salesforce, Rekomendasi
Status, Rekomendasi Catatan. Pilihan Gunakan rekomendasi juga tidak bernomor;
arti keputusan, dropdown, dan aturan kelengkapan tetap sama.

Dua masalah struktur/tampilan ditemukan pada file sebelumnya:

- Pada 20.511 baris CALON DATA BARU, sel kosong input ditambahkan sesudah
  kolom N tanpa diurutkan kembali. Contoh urutan: A, B, C, D, F, N, G, H,
  I, J, K, L, M. File kini menyimpan sel dalam urutan referensi kolom menaik.
  Helper `put()` juga diperbaiki agar sel kosong tidak membuat urutan rusak
  pada regenerasi berikutnya. Ini perbaikan struktural yang relevan terhadap
  pesan Excel Desktop yang meminta pemulihan isi; belum merupakan pembuktian
  langsung bahwa semua versi Excel Desktop tidak akan menampilkan pesan itu.
- Sepuluh header memakai style untuk satu baris penuh sehingga warna berlaku
  sampai di luar tabel. Style baris penuh serta 26 style kolom penuh dihapus;
  style efektif tetap disimpan pada sel tabel. Kolom input, format tanggal,
  dan conditional formatting di dalam tabel tetap dipertahankan.

Validator memeriksa 2.600.304 sel pada 14 sheet: urutan baris/sel, referensi
sel, shared strings, indeks style, target relasi ZIP, content types, defined
names, dimension/filter, batas dropdown/conditional formatting, serta panjang
formula daftar/pesan validasi. Tidak ada formula sel baru atau styling
baris/kolom penuh yang meluas di luar tabel. Semua 91.306 ID sumber, ID usulan,
master mapping, jawaban review, dan urutan kandidat yang sudah ada terjaga.
Seluruh 131 pengujian unit lulus. Regresi sel kosong dan perlindungan pilihan
rekomendasi tanpa nomor tercakup dalam pengujian.

Penerjemahan raw pipeline juga diuji: Buntok menghasilkan bukti Master Buntok
Kota dengan ID kandidat kosong, sehingga konsistensi tidak hanya ditambahkan
pada file akhir. Workbook lengkap berhasil dibuka/diekspor melalui LibreOffice
ke salinan uji, lalu dibuka kembali. Excel Desktop tidak tersedia pada mesin
ini; pengujian langsung di aplikasi yang dilaporkan pengguna belum dilakukan.
PDF dan PPT tetap dua halaman/slide, memakai header dan hash Excel terbaru.

```sh
python cleansing/scripts/polish_daikin_workbook.py \
  --workbook 'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  --pipeline /tmp/daikin-readability/pipeline \
  --backup /tmp/daikin-before-polish.xlsx \
  --report /tmp/daikin-polish-report.json
python cleansing/tests/check_polished_daikin_workbook.py \
  /tmp/daikin-before-polish.xlsx \
  'cleansing/client_review/Mandatory for Client/Daikin_Cleansing_Data_Regional.xlsx' \
  /tmp/daikin-readability/pipeline
```

Penerapan ulang tahap ini diuji: tidak menambah bukti/catatan berulang dan
hash workbook hasilnya identik.

Workbook 02 asli, workbook lain, README, CSV sumber, dan ZIP tidak diubah.
Pengelompokan DATA DUPLIKAT/DATA BELUM JELAS tidak berubah pada tahap ini.
