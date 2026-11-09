"""Independently validate the row-per-relationship presentation against its backup."""
import argparse
from collections import Counter,defaultdict
import csv,json,re,sys
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_relation_rows import HEADERS,TITLE,PRIMARY,CITY_PARENT,DIRECT
from check_valid_region_reclassification import Archive,NS,TAG


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def check(before,after,pipeline):
    groups=defaultdict(list)
    for c in csv_rows(pipeline/'03_Manual_Review'/'Review_candidates.csv'):
        if c['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':groups[c['Id_Sumber']].append(c)
    masters={r['Hierarki_Master'] for r in csv_rows(pipeline/'04_Master_Targets'/'Master_target_inventory.csv')}
    names={r['Id_Sumber']:r['Nama_Sumber'] for r in csv_rows(pipeline/'05_All_Records'/'KotaKabupaten_all_records.csv')}
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist() and bz.testzip() is None
        changed={n for n in az.namelist() if az.read(n)!=bz.read(n)}
        assert changed=={'xl/workbook.xml',*[f'xl/worksheets/sheet{i}.xml' for i in [1,2,3,16]]}
        a,b=Archive(az),Archive(bz)
        old={v[1]:v for v,_ in a.rows(16) if v[0]!='Objek'}
        expected_keys=set()
        for rid,v in old.items():
            if not v[7] or v[4]!=v[7] or v[19]:expected_keys.add((rid,PRIMARY if v[0]=='Kelurahan' else CITY_PARENT))
            if v[0]=='Kelurahan' and (not v[11] or v[9]!=v[11] or v[20]):expected_keys.add((rid,DIRECT))
            if all((rid,k) not in expected_keys for k in [PRIMARY,CITY_PARENT,DIRECT]):
                expected_keys.add((rid,PRIMARY if v[0]=='Kelurahan' else CITY_PARENT))
        rows=b.rows(16);assert next(rows)[0]==tuple(HEADERS)
        seen=set();id_counts=Counter();kinds=Counter();paths_by_id={};old_index={rid:i for i,rid in enumerate(old)};previous=-1
        for v,_ in rows:
            assert len(v)==19
            rid,kind=v[1],v[3];assert rid in old and (rid,kind) in expected_keys and (rid,kind) not in seen
            assert old_index[rid]>=previous;previous=old_index[rid]
            seen.add((rid,kind));id_counts[rid]+=1;kinds[kind]+=1;p=old[rid]
            assert v[:3]==p[:3] and v[13]==p[17]
            if v[7]:
                expected_status=('ID relasi tersedia; nama data perlu dikonfirmasi' if 'nama' in p[15].casefold()
                                 else 'ID relasi tersedia; menunggu konfirmasi Tim Daikin')
            elif p[15].casefold().startswith('lokasi'):expected_status='Lokasi dan ID relasi masih perlu dikonfirmasi'
            elif 'nama' in p[15].casefold():expected_status='ID relasi dan nama data masih perlu dikonfirmasi'
            else:expected_status='ID relasi masih perlu dikonfirmasi'
            assert v[11]==expected_status
            direct=kind==DIRECT
            assert v[4]==p[9 if direct else 4] and v[6]==p[10 if direct else 6]
            assert v[7:9]==(p[11],p[12]) if direct else v[7:9]==(p[7],p[8])
            assert v[5]==(names.get(p[9]) if direct else p[5])
            assert v[14:]==(p[18],p[20] if direct else p[19],p[21],p[22],p[23])
            assert p[16] in v[12]
            if not v[7]:assert v[10].startswith('Konfirmasi ID relasi dan lokasi')
            if 'Konfirmasi nama data' in (p[14] or ''):assert 'konfirmasi nama data' in v[10]
            choices=list(dict.fromkeys(c['Hierarki_Kandidat'] for c in groups[rid]))
            assert p[13] in choices and all(path in masters for path in choices)
            choices=[p[13]]+[path for path in choices if path!=p[13]]
            wanted=choices[0] if len(choices)==1 else 'Lokasi masih perlu dikonfirmasi. Pilihan pada master:\n'+'\n'.join('• '+path for path in choices)
            assert v[9]==wanted
            paths_by_id[rid]=choices
            if len(choices)>1:assert v[7] is None,'Ambiguous locations must not receive a Parent ID'
        assert seen==expected_keys and set(id_counts)==set(old)
        assert len(old)==9000 and len(seen)==12570
        assert all(n in {1,2} for n in id_counts.values())
        # No record is added to a different review group. All unchanged worksheets
        # are byte-identical; count their source IDs to check global uniqueness.
        global_ids=Counter({rid:1 for rid in id_counts})
        for index in [4,5,6,7,8,9,10,13,14]:
            with bz.open(f'xl/worksheets/sheet{index}.xml') as f:
                for _,r in E.iterparse(f,events=('end',),tag=TAG+'row'):
                    if r.get('r')!='1':
                        c=next(c for c in r if c.get('r')=='B'+r.get('r'));global_ids[b.value(c)]+=1
                    r.clear()
                    while r.getprevious() is not None:del r.getparent()[0]
        assert len(global_ids)==91306 and all(n==1 for n in global_ids.values())
        av=[v for v,_ in a.rows(2)];bv=[v for v,_ in b.rows(2)]
        assert av[1:]==bv[1:] and av[0][:-1]==bv[0][:-1]
        assert bv[0][-1]=='Perbaikan Parent ID Tetap (ID Unik)'
        assert sum(v[-1] for v in bv[1:])==len(old)
        aw,bw=E.fromstring(az.read('xl/workbook.xml')),E.fromstring(bz.read('xl/workbook.xml'))
        for x,y in zip(aw.findall('m:definedNames/m:definedName',NS),bw.findall('m:definedNames/m:definedName',NS),strict=True):
            if x.get('localSheetId')=='12' and x.get('name')=='_xlnm._FilterDatabase':
                assert y.text==f"'{TITLE}'!$A$1:$S$12571";y.text=x.text
        assert E.tostring(aw)==E.tostring(bw),'Sheet order or unrelated workbook metadata changed'
        meta=b.metadata(16)
        for key in ['dimension','autoFilter']:assert meta.find('m:'+key,NS).get('ref')=='A1:S12571'
        dv=meta.find('m:dataValidations/m:dataValidation',NS)
        assert dv.get('sqref')=='O2:O12571'
        assert dv.findtext('m:formula1',namespaces=NS)=='"SETUJU_UBAH,TOLAK_PERUBAHAN,PERLU_DISKUSI"'
        styles=E.fromstring(bz.read('xl/styles.xml')).find('m:cellXfs',NS)
        for col in meta.findall('m:cols/m:col',NS):
            assert styles[int(col.get('style'))].find('m:alignment',NS).get('wrapText')=='1'
        assert az.read('xl/styles.xml')==bz.read('xl/styles.xml')
        assert az.read('xl/sharedStrings.xml')==bz.read('xl/sharedStrings.xml')
        for entry in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):assert not re.search(rb'<f(?:\s|>)',bz.read(entry))
        assert len(paths_by_id['a1nfC00000VF9uNQAT'])==1
        assert set(paths_by_id['a1nfC00000VF9uNQAT'])=={'Sumatra Utara | Kab. Humbang Hasundutan | Dolok Sanggul | Hutagurgur (Huta Gurgur)'}
        assert id_counts['a1nfC00000VF9uNQAT']==2
        report={'unique_parent_data':len(old),'relationship_rows':len(seen),'rows_by_relationship':dict(kinds),
                'two_relationship_ids':sum(n==2 for n in id_counts.values()),'global_unique_source_ids':len(global_ids),
                'multiple_master_location_ids':sum(len(p)>1 for p in paths_by_id.values()),'changed_parts':sorted(changed)}
    wb=openpyxl.load_workbook(after,read_only=True)
    assert len(wb.sheetnames)==15 and wb[TITLE].max_column==19 and wb[TITLE].max_row==12571
    assert wb['DATA BELUM JELAS'].max_row==17129;wb.close()
    print(json.dumps(report,ensure_ascii=False,indent=2));print('PASS: ID sets, relationship proposals, master paths, source names, review inputs, dropdowns, unchanged sheets and formulas.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['before','after','pipeline']:parser.add_argument(arg,type=Path)
    args=parser.parse_args();check(args.before,args.after,args.pipeline)
