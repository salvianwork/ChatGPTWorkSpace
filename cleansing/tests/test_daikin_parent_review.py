"""Guard the boundary between uncertain mapping and same-ID Parent proposals."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_parent_review import DATA_HEADERS,HEADERS,STATUS,assess,proposal_values


class ParentReviewTests(unittest.TestCase):
    def setUp(self):
        self.path=('Provinsi A','Kab. B','Kecamatan C','Desa D')
        self.row=dict.fromkeys(DATA_HEADERS)
        self.row.update({'Objek':'Kelurahan','Id Sumber':'desa-id','Nama Sumber':'Desa D',
                         'Rekomendasi 1 Nama':'Desa D',
                         'Rekomendasi 1 ID Salesforce':'desa-id',
                         'Rekomendasi 1 Lokasi':' | '.join(self.path),
                         'Id Kota Langsung Sekarang':'kota-id',
                         'Temuan Pada Tingkat Lain':'Bukti beda tingkat tetap disimpan.'})
        self.candidate={'Objek':'Kelurahan__c','Hierarki_Kandidat':' | '.join(self.path),
                        'Nama_Kandidat':'Desa D','Id_Target_Kandidat':'',
                        'ID_Master_Perlu_Verifikasi':'desa-id'}
        self.targets={self.path[:-1]:'kecamatan-id',self.path[:2]:'kota-id'}

    def assess(self):
        return assess(self.row,[self.candidate],self.targets)

    def test_missing_parent_moves_as_pending_proposal_without_final_values(self):
        original=deepcopy(self.row)
        plan,reason=self.assess()
        self.assertEqual(reason,'eligible')
        self.assertEqual(plan['parent_id'],'kecamatan-id')
        self.assertEqual(plan['actions'],['Lengkapi Parent'])
        values=proposal_values(self.row,plan)
        output=dict(zip(HEADERS,values,strict=True))
        self.assertEqual(output['Id Data'],'desa-id')
        self.assertEqual(output['Status Review'],STATUS)
        self.assertEqual(output['Temuan Pada Tingkat Lain'],self.row['Temuan Pada Tingkat Lain'])
        self.assertEqual(output['Id Parent Usulan'],'kecamatan-id')
        self.assertTrue(all(value is None for value in values[18:]))
        self.assertEqual(self.row,original)

    def test_wrong_parent_and_city_are_separate_actions(self):
        self.row.update({'Id Parent Sekarang':'wrong-parent','Id Kota Langsung Sekarang':'wrong-city'})
        plan,reason=self.assess()
        self.assertEqual(reason,'eligible')
        self.assertEqual(plan['actions'],['Ubah Parent','Ubah kabupaten/kota langsung'])

    def test_kecamatan_needs_city_parent_only(self):
        self.row.update({'Objek':'Kecamatan','Id Sumber':'kecamatan-id','Nama Sumber':'Kecamatan C',
                         'Rekomendasi 1 Nama':'Kecamatan C',
                         'Rekomendasi 1 ID Salesforce':'kecamatan-id',
                         'Rekomendasi 1 Lokasi':' | '.join(self.path[:-1])})
        self.candidate.update({'Objek':'Kecamatan__c','Nama_Kandidat':'Kecamatan C',
                               'Hierarki_Kandidat':' | '.join(self.path[:-1]),
                               'ID_Master_Perlu_Verifikasi':'kecamatan-id'})
        plan,reason=self.assess()
        self.assertEqual(reason,'eligible')
        self.assertEqual(plan['parent_id'],'kota-id')
        self.assertEqual(plan['city_id'],'')

    def test_multiple_internal_candidates_move_without_selecting_parent(self):
        other=dict(self.candidate,Hierarki_Kandidat='Provinsi A | Kab. X | Kecamatan Y | Desa D',
                   ID_Master_Perlu_Verifikasi='other-id')
        plan,reason=assess(self.row,[other,self.candidate],self.targets)
        self.assertEqual(reason,'multiple_locations')
        self.assertEqual(plan['parent_id'],'')
        self.assertEqual(plan['city_id'],'')
        self.assertEqual(plan['status'],'Lokasi dan Parent masih perlu dikonfirmasi')
        values=proposal_values(self.row,plan)
        self.assertTrue(all(values[i] is None for i in [7,8,11,12]))
        self.assertIn('2 rekomendasi lokasi',values[16])
        self.assertEqual(values[13],self.row['Rekomendasi 1 Lokasi'])

    def test_missing_required_parent_id_moves_with_blank_proposal(self):
        for path in [self.path[:-1],self.path[:2]]:
            with self.subTest(path=path):
                targets=dict(self.targets);targets[path]=''
                plan,reason=assess(self.row,[self.candidate],targets)
                self.assertEqual(reason,'parent_id_unknown')
                self.assertEqual(plan['status'],'Parent masih perlu dikonfirmasi')
                self.assertEqual(plan['parent_id' if path==self.path[:-1] else 'city_id'],'')
                values=proposal_values(self.row,plan)
                self.assertIsNone(values[7 if path==self.path[:-1] else 11])
                self.assertTrue(all(value is None for value in values[18:]))

    def test_blank_or_different_recommended_id_stays(self):
        for target in [None,'','other-id']:
            self.row['Rekomendasi 1 ID Salesforce']=target
            self.assertEqual(self.assess(),(None,'different_or_missing_id'))

    def test_name_change_moves_with_current_name_and_explicit_note(self):
        self.row['Nama Sumber']='Desa D lama'
        plan,reason=self.assess()
        self.assertEqual(reason,'name_also_changes')
        self.assertEqual(plan['status'],'Nama masih perlu dikonfirmasi')
        values=proposal_values(self.row,plan)
        self.assertEqual(values[2],'Desa D lama')
        self.assertIn('Nama pada rekomendasi pertama: Desa D.',values[16])
        self.assertIn('Konfirmasi nama data',values[14])

    def test_different_level_stays(self):
        self.candidate['Objek']='Kecamatan__c'
        self.assertEqual(self.assess(),(None,'different_level'))

    def test_stale_pipeline_fails_instead_of_moving(self):
        self.candidate['ID_Master_Perlu_Verifikasi']='other-id'
        with self.assertRaisesRegex(ValueError,'recommendations differ'):self.assess()

    def test_same_id_without_direct_change_is_never_auto_approved(self):
        self.row['Id Parent Sekarang']='kecamatan-id'
        plan,reason=self.assess()
        self.assertEqual(reason,'no_parent_change')
        self.assertEqual(plan['status'],'Parent masih perlu dikonfirmasi')
        self.assertEqual(plan['actions'],['Periksa hubungan Parent'])
        self.assertTrue(all(v is None for v in proposal_values(self.row,plan)[18:]))

    def test_unknown_parent_and_changed_name_are_both_visible(self):
        self.targets[self.path[:-1]]='';self.row['Nama Sumber']='Desa D lama'
        plan,_=self.assess()
        self.assertEqual(plan['status'],'Nama dan Parent masih perlu dikonfirmasi')
        values=proposal_values(self.row,plan)
        self.assertIn('ID Parent yang belum dapat dipastikan',values[16])
        self.assertIn('Nama saat ini: Desa D lama.',values[16])

    def test_known_city_remains_available_when_kecamatan_id_is_unknown(self):
        self.targets[self.path[:-1]]=''
        plan,_=self.assess();values=proposal_values(self.row,plan)
        self.assertIsNone(values[7])
        self.assertEqual(values[8],'Kecamatan C')
        self.assertEqual(values[11],'kota-id')

    def test_same_parent_on_multiple_locations_is_still_pending(self):
        other=dict(self.candidate,Hierarki_Kandidat='Provinsi A | Kab. B | Kecamatan C | Desa E',
                   ID_Master_Perlu_Verifikasi='other-id',Nama_Kandidat='Desa E')
        plan,_=assess(self.row,[self.candidate,other],self.targets)
        self.assertEqual(plan['parent_id'],'')
        self.assertEqual(plan['status'],'Lokasi dan Parent masih perlu dikonfirmasi')

    def test_previous_explanation_and_cross_level_evidence_are_preserved(self):
        self.row['Rekomendasi 1 Catatan']='ID ini sama dengan ID sumber. Hubungan wilayah masih perlu diperiksa.\n\nBukti sebelumnya.'
        plan,_=self.assess();values=proposal_values(self.row,plan)
        self.assertIn('Bukti sebelumnya.',values[16])
        self.assertEqual(values[17],self.row['Temuan Pada Tingkat Lain'])

    def test_every_existing_review_input_is_retained_in_original_queue(self):
        for header in DATA_HEADERS[17:]:
            with self.subTest(header=header):
                row=dict(self.row);row[header]='existing answer'
                self.assertEqual(assess(row,[self.candidate],self.targets),(None,'existing_review_input'))


if __name__=='__main__':unittest.main()
