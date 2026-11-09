import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_parent_actions import parent_action_note
from regional_client_display import client_candidate


class ParentActionTests(unittest.TestCase):
    def setUp(self):
        self.path=('Jawa Barat','Kab. Sumedang','Paseh','Legok Kidul')
        self.ids=[{self.path[:1]:'province'},{self.path[:2]:'sumedang'},{self.path[:3]:'paseh'},{}]
        self.source={'Source_Id':'legok','Source_Name':'Legok Kidul','Source_Parent_Id':'','Source_Direct_City_Id':'sumedang'}

    def test_legok_fill_missing_parent_and_keep_correct_city(self):
        before=copy.deepcopy((self.source,self.ids))
        r=parent_action_note(self.source,self.path,self.ids,'legok')
        self.assertIn('Lengkapi kecamatan dengan Paseh, ID paseh.',r['Parent_Action_Note'])
        self.assertIn('Kabupaten Sumedang sudah sesuai.',r['Parent_Action_Note'])
        self.assertIn('Gunakan ID sumber yang sama.',r['Parent_Action_Note'])
        self.assertEqual(r['Parent_Action_Required'],'YES');self.assertEqual((self.source,self.ids),before)

    def test_wrong_parent_and_city_have_separate_actions(self):
        self.source.update(Source_Parent_Id='other-district',Source_Direct_City_Id='other-city')
        r=parent_action_note(self.source,self.path,self.ids,'legok')
        self.assertIn('Ubah kecamatan menjadi Paseh, ID paseh.',r['Parent_Action_Note'])
        self.assertIn('Ubah kabupaten/kota menjadi Kab. Sumedang, ID sumedang.',r['Parent_Action_Note'])

    def test_correct_parents_are_not_changed(self):
        self.source['Source_Parent_Id']='paseh'
        r=parent_action_note(self.source,self.path,self.ids,'legok')
        self.assertEqual(r['Parent_Action_Required'],'NO')
        self.assertNotIn('Lengkapi',r['Parent_Action_Note']);self.assertNotIn('Ubah',r['Parent_Action_Note'])

    def test_unknown_parent_id_never_borrows_other_location(self):
        self.ids[2]={('Jawa Barat','Kab. Lain','Paseh'):'wrong'}
        r=parent_action_note(self.source,self.path,self.ids,'legok')
        self.assertIn('ID untuk wilayah ini belum dapat dipastikan',r['Parent_Action_Note'])
        self.assertNotIn('wrong',r['Parent_Action_Note'])

    def test_other_destination_is_conditional_and_province_has_no_parent(self):
        r=parent_action_note(self.source,self.path,self.ids,'other-legok')
        self.assertTrue(r['Parent_Action_Note'].startswith('Jika rekomendasi ini dipilih'))
        self.assertNotIn('Gunakan ID sumber yang sama.',r['Parent_Action_Note'])
        self.assertEqual(parent_action_note(self.source,self.path[:1],self.ids,'province')['Parent_Action_Note'],'')

    def test_city_and_district_use_their_own_parent_levels(self):
        city={'Source_Id':'c','Source_Name':'Kab. Sumedang','Source_Parent_Id':''}
        r=parent_action_note(city,self.path[:2],self.ids,'c')
        self.assertIn('Lengkapi provinsi dengan Jawa Barat, ID province.',r['Parent_Action_Note'])
        district={'Source_Id':'d','Source_Name':'Paseh','Source_Parent_Id':'wrong'}
        r=parent_action_note(district,self.path[:3],self.ids,'d')
        self.assertIn('Ubah kabupaten/kota menjadi Kab. Sumedang, ID sumedang.',r['Parent_Action_Note'])

    def test_display_uses_action_note_without_repeating_generic_text(self):
        action=parent_action_note(self.source,self.path,self.ids,'legok')
        row={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'RECORD_TERSEDIA_BELUM_TERVERIFIKASI',
             'Id_Target_Kandidat':'','ID_Master_Perlu_Verifikasi':'legok','Nama_Kandidat':'Legok Kidul',
             'Hierarki_Kandidat':' | '.join(self.path),'Alasan':'Lokasi sudah cocok dengan master',
             'Jenis_Rekomendasi':'KECOCOKAN_LOKASI_PERLU_REVIEW','Id_Sumber':'legok',
             'Petunjuk_Perbaikan_Wilayah':action['Parent_Action_Note'],'Perlu_Perbaikan_Wilayah':'YES'}
        self.assertEqual(client_candidate(row)[4],action['Parent_Action_Note'])
        row['Status_Verifikasi_ID']='ID_MASTER_BERBEDA_HIERARKI'
        self.assertIn('ID pada master mengarah ke lokasi lain',client_candidate(row)[4])
