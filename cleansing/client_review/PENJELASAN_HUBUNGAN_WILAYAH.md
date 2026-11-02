# Penjelasan hubungan wilayah

Urutan wilayah yang digunakan adalah:

```text
Provinsi
└── Kota/Kabupaten
    └── Kecamatan
        └── Kelurahan
```

## Contoh

```text
Jawa Barat
└── Kab. Bandung
    └── Soreang
        └── Soreang
```

Nama Kecamatan atau Kelurahan dapat sama di beberapa tempat. Karena itu, nama saja tidak cukup. Wilayah induknya juga harus benar.

## Dampak perubahan induk

- Jika ID Kota/Kabupaten diganti, Kecamatan yang masih menunjuk ID lama perlu dipindahkan.
- Jika ID Kecamatan diganti, Kelurahan yang masih menunjuk ID lama perlu dipindahkan.
- Mengubah nama record tidak otomatis memindahkan hubungan anak.
- Menonaktifkan atau menghapus data duplikat sebelum memindahkan semua hubungan dapat menyebabkan data anak kehilangan hubungan yang benar.

## Arti mapping

Mapping berarti menentukan data sumber harus diarahkan ke data tujuan mana.

Contoh:

```text
ID sumber: Kota/Kabupaten duplikat
ID tujuan: Kota/Kabupaten yang dipertahankan
```

Semua Kecamatan yang menunjuk ID sumber perlu diubah agar menunjuk ID tujuan yang sudah disetujui.

## Temuan lintas tingkat

Jika nama Kota/Kabupaten ditemukan sebagai nama Kecamatan atau Kelurahan, hasil tersebut hanya menjadi petunjuk. ID tidak diisi otomatis karena tingkat wilayahnya berbeda.

Contoh: nama `Madura` pada data Kota/Kabupaten ditemukan sebagai nama Kelurahan di beberapa lokasi. Hal tersebut tidak membuktikan bahwa record Kota/Kabupaten harus diarahkan ke salah satu Kelurahan tersebut.
