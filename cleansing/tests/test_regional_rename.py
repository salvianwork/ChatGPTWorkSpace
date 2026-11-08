import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_rename import qualified_rename_matches,qualified_rename_groups
from regional_review import candidate_id_review
from regional_matching import ranked_candidates


class QualifiedRenameTests(unittest.TestCase):
    def setUp(self):
        self.path=('Sumatra Selatan','Kab. Muara Enim','Belimbing')
        self.targets=[{}, {self.path[:2]:'city-id'}, {}, {}]
        self.source={'Source_Id':'source-id','Source_Name':'Belimbing, Muara Enim',
                     'Source_Parent_Id':'city-id','_parent':self.path[:-1],
                     '_path':None,'_blocked':False,'_requires_review':False}

    def review(self,**kwargs):
        return candidate_id_review(self.source,self.path,kwargs.pop('inventory',{'Target_Id':'','Master_Sheet_Id':''}),
                                   {},[],qualified_records=kwargs.pop('qualified',[self.source]),
                                   target_ids=self.targets,**kwargs)

    def test_belimbing_proposes_same_id_and_name_only_without_mutating_source(self):
        before=copy.deepcopy(self.source);out=self.review()
        self.assertEqual(out['Candidate_Target_Id'],'source-id')
        self.assertEqual(out['Review_Kind'],'KOREKSI_RECORD_YANG_SAMA')
        self.assertEqual(out['ID_Verification'],'ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW')
        self.assertIn('cukup sesuaikan nama',out['ID_Explanation'])
        self.assertEqual(before,self.source)

    def test_wrong_or_unresolved_actual_parent_id_is_rejected(self):
        for pid in ['',None,'wrong-city']:
            self.source['Source_Parent_Id']=pid
            self.assertFalse(qualified_rename_matches(self.source,self.path,self.targets))
            self.assertEqual(self.review()['Candidate_Target_Id'],'')

    def test_qualifier_cannot_override_location(self):
        for name in ['Belimbing, Melawi','Belimbing, Kota Muara Enim','Belimbing,','Belimbing','Belimbingan, Muara Enim']:
            self.source['Source_Name']=name
            self.assertFalse(qualified_rename_matches(self.source,self.path,self.targets))

    def test_recovered_or_conflicting_parent_is_not_promoted(self):
        for flag in ['_blocked','_requires_review']:
            source=dict(self.source);source[flag]=True
            self.assertFalse(qualified_rename_matches(source,self.path,self.targets))

    def test_missing_target_parent_does_not_guess(self):
        self.targets[1].clear()
        self.assertFalse(qualified_rename_matches(self.source,self.path,self.targets))

    def test_multiple_qualified_records_do_not_select_primary(self):
        other=dict(self.source,Source_Id='second')
        self.assertEqual(self.review(qualified=[self.source,other])['Candidate_Target_Id'],'')

    def test_existing_or_conflicting_master_id_is_preserved(self):
        self.assertEqual(self.review(inventory={'Target_Id':'existing','Master_Sheet_Id':'existing'})['Candidate_Target_Id'],'existing')
        self.assertEqual(self.review(inventory={'Target_Id':'','Master_Sheet_Id':'conflict'})['Candidate_Target_Id'],'')

    def test_kelurahan_requires_both_parent_relationships(self):
        path=self.path+('Desa A',);source=dict(self.source,Source_Name='Desa A, Belimbing, Muara Enim',
                                             _parent=self.path,Source_Parent_Id='kec-id',Source_Direct_City_Id='city-id')
        self.targets[2][self.path]='kec-id'
        self.assertTrue(qualified_rename_matches(source,path,self.targets))
        source['Source_Direct_City_Id']='wrong-city'
        self.assertFalse(qualified_rename_matches(source,path,self.targets))

    def test_master_path_must_be_unique_after_normalization(self):
        records=[[],[],[self.source],[]];masters=[set(),set(),{self.path},set()]
        self.assertEqual(qualified_rename_groups(records,masters,self.targets)[2][self.path],[self.source])
        masters[2].add(self.path[:-1]+('BELIMBING',))
        self.assertFalse(qualified_rename_groups(records,masters,self.targets)[2])

    def test_exact_qualified_location_suppresses_unrelated_fuzzy_suggestions(self):
        other=self.path[:-1]+('Muara Enim',)
        result=ranked_candidates(2,self.source['Source_Name'],self.path[:-1],[self.path,other])
        self.assertEqual([r[2] for r in result],[self.path])


if __name__=='__main__':unittest.main()
