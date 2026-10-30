# Panduan penggunaan CSV

Folder berikut berada di dalam ZIP setelah diekstrak.

Paket berasal dari snapshot data 29 Oktober 2026. Tinjauan lintas tingkat dan penerjemahan diperbarui pada 30 Oktober 2026. Tidak ada perubahan pada Salesforce.

Mulai dari `00_Start_Here/Summary.csv`. Nama file, folder, nama wilayah, ID dan kolom API Salesforce dipertahankan. Judul kolom laporan, status, alasan, catatan, dan panduan diterjemahkan ke Bahasa Indonesia.

| Folder | Kegunaan |
|---|---|
| 00_Start_Here | Mulai di sini: Ringkasan seluruh hasil. Angka pada file lain dapat saling tumpang tindih; jangan dijumlahkan antarfile. |
| 01_Update_Proposals | Usulan pembaruan: Usulan perubahan nama atau lookup induk. Tinjau sebelum menyiapkan file upload yang hanya memuat Id dan kolom API yang disetujui. Kolom usulan kosong berarti tidak diubah, bukan dihapus. |
| 02_Duplicate_Handling | Penanganan duplikat: Pemetaan Id sumber ke Id target. Verifikasi seluruh referensi sebelum memindahkannya. File ini bukan daftar upload atau penghapusan. |
| 03_Manual_Review | Tinjauan manual: Daftar kerja cleansing, kandidat, serta temuan lintas tingkat. Temuan nama pada tingkat lain tidak membuktikan bahwa lokasinya sama. Semua ID kandidat lintas tingkat dikosongkan. |
| 04_Master_Targets | Target dan masalah master: Inventaris master, target belum terverifikasi, masalah ID, dan hierarki ganda. Target belum pasti bukan berarti harus langsung membuat record baru. |
| 05_All_Records | Seluruh record: Satu baris per record sumber, termasuk yang sudah valid. Gunakan sebagai referensi dan jejak pemeriksaan. |
| 06_Original_Gap_Analysis | Analisis gap awal: Daftar dan hitungan dari analisis gap awal pengguna beserta rekonsiliasi terhadap pemeriksaan hierarki lengkap. |
| 07_Audit | Audit: Checksum berkas masukan dan hasil validasi teknis. Bukan data untuk diunggah ke Salesforce. |

## Cara membaca temuan lintas tingkat

- `Jenis_Bukti = TEMUAN_LINTAS_TINGKAT`: nama ditemukan pada tingkat wilayah lain. `Id_Target_Kandidat` selalu kosong.
- `Tingkat_Ditemukan`: provinsi, kota/kabupaten, kecamatan, atau kelurahan tempat nama muncul.
- `Sumber_Data = Master`: ditemukan dalam master wilayah.
- `Sumber_Data = Ekspor Salesforce`: ditemukan pada data Salesforce yang masih perlu diverifikasi.
- `Jumlah_Kemunculan` menghitung lokasi/nama yang berbeda, bukan jaminan kecocokan. `Contoh_Lokasi` dibatasi maksimal lima lokasi.
- Temuan di luar provinsi asal tetap ditampilkan sebagai bukti nama saja dan diberi catatan. Jangan menyamakan dua lokasi hanya berdasarkan namanya.
- Jika nama tidak ditemukan pada objek asal tetapi ditemukan pada tingkat lain, kandidat kemiripan lama diganti dengan bukti lintas tingkat tanpa ID.
- `KANDIDAT_OBJEK_SAMA` masih dapat memiliki ID usulan dari hasil sebelumnya; temuan ini berbeda dari bukti lintas tingkat.
- `BELUM_DITEMUKAN` berarti tidak ada nama sama setelah normalisasi; kandidat berbasis kemiripan belum membuktikan pemetaan.

Pencarian lintas tingkat menggunakan kesamaan nama setelah normalisasi huruf besar/kecil, spasi, tanda baca, dan awalan administratif yang sesuai. Tidak menggunakan kecocokan sebagian kata. Penelusuran ini tidak mengubah keputusan update atau pemindahan referensi duplikat.

## Kamus kolom laporan

Kolom API `Id`, `Name`, `Provinsi__c`, `Kota_Kabupaten__c`, dan `Kecamatan__c` tetap memakai nama asli. Kolom laporan lainnya menggunakan padanan berikut.

| Kolom sebelumnya | Kolom Bahasa Indonesia |
|---|---|
| Action | Tindakan |
| Bytes | Ukuran_Byte |
| CANONICAL_UPDATE_PROPOSED | USULAN_UPDATE_RECORD_UTAMA |
| CSV_Full_Key_Unmatched | Tidak_Cocok_CSV_Kunci_Lengkap |
| CSV_Legacy_Unmatched | Tidak_Cocok_CSV_Kunci_Lama |
| CSV_SF_Count | Jumlah_Salesforce_CSV |
| Candidate_Kecamatan_Path | Hierarki_Kecamatan_Kandidat |
| Candidate_Kecamatan_Target_Id | Id_Kecamatan_Target_Kandidat |
| Candidate_Name | Nama_Kandidat |
| Candidate_Path | Hierarki_Kandidat |
| Candidate_Target_Id | Id_Target_Kandidat |
| Data_Source | Sumber_Data |
| Deterministic_Source_Count | Jumlah_Sumber_Cocok_Deterministik |
| Evidence_Type | Jenis_Bukti |
| File | Berkas |
| Found_Count | Jumlah_Kemunculan |
| Found_Level | Tingkat_Ditemukan |
| Full_Hierarchy_Master_Count | Jumlah_Master_Hierarki_Lengkap |
| Gap_Analysis_Unmatched | Tidak_Cocok_Dalam_Analisis_Gap |
| Gap_Invalid_Count | Jumlah_Tidak_Valid_Dalam_Gap |
| Issue | Masalah |
| Kelurahan_Master_Path | Hierarki_Kelurahan_Master |
| Key | Kunci |
| Location_Examples | Contoh_Lokasi |
| MAPPED_DUPLICATE | DUPLIKAT_DIPETAKAN |
| MAPPED_PARENT_TARGET_UNRESOLVED | ID_TARGET_INDUK_BELUM_TERVERIFIKASI |
| MAPPED_TARGET_UNRESOLVED | COCOK_MASTER_ID_TARGET_BELUM_TERVERIFIKASI |
| Master_Count | Jumlah_Master |
| Master_Path | Hierarki_Master |
| Master_Sheet_Id | Id_Dalam_Sheet_Master |
| Match_Method | Metode_Pencocokan |
| Notes | Catatan |
| Object | Objek |
| Original_Direct_City_Id | Id_Kota_Langsung_Sebelumnya |
| Original_Name | Nama_Sebelumnya |
| Original_Parent_Id | Id_Induk_Sebelumnya |
| Parent_Context | Konteks_Induk |
| Parent_Evidence | Bukti_Induk |
| Parent_Target_Id | Id_Target_Induk |
| Postal_Codes | Kode_Pos |
| Provisioning_Action | Tindakan_Penyediaan_Target |
| REVIEW_PARENT_CONFLICT | TINJAU_KONFLIK_INDUK |
| REVIEW_RECOVERED_PARENT | TINJAU_INDUK_HASIL_PEMULIHAN |
| REVIEW_UNMATCHED | TINJAU_BELUM_COCOK |
| Rank | Urutan |
| Reason | Alasan |
| Resolved_Parent_Path | Hierarki_Induk_Terurai |
| Rows | Jumlah_Baris |
| SHA256 | SHA256 |
| Salesforce_Count | Jumlah_Salesforce |
| Similarity | Kemiripan |
| Source_Direct_City_Id | Id_Kota_Langsung_Sumber |
| Source_Direct_City_Resolved_Path | Hierarki_Kota_Langsung_Terurai |
| Source_Id | Id_Sumber |
| Source_Legacy_Kecamatans | Kecamatan_Lama_Sumber |
| Source_Name | Nama_Sumber |
| Source_Parent_Display | Nama_Induk_Dalam_Ekspor |
| Source_Parent_Id | Id_Induk_Sumber |
| Source_Postal_Code | Kode_Pos_Sumber |
| Status | Status |
| Supplied_Name_Changes | Usulan_Perubahan_Nama_Sumber |
| Target_Id | Id_Target |
| Target_Kecamatan | Kecamatan_Target |
| Target_Kelurahan | Kelurahan_Target |
| Target_KotaKabupaten | KotaKabupaten_Target |
| Target_Name | Nama_Target |
| Target_Parent_Id | Id_Induk_Target |
| Target_Provinsi | Provinsi_Target |
| Target_Resolution | Hasil_Verifikasi_Target |
| VALID_CANONICAL | VALID_RECORD_UTAMA |
| Workbook_Master_Count | Jumlah_Master_Workbook |
| Workbook_SF_Count | Jumlah_Salesforce_Workbook |
| Workbook_Unmatched | Tidak_Cocok_Workbook |
