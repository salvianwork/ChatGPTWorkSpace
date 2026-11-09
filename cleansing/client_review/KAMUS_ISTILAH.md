# Kamus istilah cleansing data wilayah

Kamus ini menjelaskan istilah yang digunakan dalam hasil pemeriksaan data Provinsi, Kota/Kabupaten, Kecamatan, dan Kelurahan.

| Istilah | Arti sederhana | Contoh |
|---|---|---|
| Master data | Daftar wilayah yang dijadikan acuan benar | Master menyatakan nama yang benar adalah `Kab. Bandung` |
| Data Salesforce | Data yang saat ini tersimpan di Salesforce | Record Kota/Kabupaten, Kecamatan, atau Kelurahan |
| Data utama | Satu record Salesforce yang dipilih untuk dipertahankan | Dari beberapa data `Kab. Bandung`, satu record dipilih sebagai data utama |
| Canonical | Istilah teknis untuk data utama yang dipertahankan | `Canonical record` berarti data utama |
| Sudah benar | Data utama sudah sesuai dengan master dan tidak perlu diubah | Nama dan wilayah induknya sudah benar |
| Perlu diperbaiki | Data sudah ada, tetapi nama atau hubungan ke wilayah induknya perlu diperbaiki | Kecamatan sudah benar, tetapi masih terhubung ke ID Kota/Kabupaten yang salah |
| Calon data baru | Lokasi ada di master, tetapi belum ditemukan record Salesforce yang dapat dipakai | Master memiliki `Kab. Banjar`, tetapi belum ada record tujuan yang dapat dipastikan |
| Perlu diperiksa sebelum membuat data baru | Data mungkin sudah ada, tetapi ID atau hubungan induknya belum pasti | Jangan membuat record baru sebelum calon data lama diperiksa |
| Duplikat | Dua atau lebih record Salesforce mewakili lokasi yang sama | `Kabupaten Bandung` dan `Kab. Bandung` menunjukkan lokasi yang sama |
| Data sumber | Record Salesforce yang sedang diperiksa atau akan dipindahkan | `Id_Sumber` adalah ID record yang saat ini ada |
| Data tujuan | Record Salesforce yang dipilih untuk dipertahankan atau digunakan | `Id_Target` adalah ID record yang menjadi tujuan |
| ID sumber | ID Salesforce dari record asal | Digunakan untuk mengetahui record mana yang perlu diperbaiki atau dipindahkan |
| ID target | ID Salesforce dari record tujuan | Semua hubungan dari duplikat dipindahkan ke ID ini setelah disetujui |
| Induk | Wilayah yang berada satu tingkat di atas | Provinsi adalah induk Kota/Kabupaten; Kecamatan adalah induk Kelurahan |
| Data anak | Wilayah atau record yang terhubung ke record induk | Kecamatan adalah anak Kota/Kabupaten |
| Lookup | Kolom Salesforce yang menghubungkan satu record ke record lain | `Kota_Kabupaten__c` pada Kecamatan menyimpan hubungan ke Kota/Kabupaten |
| Hubungan induk | Hubungan suatu wilayah ke wilayah di atasnya | Kelurahan harus terhubung ke Kecamatan yang benar |
| Hierarki wilayah | Urutan tingkat wilayah | Provinsi → Kota/Kabupaten → Kecamatan → Kelurahan |
| Mapping atau pemetaan | Menentukan data sumber harus diarahkan ke data tujuan mana | Duplikat diarahkan ke data utama yang dipertahankan |
| Gap analysis | Perbandingan antara master dan data Salesforce untuk mencari perbedaan | Menemukan data yang kurang, berlebih, atau tidak cocok |
| Tidak cocok | Nama atau hubungan wilayah belum sesuai dengan master | Nama sama tetapi berada di Kota/Kabupaten yang berbeda |
| Kandidat | Kemungkinan data tujuan yang masih perlu diperiksa | Kandidat bukan keputusan akhir dan tidak selalu mempunyai ID target |
| Temuan lintas tingkat | Nama ditemukan pada tingkat wilayah yang berbeda | `Madura` pada data Kota/Kabupaten ditemukan sebagai nama Kelurahan |
| Nama sama setelah dibersihkan | Nama dianggap sama setelah perbedaan huruf, spasi, tanda baca, atau singkatan dirapikan | `Kabupaten Bandung` dibandingkan dengan `Kab. Bandung` |
| Konflik hubungan | Dua informasi induk menunjukkan lokasi yang berbeda | Kota langsung pada Kelurahan berbeda dengan kota milik Kecamatan |
| Tinjauan manual | Pemeriksaan oleh pengguna karena sistem belum dapat menentukan hasil dengan aman | Memastikan apakah data harus diperbaiki, dianggap duplikat, atau tidak termasuk master |
| Insert | Membuat record Salesforce baru | Dilakukan hanya jika sudah dipastikan bahwa record belum ada |
| Update | Mengubah record Salesforce yang sudah ada | Memperbaiki nama atau ID induk |
| Upsert | Membuat record baru jika belum ada, atau memperbarui jika sudah ada | Biasanya menggunakan External ID yang unik |
| External ID | Kunci unik untuk membantu mencegah data ganda | Gabungan kode Provinsi, Kota/Kabupaten, Kecamatan, dan Kelurahan |
| Pindahkan referensi | Mengubah record anak agar menunjuk ke data utama yang benar | Kecamatan yang menunjuk kota duplikat dipindahkan ke kota yang dipertahankan |
| Nonaktifkan | Membuat record tidak digunakan lagi tanpa langsung menghapusnya | Dapat dilakukan setelah semua referensi selesai dipindahkan |
| Hapus | Menghilangkan record dari Salesforce | Dilakukan setelah pemeriksaan dan sesuai kebijakan perusahaan |
| Data Loader | Alat Salesforce untuk memasukkan atau memperbarui data dalam jumlah banyak | File upload sebaiknya hanya berisi `Id` dan kolom yang sudah disetujui |
| Snapshot data | Salinan data pada tanggal tertentu yang digunakan untuk analisis | Paket ini menggunakan data yang tersedia pada 29 Oktober 2026 |

## Istilah status yang sering terlihat

| Status teknis | Arti sederhana |
|---|---|
| `VALID_RECORD_UTAMA` | Data utama sudah benar |
| `USULAN_UPDATE_RECORD_UTAMA` | Data utama perlu diperbaiki |
| `DUPLIKAT_DIPETAKAN` | Data duplikat sudah mempunyai usulan data tujuan |
| `TINJAU_BELUM_COCOK` | Belum ditemukan kecocokan yang cukup aman |
| `TINJAU_KONFLIK_INDUK` | Ada perbedaan informasi mengenai wilayah induk |
| `TINJAU_INDUK_HASIL_PEMULIHAN` | Induk diperkirakan dari informasi lain dan masih perlu dipastikan |
| `COCOK_MASTER_ID_TARGET_BELUM_TERVERIFIKASI` | Lokasi cocok dengan master, tetapi ID Salesforce tujuan belum dapat dipastikan |
| `BELUM_ADA_RECORD_UTAMA_TERVERIFIKASI` | Belum ditemukan record Salesforce yang dapat dipastikan sebagai data utama |
| `USULAN_INSERT_SETELAH_INDUK_TERSEDIA` | Calon data baru; buat hanya setelah induk tersedia dan dipastikan tidak ada data lama yang bisa dipakai |
| `TINJAU_ID_TARGET` | Jangan membuat data baru dahulu; periksa ID tujuan dan hubungan wilayahnya |

Jika suatu istilah masih terasa teknis, gunakan kolom “Arti sederhana” sebagai dasar pengambilan keputusan.
