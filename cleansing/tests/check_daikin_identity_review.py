"""Audit identity-review proposals, source conservation, answers and XLSX validity."""
import argparse,hashlib,json,sys,re
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_review_readability import Package,NS
from daikin_identity_review import Context,LABELS,plan
from regional_matching import normalize,name_identity_kind
from regional_review_context import one_edit_typo
from regional_client_display import INFORMATIONAL_STATUSES
from check_polished_daikin_workbook import package_audit

WIDTHS={1:2,2:8,3:3,4:6,5:10,6:11,7:17,8:19,9:19,10:19,11:14,13:17,14:23,15:12}
MAIN=[4,5,6,7,8,9,10,13,14]
EXAMPLES={'a1nJ4000000KXFjIAO':'a1nfC00000VF8EpQAL',
          'a1nJ4000000KXZlIAO':'a1nfC00000VF9cwQAD',
          'a1pJ40000008XNrIAM':'a1pfC00000DcH4HQAV',
          'a1pJ40000008XPGIA2':'a1pfC00000DcH4EQAV'}


def check(before,after,pipeline,baseline_pipeline):
    ctx=Context(pipeline);stats=Counter()
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist(),'Package parts added or removed'
        a,b=Package(az),Package(bz)
        formulas=lambda archive,i:[n.findtext('m:cfRule/m:formula',namespaces=NS) for n in archive.metadata(i).findall('m:conditionalFormatting',NS)]
        assert formulas(a,14)==formulas(b,14),'Existing client completion rules changed'
        shift={'K':'M','L':'N','N':'P','O':'Q'}
        assert [re.sub(r'\$([KLNO])(?=\d)',lambda m:'$'+shift[m[1]],f) for f in formulas(a,13)]==formulas(b,13)
        old={i:[a.values(r,15 if i==13 else w) for r in a.rows(i)] for i,w in WIDTHS.items()}
        new={i:[b.values(r,w) for r in b.rows(i)] for i,w in WIDTHS.items()}
        plans,counts=plan(ctx,old[14][1:]);olddata={v[1]:v for v in old[14][1:]}
        dupids={rid for rid,p in plans.items() if p['action']=='duplicate'}
        repairids={rid for rid,p in plans.items() if p['action']=='repair'}
        assert not repairids,'This snapshot has no same-ID repairs; audit them before enabling future reclassification'
        assert len(plans)==counts['duplicate']+counts['recommendation']
        for i in [4,5,6,7,8,9,10,11]:
            assert az.read(f'xl/worksheets/sheet{i}.xml')==bz.read(f'xl/worksheets/sheet{i}.xml'),('Unrelated source/answer sheet changed',i)
        # Exact identity conservation, with a source assigned to one main group.
        def groups(rows):
            ids={}
            for i in MAIN:
                local={}
                for v in rows[i][1:]:
                    if v[1] in local:assert i in [8,9,10] and local[v[1]]==tuple(v[:3])
                    local[v[1]]=tuple(v[:3])
                for rid,identity in local.items():
                    assert rid not in ids,('Source belongs to two groups',rid)
                    ids[rid]=identity
            return ids
        assert groups(old)==groups(new);assert len(groups(new))==91306
        stats['source_ids']=91306
        duptable={v[1]:v for v in new[13][1:]}
        assert len(duptable)==len(new[13])-1
        assert len(new[13])==len(old[13])+len(dupids)
        for ov,nv in zip(old[13][1:],new[13][1:]):
            assert ov==nv[:6]+nv[8:],'Existing duplicate values/answers changed'
        assert [v[1] for v in new[14][1:]]==[v[1] for v in old[14][1:] if v[1] not in dupids]
        # Actual source FK fields are never filled with hypothetical Parents.
        for nv in new[14][1:]:
            ov=olddata[nv[1]]
            assert ov[:8]==nv[:8] and ov[10]==nv[10] and ov[16:]==nv[16:]
            if nv[1] not in plans:assert ov==nv
            if nv[13]:assert nv[13]!=nv[1],'Self recommendation reintroduced'
        changes={v[1] for i in [8,9,10] for v in new[i][1:]}
        assert not changes&dupids,'Merge source also given a Parent update'
        for rid in dupids:
            p=plans[rid];v=duptable[rid];ov=olddata[rid];level=LABELS.index(v[0]);raw=ctx.records[level][rid]
            assert v[3] and v[3]!=rid and v[3] not in duptable,'Duplicate chain/cycle'
            assert v[3]==ctx.inventory[tuple(v[5].split(' | '))]['Target_Id']
            assert ctx.records[level][v[3]]['_path']==tuple(p['path'])
            parent,note=ctx.parent(level,raw);assert parent==tuple(p['path'])[:-1]
            if p['kind']=='one_letter':assert one_edit_typo(v[2],v[4],level)
            else:assert name_identity_kind(v[2],v[4],level,parent)
            assert p['candidate']['ID_Verification']=='ID_TERVERIFIKASI'
            for col in [3,4,5,6,7]:
                if ov[col]:assert str(ov[col]) in v[7],('Lost actual source Parent context',rid,col)
            if ov[10]:assert ov[10] in v[7],'Lost cross-level evidence'
            assert not any(v[12:]),'Generated a client approval/final answer'
            if v[3] in changes:assert 'PERUBAHAN' in v[7],'Missing target repair dependency'
            if raw['Source_Legacy_Kecamatans']:assert raw['Source_Legacy_Kecamatans'] in v[7]
        for rid,tid in EXAMPLES.items():assert duptable[rid][3]==tid
        pajar=ctx.records[3]['a1nfC00000VF9cwQAD']
        assert pajar['Source_Parent_Id']=='a1pfC00000DcH6XQAV'
        # All informational evidence survives verbatim, including Salesforce
        # locations. Only selectable candidates for affected IDs are replaced.
        info=lambda rows:Counter(tuple(v[:3]+v[4:]) for v in rows[1:] if v[7] in INFORMATIONAL_STATUSES)
        assert info(old[15])==info(new[15])
        unaffected=lambda rows:Counter(tuple(v) for v in rows[1:] if v[1] not in plans)
        assert unaffected(old[15])==unaffected(new[15])
        mapping=defaultdict(list)
        for v in new[15][1:]:mapping[v[1]].append(v)
        for rid,p in plans.items():
            rows=mapping[rid];assert [int(v[3]) for v in rows]==list(range(1,len(rows)+1))
            selectable=[v for v in rows if v[7] not in INFORMATIONAL_STATUSES]
            assert len(selectable)==1 and selectable[0][5]==' | '.join(p['path'])
            if p['action']=='duplicate':
                assert selectable[0][6]==duptable[rid][3]
                assert selectable[0][7:9]==duptable[rid][6:8],'Conflicting merge/Parent instructions'
        for r in new[2][1:]:
            label=r[0]
            assert r[5]==sum(v[0]==label for v in new[13][1:])
            assert r[6]==sum(v[0]==label for v in new[14][1:])
        assert sum(sum(r[j] for r in new[2][1:]) for j in [2,3,5,6])==91306
        stats.update(counts);stats['data_duplicate']=len(new[13])-1;stats['data_unclear']=len(new[14])-1
        stats['mapping_rows']=len(new[15])-1
        stats['stable_unchanged_sheets']=8
    # Automatic matching/update/insert exports must remain exactly unchanged.
    for f in baseline_pipeline.rglob('*.csv'):
        rel=f.relative_to(baseline_pipeline)
        if str(rel)=='03_Manual_Review/Review_candidates.csv':continue
        assert f.read_bytes()==(pipeline/rel).read_bytes(),('Automatic output changed',str(rel))
        stats['unchanged_automatic_csvs']+=1
    original=after.parent/'02_REVIEW_CLIENT_DATA_REGIONAL.xlsx'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='e44e3c4de355c41eb1cf26ca6247fdd22dbad7c39ab66c0b97d241db1b5d9ab7'
    audit=package_audit(after)
    wb=openpyxl.load_workbook(after,read_only=True)
    assert len(wb.sheetnames)==14
    assert wb['DATA DUPLIKAT'].max_column==17
    assert wb['DATA BELUM JELAS']['L1'].value=='Rekomendasi Nama';wb.close()
    return {'checks':'PASS','counts':dict(stats),'examples':EXAMPLES,'package_audit':audit,
            'sha256':hashlib.sha256(after.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['before','after','pipeline','baseline_pipeline']:p.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=check(a.before,a.after,a.pipeline,a.baseline_pipeline)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
