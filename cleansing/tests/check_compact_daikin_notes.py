"""Verify that only allowed note cells change and every specific fact survives."""
import argparse,hashlib,json,sys
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_review_readability import Package
from regional_note_compaction import compact_recommendation_note,compact_line,id_tokens,ID_WARNING,SHORT_WARNING
from check_polished_daikin_workbook import package_audit


def check(before,after):
    stats=Counter()
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist()
        a,b=Package(az),Package(bz)
        data_ids={a.values(r,23)[1] for r in a.rows(14) if r.get('r')!='1'}
        for name in az.namelist():
            if name not in {'xl/sharedStrings.xml','xl/worksheets/sheet14.xml','xl/worksheets/sheet15.xml'}:
                assert az.read(name)==bz.read(name),('Unrelated workbook part changed',name)
        for i,width,col in [(14,23,16),(15,12,9)]:
            assert E.tostring(a.metadata(i))==E.tostring(b.metadata(i)),'Layout, filter, dropdown or completion rules changed'
            for old,new in zip_longest(a.rows(i),b.rows(i)):
                assert old is not None and new is not None,'Row count changed'
                assert old.get('r')==new.get('r')
                ov,nv=a.values(old,width),b.values(new,width)
                eligible=old.get('r')!='1' and ov[1] in data_ids
                for c,(x,y) in enumerate(zip(ov,nv),1):
                    if c!=col or not eligible:
                        assert x==y,('Changed value/ID/review answer',i,old.get('r'),c)
                    else:
                        assert y==compact_recommendation_note(x)
                        assert id_tokens(x)==id_tokens(y)
                        if x!=y:
                            assert len(y)<len(x);stats[f'sheet_{i}_updated']+=1
                            assert compact_recommendation_note(y)==y
                            for line in x.splitlines():
                                if line in (ID_WARNING,SHORT_WARNING):
                                    assert y.count(SHORT_WARNING)==1
                                elif line.strip():assert compact_line(line).strip() in y,('Lost a fact or action',ov[1],line)
                        if x:
                            stats[f'sheet_{i}_chars_before']+=len(x);stats[f'sheet_{i}_chars_after']+=len(y)
                oldstyles={c.get('r'):c.get('s') for c in old};newstyles={c.get('r'):c.get('s') for c in new}
                assert oldstyles==newstyles,'Cell/input/date styles changed'
                stats[f'sheet_{i}_rows']+=1
    audit=package_audit(after)
    assert stats['sheet_14_rows']==14413 and stats['sheet_15_rows']==54235
    return {'checks':'PASS','counts':dict(stats),'package_audit':audit,
            'sha256':hashlib.sha256(after.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['before','after','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=check(a.before,a.after);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
