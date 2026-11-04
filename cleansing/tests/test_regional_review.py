import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from regional_review import candidate_id_review, unknown_parent_city_candidates
from regional_matching import district_context_candidates


class RegionalReviewTests(unittest.TestCase):
    def source(self, rid='self', path=('P','C','D'), blocked=False, recovered=False):
        return {'Source_Id':rid,'Source_Name':path[-1], '_path':path,
                '_parent':path[:-1], '_blocked':blocked, '_requires_review':recovered}

    def inventory(self, tid='', master=''):
        return {'Target_Id':tid,'Master_Sheet_Id':master}

    def test_unknown_parent_alias_and_explicit_proposal(self):
        paths=[('DKI Jakarta','Kota Jakarta Barat'),('Jawa Barat','Kota Bogor')]
        self.assertEqual(unknown_parent_city_candidates('jakbar','',paths)[0][0],paths[0])
        self.assertEqual(unknown_parent_city_candidates('Bogor','Kota Bogor',paths)[0][0],paths[1])
        self.assertEqual(unknown_parent_city_candidates('jakbar','Kota Bogor',paths),[])
        self.assertEqual(unknown_parent_city_candidates('bog','',paths),[])

    def test_buntok_scoped_child_variation(self):
        path=('Kalimantan Tengah','Kab. Barito Selatan','Dusun Selatan','Buntok Kota')
        result=district_context_candidates('Buntok',path[:2],[path])
        self.assertEqual(result[0][0],path[:3])
        self.assertIn('Variasi nama anak',result[0][1])
        self.assertEqual(district_context_candidates('Buntok',('Kalimantan Tengah','Kab. Barito Utara'),[path]),[])
        self.assertEqual(district_context_candidates('Bun',path[:2],[path]),[])

    def test_verified_target_does_not_erase_source_conflict(self):
        src=self.source(blocked=True)
        out=candidate_id_review(src,src['_path'],self.inventory('other'),{},[])
        self.assertEqual(out['Candidate_Target_Id'],'other')
        self.assertIn('konflik',out['ID_Explanation'])

    def test_cintaasih_conflicting_master_stays_unverified(self):
        src=self.source(blocked=True);before=copy.deepcopy(src)
        out=candidate_id_review(src,src['_path'],self.inventory(master='self'),{'self':src},[src])
        self.assertEqual(out['Candidate_Target_Id'],'')
        self.assertEqual(out['Unverified_Master_ID'],'self')
        self.assertEqual(out['ID_Verification'],'KONFLIK_RELASI_ID_MASTER')
        self.assertEqual(out['Review_Kind'],'KOREKSI_RECORD_YANG_SAMA')
        self.assertEqual(src,before)

    def test_lohong_recovered_ancestor_needs_review(self):
        src=self.source(recovered=True)
        out=candidate_id_review(src,src['_path'],self.inventory(master='self'),{'self':src},[src])
        self.assertEqual(out['Candidate_Target_Id'],'')
        self.assertEqual(out['ID_Verification'],'INDUK_ID_MASTER_PERLU_KONFIRMASI')

    def test_muara_no_id_does_not_borrow_homonym(self):
        src=self.source(path=('Sumatra Utara','Kab. Tapanuli Utara','Hutanagodang'))
        intended=('Sumatra Utara','Kab. Tapanuli Utara','Muara')
        wrong=self.source('papua',('Papua Pegunungan','Kab. Lanny Jaya','Muara'))
        out=candidate_id_review(src,intended,self.inventory(),{'papua':wrong},[])
        self.assertEqual(out['Candidate_Target_Id'],'')
        self.assertEqual(out['Unverified_Master_ID'],'')
        self.assertEqual(out['ID_Verification'],'BELUM_ADA_ID_TERVERIFIKASI')

    def test_safe_alternative_is_only_review_candidate(self):
        src=self.source();good=self.source('good')
        inv=self.inventory(master='wrong');before=copy.deepcopy(inv)
        out=candidate_id_review(src,src['_path'],inv,{},[good])
        self.assertEqual(out['Candidate_Target_Id'],'good')
        self.assertEqual(out['ID_Verification'],'ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW')
        self.assertEqual(inv,before)
        alternative=candidate_id_review(src,src['_path'],self.inventory(master='self'),{'self':self.source(blocked=True)},[good])
        self.assertEqual(alternative['Review_Kind'],'KANDIDAT_RECORD_TUJUAN')
        self.assertEqual(candidate_id_review(src,src['_path'],self.inventory(),{},[good,self.source('other')])['Candidate_Target_Id'],'')

    def test_master_missing_or_different_path_is_not_verified(self):
        src=self.source();wrong=self.source('wrong',('P','Other','D'))
        for candidates in [{},{'wrong':wrong}]:
            out=candidate_id_review(src,src['_path'],self.inventory(master='wrong'),candidates,[])
            self.assertEqual(out['Candidate_Target_Id'],'')
            self.assertIn('MASTER',out['ID_Verification'])

    def test_different_city_can_suggest_correcting_source_id(self):
        source=self.source('bogor-west',('Jawa Barat','Kab. Bogor','Bogor Barat'))
        source['_path']=None
        source['_parent']=('Jawa Barat','Kab. Bogor')
        candidate=('Jawa Barat','Kota Bogor','Bogor Barat')
        before=copy.deepcopy(source)
        result=candidate_id_review(source,candidate,self.inventory(),{},[],
            'Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda: Jawa Barat | Kota Bogor | Bogor Barat')
        self.assertEqual(result['Candidate_Target_Id'],'')
        self.assertEqual(result['Unverified_Master_ID'],'bogor-west')
        self.assertEqual(result['Review_Kind'],'KOREKSI_RECORD_YANG_SAMA')
        self.assertEqual(result['ID_Verification'],'KOTA_SUMBER_PERLU_KONFIRMASI')
        self.assertEqual(source,before)
        wrong=candidate_id_review(source,('Banten','Kota Bogor','Bogor Barat'),self.inventory(),{},[],
            'Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda: test')
        self.assertEqual(wrong['Unverified_Master_ID'],'')


if __name__ == '__main__':
    unittest.main()
