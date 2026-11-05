import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_id_explanations import IDExplanation
from regional_client_display import client_candidate


def row(rid,name,parent='',path=None,**more):
    return dict(Source_Id=rid,Source_Name=name,Source_Parent_Id=parent,_path=path,
                _blocked=False,_requires_review=False,**more)


class IDExplanationTests(unittest.TestCase):
    def setUp(self):
        self.path=('Sumatra Utara','Kab. Toba','Lumban Julu')
        self.records=[{'province':row('province','Sumatra Utara',path=self.path[:1])},
                      {'toba':row('toba','Kabupaten Toba','province',self.path[:2]),
                       'other-city':row('other-city','Kab. Tapanuli Utara','province',('Sumatra Utara','Kab. Tapanuli Utara'))},
                      {'district':row('district','Lumban Julu','other-city')},{}]
        self.targets=[{self.path[:1]:'province'},{self.path[:2]:'toba'},{},{}]
        self.explain=IDExplanation(self.records,self.targets)

    def test_existing_name_in_other_city_is_explained_without_approving_id(self):
        source=row('source','Jangga Dolok','toba')
        review={'Candidate_Target_Id':'','Unverified_Master_ID':''}
        before=copy.deepcopy((self.records,self.targets,source,review))
        text=self.explain.for_candidate(source,self.path,review)['Client_ID_Note']
        self.assertIn('ID district',text);self.assertIn('Kab. Tapanuli Utara',text)
        self.assertIn('Kabupaten/kota yang diperlukan: Sumatra Utara | Kab. Toba.',text)
        self.assertIn('belum ditetapkan sebagai ID tujuan',text)
        self.assertEqual((self.records,self.targets,source,review),before)
        self.assertEqual(review['Candidate_Target_Id'],'')

    def test_missing_name_is_not_reported_as_existing(self):
        text=self.explain.missing_location_id(self.path[:-1]+('Tidak Ada',))
        self.assertIn('tidak ditemukan di file Salesforce',text)
        self.assertIn('data baru perlu persetujuan client',text)
        self.assertNotIn('ID district',text)

    def test_missing_or_unknown_actual_parent_never_uses_recovered_path_as_lookup(self):
        district=self.records[2]['district'];district['_path']=self.path
        for parent,expected in [('', 'kolom kabupaten/kota utama masih kosong'),('missing','ID kabupaten/kota missing tidak ditemukan')]:
            district['Source_Parent_Id']=parent
            text=self.explain.missing_location_id(self.path)
            self.assertIn(expected,text)
            self.assertNotIn('kabupaten/kota saat ini: Sumatra Utara | Kab. Toba',text)

    def test_multiple_matching_records_and_three_item_limit(self):
        self.records[2]={str(i):row(str(i),'Lumban Julu','toba',self.path) for i in range(5)}
        text=IDExplanation(self.records,self.targets).missing_location_id(self.path)
        self.assertIn('Ada 5 data',text);self.assertIn('+2 data bernama sama lainnya',text)
        self.assertEqual(text.count('• ID '),3)

    def test_self_id_repair_explains_missing_parent_and_duplicate_city(self):
        self.targets[2][self.path]='district'
        self.records[1]['duplicate']=row('duplicate','Toba','province',self.path[:2],Status='MAPPED_DUPLICATE',Target_Id='toba')
        source=row('self','Jangga Toruan','',Source_Direct_City_Id='duplicate')
        path=self.path+('Jangga Toruan',)
        text=self.explain.for_candidate(source,path,{'Candidate_Target_Id':'','Unverified_Master_ID':'self'})['Client_ID_Note']
        self.assertIn('Kolom kecamatan utama saat ini kosong',text)
        self.assertIn('Kabupaten/kota langsung saat ini memakai data duplikat Toba',text)
        self.assertIn('ID yang dipertahankan adalah toba',text)

    def test_child_with_pending_parent_gets_specific_parent_explanation(self):
        source=row('self','Jangga Toruan','district',Source_Direct_City_Id='toba')
        text=self.explain.for_candidate(source,self.path+('Jangga Toruan',),{'Candidate_Target_Id':'','Unverified_Master_ID':'self'})['Client_ID_Note']
        self.assertIn('Alasan ID kecamatan Lumban Julu belum dipastikan',text)
        self.assertIn('Kab. Tapanuli Utara',text)

    def test_complete_self_record_needs_no_extra_note(self):
        self.targets[2][self.path]='district'
        source=row('self','Desa','district',Source_Direct_City_Id='toba')
        text=self.explain.for_candidate(source,self.path+('Desa',),{'Candidate_Target_Id':'self','Unverified_Master_ID':''})['Client_ID_Note']
        self.assertEqual(text,'')

    def test_rendered_missing_id_retains_context_and_specific_reason(self):
        detail=self.explain.missing_location_id(self.path)
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'BELUM_ADA_ID_TERVERIFIKASI',
           'Id_Target_Kandidat':'','ID_Master_Perlu_Verifikasi':'','Id_Sumber':'source',
           'Nama_Kandidat':'Lumban Julu','Hierarki_Kandidat':' | '.join(self.path),'Tingkat_Ditemukan':'Kecamatan',
           'Alasan':'Nama sumber ditemukan sebagai Kelurahan: Sumatra Utara | Kab. Toba | Lumban Julu | Jangga Dolok. Jika record dimaksudkan sebagai Kecamatan, gunakan Lumban Julu.',
           'Penjelasan_ID_Client':detail,
           'Petunjuk_Perbaikan_Wilayah':'Hubungan wilayah untuk lokasi rekomendasi:\n• Kabupaten Toba sudah sesuai.\n• Tidak perlu mengubah hubungan wilayah.'}
        view=client_candidate(d)
        self.assertEqual(view[2],'');self.assertEqual(view[3],'ID belum dipastikan')
        self.assertIn('Jangga Dolok adalah kelurahan',view[4]);self.assertIn('ID district',view[4])
        self.assertIn('Kab. Tapanuli Utara',view[4])
        self.assertEqual(view[4].count(detail),1)
        self.assertIn('Hubungan wilayah pada data sumber untuk pilihan ini:',view[4])

    def test_rendered_self_note_does_not_repeat_keep_id_instruction(self):
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'RECORD_TERSEDIA_BELUM_TERVERIFIKASI',
           'Id_Target_Kandidat':'','ID_Master_Perlu_Verifikasi':'self','Id_Sumber':'self','Nama_Kandidat':'Desa',
           'Hierarki_Kandidat':'P | C | D | Desa','Penjelasan_ID_Client':'Kondisi data: kecamatan utama kosong.',
           'Petunjuk_Perbaikan_Wilayah':'Setelah client memastikan lokasi:\n• Lengkapi kecamatan dengan D, ID district.\n• Gunakan ID sumber yang sama.',
           'Perlu_Perbaikan_Wilayah':'YES'}
        view=client_candidate(d)
        self.assertIn('ID ini sama dengan ID sumber. Hubungan wilayah masih perlu diperiksa.',view[4])
        self.assertIn('Kondisi data: kecamatan utama kosong.',view[4])
        self.assertNotIn('Gunakan ID sumber yang sama.',view[4])
        self.assertEqual(view[2],'self')

    def test_self_id_detail_preserves_different_level_context(self):
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'RECORD_TERSEDIA_BELUM_TERVERIFIKASI',
           'Id_Target_Kandidat':'','ID_Master_Perlu_Verifikasi':'self','Id_Sumber':'self','Nama_Kandidat':'Lumban Julu',
           'Hierarki_Kandidat':'Sumatra Utara | Kab. Toba | Lumban Julu','Tingkat_Ditemukan':'Kecamatan',
           'Alasan':'Nama source ditemukan', 'Penjelasan_ID_Client':'Kondisi yang perlu diperiksa.',
           'Petunjuk_Perbaikan_Wilayah':'Setelah client memastikan lokasi:\n• Pastikan kabupaten/kota Kab. Toba.',
           'Perlu_Perbaikan_Wilayah':'YES'}
        d['Alasan']='Nama sumber ditemukan sebagai Kelurahan: Sumatra Utara | Kab. Toba | Lumban Julu | Jangga Dolok. Jika record dimaksudkan sebagai Kecamatan, gunakan Lumban Julu.'
        view=client_candidate(d)
        self.assertIn('Jangga Dolok adalah kelurahan',view[4])
        self.assertIn('tingkat wilayahnya perlu diperbaiki',view[4])
        self.assertIn('ID ini sama dengan ID sumber',view[4])


if __name__=='__main__':unittest.main()
