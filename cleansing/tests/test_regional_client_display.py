import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_client_display import client_candidate,source_text,CHOICE_HEADERS,MAPPING_HEADERS


class ClientDisplayTests(unittest.TestCase):
    def candidate(self,**changes):
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'ID_TERVERIFIKASI',
           'Id_Target_Kandidat':'verified','ID_Master_Perlu_Verifikasi':'old',
           'Nama_Kandidat':'Martapura','Hierarki_Kandidat':'Kalimantan Selatan | Kab. Banjar | Martapura',
           'Alasan':'Lokasi sudah cocok dengan master','Jenis_Rekomendasi':'KANDIDAT_RECORD_TUJUAN',
           'Id_Sumber':'source','Tingkat_Ditemukan':'Kecamatan'}
        d.update(changes);return d

    def test_one_id_column_and_priority(self):
        view=client_candidate(self.candidate())
        self.assertEqual(len(view),5);self.assertEqual(view[2],'verified')
        self.assertNotIn('old',view[4]);self.assertEqual(len(CHOICE_HEADERS),15)
        self.assertEqual(sum('ID_Salesforce' in c for c in CHOICE_HEADERS),3)
        self.assertEqual(sum('ID_' in c for c in MAPPING_HEADERS),1)

    def test_pending_id_is_visible_with_warning(self):
        view=client_candidate(self.candidate(Id_Target_Kandidat='',Status_Verifikasi_ID='INDUK_ID_MASTER_PERLU_KONFIRMASI'))
        self.assertEqual(view[2],'old');self.assertEqual(view[3],'Hubungan wilayah perlu dicek')
        self.assertNotIn('verifikasi',view[4]);self.assertIn('hubungan',view[4])

    def test_multiple_ids_and_missing_id(self):
        view=client_candidate(self.candidate(Id_Target_Kandidat='',ID_Master_Perlu_Verifikasi='one;two',Status_Verifikasi_ID='ID_MASTER_AMBIGU'))
        self.assertEqual(view[2],'one;two');self.assertEqual(view[3],'Perlu pilih satu ID')
        view=client_candidate(self.candidate(Id_Target_Kandidat='',ID_Master_Perlu_Verifikasi='',Status_Verifikasi_ID='BELUM_ADA_ID_TERVERIFIKASI'))
        self.assertEqual(view[2],'');self.assertEqual(view[3],'ID belum dipastikan')

    def test_alternative_and_source_warning_are_simple(self):
        view=client_candidate(self.candidate(Status_Verifikasi_ID='ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'))
        self.assertEqual(view[3],'Perlu konfirmasi ID utama')
        self.assertEqual(view[4],'Nama dan lokasi rekomendasi sesuai master. Client perlu memastikan ID yang akan digunakan.')

    def test_self_id_and_child_hypothesis(self):
        view=client_candidate(self.candidate(Id_Sumber='verified',Jenis_Rekomendasi='KOREKSI_RECORD_YANG_SAMA'))
        self.assertIn('ID ini sama dengan ID sumber',view[4])
        view=client_candidate(self.candidate(Nama_Kandidat='Tuban',Alasan='Nama sumber ditemukan sebagai Kelurahan: Jawa Timur | Kab. Tuban | Tuban | Kingking. Jika record dimaksudkan sebagai Kecamatan, rekomendasi berdasarkan induk kelurahan adalah Tuban.'))
        self.assertIn('Kingking adalah kelurahan',view[4]);self.assertIn('gunakan Tuban',view[4]);self.assertIn('tingkat wilayahnya perlu diperbaiki',view[4])

    def test_cross_level_never_displays_an_id(self):
        view=client_candidate(self.candidate(Jenis_Bukti='TEMUAN_LINTAS_TINGKAT',Contoh_Lokasi='Jawa Barat | Kota Banjar | Banjar'))
        self.assertEqual(view[2],'')

    def test_source_notes_idempotent_and_locations_preserved(self):
        cross='• Hasil Master:\n  - Kelurahan: Jawa Timur | Kab. Tuban | Tuban | Kingking\n\n• Tindak Lanjut:\n  Old text'
        args=('Lokasi cocok dengan master tetapi ID tujuan belum pasti','record lookup','Jawa Timur | Kab. Tuban',None,cross)
        a=source_text(*args);b=source_text(a[0],a[1],args[2],None,a[2]);self.assertEqual(a,b)
        self.assertEqual(a[2].split('• Tindak Lanjut:')[0],cross.split('• Tindak Lanjut:')[0])

    def test_other_city_reason_is_visible_and_simple(self):
        reason='Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda: Jawa Barat | Kota Bogor | Bogor Barat. Kabupaten/kota pada data sumber adalah Kab. Bogor. Client perlu memastikan perubahan kabupaten/kota.'
        view=client_candidate(self.candidate(Nama_Kandidat='Bogor Barat',Alasan=reason,
            Id_Target_Kandidat='',ID_Master_Perlu_Verifikasi='source',
            Status_Verifikasi_ID='KOTA_SUMBER_PERLU_KONFIRMASI',Jenis_Rekomendasi='KOREKSI_RECORD_YANG_SAMA'))
        self.assertEqual(view[2],'source');self.assertEqual(view[3],'Kabupaten/kota perlu dikonfirmasi')
        self.assertIn('Kota Bogor',view[4]);self.assertIn('Kab. Bogor',view[4])

    def test_other_city_preserves_pending_id_warning(self):
        reason='Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda: Jawa Barat | Kota Bogor | Bogor Barat.'
        view=client_candidate(self.candidate(Alasan=reason,Id_Target_Kandidat='',
            ID_Master_Perlu_Verifikasi='another',Status_Verifikasi_ID='ID_MASTER_BERBEDA_HIERARKI'))
        self.assertIn('ID pada master mengarah ke lokasi lain',view[4])
        view=client_candidate(self.candidate(Alasan=reason,Id_Target_Kandidat='',
            ID_Master_Perlu_Verifikasi='one;two',Status_Verifikasi_ID='ID_MASTER_AMBIGU'))
        self.assertEqual(view[3],'Perlu pilih satu ID')


if __name__=='__main__':unittest.main()
