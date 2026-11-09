"""Finalize the Daikin workbook: remove the technical counter and rejected Madura guesses.

Run after Daikin branding, same-ID separation and relationship-row presentation.
The internal recommendation count remains available to the earlier pipeline stages.
"""
import argparse
from io import BytesIO
from pathlib import Path
import hashlib,json,re,shutil,tempfile
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string,get_column_letter
from daikin_parent_review import NS,TAG

SOURCE_ID='a1oJ40000009JPKIA2'
REJECTED={'a1oJ40000009JPJIA2','a1ofC00000EcXDLQA3'}
COUNTER='Jumlah Rekomendasi Ditampilkan'
REASON='Nama Madura belum menunjukkan kota/kabupaten yang sesuai pada master. Konfirmasikan tingkat wilayah, lokasi, dan provinsinya sebelum memilih ID tujuan.'


def apply(workbook,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    before_hash=hashlib.sha256(workbook.read_bytes()).hexdigest();shutil.copy2(workbook,backup)
    with ZipFile(backup) as z:
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));strings=[''.join(si.itertext()) for si in shared]
        def val(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            v=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(v)]
            return int(v) if v and v.isdigit() and c.get('t') is None else v
        def put(c,value):
            for child in list(c):c.remove(child)
            c.attrib.pop('t',None)
            if value is None:return
            if isinstance(value,int):E.SubElement(c,TAG+'v').text=str(value)
            else:c.set('t','inlineStr');E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t').text=value
        def col(c):return column_index_from_string(re.sub(r'\d','',c.get('r')))
        replacements={};report={};dropped=set();mapping_order=0
        for number in [14,15]:
            entry=f'xl/worksheets/sheet{number}.xml';raw=z.read(entry)
            assert not re.search(rb'<f(?:\s|>)',raw)
            start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
            meta=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);out=BytesIO();n=0
            fields=None;remove_col=None;updated=0
            with z.open(entry) as f:
                for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                    cells={col(c):c for c in row};header=row.get('r')=='1'
                    if header:
                        fields={val(c):i for i,c in cells.items()}
                        if number==14:
                            remove_col=fields.get(COUNTER)
                            assert fields['Id Sumber']==2 and fields['Rekomendasi 1 ID Salesforce'] in {14,15}
                        take=True
                    else:
                        rid=val(cells.get(fields['Id Sumber']));take=True
                        if number==14 and rid==SOURCE_ID:
                            assert val(cells[fields['Nama Sumber']])=='Madura'
                            assert not any(val(cells.get(fields[h])) for h in ['Keputusan Tim Daikin','Id Target Final Tim Daikin','Nama Final Tim Daikin','Id Parent Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi'])
                            target=val(cells.get(fields['Rekomendasi 1 ID Salesforce']))
                            assert target in REJECTED|{None,''}
                            put(cells[fields['Alasan Belum Jelas']],REASON)
                            for h in ['Nama','Lokasi','ID Salesforce','Status','Catatan']:
                                c=cells.get(fields['Rekomendasi 1 '+h])
                                if c is not None:put(c,None)
                            updated+=1
                        elif number==15 and rid==SOURCE_ID:
                            target=val(cells.get(fields['ID Salesforce Rekomendasi']))
                            if target in REJECTED:dropped.add(target);take=False
                            else:
                                assert not target,'Unexpected additional same-level recommendation for Madura'
                                mapping_order+=1;put(cells[fields['Urutan']],mapping_order)
                    if take:
                        n+=1;row.set('r',str(n))
                        for c in list(row):
                            old=col(c)
                            if number==14 and old==remove_col:row.remove(c);continue
                            new=old-1 if number==14 and remove_col and old>remove_col else old
                            c.set('r',get_column_letter(new)+str(n))
                        if number==14 and row.get('spans'):row.set('spans','1:23')
                        serialized=E.tostring(row)
                        for decl in [b' xmlns="'+NS['m'].encode()+b'"',b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"']:
                            serialized=serialized.replace(decl,b'',1)
                        out.write(serialized)
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
            if number==14:
                assert updated==1
                if remove_col:
                    cols=meta.find('m:cols',NS)
                    for c in list(cols):
                        low,high=int(c.get('min')),int(c.get('max'));assert low==high
                        if low==remove_col:cols.remove(c)
                        elif low>remove_col:c.set('min',str(low-1));c.set('max',str(high-1))
                    for dv in meta.findall('m:dataValidations/m:dataValidation',NS):
                        assert dv.get('sqref')==f'R2:R{n}';dv.set('sqref',f'Q2:Q{n}')
                report.update(data_rows=n-1,removed_counter=bool(remove_col),madura_records_updated=updated)
            else:report.update(mapping_rows=n-1,removed_mapping_candidates=len(dropped))
            for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:{"W" if number==14 else "L"}{n}')
            replacements[entry]=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+out.getvalue()+b'</sheetData>')
        assert dropped in (set(),REJECTED)
        wb=E.fromstring(z.read('xl/workbook.xml'))
        for name in wb.findall('m:definedNames/m:definedName',NS):
            if name.text.startswith("'DATA BELUM JELAS'!"):name.text=f"'DATA BELUM JELAS'!$A$1:$W${report['data_rows']+1}"
            elif name.text.startswith("'PILIHAN MAPPING'!"):name.text=f"'PILIHAN MAPPING'!$A$1:$L${report['mapping_rows']+1}"
        replacements['xl/workbook.xml']=E.tostring(wb)
        refs=0
        for entry in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):
                refs+=len(re.findall(rb'<c\b[^>]*\bt="s"',replacements.get(entry,z.read(entry))))
        if int(shared.get('count'))!=refs:
            shared.set('count',str(refs));replacements['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return dict(report,before_sha256=before_hash)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['workbook','backup']:parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=apply(args.workbook,args.backup)
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
