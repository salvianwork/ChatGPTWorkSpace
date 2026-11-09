import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from merge_daikin_changes import wide_changes,parent_change,name_confirmation,master_paths,needs_location,can_accept


class MergeChangesTests(unittest.TestCase):
    def wide(self):
        return ['Kelurahan','source','Old Name','New Name','Old District','old-kec','New District','new-kec',
                'old-city','new-city','Province | City | New District | New Name','Nama dan Wilayah Parent dan Kota/Kabupaten langsung',
                'Specific reason','Setujui usulan','Final Name','final-kec','final-city','Review note','PIC',46000]

    def parent(self):
        return ['Kelurahan','source','Old Name','Parent Kecamatan','old-kec','District','Inferred context',
                None,'District','Province | City | District | New Name','Konfirmasi ID relasi dan lokasi',
                'ID relasi masih perlu dikonfirmasi','ID belum tersedia. Nama data juga perlu dikonfirmasi.',
                'Cross-level evidence','Gunakan ID final','confirmed-kec','Notes','PIC',46000]

    def test_combined_update_splits_into_three_fields_without_changing_data_id(self):
        rows=wide_changes(self.wide(),{'old-city':'Old City'},{'old-kec':'P | C | D','old-city':'P | C'})
        self.assertEqual([r[3] for r in rows],['Nama','Parent Kecamatan','Kabupaten/Kota Langsung'])
        self.assertEqual([r[4] for r in rows],['Old Name','old-kec','old-city'])
        self.assertEqual([r[7] for r in rows],['New Name','new-kec','new-city'])
        self.assertEqual([r[14] for r in rows],['Final Name','final-kec','final-city'])
        self.assertTrue(all(r[1]=='source' and r[13]=='Setujui usulan' and r[16:]==['Review note','PIC',46000] for r in rows))
        self.assertEqual(rows[2][5],'Old City')

    def test_unchanged_fields_are_not_created_but_answered_fields_are_kept(self):
        v=self.wide();v[2]=v[3];v[5]=v[7];v[14]=v[15]=None
        self.assertEqual([r[3] for r in wide_changes(v)],['Kabupaten/Kota Langsung'])
        v[14]='User corrected name'
        self.assertEqual([r[3] for r in wide_changes(v)],['Nama','Kabupaten/Kota Langsung'])

    def test_blank_parent_proposal_stays_blank_and_answers_follow_the_relation(self):
        r=parent_change(self.parent())
        self.assertIsNone(r[7]);self.assertEqual(r[1],'source');self.assertEqual(r[14],'confirmed-kec')
        self.assertEqual(r[13],'Gunakan nilai final');self.assertEqual(r[16:],['Notes','PIC',46000])
        self.assertEqual(r[12],'Cross-level evidence');self.assertFalse(can_accept(r))

    def test_name_confirmation_does_not_inherit_a_parent_approval(self):
        p=self.parent();p[14]='Setujui usulan'
        r=name_confirmation([p]);self.assertEqual(r[3],'Nama');self.assertEqual(r[7],'New Name')
        self.assertEqual(r[4],'Old Name');self.assertTrue(all(v is None for v in r[13:]))
        self.assertTrue(can_accept(r));self.assertEqual(r[1],p[1])

    def test_multiple_master_names_are_not_chosen_automatically(self):
        p=self.parent();other=p.copy();other[9]='Province | Other City | Other District | Another Name'
        r=name_confirmation([p,other]);self.assertIsNone(r[7]);self.assertTrue(needs_location(r));self.assertFalse(can_accept(r))
        self.assertEqual(master_paths(r[9]),[p[9],other[9]])

    def test_exact_current_name_does_not_get_an_extra_rename(self):
        p=self.parent();p[2]='New Name';self.assertIsNone(name_confirmation([p]))

    def test_one_name_at_multiple_locations_still_needs_location_confirmation(self):
        p=self.parent();other=p.copy();other[9]='Province | Other City | Other District | New Name'
        r=name_confirmation([p,other]);self.assertEqual(r[7],'New Name')
        self.assertTrue(needs_location(r));self.assertFalse(can_accept(r))

    def test_known_parent_id_does_not_approve_an_unresolved_location(self):
        p=self.parent();p[7]='candidate-kec';p[11]='Lokasi dan ID relasi masih perlu dikonfirmasi'
        r=parent_change(p);self.assertFalse(can_accept(r));self.assertTrue(needs_location(r))

if __name__=='__main__':unittest.main()
