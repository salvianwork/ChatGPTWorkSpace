import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from regional_matching import ranked_candidates, district_context_candidates


class RegionalMatchingTests(unittest.TestCase):
    def test_banjar(self):
        p = ('Jawa Barat', 'Kota Banjar')
        result = ranked_candidates(1, 'Banjar', ('Jawa Barat',), [p, ('Bali', 'Kota Banjar')])
        self.assertEqual([(r[0], r[2]) for r in result], [(2, p)])

    def test_alias_beats_text_similarity(self):
        paths = [('Banten', n) for n in ['Kab. Tangerang', 'Kota Tangerang Selatan', 'Kota Tangerang']]
        result = ranked_candidates(1, 'Tangsel', ('Banten',), paths)
        self.assertEqual(result[0][2], ('Banten', 'Kota Tangerang Selatan'))
        self.assertEqual(result[0][0], 1)
        self.assertLess(result[0][1], result[1][1])

    def test_alias_scope(self):
        self.assertFalse(any(r[0] == 1 for r in ranked_candidates(1, 'Tangsel', ('Jawa Barat',), [('Jawa Barat', 'Kota Tangerang Selatan')])))
        self.assertEqual(ranked_candidates(1, 'Tangsel', None, [('Banten', 'Kota Tangerang Selatan')]), [])
        self.assertFalse(any(r[0] == 1 for r in ranked_candidates(2, 'Tangsel', ('Banten', 'Kota Tangerang'), [('Banten', 'Kota Tangerang', 'Kota Tangerang Selatan')])))

    def test_ambiguous_and_conflicting_types(self):
        paths = [('Banten', 'Kota Serang'), ('Banten', 'Kab. Serang')]
        result = ranked_candidates(1, 'Serang', ('Banten',), paths)
        self.assertEqual(len(result), 2)
        self.assertTrue(all('Ambigu' in r[3] for r in result))
        result = ranked_candidates(1, 'Kota Serang', ('Banten',), paths)
        self.assertEqual(result[0][0], 0)
        self.assertIn('Konflik jenis', result[1][3])

    def test_normalization_and_full_parent(self):
        p = ('Banten', 'Kota Tangerang', 'Cipondoh')
        other = ('Banten', 'Kota Serang', 'Cipondoh')
        result = ranked_candidates(2, ' KEC. CIPONDOH ', p[:-1], [p, other])
        self.assertEqual([r[2] for r in result], [p])
        result = ranked_candidates(1, '  KOTA   BANJAR. ', ('Jawa Barat',), [('Jawa Barat', 'Kota Banjar')])
        self.assertEqual(result[0][0], 0)

    def test_all_ambiguous_core_matches_are_retained(self):
        paths = [('Banten', n) for n in ['Serang', 'Kota Serang', 'Kab. Serang', 'Kabupaten Serang']]
        result = ranked_candidates(1, 'SERANG.', ('Banten',), paths)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0][0], 0)
        self.assertTrue(all('Ambigu' in r[3] for r in result[1:]))

    def test_unknown_parent_does_not_guess_from_core(self):
        self.assertEqual(ranked_candidates(1, 'Banjar', None, [('Jawa Barat', 'Kota Banjar')]), [])
        result = ranked_candidates(1, 'Kota Banjar', None, [('Jawa Barat', 'Kota Banjar')])
        self.assertEqual(result[0][0], 0)
        self.assertIn('induk belum diketahui', result[0][3])

    def test_kingking_district_from_master_child(self):
        path = ('Jawa Timur', 'Kab. Tuban', 'Tuban', 'Kingking')
        result = district_context_candidates('Kingking', path[:2], [path])
        self.assertEqual(result[0][0], path[:3])
        self.assertIn('Kelurahan: Jawa Timur | Kab. Tuban | Tuban | Kingking', result[0][1])
        self.assertIn('Jika record dimaksudkan sebagai Kecamatan', result[0][1])
        self.assertIn('Jika record dimaksudkan sebagai Kelurahan', result[0][1])
        self.assertEqual(district_context_candidates('Kingking', None, [path]), [])
        self.assertEqual(district_context_candidates('Kingking', ('Banten', 'Kab. Tuban'), [path]), [])

    def test_context_ambiguity_and_exact_name(self):
        paths = [('Jawa Timur', 'Kab. Tuban', d, 'Kingking') for d in ['Tuban', 'Lain']]
        result = district_context_candidates('Kel. Kingking', paths[0][:2], paths)
        self.assertEqual(len(result), 2)
        self.assertTrue(all('Ambigu' in reason for _, reason in result))
        self.assertEqual(district_context_candidates('King', paths[0][:2], paths), [])


if __name__ == '__main__':
    unittest.main()
