"""Check grouped changes, independent inputs, text evidence, and unchanged source IDs."""
import argparse,csv,hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_review_readability import Package
from kelurahan_wide import unflatten,section_note,HEADERS,COLS
from regional_note_compaction import id_tokens
from regional_location_text import LocationTextIndex,TEXT_REASON
from regional_client_display import INFORMATIONAL_STATUSES
from daikin_identity_review import Context
from check_polished_daikin_workbook import package_audit


def check(before,after,pipeline,baseline_pipeline,source_dir,report):
    applied=json.loads(report.read_text());changed=set(applied['updated_source_ids']);ctx=Context(pipeline)
    index=LocationTextIndex(ctx.paths[3]);stats=Counter();source_ids_before=set();source_ids_after=set()
    with (source_dir/'Kelurahan.csv').open(encoding='cp1252',newline='') as f:raw={r['Id']:r for r in csv.DictReader(f)}
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist();a,b=Package(az),Package(bz)
        for i in [2,4,5,6,7,8,9,11,13]:assert az.read(f'xl/worksheets/sheet{i}.xml')==bz.read(f'xl/worksheets/sheet{i}.xml')
        oldgroups=defaultdict(list)
        for row in a.rows(10):
            if row.get('r')!='1':
                v=a.values(row,19);oldgroups[v[1]].append(v)
        assert b.values(next(b.rows(10)),43)==HEADERS
        recovered={};order=[];example=None
        for row in b.rows(10):
            if row.get('r')=='1':continue
            v=b.values(row,43);assert v[1] not in recovered
            recovered[v[1]]=unflatten(v);order.append(v[1])
            active=set(v[3].split('; '))
            for kind,cols in COLS.items():
                if kind not in active:assert not any(v[c-1] for c in cols.values())
            if v[1]=='a1nJ4000000Kcc4IAC':example=v
        assert order==list(oldgroups) and len(order)==16329
        for rid,group in oldgroups.items():
            expected={v[3]:v.copy() for v in group}
            for kind,v in expected.items():v[11]=section_note(v[11],kind)
            actual={v[3]:v for v in recovered[rid]}
            assert actual==expected,('Lost or changed a proposal/context/answer',rid)
            for original in group:
                assert id_tokens(original[11])==id_tokens(actual[original[3]][11]),('Lost an ID in explanation',rid)
            stats['change_items']+=len(group)
        assert stats['change_items']==20039 and len(recovered)==16329
        assert example and len(unflatten(example))==2
        assert example[COLS['Parent Kecamatan'][7]-1] is None and example[COLS['Kabupaten/Kota Langsung'][7]-1] is None
        assert 'Taman Sari' in example[4] and 'Karang Sari' in example[4]
        olddata=[a.values(r,23) for r in a.rows(14)];newdata=[b.values(r,23) for r in b.rows(14)]
        assert len(olddata)==len(newdata)==14413
        for old,new in zip(olddata,newdata):
            if old[1] not in changed:assert old==new;continue
            assert old[:8]==new[:8] and old[10]==new[10] and old[16:]==new[16:]
            assert new[14]=='Lokasi dari teks; perlu konfirmasi'
            hits=index.candidates(new[2],raw[new[1]]);assert len(hits)==1
            assert new[12]==' | '.join(hits[0][0]) and raw[new[1]]['Combined__c'] in new[15]
            assert new[13]!=new[1] and not any(new[16:])
            candidates=[c for c in ctx.candidates[new[1]] if c['Reason'].startswith(TEXT_REASON)]
            assert candidates and candidates[0]['Rank']=='1'
            stats['text_supported_sources']+=1
        sukajaya=next(v for v in newdata if v[1]=='a1nJ4000000KWlUIAW')
        assert sukajaya[12]=='Jawa Barat | Kab. Bandung Barat | Lembang | Sukajaya'
        assert sukajaya[13] is None
        assert all(word in sukajaya[15] for word in ['Pinrang','Garut','Cisewu','Konfirmasikan'])
        oldmap=[a.values(r,12) for r in a.rows(15)];newmap=[b.values(r,12) for r in b.rows(15)]
        info=lambda rows:Counter(tuple(v[:3]+v[4:]) for v in rows[1:] if v[7] in INFORMATIONAL_STATUSES)
        assert info(oldmap)==info(newmap),'Informational evidence changed'
        unaffected=lambda rows:Counter(tuple(v) for v in rows[1:] if v[1] not in changed)
        assert unaffected(oldmap)==unaffected(newmap)
        newby=defaultdict(list)
        for v in newmap[1:]:newby[v[1]].append(v)
        for v in newdata[1:]:
            if v[1] not in changed:continue
            m=newby[v[1]];assert m[0][4:9]==v[11:16]
            assert [int(x[3]) for x in m]==list(range(1,len(m)+1))
        # Every old alternative survives unless its same path is replaced by the
        # newly explained primary candidate; no preferred path/ID is auto-approved.
        current={v[1]:v for v in newdata[1:]}
        for v in oldmap[1:]:
            if v[1] in changed and not (v[5]==current[v[1]][12] and v[7] not in INFORMATIONAL_STATUSES):
                assert any(x[:3]+x[4:]==v[:3]+v[4:] for x in newby[v[1]])
        for i,width in [(4,6),(5,10),(6,11),(7,17),(8,19),(9,19),(10,43),(13,17),(14,23)]:
            oldwidth=19 if i==10 else width
            source_ids_before.update(a.values(r,oldwidth)[1] for r in a.rows(i) if r.get('r')!='1')
            source_ids_after.update(b.values(r,width)[1] for r in b.rows(i) if r.get('r')!='1')
        assert source_ids_before==source_ids_after and len(source_ids_after)==91306
    for f in baseline_pipeline.rglob('*.csv'):
        rel=f.relative_to(baseline_pipeline)
        if str(rel)=='03_Manual_Review/Review_candidates.csv':continue
        assert f.read_bytes()==(pipeline/rel).read_bytes(),('Automatic output changed',str(rel))
        stats['unchanged_automatic_csvs']+=1
    audit=package_audit(after)
    return {'checks':'PASS','counts':dict(stats),'source_ids':91306,'sheet_count':14,'kelurahan_rows':16329,
            'sukajaya_location':sukajaya[12],'package_audit':audit,'sha256':hashlib.sha256(after.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['before','after','pipeline','baseline_pipeline','source_dir','applied_report','report']:
        p.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    a=p.parse_args();r=check(a.before,a.after,a.pipeline,a.baseline_pipeline,a.source_dir,a.applied_report)
    a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
