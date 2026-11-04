import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from regional_matching import ranked_candidates, district_context_candidates, city_context_candidates


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

    def test_babelan_city_from_master_district(self):
        path = ('Jawa Barat', 'Kab. Bekasi', 'Babelan')
        result = city_context_candidates('Babelan', path[:1], [path])
        self.assertEqual(result[0][0], path[:2])
        self.assertIn('Kecamatan: Jawa Barat | Kab. Bekasi | Babelan', result[0][1])
        self.assertIn('Jika record dimaksudkan sebagai Kota/Kabupaten', result[0][1])
        self.assertIn('Jika record sebenarnya dimaksudkan sebagai Kecamatan', result[0][1])
        self.assertEqual(city_context_candidates('Babelan', None, [path])[0][0],path[:2])
        self.assertEqual(city_context_candidates('Babelan', ('Banten',), [path]), [])
        self.assertEqual(city_context_candidates('Babel', path[:1], [path]), [])

    def test_city_context_ambiguity_and_deduplication(self):
        districts = [('Jawa Barat', 'Kab. Bekasi', 'Babelan'), ('Jawa Barat', 'Kab. Lain', 'Babelan')]
        children = [('Jawa Barat', 'Kab. Bekasi', 'Babelan', 'Babelan')]
        result = city_context_candidates('Babelan', ('Jawa Barat',), districts, children)
        self.assertEqual(len(result), 2)
        self.assertTrue(all('Ambigu' in reason for _, reason in result))
        self.assertIn('Kecamatan:', result[0][1])
        result = city_context_candidates('Babelan', ('Jawa Barat',), [], children)
        self.assertEqual(result[0][0], children[0][:2])
        self.assertIn('Kelurahan:', result[0][1])

    def test_comma_parent_buay_pemaca(self):
        parent = ('Sumatra Selatan', 'Kab. Ogan Komering Ulu Selatan')
        path = parent + ('Buay Pemaca',)
        result = ranked_candidates(2, 'Buay Pemaca, Ogan Komering Ulu Selatan', parent, [path])
        self.assertEqual(result[0][2], path)
        self.assertEqual(result[0][0], 0)
        self.assertLess(result[0][1], 50)
        self.assertIn('keterangan induk setelah koma', result[0][3])

    def test_comma_qualifier_does_not_guess_or_ignore_conflict(self):
        from regional_matching import name_with_validated_parent as extract
        parent = ('Sumatra Selatan', 'Kab. Ogan Komering Ulu Selatan')
        self.assertIsNone(extract('Buay Pemaca, Ogan Komering Ulu Selatan', 2, None))
        self.assertIsNone(extract('Buay Pemaca, Kabupaten Lain', 2, parent))
        self.assertIsNone(extract('Buay Pemaca, Kota Ogan Komering Ulu Selatan', 2, parent))
        self.assertIsNone(extract('Buay Pemaca,', 2, parent))
        self.assertIsNone(extract('Buay Pemaca, Ogan Komering Ulu Selatan, Banten', 2, parent))
        self.assertIsNone(extract('Buay Pemaca Ogan Komering Ulu Selatan', 2, parent))
        self.assertEqual(extract('Buay Pemaca, Kab. Ogan Komering Ulu Selatan, Sumatra Selatan', 2, parent), 'Buay Pemaca')

    def test_comma_qualifiers_across_levels(self):
        from regional_matching import name_with_validated_parent as extract
        self.assertEqual(extract('Kab. Bekasi, Jawa Barat', 1, ('Jawa Barat',)), 'Kab. Bekasi')
        parent = ('Jawa Timur', 'Kab. Tuban', 'Tuban')
        self.assertEqual(extract('Kingking, Kec. Tuban, Kabupaten Tuban, Jawa Timur', 3, parent), 'Kingking')
        self.assertIsNone(extract('Kingking, Kabupaten Tuban, Kec. Tuban', 3, parent))
        path = parent + ('Kingking',)
        result = ranked_candidates(3, 'Kingking, Kecamatan Tuban', parent, [path])
        self.assertEqual(result[0][0], 0)
        # A conflicting qualifier may still produce a fuzzy suggestion, never an exact one.
        result = ranked_candidates(3, 'Kingking, Kecamatan Lain', parent, [path])
        self.assertFalse(any(r[0] == 0 for r in result))

    def test_unknown_province_unique_child_city_only(self):
        paths=[('Jawa Barat','Kota Bogor','Bogor Timur')]
        result=city_context_candidates('Bogor Timur',None,paths)
        self.assertEqual(result[0][0],('Jawa Barat','Kota Bogor'))
        self.assertIn('Provinsi pada data sumber belum diketahui',result[0][1])
        self.assertEqual(city_context_candidates('Bogor Timur',None,paths+[('Provinsi Lain','Kota Lain','Bogor Timur')]),[])
        self.assertEqual(city_context_candidates('Bogor',None,paths),[])

    def test_exact_district_in_another_city_same_province(self):
        from regional_matching import district_other_city_candidates
        path=('Jawa Barat','Kota Bogor','Bogor Barat')
        parent=('Jawa Barat','Kab. Bogor')
        result=district_other_city_candidates('Bogor Barat',parent,[path])
        self.assertEqual(result[0][0],path)
        self.assertIn('Kab. Bogor',result[0][1]);self.assertIn('Kota Bogor',result[0][1])
        self.assertEqual(district_other_city_candidates('Bogor',parent,[path]),[])
        self.assertEqual(district_other_city_candidates('Bogor Barat',None,[path]),[])
        self.assertEqual(district_other_city_candidates('Bogor Barat',('Banten','Kab. Bogor'),[path]),[])
        # Do not propose other cities if an exact district already exists under the source parent.
        self.assertEqual(district_other_city_candidates('Bogor Barat',parent,[path,parent+('Bogor Barat',)]),[])
        result=district_other_city_candidates('Bogor Barat',parent,[path,('Jawa Barat','Kota Lain','Bogor Barat')])
        self.assertEqual(len(result),2)
        self.assertTrue(all('beberapa kabupaten/kota' in reason for _,reason in result))


if __name__ == '__main__':
    unittest.main()
