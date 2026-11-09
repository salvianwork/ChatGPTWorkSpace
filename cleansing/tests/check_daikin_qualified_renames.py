"""Verify same-ID rename migration, removal of insert proposals and unchanged children."""
import argparse,csv,json,re,sys
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_valid_region_reclassification import Archive,NS


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def check(before,after,pipeline):
    chosen={r['Source_Id']:r for r in read_csv(pipeline/'03_Manual_Review/Review_candidates.csv')
            if r['ID_Explanation'].startswith('Nama sebelum koma sesuai master')}
    inventory={r['Master_Path']:r for r in read_csv(pipeline/'04_Master_Targets/Master_target_inventory.csv')}
    sources={r['Source_Id']:r for r in read_csv(pipeline/'05_All_Records/Kecamatan_all_records.csv')}
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist() and bz.testzip() is None
        changed={n for n in az.namelist() if az.read(n)!=bz.read(n)}
        allowed={f'xl/worksheets/sheet{i}.xml' for i in [2,9,11,14,15]}|{'xl/workbook.xml','xl/sharedStrings.xml'}
        assert changed<=allowed,changed-allowed
        a,b=Archive(az),Archive(bz);moved={};old_ids=Counter();new_ids=Counter()
        def remaining_data():
            for values,sig in a.rows(14):
                if values[0]=='Objek':yield values,sig;continue
                old_ids[values[1]]+=1
                if values[1] in chosen:
                    v=values+(None,)*(23-len(values));assert not any(v[16:]);moved[v[1]]=v
                else:yield values,sig
        for old,new in zip_longest(remaining_data(),b.rows(14)):
            assert old==new and old is not None,'Remaining data cell/style/order changed'
            if new[0][0]!='Objek':new_ids[new[0][1]]+=1
        assert set(moved)==set(chosen) and len(moved)==11
        rows=b.rows(9)
        for expected in a.rows(9):
            actual=next(rows);assert expected==actual,'Existing change proposal altered'
            if actual[0][0]!='Objek':old_ids[actual[0][1]]+=1;new_ids[actual[0][1]]+=1
        for rid,old in moved.items():
            v=next(rows)[0];source=sources[rid];path=chosen[rid]['Candidate_Path'];parts=path.split(' | ')
            assert v[:3]==old[:3] and v[3]==parts[-1]
            assert v[4:10]==(old[4],old[3],parts[-2],old[3],old[6],old[6])
            assert v[10:12]==(path,'Nama') and 'Pertahankan ID ini' in v[12]
            assert all(x is None for x in v[13:])
            assert source['Source_Name']==old[2] and source['Source_Parent_Id']==old[3]
            assert inventory[path]['Parent_Target_Id']==old[3]
            assert not inventory[path]['Target_Id'] and not inventory[path]['Master_Sheet_Id']
            assert chosen[rid]['Candidate_Target_Id']==rid and chosen[rid]['ID_Verification']=='ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'
            assert old[12]==path and old[11]==parts[-1]
            assert source['Parent_Evidence']=='PARENT_LOOKUP_ID'
            assert ' | '.join(parts[:-1])==source['Resolved_Parent_Path']
            new_ids[rid]+=1
        assert next(rows,None) is None
        paths={chosen[rid]['Candidate_Path'] for rid in moved};removed_new=0;removed_mapping=0
        for index in [11,15]:
            def expected_rows():
                nonlocal removed_new,removed_mapping
                for values,sig in a.rows(index):
                    if index==11 and values[2] in paths:
                        assert not any(values[6:13]);removed_new+=1;continue
                    if index==15 and values[1] in moved:removed_mapping+=1;continue
                    yield values,sig
            for old,new in zip_longest(expected_rows(),b.rows(index)):
                assert old==new and old is not None,'Unrelated location or mapping evidence changed'
        assert removed_new==11 and removed_mapping==29
        # All other grouping sheets are byte-identical; count their source IDs.
        for index in [4,5,6,7,8,10,13]:
            for v,_ in a.rows(index):
                if v[0]!='Objek':old_ids[v[1]]+=1;new_ids[v[1]]+=1
        parent_ids={v[1] for v,_ in a.rows(16) if v[0]!='Objek'}
        old_ids.update(parent_ids);new_ids.update(parent_ids)
        assert old_ids==new_ids and len(new_ids)==91306 and all(n==1 for n in new_ids.values())
        oldsummary=[v for v,_ in a.rows(2)];newsummary=[v for v,_ in b.rows(2)]
        assert oldsummary[0]==newsummary[0]
        for old,new in zip(oldsummary[1:],newsummary[1:],strict=True):
            expected=list(old)
            if old[0]=='Kecamatan':expected[3]+=11;expected[4]-=11;expected[6]-=11
            assert tuple(expected)==new
        lengths={9:620,11:20512,14:17118,15:58559};endcols={9:'T',11:'N',14:'W',15:'L'}
        for index,last in lengths.items():
            am,bm=a.metadata(index),b.metadata(index)
            for key in ['dimension','autoFilter']:
                assert bm.find('m:'+key,NS).get('ref')==f'A1:{endcols[index]}{last}'
                bm.find('m:'+key,NS).set('ref',am.find('m:'+key,NS).get('ref'))
            for x,y in zip(am.findall('m:dataValidations/m:dataValidation',NS),bm.findall('m:dataValidations/m:dataValidation',NS),strict=True):
                oldrange=x.get('sqref');col=oldrange.split(':')[-1].rstrip('0123456789')
                assert y.get('sqref').endswith(col+str(last));y.set('sqref',oldrange)
            assert E.tostring(am)==E.tostring(bm),'Unrelated worksheet metadata changed'
        aw,bw=E.fromstring(az.read('xl/workbook.xml')),E.fromstring(bz.read('xl/workbook.xml'))
        for x,y in zip(aw.findall('m:definedNames/m:definedName',NS),bw.findall('m:definedNames/m:definedName',NS),strict=True):
            if x.text!=y.text:
                assert any(f'${endcols[i]}${n}' in y.text for i,n in lengths.items());y.text=x.text
        assert E.tostring(aw)==E.tostring(bw)
        if 'xl/sharedStrings.xml' in changed:
            x,y=E.fromstring(az.read('xl/sharedStrings.xml')),E.fromstring(bz.read('xl/sharedStrings.xml'))
            y.set('count',x.get('count'));assert E.tostring(x)==E.tostring(y)
        for entry in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):assert not re.search(rb'<f(?:\s|>)',bz.read(entry))
        assert 'a1pJ40000008X0WIAU' in moved
    wb=openpyxl.load_workbook(after,read_only=True)
    assert len(wb.sheetnames)==15 and wb['DATA BELUM JELAS'].max_column==23
    assert wb['PERBAIKAN PARENT - ID TETAP'].max_row==12571;wb.close()
    print(json.dumps({'rename_proposals':len(moved),'removed_insert_locations':removed_new,'removed_mapping_rows':removed_mapping,
                      'global_source_ids':91306,'changed_parts':sorted(changed)},indent=2))
    print('PASS: same-ID name-only proposals, correct Parent IDs, no insert duplication, inputs/styles, unchanged rows and sheet order.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['before','after','pipeline']:p.add_argument(name,type=Path)
    args=p.parse_args();check(args.before,args.after,args.pipeline)
