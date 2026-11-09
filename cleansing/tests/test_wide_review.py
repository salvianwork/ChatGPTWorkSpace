import sys,unittest,copy
from pathlib import Path
from lxml import etree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_location_text import LocationTextIndex,TEXT_REASON
from kelurahan_wide import flatten,unflatten,COLS,format_sheet,HEADERS,section_note
from daikin_review_readability import NS,TAG
from regional_client_display import client_candidate


class WideReviewTests(unittest.TestCase):
    def record(self,kind='Parent Kecamatan',**changes):
        v=['Kelurahan','a1nJ4000000Kcc4IAC','Taman Sari',kind,'a1pJ40000008XLNIA2','Ketapang',
           'Lampung | Kab. Lampung Selatan | Ketapang',None,None,
           'Lampung | Kab. Lampung Selatan | Ketapang | Taman Sari','Lokasi dan ID usulan perlu dikonfirmasi',
           'Konfirmasikan Taman Sari atau Karang Sari; jangan memilih ID sebelum lokasi diketahui.',None,None,None,None,None,None,None]
        for index,value in changes.items():v[int(index)]=value
        return v

    def test_each_approved_change_and_author_remain_independent(self):
        kec=self.record(**{'13':'Gunakan nilai final','14':'a1pJ40000008XLNIA2','17':'PIC A','18':46000})
        kota=self.record('Kabupaten/Kota Langsung',**{'4':'a1oJ40000009JM1IAM','5':'Kab. Tanggamus','13':'Perlu diskusi','16':'Tunggu lokasi','17':'PIC B','18':46001})
        out=flatten([kec,kota]);recovered={v[3]:v for v in unflatten(out)}
        self.assertEqual(len(out),43)
        for old in [kec,kota]:self.assertEqual(recovered[old[3]],old)
        self.assertNotEqual(COLS['Parent Kecamatan'][13],COLS['Kabupaten/Kota Langsung'][13])
        for c in COLS['Nama'].values():self.assertIsNone(out[c-1])

    def test_master_locations_stay_associated_with_their_changes(self):
        a=self.record();b=self.record('Kabupaten/Kota Langsung',**{'9':'Lampung | Kab. Lampung Selatan | Ketapang | Karang Sari'})
        result=unflatten(flatten([a,b]));self.assertEqual([v[9] for v in result],[a[9],b[9]])

    def test_no_automatic_values_or_duplicate_sections(self):
        row=flatten([self.record()])
        self.assertIsNone(row[COLS['Parent Kecamatan'][7]-1])
        self.assertIsNone(row[COLS['Parent Kecamatan'][13]-1])
        with self.assertRaises(AssertionError):flatten([self.record(),self.record()])

    def test_name_source_is_shared_but_its_final_answer_is_separate(self):
        name=self.record('Nama',**{'4':'Taman Sari','5':None,'8':None,'7':'Karang Sari','14':'Taman Sari'})
        self.assertEqual(unflatten(flatten([name]))[0],name)

    def test_dropdowns_do_not_approve_unknown_parent_and_date_is_per_section(self):
        meta=E.Element(TAG+'worksheet',nsmap={None:NS['m']})
        E.SubElement(meta,TAG+'dimension',ref='A1:S2');views=E.SubElement(meta,TAG+'sheetViews');E.SubElement(views,TAG+'sheetView',workbookViewId='0')
        E.SubElement(meta,TAG+'cols');E.SubElement(meta,TAG+'sheetData');E.SubElement(meta,TAG+'autoFilter',ref='A1:S2')
        xml,rows=format_sheet(meta,[[self.record()]])
        root=E.fromstring(xml);dvs=root.findall('m:dataValidations/m:dataValidation',NS)
        choices=[n.findtext('m:formula1',namespaces=NS) for n in dvs if n.get('sqref')=='O2']
        self.assertTrue(choices);self.assertNotIn('Setujui usulan',choices[0])
        self.assertEqual(root.find("m:sheetData/m:row[@r='2']/m:c[@r='T2']",NS).get('s'),'18')
        self.assertEqual(root.find("m:sheetData/m:row[@r='2']/m:c[@r='AG2']",NS).get('s'),'6')
        self.assertEqual(root.find('m:dimension',NS).get('ref'),'A1:AQ2')


class TextLocationTests(unittest.TestCase):
    def setUp(self):
        self.path=('Jawa Barat','Kab. Bandung Barat','Lembang','Sukajaya')
        self.raw={'Combined__c':'Sukajaya,Lembang, Bandung Barat, Jawa Barat 40391','Kode_Pos__c':'40391',
                  'Kecamatan__c':'pinrang-id','Kota_Kabupaten__c':'garut-id'}
        self.index=LocationTextIndex([self.path,('Jawa Barat','Kab. Garut','Cisewu','Sukajaya')])

    def test_explicit_master_path_is_found_despite_lookup_conflict_without_mutation(self):
        before=copy.deepcopy(self.raw);hits=self.index.candidates('Sukajaya',self.raw)
        self.assertEqual(hits[0][0],self.path);self.assertTrue(hits[0][1].startswith(TEXT_REASON))
        self.assertIn('tidak ditetapkan otomatis',hits[0][1]);self.assertEqual(before,self.raw)

    def test_full_hierarchy_and_postal_consistency_are_required(self):
        for text in ['Sukajaya,Lembang','Sukajaya,Lembang, Bandung Barat, Sulawesi Selatan 40391',
                     'Sukajaya,Cisewu, Bandung Barat, Jawa Barat 40391','Sukajaya,Lembang, Kota Bandung Barat, Jawa Barat 40391',
                     'Lainnya,Lembang, Bandung Barat, Jawa Barat 40391']:
            self.assertFalse(self.index.candidates('Sukajaya',dict(self.raw,Combined__c=text)))
        self.assertFalse(self.index.candidates('Sukajaya',dict(self.raw,Kode_Pos__c='91254')))

    def test_ambiguous_city_type_is_not_guessed(self):
        other=('Jawa Barat','Kota Bandung Barat','Lembang','Sukajaya')
        self.assertEqual(LocationTextIndex([self.path,other]).candidates('Sukajaya',self.raw),[])

    def test_a_path_absent_from_master_is_not_created(self):
        raw=dict(self.raw,Combined__c='Sukajaya,Lembang, Pinrang, Sulawesi Selatan 91254',Kode_Pos__c='91254')
        self.assertEqual(self.index.candidates('Sukajaya',raw),[])

    def test_visible_status_retains_location_confirmation_even_when_id_exists(self):
        reason=self.index.candidates('Sukajaya',self.raw)[0][1]
        d={'Jenis_Bukti':'KANDIDAT_OBJEK_SAMA','Status_Verifikasi_ID':'ID_TERVERIFIKASI','Id_Target_Kandidat':'target',
           'ID_Master_Perlu_Verifikasi':'','Nama_Kandidat':'Sukajaya','Hierarki_Kandidat':' | '.join(self.path),
           'Id_Sumber':'source','Alasan':reason}
        result=client_candidate(d)
        self.assertEqual(result[2],'target');self.assertEqual(result[3],'Lokasi dari teks; perlu konfirmasi')
        self.assertIn(self.raw['Combined__c'],result[4])


if __name__=='__main__':unittest.main()
