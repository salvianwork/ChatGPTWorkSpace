"""Move correct region records out of unclear review without approving canonical IDs."""
from collections import Counter
import csv
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import get_column_letter,column_index_from_string,range_boundaries
from regional_validity import VALID_SHEETS,OBJECT_LABELS,PENDING_REGION,PENDING_PRIMARY,translated_path,valid_client_row

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};TAG='{'+NS['m']+'}'
PREFIXES=['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']
OBJECTS=list(OBJECT_LABELS)
PENDING_REASON='Data wilayah sudah sesuai. Penetapan ID utama masih menunggu konfirmasi client.'


def existing_pending_ids(z,value):
    """Stream existing valid sheets; do not overwrite client comments on repeat runs."""
    result=set()
    for index in range(4,8):
        with z.open(f'xl/worksheets/sheet{index}.xml') as f:
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                cells={re.sub(r'\d','',c.get('r')):c for c in row}
                if value(cells.get('J'))==PENDING_REASON:result.add(value(cells.get('B')))
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
    return result


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);return reader.fieldnames,list(reader)


def reclassify(workbook,records_root):
    root=Path(records_root)
    files=[root/'05_All_Records'/f'{prefix}_all_records.csv' for prefix in PREFIXES]
    if not all(p.exists() for p in files):return {'enabled':False}
    headers,tables=zip(*(read_csv(p) for p in files))
    if not any('Status_Validasi_Wilayah' in h for h in headers):return {'enabled':False}
    assert all({'Status_Validasi_Wilayah','Status_Penetapan_ID_Utama'}<=set(h) for h in headers)
    _,inventory=read_csv(root/'04_Master_Targets'/'Master_target_inventory.csv')
    inv={r['Hierarki_Master']:r for r in inventory}
    pending={};counts=Counter()
    for level,rows in enumerate(tables):
        for source in rows:
            if source['Status_Validasi_Wilayah']!=PENDING_REGION:continue
            source=dict(source,Objek=OBJECTS[level]);path=translated_path(source)
            assert len(path)==level+1 and source['Nama_Sumber']==path[-1]
            assert source['Status_Penetapan_ID_Utama']==PENDING_PRIMARY
            assert source['Metode_Pencocokan']=='COCOK_PERSIS_DALAM_HIERARKI'
            assert source['Status']=='COCOK_MASTER_ID_TARGET_BELUM_TERVERIFIKASI'
            if level:
                parent=inv[' | '.join(path[:-1])]['Id_Target']
                assert parent and source['Id_Induk_Sumber']==parent
                assert source['Bukti_Induk']=='ID_LOOKUP_INDUK'
            if level==3:
                assert source['Id_Kota_Langsung_Sumber']==inv[' | '.join(path[:2])]['Id_Target']
            assert source['Id_Sumber'] not in pending
            pending[source['Id_Sumber']]=(level,source)
    with ZipFile(workbook) as z:
        strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        def value(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            text=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(text)]
            return int(text) if text and c.get('t') is None and text.isdigit() else text
        def put(c,v):
            for child in list(c):c.remove(child)
            c.attrib.pop('t',None)
            if v is None or v=='':return
            if isinstance(v,int):E.SubElement(c,TAG+'v').text=str(v)
            else:
                c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t');t.text=v
                if v!=v.strip():t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        styles=E.fromstring(z.read('xl/styles.xml'));xfs=styles.find('m:cellXfs',NS);added_style=False
        def wrap(c):
            nonlocal added_style
            i=int(c.get('s','0'));a=xfs[i].find('m:alignment',NS)
            if a is not None and a.get('wrapText')=='1':return
            new=deepcopy(xfs[i]);a=new.find('m:alignment',NS)
            if a is None:a=E.SubElement(new,TAG+'alignment')
            a.set('wrapText','1');new.set('applyAlignment','1')
            match=next((j for j,xf in enumerate(xfs) if E.tostring(xf)==E.tostring(new)),None)
            if match is None:match=len(xfs);xfs.append(new);added_style=True
            c.set('s',str(match))
        data=E.fromstring(z.read('xl/worksheets/sheet14.xml'));sd=data.find('m:sheetData',NS)
        assert not data.findall('.//m:f',NS),'Review formulas before removing source rows.'
        before_rows=len(sd)-1;old_last=int(sd[-1].get('r'))
        already=existing_pending_ids(z,value)
        assert already<=set(pending),'Previously valid records need a fresh review before reclassification'
        move=[];deferred=[]
        for row in list(sd)[1:]:
            cells={column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
            rid=value(cells[2])
            assert rid not in already,'Record appears in both valid and unclear sheets'
            if rid not in pending:continue
            level,source=pending[rid]
            assert value(cells[1])==OBJECT_LABELS[source['Objek']]
            assert value(cells[3])==source['Nama_Sumber'] and (value(cells.get(4)) or '')==source['Id_Induk_Sumber']
            assert (value(cells.get(7)) or '')==source['Id_Kota_Langsung_Sumber']
            if any(value(cells.get(i)) not in (None,'') for i in range(28,36)):
                deferred.append(rid);continue
            move.append((level,source));sd.remove(row);counts[level]+=1
        moved_ids={r['Id_Sumber'] for _,r in move}
        assert set(pending)<=moved_ids|already|set(deferred),'Pending record missing from expected sheets'
        replacements={};ranges={};valid_counts={}
        if move:
            for i,row in enumerate(sd,1):
                row.set('r',str(i))
                for c in row:c.set('r',re.sub(r'\d','',c.get('r'))+str(i))
            end=len(sd)
            for key in ['dimension','autoFilter']:data.find('m:'+key,NS).set('ref',f'A1:AI{end}')
            dv=data.find('m:dataValidations',NS)
            for validation in dv if dv is not None else []:
                refs=[]
                for area in validation.get('sqref').split():
                    minc,minr,maxc,maxr=range_boundaries(area)
                    assert minr==2 and maxr==old_last
                    refs.append(f'{get_column_letter(minc)}2:{get_column_letter(maxc)}{end}')
                validation.set('sqref',' '.join(refs))
            replacements['xl/worksheets/sheet14.xml']=E.tostring(data);ranges[13]=('AI',end)
        for level in range(4):
            additions=[r for lev,r in move if lev==level]
            pending_here={rid for rid in already|moved_ids if rid in pending and pending[rid][0]==level}
            valid_counts[level]=len(pending_here)
            if not additions:continue
            name=f'xl/worksheets/sheet{level+4}.xml';tree=E.fromstring(z.read(name));rows=tree.find('m:sheetData',NS)
            existing={value(next(c for c in r if re.sub(r'\d','',c.get('r'))=='B')) for r in list(rows)[1:]}
            assert not existing&moved_ids
            assert len(rows[0])==12
            template=rows[1] if len(rows)>1 else [];colstyles={column_index_from_string(re.sub(r'\d','',c.get('r'))):c.get('s') for c in template}
            for source in additions:
                number=len(rows)+1;row=E.SubElement(rows,TAG+'row',r=str(number))
                for col,v in enumerate(valid_client_row(source),1):
                    if v is None:continue
                    c=E.SubElement(row,TAG+'c',r=get_column_letter(col)+str(number))
                    if colstyles.get(col) is not None:c.set('s',colstyles[col])
                    put(c,v)
                    if col==5 or col>=9:wrap(c)
            for key in ['dimension','autoFilter']:
                element=tree.find('m:'+key,NS)
                if element is not None:element.set('ref','A1:L'+str(len(rows)))
            replacements[name]=E.tostring(tree);ranges[level+3]=('L',len(rows))
        # Remove review suggestions for records now listed as valid region data.
        hidden=moved_ids|already
        raw=z.read('xl/worksheets/sheet15.xml')
        start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        mapping=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:])
        content=BytesIO();kept=0;removed=0
        with z.open('xl/worksheets/sheet15.xml') as f:
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                cells={re.sub(r'\d','',c.get('r')):c for c in row}
                if row.get('r')=='1':content.write(E.tostring(row))
                elif value(cells.get('B')) in hidden:removed+=1
                else:
                    kept+=1;row.set('r',str(kept+1))
                    for c in row:c.set('r',re.sub(r'\d','',c.get('r'))+str(kept+1))
                    content.write(E.tostring(row))
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
        if removed:
            for key in ['dimension','autoFilter']:mapping.find('m:'+key,NS).set('ref','A1:L'+str(kept+1))
            replacements['xl/worksheets/sheet15.xml']=E.tostring(mapping).replace(b'<sheetData/>',b'<sheetData>'+content.getvalue()+b'</sheetData>')
            ranges[14]=('L',kept+1)
        # Existing summary columns retain their meaning as record counts; the new
        # column explicitly shows which valid-region records still await a primary ID.
        summary=E.fromstring(z.read('xl/worksheets/sheet2.xml'));ss=summary.find('m:sheetData',NS);sh={re.sub(r'\d','',c.get('r')):c for c in ss[0]}
        if 'I' in sh:assert value(sh['I'])=='Valid_Menunggu_ID_Utama'
        else:
            c=E.SubElement(ss[0],TAG+'c',r='I1');c.set('s',sh['H'].get('s','0'));put(c,'Valid_Menunggu_ID_Utama');wrap(c)
            E.SubElement(summary.find('m:cols',NS),TAG+'col',min='9',max='9',width='32',customWidth='1')
        labels=list(OBJECT_LABELS.values())
        for row in list(ss)[1:]:
            cells={re.sub(r'\d','',c.get('r')):c for c in row};level=labels.index(value(cells['A']))
            if counts[level]:
                put(cells['C'],int(value(cells['C']))+counts[level]);put(cells['H'],int(value(cells['H']))-counts[level])
                assert value(cells['H'])>=0
            cell=cells.get('I')
            if cell is None:cell=E.SubElement(row,TAG+'c',r='I'+row.get('r'))
            if cells['H'].get('s'):cell.set('s',cells['H'].get('s'))
            put(cell,valid_counts[level])
        summary.find('m:dimension',NS).set('ref','A1:I'+str(len(ss)))
        af=summary.find('m:autoFilter',NS)
        if af is not None:af.set('ref','A1:I'+str(len(ss)))
        if E.tostring(summary)!=z.read('xl/worksheets/sheet2.xml'):
            replacements['xl/worksheets/sheet2.xml']=E.tostring(summary);ranges[1]=('I',len(ss))
        wb=E.fromstring(z.read('xl/workbook.xml'));names=wb.find('m:definedNames',NS)
        for name in names if names is not None else []:
            if name.get('name')=='_xlnm._FilterDatabase' and int(name.get('localSheetId','-1')) in ranges:
                col,last=ranges[int(name.get('localSheetId'))];name.text=name.text.rsplit('!',1)[0]+'!$A$1:$'+col+'$'+str(last)
        if ranges:replacements['xl/workbook.xml']=E.tostring(wb)
        if added_style:xfs.set('count',str(len(xfs)));replacements['xl/styles.xml']=E.tostring(styles)
        with tempfile.NamedTemporaryFile(prefix='region-classification-',suffix='.xlsx',dir=workbook.parent,delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'enabled':True,'moved':len(move),'moved_by_sheet':{VALID_SHEETS[i]:counts[i] for i in range(4)},
            'moved_ids':[r['Id_Sumber'] for _,r in move],'deferred_client_inputs':deferred,
            'valid_waiting_primary':sum(valid_counts.values()),'data_rows_before':before_rows,
            'data_rows_after':before_rows-len(move),'mapping_rows_after':kept,'mapping_rows_removed':removed}
