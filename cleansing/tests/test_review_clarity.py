import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_matching import ranked_candidates,parenthesized_name_core,province_name_forms
from regional_client_display import clarify_no_exact_rows,NO_EXACT_WITH_CANDIDATES,client_candidate
from daikin_relation_rows import relationship_status


class ReviewClarityTests(unittest.TestCase):
    def test_aceh_province_alias_blocks_unrelated_counties(self):
        parent=('Aceh (NAD)',);paths=[parent+(n,) for n in ['Kab. Aceh Jaya','Kab. Aceh Barat','Kab. Aceh Besar']]
        self.assertEqual(ranked_candidates(1,'Aceh',parent,paths,[parent]),[])
        self.assertIn('nad',province_name_forms('Aceh (NAD)'))

    def test_province_alias_retains_a_real_city_core_match(self):
        parent=('Aceh (NAD)',);path=parent+('Kota Aceh',)
        self.assertEqual(ranked_candidates(1,'Aceh',parent,[path],[parent])[0][0],2)

    def test_kulisusu_prefers_base_name_without_selecting_barat_or_utara(self):
        parent=('Sulawesi Tenggara','Kab. Buton Utara');paths=[parent+(n,) for n in ['Kulisusu','Kulisusu Barat','Kulisusu Utara']]
        out=ranked_candidates(2,'Kulisusu (Kalingsusu/Kalisusu)',parent,paths)
        self.assertEqual([r[2] for r in out],[paths[0]])
        self.assertIn('alias dalam tanda kurung',out[0][3])

    def test_parenthesized_location_or_direction_is_not_discarded(self):
        for text in ['Kulisusu (Barat)','Belimbing (Melawi)','Martapura (Kalimantan Selatan)',
                     'Misool (Misool Utara)','Misool (MisoolUtara)','Rumbai (Rumbai Pesisir)',
                     'Labuan (Labuan Induk)','Labuan (LabuanInduk)','X (Y)','A (B (C))']:
            self.assertIsNone(parenthesized_name_core(text,2))

    def test_parent_required_and_exact_full_name_takes_precedence(self):
        parent=('P','C');name='Hutagurgur (Huta Gurgur)';paths=[parent+('Hutagurgur',),parent+(name,)]
        out=ranked_candidates(2,name,parent,paths)
        self.assertEqual(out[0][2],paths[1])
        self.assertFalse(ranked_candidates(2,name,None,[paths[0]]))

    def test_different_parent_and_ambiguous_base_are_not_promoted(self):
        parent=('P','C');out=ranked_candidates(2,'Kulisusu (Kalisusu)',parent,[('P','Other','Kulisusu')])
        self.assertEqual(out,[])
        out=ranked_candidates(2,'Kulisusu (Kalisusu)',parent,[parent+('Kulisusu',),parent+('KULISUSU',)])
        self.assertFalse(any(r[0]==0 for r in out))

    def test_no_exact_message_is_source_specific_and_idempotent(self):
        candidate=['Kecamatan','id','Nama',1,'Usulan','P | C | Usulan','target','ID sesuai lokasi','note','Master','Kecamatan',None]
        nohit=['Kecamatan','id','Nama',2,None,None,None,'Nama belum ditemukan','old','Master dan ekspor Salesforce',None,0]
        unrelated=list(nohit);unrelated[1]='other'
        original=[candidate,nohit,unrelated];out=clarify_no_exact_rows(original)
        self.assertEqual(tuple(out[1][7:9]),NO_EXACT_WITH_CANDIDATES)
        self.assertEqual(out[2][7],'Nama belum ditemukan');self.assertEqual(original[1][7],'Nama belum ditemukan')
        self.assertEqual(clarify_no_exact_rows(out),out)

    def test_cross_level_only_does_not_imply_same_level_candidate(self):
        rows=[['Kecamatan','id','Nama',1,'Nama','P | C | D | Nama',None,'Nama ditemukan di tingkat lain','note'],
              ['Kecamatan','id','Nama',2,None,None,None,'Nama belum ditemukan','old']]
        self.assertEqual(clarify_no_exact_rows(rows)[1][7],'Nama belum ditemukan')

    def test_relationship_status_is_local_and_never_approves(self):
        s=relationship_status('city-id','Parent masih perlu dikonfirmasi')
        self.assertEqual(s,'ID relasi tersedia; menunggu konfirmasi Tim Daikin')
        self.assertEqual(relationship_status(None,'Parent masih perlu dikonfirmasi'),'ID relasi masih perlu dikonfirmasi')
        self.assertEqual(relationship_status(None,'Lokasi dan Parent masih perlu dikonfirmasi'),'Lokasi dan ID relasi masih perlu dikonfirmasi')
        self.assertEqual(relationship_status('id','Nama masih perlu dikonfirmasi'),'ID relasi tersedia; nama data perlu dikonfirmasi')
        self.assertEqual(relationship_status('id',s),s)

    def test_missing_id_keeps_alias_explanation_and_id_warning(self):
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'BELUM_ADA_ID_TERVERIFIKASI',
           'Id_Target_Kandidat':'','ID_Master_Perlu_Verifikasi':'','Id_Sumber':'source',
           'Nama_Kandidat':'Nama','Hierarki_Kandidat':'P | C | Nama',
           'Alasan':'Nama sebelum tanda kurung sama dengan master; alias dalam tanda kurung adalah variasi ejaan.',
           'Penjelasan_ID_Client':'Alasan ID belum dipastikan: perlu penelusuran.'}
        v=client_candidate(d)
        self.assertEqual(v[2],'');self.assertIn('tanda kurung',v[4]);self.assertIn('Alasan ID belum dipastikan',v[4])


if __name__=='__main__':unittest.main()
