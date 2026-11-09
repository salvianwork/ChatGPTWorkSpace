"""Compare all rows after recommendation, evidence wording and relationship status fixes."""
import argparse,csv,json,re,sys
from collections import Counter,defaultdict
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_valid_region_reclassification import Archive,NS,TAG,signature
from regional_client_display import NO_EXACT_WITH_CANDIDATES


def mapping_rows(archive):
    with archive.z.open('xl/worksheets/sheet15.xml') as f:
        for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
            cells={openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
            yield (tuple(archive.value(cells[i]) if i in cells else None for i in range(1,max(cells)+1)),
                   {i:signature(c) for i,c in cells.items()})
            row.clear()
            while row.getprevious() is not None:del row.getparent()[0]


def check(before,after,pipeline):
    with (pipeline/'03_Manual_Review/Review_candidates.csv').open(encoding='utf-8-sig',newline='') as f:
        aliases={r['Source_Id']:r for r in csv.DictReader(f) if 'alias dalam tanda kurung' in r['Reason']}
    aceh='a1ofC000000MuErQAK';affected=set(aliases)|{aceh}
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist() and bz.testzip() is None
        changed={n for n in az.namelist() if az.read(n)!=bz.read(n)}
        assert changed<={'xl/workbook.xml','xl/sharedStrings.xml',*[f'xl/worksheets/sheet{i}.xml' for i in [14,15,16]]}
        a,b=Archive(az),Archive(bz);source_ids=Counter();data_stats=Counter();seen=set();examples={}
        for old,new in zip_longest(a.rows(14),b.rows(14)):
            assert old is not None and new is not None
            ov,os=old;nv,ns=new;ov=ov+(None,)*(23-len(ov));nv=nv+(None,)*(23-len(nv));rid=ov[1]
            assert ov[:9]==nv[:9] and ov[16:]==nv[16:],'Source fields or review inputs changed'
            if ov[0]=='Objek':assert old==new;continue
            source_ids[rid]+=1
            if rid not in affected:assert old==new,'Unrelated recommendation changed'
            elif rid==aceh:
                assert not any(nv[11:16]);assert 'Aceh (NAD)' in nv[9]
                assert 'Provinsi: Aceh (NAD)' in nv[10]
                for line in (ov[10] or '').splitlines():assert not line or line in nv[10]
            else:
                seen.add(rid);r=aliases[rid]
                assert nv[11]==r['Candidate_Name'] and nv[12]==r['Candidate_Path']
                assert (nv[13] or '')==(r['Candidate_Target_Id'] or r['Unverified_Master_ID'])
                assert nv[9:11]==ov[9:11] and 'tanda kurung' in nv[15]
                assert nv[13]!=rid
            data_stats['ID tersedia' if nv[13] else 'ID kosong']+=1
            data_stats['Ada rekomendasi' if nv[11] else 'Tanpa rekomendasi']+=1
            if rid in {aceh,'a1pJ40000008XNrIAM'}:examples[rid]=nv
        assert seen==set(aliases) and len(seen)==36 and len(source_ids)==17117
        assert examples['a1pJ40000008XNrIAM'][11:14]==('Kulisusu','Sulawesi Tenggara | Kab. Buton Utara | Kulisusu','a1pfC00000DcH4HQAV')
        # Compare every unaffected mapping row, including exact wording/style
        # outside the two clarified no-exact-name columns.
        same=set(aliases)
        for v,_ in a.rows(15):
            if v[1]!=aceh and len(v)>7 and v[5] and v[7]!='Nama ditemukan di tingkat lain':same.add(v[1])
        old_affected=defaultdict(list);new_affected=defaultdict(list);labels=0
        def filtered(archive,store):
            for v,s in mapping_rows(archive):
                if v[1] in affected:store[v[1]].append(v);continue
                yield v,s
        for old,new in zip_longest(filtered(a,old_affected),filtered(b,new_affected)):
            assert old is not None and new is not None
            ov,os=old;nv,ns=new
            if ov[1] in same and ov[7]=='Nama belum ditemukan':
                assert nv[:7]==ov[:7] and nv[9:]==ov[9:]
                assert nv[7:9]==NO_EXACT_WITH_CANDIDATES;labels+=1
                assert os.keys()==ns.keys()
                for i,x in os.items():
                    if i not in {8,9}:assert x==ns[i]
            else:assert old==new,'Unrelated mapping row changed'
        for rid,items in new_affected.items():
            assert [int(v[3]) for v in items]==list(range(1,len(items)+1))
            if rid==aceh:
                assert all(not v[6] for v in items)
                assert sum(v[10]=='Provinsi' for v in items)==2
                assert not any(v[10]=='Kota/Kabupaten' for v in items)
                expected_cross=[v[:3]+v[4:] for v in old_affected[rid] if v[7]=='Nama ditemukan di tingkat lain']
                actual_cross=[v[:3]+v[4:] for v in items if v[10]!='Provinsi']
                assert expected_cross==actual_cross
            else:
                candidates=[v for v in items if v[5] and v[7]!='Nama ditemukan di tingkat lain']
                assert len(candidates)==1 and candidates[0][5]==aliases[rid]['Candidate_Path']
                assert (candidates[0][6] or '')==(aliases[rid]['Candidate_Target_Id'] or aliases[rid]['Unverified_Master_ID'])
                old_cross=[v[:3]+v[4:] for v in old_affected[rid] if v[7]=='Nama ditemukan di tingkat lain']
                new_cross=[v[:3]+v[4:] for v in items if v[7]=='Nama ditemukan di tingkat lain']
                assert old_cross==new_cross
                for v in items:
                    if v[7]==NO_EXACT_WITH_CANDIDATES[0]:labels+=1;assert v[8]==NO_EXACT_WITH_CANDIDATES[1]
        assert labels==2679
        statuses=Counter();pairs=set();parent_ids=set();dependency=0
        for old,new in zip_longest(a.rows(16),b.rows(16)):
            assert old is not None and new is not None;ov,os=old;nv,ns=new
            if ov[0]=='Objek':assert old==new;continue
            assert ov[:11]==nv[:11] and ov[13:]==nv[13:],'Parent IDs, master paths or answers changed'
            if nv[7]:assert nv[11].startswith('ID relasi tersedia;')
            else:assert 'masih perlu dikonfirmasi' in nv[11] and 'tersedia;' not in nv[11]
            if ov[7] and ov[11]=='Parent masih perlu dikonfirmasi':
                dependency+=1;assert nv[12].endswith(ov[12]) and 'Hubungan lain' in nv[12]
            else:assert ov[12]==nv[12]
            statuses[nv[11]]+=1;assert (nv[1],nv[3]) not in pairs;pairs.add((nv[1],nv[3]));parent_ids.add(nv[1])
            for i,(x,y) in enumerate(zip(os[-1],ns[-1],strict=True)):
                if i not in {11,12}:assert x==y
        assert len(pairs)==12570 and len(parent_ids)==9000 and dependency==254
        # Byte-identical grouping sheets account for all other Salesforce IDs.
        for index in [4,5,6,7,8,9,10,13]:
            for v,_ in a.rows(index):
                if v[0]!='Objek':source_ids[v[1]]+=1
        source_ids.update(parent_ids)
        assert len(source_ids)==91306 and all(n==1 for n in source_ids.values())
        assert az.read('xl/styles.xml')==bz.read('xl/styles.xml')
        for index in [14,16]:assert E.tostring(a.metadata(index))==E.tostring(b.metadata(index))
        meta=b.metadata(15)
        assert meta.find('m:dimension',NS).get('ref')=='A1:L58548'
        assert meta.find('m:autoFilter',NS).get('ref')=='A1:L58548'
        for entry in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):assert not re.search(rb'<f(?:\s|>)',bz.read(entry))
        result={'alias_records':len(seen),'province_records':1,'clarified_labels':labels,'parent_dependency_notes':dependency,
                'parent_status_counts':dict(statuses),'source_ids':len(source_ids),'data_counts':dict(data_stats),'changed_parts':sorted(changed)}
    wb=openpyxl.load_workbook(after,read_only=True)
    assert len(wb.sheetnames)==15 and wb['DATA BELUM JELAS'].max_row==17118 and wb['DATA BELUM JELAS'].max_column==23
    assert wb['PERBAIKAN PARENT - ID TETAP'].max_row==12571;wb.close()
    print(json.dumps(result,ensure_ascii=False,indent=2));print('PASS: source IDs, review answers, alias/province candidates, evidence, per-relationship statuses and unchanged sheets.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['before','after','pipeline']:p.add_argument(name,type=Path)
    args=p.parse_args();check(args.before,args.after,args.pipeline)
