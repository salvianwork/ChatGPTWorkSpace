"""Relationship review must preserve identity and avoid guessing master locations."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_relation_rows import master_relation,relation_rows,PRIMARY,DIRECT


class RelationRowTests(unittest.TestCase):
    def setUp(self):
        self.path='Provinsi A | Kab. B | Kecamatan C | Desa D'
        self.row=['Kelurahan','data-id','Desa D','Kecamatan',None,None,'hasil pencocokan',
                  'kec-id','Kecamatan C','city-old','lokasi hasil pencocokan','city-new','Kab. B',self.path,
                  'Lengkapi Parent; Ubah kabupaten/kota langsung','Menunggu konfirmasi Tim Daikin',
                  'Catatan asal','Temuan beda tingkat',None,None,None,None,None,None]

    def test_two_relationships_share_id_but_have_distinct_current_and_proposed_ids(self):
        rows=relation_rows(self.row,self.path,{'city-old':'Nama kota dari ekspor'})
        self.assertEqual([r[3] for r in rows],[PRIMARY,DIRECT])
        self.assertEqual([r[7] for r in rows],['kec-id','city-new'])
        self.assertEqual(rows[1][5],'Nama kota dari ekspor')
        self.assertTrue(all(r[1]=='data-id' and r[9]==self.path for r in rows))
        self.assertTrue(all(not any(r[14:]) for r in rows))

    def test_correct_other_relationship_is_kept_in_note_without_extra_row(self):
        self.row[9]='city-new'
        rows=relation_rows(self.row,self.path)
        self.assertEqual(len(rows),1)
        self.assertIn('Hubungan lain sudah sesuai',rows[0][12])
        self.assertIn('city-new',rows[0][12])

    def test_unknown_ids_stay_blank_and_original_evidence_remains(self):
        self.row[7]=self.row[11]=None
        rows=relation_rows(self.row,self.path)
        self.assertEqual(len(rows),2)
        for r in rows:
            self.assertIsNone(r[7]);self.assertIn('Catatan asal',r[12])
            self.assertEqual(r[13],'Temuan beda tingkat')

    def test_existing_answers_and_final_ids_follow_the_correct_relationship(self):
        self.row[18:]=['SETUJU_UBAH','final-kec','final-city','Jawaban','PIC A',46000]
        rows=relation_rows(self.row,self.path)
        self.assertEqual([r[15] for r in rows],['final-kec','final-city'])
        for r in rows:self.assertEqual(r[14:15]+r[16:],['SETUJU_UBAH','Jawaban','PIC A',46000])

    def test_name_only_review_does_not_drop_source_id(self):
        self.row[4]='kec-id';self.row[9]='city-new';self.row[14]='Konfirmasi nama data'
        rows=relation_rows(self.row,self.path)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0][1],'data-id')
        self.assertIn('relasi sudah sesuai',rows[0][10]);self.assertIn('konfirmasi nama data',rows[0][10])

    def test_multiple_master_paths_are_marked_as_unresolved(self):
        other='Provinsi A | Kab. E | Kecamatan F | Desa D'
        choices=[{'Hierarki_Kandidat':other},{'Hierarki_Kandidat':self.path}]
        result=master_relation(self.path,choices,{self.path,other})
        self.assertTrue(result.startswith('Lokasi masih perlu dikonfirmasi.'))
        self.assertEqual(result.splitlines()[1:],[f'• {self.path}',f'• {other}'])

    def test_paths_outside_master_or_missing_recommendation_are_rejected(self):
        with self.assertRaises(ValueError):master_relation(self.path,[{'Hierarki_Kandidat':self.path}],set())
        with self.assertRaises(ValueError):master_relation(self.path,[],{self.path})

    def test_exported_city_name_is_not_guessed_from_recovered_location(self):
        rows=relation_rows(self.row,self.path)
        self.assertIsNone(rows[1][5])


if __name__=='__main__':unittest.main()
