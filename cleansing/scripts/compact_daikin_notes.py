"""Compact recommendation notes only; preserve mapping, evidence and review input."""
import argparse,hashlib,json,re,tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from daikin_review_readability import Package,NS,put,encode,row_height
from regional_note_compaction import compact_recommendation_note,id_tokens


def apply(workbook,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    backup.write_bytes(workbook.read_bytes());stats=Counter()
    with ZipFile(backup) as z:
        a=Package(z);replacements={}
        data_ids={a.values(row,23)[1] for row in a.rows(14) if row.get('r')!='1'}
        styles=E.fromstring(z.read('xl/styles.xml'))
        assert styles.find('m:cellXfs',NS)[6].find('m:alignment',NS).get('wrapText')=='1'
        for i,width,col in [(14,23,16),(15,12,9)]:
            meta=a.metadata(i);body=BytesIO()
            widths=[float(c.get('width','25')) for c in meta.findall('m:cols/m:col',NS)
                    for _ in range(int(c.get('min')),int(c.get('max'))+1)]
            for row in a.rows(i):
                v=a.values(row,width)
                if row.get('r')!='1' and v[1] in data_ids:
                    old=v[col-1];new=compact_recommendation_note(old)
                    if old:
                        stats[f'sheet_{i}_chars_before']+=len(old);stats[f'sheet_{i}_chars_after']+=len(new)
                    if old!=new:
                        assert len(new)<len(old) and id_tokens(old)==id_tokens(new)
                        assert compact_recommendation_note(new)==new
                        put(row,col,new);v[col-1]=new
                        row_height(row,v,widths,360);stats[f'sheet_{i}_updated']+=1
                body.write(encode(row))
            replacements[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for name in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):
                refs+=len(re.findall(rb'<(?:\w+:)?c\b[^>]*\bt="s"',replacements.get(name,z.read(name))))
        shared.set('count',str(refs));replacements['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as out:assert out.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'counts':dict(stats),'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','backup','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=apply(a.workbook,a.backup);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
