import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_note_compaction import compact_recommendation_note as compact,ID_WARNING,SHORT_WARNING,id_tokens


class NoteCompactionTests(unittest.TestCase):
    def test_ids_locations_and_distinct_parent_blocks_survive(self):
        text=('Alasan ID kelurahan Riding Panjang belum dipastikan:\n'
              '• Kecamatan yang diperlukan: Kepulauan Bangka Belitung | Kab. Bangka | Belinyu.\n'
              '• Data bernama Riding Panjang ditemukan, tetapi hubungan wilayah untuk lokasi rekomendasi belum dapat dipastikan.\n'
              '• ID a1nJ4000000KamyIAC: kecamatan pada file bernama Belinyu (ID a1pJ40000008X0XIAU); lokasi lengkap dan hubungannya masih perlu dikonfirmasi.\n'+ID_WARNING+'\n\n'
              'Alasan ID kecamatan Belinyu belum dipastikan:\n'
              '• Kabupaten/kota yang diperlukan: Kepulauan Bangka Belitung | Kab. Bangka.\n'
              '• ID a1pJ40000008X0XIAU: kabupaten/kota pada file bernama Sungai Liat (ID a1oJ40000009JQpIAM); lokasi lengkap dan hubungannya masih perlu dikonfirmasi.\n'+ID_WARNING)
        out=compact(text)
        self.assertLess(len(out),len(text));self.assertEqual(id_tokens(text),id_tokens(out))
        for fact in ['Riding Panjang','Belinyu','Sungai Liat','Kepulauan Bangka Belitung | Kab. Bangka | Belinyu',
                     'ID kelurahan','ID kecamatan']:self.assertIn(fact,out)
        self.assertEqual(out.count(SHORT_WARNING),1);self.assertEqual(compact(out),out)

    def test_unknown_text_and_short_notes_are_preserved(self):
        for text in [None,'','• Kabupaten Barito Selatan sudah sesuai.',
                     'Catatan khusus: jangan gunakan ID lain sebelum rapat Tim Daikin.\n\n  Bukti disimpan.']:
            self.assertEqual(compact(text),text)

    def test_action_verbs_and_conditional_approval_are_not_collapsed(self):
        text=('Nama cocok dengan nama pada master.\n\nJika rekomendasi ini dipilih setelah Tim Daikin memastikan lokasi:\n'
              '• Lengkapi kecamatan dengan Belinyu, ID a1pJ40000008X0XIAU.\n'
              '• Ubah kabupaten/kota menjadi Kab. Bangka, ID a1ofC00000EcXDkQAN.')
        out=compact(text)
        self.assertEqual(text.split('\n\n',1)[1],out.split('\n\n',1)[1])

    def test_other_candidates_do_not_become_same_location_ids(self):
        text=('ID rekomendasi pertama belum tersedia. Pilihan lain pada PILIHAN MAPPING memiliki ID, '
              'tetapi mewakili kandidat yang berbeda. Pastikan lokasi terlebih dahulu; jangan memilih hanya karena ID tersedia.')
        out=compact(text)
        self.assertIn('kandidat lain',out);self.assertIn('jangan memilih hanya karena ID tersedia',out)
        self.assertNotIn('lokasi berbeda',out)

    def test_missing_export_record_does_not_approve_new_record(self):
        text=('• Nama Kab. Kupang ada di master, tetapi data bernama sama pada tingkat kabupaten/kota tidak ditemukan di file Salesforce yang diperiksa.\n'
              'Tindak lanjut: telusuri nama atau ID lain. Pembuatan data baru perlu persetujuan Tim Daikin setelah pemeriksaan data lama.')
        out=compact(text)
        for fact in ['Kab. Kupang','tingkat kabupaten/kota','tidak ditemukan di ekspor Salesforce','data lama','nama/ID lain','persetujuan Tim Daikin']:
            self.assertIn(fact,out)

    def test_counts_and_source_master_evidence_remain_distinct(self):
        text=('Nama cocok dengan nama pada master.\n• Struktur pada master:\n'
              '  - Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota\n'
              '• Ekspor Salesforce: Lokasi lengkap belum tersedia — perlu dikonfirmasi\n'
              '• +27 data bernama sama lainnya; periksa lokasi masing-masing.')
        self.assertEqual(text.split('\n',1)[1],compact(text).split('\n',1)[1])


if __name__=='__main__':unittest.main()
