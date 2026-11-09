"""Shorten reviewed wording without inferring locations, IDs or decisions.

Only explicitly listed prose templates are rewritten. Unrecognised text and
case-specific facts remain intact; no length limit or truncation is used.
"""
import re

ID_WARNING=('Tindak lanjut: pastikan lokasi yang dimaksud dan periksa hubungan data di atas. '
            'ID dalam catatan hanya untuk pemeriksaan; belum ditetapkan sebagai ID tujuan.')
SHORT_WARNING='Konfirmasikan lokasi dan relasi. ID dalam catatan hanya untuk pemeriksaan, belum ID tujuan.'

PHRASES={
    'Kabupaten/kota yang tercatat langsung berbeda dengan kabupaten/kota dari kecamatannya. Tim Daikin perlu memastikan lokasi yang benar.':
        'Kabupaten/kota langsung berbeda dari relasi kecamatan. Tim Daikin perlu memastikan lokasi.',
    'Nama dan lokasi rekomendasi sesuai master. Tim Daikin perlu memastikan ID yang akan digunakan.':
        'Nama/lokasi sesuai master; Tim Daikin perlu memastikan ID.',
    'Nama cocok dengan nama pada master.':'Nama cocok dengan master.',
    'Nama mirip dengan data sumber. Tim Daikin perlu memastikan lokasinya.':
        'Nama mirip dengan sumber; Tim Daikin perlu memastikan lokasi.',
    'Data untuk lokasi ini ditemukan. Tim Daikin perlu memeriksa hubungan wilayah dan ID yang akan digunakan.':
        'Data lokasi ini ditemukan; Tim Daikin perlu memeriksa relasi dan ID.',
    'Ada beberapa ID untuk lokasi ini. Tim Daikin perlu memilih ID yang akan digunakan.':
        'Beberapa ID tersedia untuk lokasi ini; Tim Daikin perlu memilih satu.',
    '• Ada beberapa ID untuk lokasi ini. Pilih satu setelah dikonfirmasi: gunakan keputusan Gunakan ID lain, lalu isi satu ID pada Id Target Final.':
        '• Beberapa ID untuk lokasi ini: setelah dikonfirmasi, pilih Gunakan ID lain dan isi satu ID pada Id Target Final.',
    'ID rekomendasi pertama belum tersedia. Pilihan lain pada PILIHAN MAPPING memiliki ID, tetapi mewakili kandidat yang berbeda. Pastikan lokasi terlebih dahulu; jangan memilih hanya karena ID tersedia.':
        'ID rekomendasi kosong. ID di PILIHAN MAPPING mewakili kandidat lain; pastikan lokasi sebelum memilih, jangan memilih hanya karena ID tersedia.',
    'Tindak lanjut: telusuri nama atau ID lain. Pembuatan data baru perlu persetujuan Tim Daikin setelah pemeriksaan data lama.':
        'Tindak lanjut: periksa data lama dan cari nama/ID lain; pembuatan data baru perlu persetujuan Tim Daikin.',
    'lokasi lengkap dan hubungannya masih perlu dikonfirmasi':'lokasi lengkap/relasi perlu dikonfirmasi',
    'kabupaten/kota langsung bernama ':'kabupaten/kota langsung: ',
}

PATTERNS=[
    (r'Alasan ID (provinsi|kabupaten/kota|kecamatan|kelurahan) (.+?) belum dipastikan:',r'ID \1 \2 belum pasti:'),
    (r'• (Provinsi|Kabupaten/kota|Kecamatan) yang diperlukan: ',r'• \1 acuan: '),
    (r'• Data bernama (.+?) ditemukan, tetapi hubungan wilayah untuk lokasi rekomendasi belum dapat dipastikan\.',
     r'• \1 ditemukan; relasi ke lokasi rekomendasi belum pasti.'),
    (r'• Nama (.+?) ada di master, tetapi data bernama sama pada tingkat (provinsi|kabupaten/kota|kecamatan|kelurahan) tidak ditemukan di file Salesforce yang diperiksa\.',
     r'• \1 ada di master; nama sama pada tingkat \2 tidak ditemukan di ekspor Salesforce.'),
    (r'(provinsi|kabupaten/kota|kecamatan) pada file bernama (.+?) \(ID ',r'\1 pada file: \2 (ID '),
    (r'• Pastikan (provinsi|kabupaten/kota|kecamatan) (.+?)\. ID untuk wilayah ini belum dapat dipastikan; periksa sebelum mengisi atau mengubahnya\.',
     r'• Pastikan \1 \2; ID belum pasti. Periksa sebelum mengisi/mengubah.'),
    (r'Ada (\d+) data bernama (.+?) dengan lokasi yang cocok, tetapi ID utama untuk lokasi ini belum ditentukan\.',
     r'Ada \1 data bernama \2 di lokasi yang cocok; ID utama belum ditentukan.'),
    (r'Ada data bernama (.+?) dengan lokasi yang cocok, tetapi penetapan ID utamanya masih perlu dikonfirmasi\.',
     r'Data bernama \1 cocok lokasinya; ID utama perlu dikonfirmasi.'),
]


def compact_line(line):
    """Preserve interpolated names, counts, full paths, IDs and action verbs."""
    for old,new in PHRASES.items():line=line.replace(old,new)
    for pattern,replacement in PATTERNS:line=re.sub(pattern,replacement,line)
    return line


def compact_recommendation_note(text):
    if not text:return text
    lines=[];warning=False
    for line in text.splitlines():
        if line in (ID_WARNING,SHORT_WARNING):warning=True;continue
        lines.append(compact_line(line))
    # This sentence is global and contains no record-specific facts. Show it
    # once after all evidence blocks rather than repeating it per Parent level.
    if warning:lines.extend(['',SHORT_WARNING])
    result=re.sub(r'\n{3,}','\n\n','\n'.join(lines)).strip()
    # Leave already concise/unknown notes untouched, including their spacing.
    return result if len(result)<len(text) else text


def id_tokens(text):
    return set(re.findall(r'\b[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?\b',text or ''))
