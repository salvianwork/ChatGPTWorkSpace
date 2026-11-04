"""Apply validated review CSV to the regional workbook, preserving client inputs.

Only DATA BELUM JELAS and PILIHAN MAPPING are edited. Review metadata columns
are grouped beside each choice. Client inputs move together with their dropdown references.
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
from openpyxl.utils import get_column_letter, column_index_from_string, range_boundaries as openpyxl_range
from regional_review import REVIEW_FIELDS
from regional_client_display import CHOICE_HEADERS, MAPPING_HEADERS, client_candidate, mapping_row, source_text, ensure_selection_matches

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
    existing_changes=changed_records=0
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
                al.set('wrapText','1');xf.set('applyAlignment','1')
                existing=next((j for j,old in enumerate(xfs) if E.tostring(old)==E.tostring(xf)),None)
                if existing is None:existing=len(xfs);xfs.append(xf)
                wrapmap[i]=existing
            c.set('s',str(wrapmap[i]))
        data=E.fromstring(z.read('xl/worksheets/sheet14.xml'));sd=data.find('m:sheetData',NS)
        header=sd[0];headers=[value(c) for c in header]
        assert len(headers) in (32,44,35), headers
        compact=len(headers)==35
        client_start=28 if compact else 25
        assert headers[1]=='Id_Sumber'
        assert headers[client_start-1]=='Keputusan_Client' and headers[client_start+6]=='Tanggal_Konfirmasi'
        if compact:
            assert headers[11]=='Jumlah_Rekomendasi' and headers[12:27]==CHOICE_HEADERS
        elif len(headers)==44:
            assert headers[32:]==EXTRA_HEADERS
        assert not data.findall('.//m:f',NS), 'Workbook contains formulas; review column references before changing its layout.'
        def colnum(c):return column_index_from_string(re.sub(r'\d','',c.get('r')))
        old_cols=data.find('m:cols',NS)
        settings={i:dict(c.attrib) for c in old_cols for i in range(int(c.get('min')),int(c.get('max'))+1)}
        first_row=sd[1];body_styles={colnum(c):c.get('s') for c in first_row}
        name_style=body_styles.get(13,body_styles.get(1));location_style=body_styles.get(14,name_style)
        id_style=body_styles.get(15,name_style);note_style=body_styles.get(16,name_style)
        header_style=header[0].get('s')
        for row in sd:
            row_id=row.get('r');is_header=row_id=='1'
            cells={colnum(c):c for c in row}
            protected=[deepcopy(c) for c in row if colnum(c)<=11]
            clients=[deepcopy(c) for c in row if client_start<=colnum(c)<client_start+8]
            cs=[] if is_header else groups[value(cells[2])]
            if not is_header:
                assert all(d['Nama_Sumber']==value(cells[3]) for d in cs)
                step=5 if compact else 4
                old_choices=[[value(cells.get(13+i*step+j)) for j in range(3)] for i in range(3)]
                try:
                    ensure_selection_matches(old_choices,[client_candidate(d)[:3] for d in cs[:3]],value(cells.get(client_start)),value(cells.get(client_start+1)))
                except ValueError as exc:
                    raise ValueError(str(value(cells[2]))+': '+str(exc)) from exc
                new_notes=source_text(value(cells[9]),value(cells[10]),value(cells.get(6)),value(cells.get(8)),value(cells.get(11)))
                for col,v in zip([9,10,11],new_notes):
                    old=next((c for c in protected if colnum(c)==col),None)
                    if old is None and v is not None:
                        old=E.Element(TAG+'c',r=get_column_letter(col)+row_id)
                        if note_style is not None:old.set('s',note_style)
                        protected.append(old);protected.sort(key=colnum)
                    if old is not None and value(old)!=v:put(old,v);wrap(old)
            for c in list(row):row.remove(c)
            for c in protected:row.append(c)
            vals=['Jumlah_Rekomendasi']+CHOICE_HEADERS if is_header else [len(cs)]+[v for i in range(3) for v in (client_candidate(cs[i]) if i<len(cs) else ['']*5)]
            row_changed=False
            for col,v in enumerate(vals,12):
                v=v if v!='' else None
                old=cells.get(col)
                if value(old)!=v:existing_changes+=1;row_changed=True
                if v is None:continue
                c=E.SubElement(row,TAG+'c',r=get_column_letter(col)+row_id)
                style=header_style if is_header else [name_style,location_style,id_style,name_style,note_style][(col-13)%5] if col>=13 else name_style
                if style is not None:c.set('s',style)
                put(c,v);wrap(c)
            if not is_header:changed_records+=row_changed
            for c in clients:
                c.set('r',get_column_letter(colnum(c)-client_start+28)+row_id);row.append(c)
            if row.get('spans'):row.set('spans','1:35')
        # Keep source-column widths and client formats; replace only the recommendation layout.
        for c in list(old_cols):
            if int(c.get('min'))>=12:old_cols.remove(c)
            elif int(c.get('max'))>11:c.set('max','11')
        widths=[20]+[30,55,26,32,85]*3
        for col,width in enumerate(widths,12):E.SubElement(old_cols,TAG+'col',min=str(col),max=str(col),width=str(width),customWidth='1')
        for offset in range(8):
            attrib=settings.get(client_start+offset,{'width':'30','customWidth':'1'}).copy()
            attrib.update(min=str(28+offset),max=str(28+offset));E.SubElement(old_cols,TAG+'col',attrib=attrib)
        # The existing list options remain byte-for-byte the same; only their target cells move.
        dv=data.find('m:dataValidations',NS)
        if dv is not None:
            for validation in dv:
                ranges=[]
                for area in validation.get('sqref').split():
                    bounds=openpyxl_range(area)
                    assert client_start<=bounds[0]<=bounds[2]<client_start+8
                    ranges.append(get_column_letter(bounds[0]-client_start+28)+str(bounds[1])+':'+get_column_letter(bounds[2]-client_start+28)+str(bounds[3]))
                validation.set('sqref',' '.join(ranges))
        last=sd[-1].get('r')
        for key in ['dimension','autoFilter']:data.find('m:'+key,NS).set('ref','A1:AI'+last)
        raw=z.read('xl/worksheets/sheet15.xml');start=raw.index(b'<sheetData>');contentstart=start+len(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        hend=raw.index(b'</row>',contentstart)+len(b'</row>');secondend=raw.index(b'</row>',hend)+len(b'</row>')
        wrapper=lambda text:E.fromstring(b'<root xmlns="'+NS['m'].encode()+b'">'+text+b'</root>')[0]
        mh=wrapper(raw[contentstart:hend]);template=wrapper(raw[hend:secondend]);mapping_headers=[value(c) for c in mh]
        assert len(mapping_headers) in (16,20,12)
        if len(mapping_headers)==12:assert mapping_headers==MAPPING_HEADERS
        else:assert mapping_headers[:16]==['Kegunaan']+MAPPING_KEYS
        ms={column_index_from_string(re.sub(r'\d','',c.get('r'))):c.get('s') for c in template}
        mapping_header_style=mh[0].get('s')
        content=io.BytesIO()
        for i,vals in enumerate([MAPPING_HEADERS]+[mapping_row(d) for d in records],1):
            row=E.Element(TAG+'row',nsmap={None:NS['m']},r=str(i))
            for col,v in enumerate(vals,1):
                if v=='':continue
                c=E.SubElement(row,TAG+'c',r=get_column_letter(col)+str(i))
                style=mapping_header_style if i==1 else ms.get(1)
                if style is not None:c.set('s',style)
                put(c,v);wrap(c)
            content.write(E.tostring(row))
        mapping=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);cols=mapping.find('m:cols',NS)
        for c in list(cols):cols.remove(c)
        for col,width in enumerate([20,24,40,12,35,75,30,35,100,24,24,18],1):
            E.SubElement(cols,TAG+'col',min=str(col),max=str(col),width=str(width),customWidth='1')
        before_count=int(re.sub(r'^[A-Z]+','',mapping.find('m:dimension',NS).get('ref').split(':')[-1]))-1
        for key in ['dimension','autoFilter']:mapping.find('m:'+key,NS).set('ref','A1:L'+str(len(records)+1))
        mappingbytes=E.tostring(mapping).replace(b'<sheetData/>',b'<sheetData>'+content.getvalue()+b'</sheetData>')
        xfs.set('count',str(len(xfs)))
        replacements={'xl/worksheets/sheet14.xml':E.tostring(data),'xl/worksheets/sheet15.xml':mappingbytes}
        if wrapmap:replacements['xl/styles.xml']=E.tostring(styles)
        names=wb.find('m:definedNames',NS)
        if names is not None:
            for name in names:
                if name.get('name')=='_xlnm._FilterDatabase' and name.get('localSheetId') in {'13','14'}:
                    endcol,endrow=('AI',last) if name.get('localSheetId')=='13' else ('L',str(len(records)+1))
                    name.text=name.text.rsplit('!',1)[0]+'!$A$1:$'+endcol+'$'+endrow
            replacements['xl/workbook.xml']=E.tostring(wb)
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
            'data_columns_before':len(headers),'data_columns_after':35,'mapping_columns_after':12,
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
