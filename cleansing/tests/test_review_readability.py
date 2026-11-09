import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_matching import ranked_candidates,conflicting_region_words
from regional_client_display import client_candidate,clarify_no_exact_rows,ensure_selection_matches
from daikin_review_readability import master_evidence,master_locations,parent_note,compact_note


class ReviewReadabilityTests(unittest.TestCase):
    def test_opposing_parts_are_not_spelling_recommendations(self):
        for name,target in [('Misool (Misool Utara)','Misool Selatan'),
                            ('Rumbai (Rumbai Pesisir)','Rumbai Barat'),
                            ('Sei Kera Hilir I','Sei Kera Hulu'),
                            ('Muara Panco Timur','Muaro Panco Barat')]:
            self.assertTrue(conflicting_region_words(name,target))
            self.assertEqual(ranked_candidates(2,name,('P','C'),[('P','C',target)]),[])

    def test_real_exact_and_reviewed_spelling_matches_survive(self):
        parent=('Sulawesi Tenggara','Kab. Buton Utara')
        path=parent+('Kulisusu',)
        self.assertEqual(ranked_candidates(2,'Kulisusu (Kalisusu)',parent,[path])[0][2],path)
        self.assertEqual(ranked_candidates(2,'Muara Panco Timur',('P','C'),[('P','C','Muara Panco Timur')])[0][0],0)
        self.assertFalse(conflicting_region_words('Pariaman Tengah','Pariaman Tengah'))
        self.assertFalse(conflicting_region_words('Bungursari','Bungursari'))

    def test_evidence_is_actual_and_capped(self):
        paths=['P | C | D | Name '+str(i) for i in range(7)]
        text=master_evidence(paths)
        self.assertEqual(text.count('• '),3);self.assertTrue(text.endswith('+4 lokasi lainnya'))
        self.assertNotIn(paths[3],text)
        ix={(3,'sukarindik'):{'Jawa Barat | Kota Tasikmalaya | Bungursari | Sukarindik'}}
        self.assertEqual(master_locations('SUKARINDIK',3,ix),sorted(ix[(3,'sukarindik')]))
        self.assertEqual(master_locations('missing',3,ix),[])

    def test_information_is_not_a_recommendation_and_never_gets_id(self):
        d={'Jenis_Bukti':'NAMA_SAMA_LOKASI_LAIN','Nama_Kandidat':'Pulau Jambu',
           'Contoh_Lokasi':'Kalimantan Barat | Kab. Kubu Raya | Sungai Raya | Pulau Jambu',
           'Id_Target_Kandidat':'must-not-be-used'}
        view=client_candidate(d);self.assertEqual(view[2],'');self.assertIn('lokasi perlu dikonfirmasi',view[3])
        info=['Kelurahan','id','Pulau Jambu',1]+view
        nohit=['Kelurahan','id','Pulau Jambu',2,None,None,None,'Nama belum ditemukan','text']
        self.assertEqual(clarify_no_exact_rows([info,nohit])[1][7],'Nama belum ditemukan')
        d['Jumlah_Kemunculan']='5'
        self.assertTrue(client_candidate(d)[1].endswith('+2 lokasi lainnya'))

    def test_parent_notes_keep_id_reason_and_show_dependency(self):
        v=[None]*19;v[3]='Parent Kecamatan';v[11]='ID relasi masih perlu dikonfirmasi'
        v[12]='Old copy\nAlasan ID kecamatan belum dipastikan:\n• Data bernama sama belum ditemukan.\n\nSetelah Tim Daikin memastikan lokasi:\n• Old instruction'
        note=parent_note(v,2)
        self.assertIn('Data bernama sama belum ditemukan',note)
        self.assertIn('baris hubungan lain',note)
        self.assertNotIn('Old instruction',note)
        v[11]='Lokasi dan ID relasi masih perlu dikonfirmasi'
        self.assertNotIn('Alasan ID',parent_note(v,1))
        self.assertIn('konfirmasikan lokasi',parent_note(v,1))

    def test_case_specific_id_explanation_is_preserved(self):
        text='Alasan ID kosong: nama ada di master, tetapi data ID berbeda lokasi.\n\nHubungan wilayah untuk lokasi rekomendasi:\n• Kota A sudah sesuai.\n• Tidak perlu mengubah hubungan wilayah.'
        note=compact_note(text)
        self.assertIn('data ID berbeda lokasi',note);self.assertIn('Kota A sudah sesuai',note)
        self.assertNotIn('Tidak perlu',note);self.assertEqual(compact_note(note),note)

    def test_plain_language_decision_also_protects_existing_choice(self):
        with self.assertRaises(ValueError):
            ensure_selection_matches([('A','P | A','id-a')],[('B','P | B','id-b')],'Gunakan rekomendasi 1')

if __name__=='__main__':unittest.main()
