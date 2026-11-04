"""Apply validated review CSV to the regional workbook, preserving client inputs.

Only DATA BELUM JELAS and PILIHAN MAPPING are edited. Review metadata columns
are appended, so existing client-input columns and dropdown references stay put.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZipFile

from lxml import etree as E
from openpyxl.utils import get_column_letter, column_index_from_string
from regional_review import REVIEW_FIELDS

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
TAG = '{' + NS['m'] + '}'
MAPPING_KEYS = ['Objek','Id_Sumber','Nama_Sumber','Urutan','Kemiripan','Hierarki_Kandidat',
                'Nama_Kandidat','Alasan','Id_Target_Kandidat','Jenis_Bukti','Tingkat_Ditemukan',
                'Sumber_Data','Jumlah_Kemunculan','Contoh_Lokasi','Konteks_Induk']
METADATA = list(REVIEW_FIELDS.values())
EXTRA_HEADERS = [f'Pilihan_{i}_{name}' for i in range(1,4) for name in METADATA]
PURPOSES = {'KANDIDAT_OBJEK_SAMA':'Pilihan mapping yang masih perlu dikonfirmasi',
            'TEMUAN_LINTAS_TINGKAT':'Petunjuk nama pada tingkat wilayah lain; bukan mapping otomatis',
            'BELUM_DITEMUKAN':'Belum ditemukan nama yang sama'}


def apply(workbook, candidates, backup):
    assert not backup.exists(), 'Backup already exists; choose a new path.'
    assert workbook.resolve() != backup.resolve()
    with candidates.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        assert set(MAPPING_KEYS + METADATA) <= set(reader.fieldnames)
        records=list(reader)
    groups=defaultdict(list)
    for d in records:
        if d['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':
            assert d['Status_Verifikasi_ID'] and d['Alasan_Verifikasi_ID']
            if d['Id_Target_Kandidat']:
                assert d['Status_Verifikasi_ID'] in {'ID_TERVERIFIKASI','ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'}
            groups[d['Id_Sumber']].append(d)
        else:
            assert not d['Id_Target_Kandidat']
    shutil.copy2(workbook, backup)
    existing_changes=metadata_changes=changed_records=metadata_records=0
    with ZipFile(backup) as z:
        # Assert the expected workbook layout rather than silently editing another sheet.
        wb=E.fromstring(z.read('xl/workbook.xml'))
        titles=[s.get('name') for s in wb.find('m:sheets',NS)]
        assert titles[13:15]==['DATA BELUM JELAS','PILIHAN MAPPING']
        rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.get('Id'):r.get('Target').lstrip('/') for r in rels}
        for index,expected in [(13,'worksheets/sheet14.xml'),(14,'worksheets/sheet15.xml')]:
            rid=wb.find('m:sheets',NS)[index].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            assert targets[rid] in {expected,'xl/'+expected}
        strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        def value(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            text=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(text)]
            return int(text) if text and c.get('t') is None and text.isdigit() else text
        def put(c,v):
            for e in list(c):c.remove(e)
            c.attrib.pop('t',None)
            if v is None:return
            if isinstance(v,int):E.SubElement(c,TAG+'v').text=str(v)
            else:
                c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t');t.text=v
                if v!=v.strip():t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        styles=E.fromstring(z.read('xl/styles.xml'));xfs=styles.find('m:cellXfs',NS);wrapmap={}
        def wrap(c):
            i=int(c.get('s','0'));al=xfs[i].find('m:alignment',NS)
            if al is not None and al.get('wrapText')=='1':return
            if i not in wrapmap:
                xf=deepcopy(xfs[i]);al=xf.find('m:alignment',NS)
                if al is None:al=E.SubElement(xf,TAG+'alignment')
                al.set('wrapText','1');xf.set('applyAlignment','1');wrapmap[i]=len(xfs);xfs.append(xf)
            c.set('s',str(wrapmap[i]))
        data=E.fromstring(z.read('xl/worksheets/sheet14.xml'));sd=data.find('m:sheetData',NS)
        header=sd[0];headers=[value(c) for c in header]
        assert len(headers) in (32,44), headers
        assert headers[1]=='Id_Sumber' and headers[11]=='Jumlah_Pilihan_Mapping' and headers[24]=='Keputusan_Client' and headers[31]=='Tanggal_Konfirmasi'
        if len(headers)==44:assert headers[32:]==EXTRA_HEADERS
        colstyles={}
        for row in list(sd)[1:]:
            for c in row:colstyles.setdefault(re.sub(r'\d','',c.get('r')),c.get('s'))
        def assign(row,col,v,default_style):
            ref=get_column_letter(col)+row.get('r');c=next((c for c in row if c.get('r')==ref),None)
            if value(c)==v:return False
            if c is None:
                c=E.Element(TAG+'c',r=ref)
                if default_style is not None:c.set('s',default_style)
                pos=next((i for i,cc in enumerate(row) if column_index_from_string(re.sub(r'\d','',cc.get('r')))>col),len(row))
                row.insert(pos,c)
            put(c,v);wrap(c);return True
        if len(headers)==32:
            for col,text in enumerate(EXTRA_HEADERS,33):assign(header,col,text,header[-1].get('s'))
            cols=data.find('m:cols',NS)
            for col in range(33,45):
                E.SubElement(cols,TAG+'col',min=str(col),max=str(col),width='75' if (col-33)%4==2 else '35',customWidth='1')
        for row in list(sd)[1:]:
            cells={re.sub(r'\d','',c.get('r')):c for c in row};rid=value(cells['B']);source_name=value(cells['C']);cs=groups[rid]
            assert all(d['Nama_Sumber']==source_name for d in cs),(rid,source_name)
            vals=[len(cs)]
            for i in range(3):vals += [(cs[i][k] or None) for k in ['Nama_Kandidat','Hierarki_Kandidat','Id_Target_Kandidat','Alasan']] if i<len(cs) else [None]*4
            changed=False;meta=False
            for col,v in enumerate(vals,12):
                result=assign(row,col,v,colstyles.get(get_column_letter(col),colstyles.get('P')))
                existing_changes+=result;changed |= result
            for i in range(3):
                for j,key in enumerate(METADATA):
                    v=(cs[i][key] or None) if i<len(cs) else None
                    result=assign(row,33+i*4+j,v,colstyles.get('P'))
                    metadata_changes+=result;meta |= result
            changed_records+=changed;metadata_records+=meta
            if row.get('spans'):row.set('spans','1:44')
        if header.get('spans'):header.set('spans','1:44')
        last=sd[-1].get('r')
        for key in ['dimension','autoFilter']:data.find('m:'+key,NS).set('ref','A1:AR'+last)
        raw=z.read('xl/worksheets/sheet15.xml');start=raw.index(b'<sheetData>');contentstart=start+len(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        hend=raw.index(b'</row>',contentstart)+len(b'</row>');secondend=raw.index(b'</row>',hend)+len(b'</row>')
        wrapper=lambda text:E.fromstring(b'<root xmlns="'+NS['m'].encode()+b'">'+text+b'</root>')[0]
        mh=wrapper(raw[contentstart:hend]);template=wrapper(raw[hend:secondend]);mapping_headers=[value(c) for c in mh]
        assert mapping_headers[:16]==['Kegunaan']+MAPPING_KEYS
        assert len(mapping_headers) in (16,20)
        if len(mapping_headers)==20:assert mapping_headers[16:]==METADATA
        else:
            for col,text in enumerate(METADATA,17):assign(mh,col,text,mh[-1].get('s'))
        if mh.get('spans'):mh.set('spans','1:20')
        ms={re.sub(r'\d','',c.get('r')):c.get('s') for c in template}
        content=io.BytesIO();content.write(E.tostring(mh))
        for i,d in enumerate(records,2):
            row=E.Element(TAG+'row',nsmap={None:NS['m']},attrib=dict(template.attrib));row.set('r',str(i))
            if row.get('spans'):row.set('spans','1:20')
            for col,v in enumerate([PURPOSES[d['Jenis_Bukti']]]+[d[k] or None for k in MAPPING_KEYS+METADATA],1):
                letter=get_column_letter(col);c=E.SubElement(row,TAG+'c',r=letter+str(i));style=ms.get(letter,ms.get('I'))
                if style is not None:c.set('s',style)
                put(c,v);wrap(c)
            content.write(E.tostring(row))
        mapping=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);cols=mapping.find('m:cols',NS)
        if len(mapping_headers)==16:
            for col in range(17,21):E.SubElement(cols,TAG+'col',min=str(col),max=str(col),width='75' if col==19 else '35',customWidth='1')
        before_count=int(mapping.find('m:dimension',NS).get('ref').split(':')[-1][1:])-1
        for key in ['dimension','autoFilter']:mapping.find('m:'+key,NS).set('ref','A1:T'+str(len(records)+1))
        mappingbytes=E.tostring(mapping).replace(b'<sheetData/>',b'<sheetData>'+content.getvalue()+b'</sheetData>')
        xfs.set('count',str(len(xfs)))
        replacements={'xl/worksheets/sheet14.xml':E.tostring(data),'xl/worksheets/sheet15.xml':mappingbytes}
        if wrapmap:replacements['xl/styles.xml']=E.tostring(styles)
        # Write a temporary archive first; replace the workbook only after ZIP integrity succeeds.
        with tempfile.NamedTemporaryFile(prefix='regional-review-',suffix='.xlsx',dir=workbook.parent,delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as output:
                for info in z.infolist():output.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:
            temp.unlink(missing_ok=True)
    return {'existing_candidate_cells_changed':existing_changes,'records_with_candidate_changes':changed_records,
            'metadata_cells_added_or_updated':metadata_changes,'records_with_metadata':metadata_records,
            'mapping_rows_before':before_count,'mapping_rows_after':len(records),'backup':str(backup)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--backup',type=Path,required=True,help='New backup path outside the checkout')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=apply(args.workbook,args.candidates,args.backup)
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
