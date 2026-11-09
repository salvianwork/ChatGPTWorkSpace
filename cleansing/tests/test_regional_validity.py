import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_validity import valid_region_pending_primary


class RegionValidityTests(unittest.TestCase):
    def setUp(self):
        self.path=('Sumatra Selatan','Kab. Empat Lawang','Pasemah Air Keruh','Lawang Agung')
        self.ids=[{}, {self.path[:2]:'city'}, {self.path[:3]:'district'}, {}]
        self.row={'_path':self.path,'Source_Name':'Lawang Agung','Status':'MAPPED_TARGET_UNRESOLVED',
                  'Match_Method':'EXACT_HIERARCHY','_blocked':False,'_requires_review':False,
                  'Source_Parent_Id':'district','Source_Direct_City_Id':'city'}

    def test_clean_record_is_valid_region_without_approving_primary(self):
        before=copy.deepcopy((self.row,self.ids))
        self.assertTrue(valid_region_pending_primary(self.row,self.ids))
        self.assertEqual((self.row,self.ids),before)
        self.assertEqual(self.row['Status'],'MAPPED_TARGET_UNRESOLVED')

    def test_missing_recovered_or_wrong_relationship_stays_in_review(self):
        for edits in [{'Source_Parent_Id':''},{'Source_Parent_Id':'wrong'},{'Source_Direct_City_Id':''},
                      {'Source_Direct_City_Id':'wrong'},{'_blocked':True},{'_requires_review':True}]:
            self.assertFalse(valid_region_pending_primary(dict(self.row,**edits),self.ids),edits)

    def test_name_correction_or_unmatched_location_stays_in_review(self):
        for edits in [{'Source_Name':'LAWANG AGUNG'},{'Match_Method':'NORMALIZED_HIERARCHY'},
                      {'_path':None},{'Status':'MAPPED_DUPLICATE'},{'Status':'VALID_CANONICAL'}]:
            self.assertFalse(valid_region_pending_primary(dict(self.row,**edits),self.ids),edits)

    def test_unverified_parent_never_promotes_child(self):
        self.ids[2]={}
        self.assertFalse(valid_region_pending_primary(self.row,self.ids))


if __name__=='__main__':unittest.main()
