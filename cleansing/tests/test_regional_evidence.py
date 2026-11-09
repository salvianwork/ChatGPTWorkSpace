import sys,unittest
from pathlib import Path
from lxml import etree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_evidence import candidate_proof,rename_recommendation_label
from polish_daikin_workbook import clean_cross,evidence_note
from daikin_review_readability import put,TAG
from regional_client_display import ensure_selection_matches


class EvidenceTests(unittest.TestCase):
    def record(self):
        return {'Reason':'Nama sumber ditemukan sebagai Kelurahan: Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota. Jika record dimaksudkan sebagai Kecamatan, rekomendasi berdasarkan induk kelurahan adalah Dusun Selatan.',
                'Candidate_Path':'Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan'}

    def test_full_proof_is_extracted_only_for_its_own_parent_candidate(self):
        r=self.record();p=candidate_proof(r);self.assertEqual(p[-1],'Buntok Kota');self.assertEqual(len(p),4)
        r['Candidate_Path']='Kalimantan Tengah | Kab. Barito Utara | Teweh Selatan';self.assertIsNone(candidate_proof(r))
        r['Reason']='Nama mirip berdasarkan teks';self.assertIsNone(candidate_proof(r))

    def test_full_paths_without_level_prefixes_and_source_separation(self):
        p=candidate_proof(self.record())
        old='• Hasil Salesforce:\n  - Kelurahan: Lokasi lengkap belum tersedia — perlu dikonfirmasi\n\n• Tindak Lanjut:\n  Old'
        out=clean_cross(old,{3:{p}},['“Buntok” → “Buntok Kota”'])
        self.assertIn('  - '+' | '.join(p),out);self.assertNotIn('Kelurahan:',out)
        self.assertIn('variasi nama',out)
        salesforce=out.split('• Hasil Salesforce:',1)[1]
        self.assertNotIn('Buntok Kota',salesforce);self.assertIn('Lokasi lengkap belum tersedia — perlu dikonfirmasi',salesforce)

    def test_locations_are_capped_per_level_with_exact_remainder(self):
        paths={('P','C','D','X'+str(i)) for i in range(7)}
        out=clean_cross(None,{3:paths})
        self.assertEqual(out.count('  - P | C | D'),3);self.assertIn('+4 lokasi lainnya',out)
        preferred=('P','C','D','X6')
        prioritized=clean_cross(None,{3:paths},priority=[preferred])
        self.assertEqual(prioritized.splitlines()[1],'  - '+' | '.join(preferred))

    def test_complete_hierarchy_note_preserves_missing_id_reason(self):
        old='Di master, old relationship. Jika yang dimaksud kelurahan, tingkat wilayahnya perlu diperbaiki. ID masih perlu dipilih.\n\nAlasan ID belum tersedia: record lain berbeda lokasi.'
        out=evidence_note(old,[candidate_proof(self.record())],2,'Dusun Selatan')
        self.assertIn('Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota',out)
        self.assertIn('Alasan ID belum tersedia: record lain berbeda lokasi.',out)
        self.assertIn('ID masih perlu dipilih.',out)
        self.assertNotIn('old relationship',out);self.assertNotIn('Kelurahan:',out)
        self.assertEqual(evidence_note(out,[candidate_proof(self.record())],2,'Dusun Selatan'),out)

    def test_blank_new_cell_is_sorted_before_a_later_column(self):
        row=E.Element(TAG+'row',r='2');put(row,14,'Reason');put(row,7,None,17)
        self.assertEqual([c.get('r') for c in row],['G2','N2'])
        put(row,3,None);self.assertEqual([c.get('r') for c in row],['C2','G2','N2'])

    def test_numberless_label_does_not_change_other_numbers_or_existing_choice(self):
        self.assertEqual(rename_recommendation_label('Rekomendasi 1 ID Salesforce'),'Rekomendasi ID Salesforce')
        self.assertEqual(rename_recommendation_label('Gunakan rekomendasi 1'),'Gunakan rekomendasi')
        self.assertEqual(rename_recommendation_label('Rekomendasi 10'),'Rekomendasi 10')
        with self.assertRaises(ValueError):ensure_selection_matches([('A','P | A','id-a')],[('B','P | B','id-b')],'Gunakan rekomendasi')

if __name__=='__main__':unittest.main()
