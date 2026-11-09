import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_matching import ranked_candidates,unique_identity_paths,name_identity_kind
from regional_review_context import legacy_parent_context,one_edit_typo,city_alias_candidates
from daikin_identity_review import Context
from collections import defaultdict


class IdentityReviewTests(unittest.TestCase):
    def test_master_parentheses_beat_unrelated_fuzzy_name(self):
        parent=('Sulawesi Selatan','Kab. Takalar','Galesong Utara')
        correct=parent+('Bontolanra (Bonto Lanra)',)
        out=ranked_candidates(3,'Bontolanra',parent,[parent+('Bontolebang',),correct,parent+('Bontokaddopepe',)])
        self.assertEqual([r[2] for r in out],[correct]);self.assertEqual(out[0][0],0)
        self.assertEqual(name_identity_kind('Bonto Lanra',correct[-1],3,parent),'spelling_alias')

    def test_two_sided_spelling_and_full_name_precedence(self):
        parent=('P','C','D');path=parent+('Pajar Indah (Fajar Indah)',)
        self.assertEqual(ranked_candidates(3,'Pajar Indah',parent,[path])[0][2],path)
        self.assertEqual(ranked_candidates(3,'Fajar Indah',parent,[path])[0][2],path)
        literal=parent+('Pajar Indah',)
        self.assertEqual(unique_identity_paths(3,'Pajar Indah',parent,[path,literal]),{literal:'exact'})

    def test_ambiguity_and_geographic_parentheses_do_not_become_aliases(self):
        parent=('P','C')
        paths=[parent+('Kulisusu (Kalisusu)',),parent+('Kulisusu (Kalingsusu)',)]
        self.assertEqual(unique_identity_paths(2,'Kulisusu',parent,paths),{})
        for target in ['Misool (Misool Utara)','Labuan (Labuan Induk)']:
            self.assertIsNone(name_identity_kind(target.split(' (')[0],target,2,parent))
        self.assertEqual(unique_identity_paths(2,'Gunung Megang',None,[('P','C','Gunung Megang')]),{})

    def test_parent_legacy_comma_matches_only_its_actual_city(self):
        city=('Sumatra Selatan','Kab. Muara Enim');path=city+('Gunung Megang',)
        raw={'Kecamatan__c':'','Kecamatans__c':'legacy-id'}
        districts={'legacy-id':{'Source_Name':'Gunung Megang, Muara Enim','Source_Parent_Id':'city-id','_blocked':False}}
        cities={'city-id':{'_path':city,'_blocked':False}}
        out=legacy_parent_context(raw,city,districts,cities,[path]);self.assertEqual(out[0],path)
        self.assertEqual(raw['Kecamatan__c'],'')
        self.assertIsNone(legacy_parent_context(raw,('P','Other'),districts,cities,[path]))
        districts['legacy-id']['Source_Name']='Gunung Megang, Lahat'
        self.assertIsNone(legacy_parent_context(raw,city,districts,cities,[path]))

    def test_existing_primary_parent_is_not_overridden_and_ambiguous_parent_is_not_chosen(self):
        city=('P','C');raw={'Kecamatan__c':'already-linked','Kecamatans__c':'D'}
        self.assertIsNone(legacy_parent_context(raw,city,{}, {},[city+('D',)]))
        raw['Kecamatan__c']='';self.assertIsNone(legacy_parent_context(raw,city,{}, {},[city+('D',),city+('d',)]))
        raw['Kecamatans__c']='a1pJ40000008XCMIA2'
        self.assertIsNone(legacy_parent_context(raw,city,{}, {},[city+('D',)]))

    def test_city_only_evidence_stays_within_city(self):
        city=('P','C');a=city+('D','Pajar Indah (Fajar Indah)');b=('P','Other','D','Pajar Indah (Fajar Indah)')
        out=city_alias_candidates('Pajar Indah',city,[a,b]);self.assertEqual([p for p,note in out],[a])
        self.assertIn('kecamatan sumber belum diketahui',out[0][1])

    def test_typo_is_narrow_and_preserves_direction_numbers_and_level(self):
        self.assertTrue(one_edit_typo('Lantara Jaya','Lantari Jaya',2))
        self.assertFalse(one_edit_typo('Bontolanra','Bontolebang',3))
        self.assertFalse(one_edit_typo('Sei Kera Hilir I','Sei Kera Hilir II',3))
        self.assertFalse(one_edit_typo('Tanjung Utara','Tanjung Utaro',2))
        self.assertFalse(one_edit_typo('Desa 1','Desa 2',3))
        self.assertFalse(one_edit_typo('Banjar','Banjaran',2))
        self.assertFalse(one_edit_typo('Lantara Jaya','Lantari Jaya',1))
        self.assertFalse(one_edit_typo('Tanjungbarat','Tanjungbaras',3))
        self.assertFalse(one_edit_typo('Sidomulyo','Sidomulyoi',3))

    def test_exact_name_in_same_city_blocks_typo_under_other_district(self):
        ctx=Context.__new__(Context);ctx.children=[defaultdict(list) for _ in range(4)]
        parent=('P','C','Wrong district');near=parent+('Lantari Jaya',)
        exact=('P','C','Other district','Lantara Jaya')
        ctx.children[3][parent]=[near];ctx.city_children={('P','C'):[near,exact]}
        self.assertEqual(ctx.strong(3,{'Source_Name':'Lantara Jaya'},parent),{})

    def test_ambiguous_typo_never_becomes_duplicate_proposal(self):
        ctx=Context.__new__(Context);ctx.children=[defaultdict(list) for _ in range(4)]
        parent=('P','C');ctx.children[2][parent]=[parent+('Lantari Jaya',),parent+('Lantaro Jaya',)]
        self.assertEqual(ctx.strong(2,{'Source_Name':'Lantara Jaya'},parent),{})

if __name__=='__main__':unittest.main()
