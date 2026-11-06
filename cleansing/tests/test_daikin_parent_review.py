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
                         'Rekomendasi 1 ID Salesforce':'kecamatan-id',
                         'Rekomendasi 1 Lokasi':' | '.join(self.path[:-1])})
        self.candidate.update({'Objek':'Kecamatan__c','Nama_Kandidat':'Kecamatan C',
                               'Hierarki_Kandidat':' | '.join(self.path[:-1]),
                               'ID_Master_Perlu_Verifikasi':'kecamatan-id'})
        plan,reason=self.assess()
        self.assertEqual(reason,'eligible')
        self.assertEqual(plan['parent_id'],'kota-id')
        self.assertEqual(plan['city_id'],'')

    def test_multiple_internal_candidates_stay_even_with_one_visible(self):
        plan,reason=assess(self.row,[self.candidate,dict(self.candidate)],self.targets)
        self.assertIsNone(plan)
        self.assertEqual(reason,'multiple_locations')

    def test_missing_required_parent_id_stays(self):
        for path in [self.path[:-1],self.path[:2]]:
            with self.subTest(path=path):
                targets=dict(self.targets);targets[path]=''
                self.assertEqual(assess(self.row,[self.candidate],targets),(None,'parent_id_unknown'))

    def test_blank_or_different_recommended_id_stays(self):
        for target in [None,'','other-id']:
            self.row['Rekomendasi 1 ID Salesforce']=target
            self.assertEqual(self.assess(),(None,'different_or_missing_id'))

    def test_name_change_stays(self):
        self.row['Nama Sumber']='Desa D lama'
        self.assertEqual(self.assess(),(None,'name_also_changes'))

    def test_different_level_stays(self):
        self.candidate['Objek']='Kecamatan__c'
        self.assertEqual(self.assess(),(None,'different_level'))

    def test_stale_pipeline_fails_instead_of_moving(self):
        self.candidate['ID_Master_Perlu_Verifikasi']='other-id'
        with self.assertRaisesRegex(ValueError,'recommendations differ'):self.assess()

    def test_correct_parent_and_city_stay(self):
        self.row['Id Parent Sekarang']='kecamatan-id'
        self.assertEqual(self.assess(),(None,'no_parent_change'))

    def test_every_existing_review_input_is_retained_in_original_queue(self):
        for header in DATA_HEADERS[17:]:
            with self.subTest(header=header):
                row=dict(self.row);row[header]='existing answer'
                self.assertEqual(assess(row,[self.candidate],self.targets),(None,'existing_review_input'))


if __name__=='__main__':unittest.main()
