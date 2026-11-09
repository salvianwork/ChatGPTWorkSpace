"""Separate same-ID Parent repair proposals in the Daikin workbook, without approval."""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
import csv,hashlib,json,re,shutil,tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import get_column_letter,column_index_from_string

TITLE='PERBAIKAN PARENT - ID TETAP'
DATA_HEADERS=['Objek','Id Sumber','Nama Sumber','Id Parent Sekarang','Nama Parent Dalam Ekspor',
              'Hierarki Parent Yang Teridentifikasi','Id Kota Langsung Sekarang','Hierarki Kota Langsung',
              'Status Sederhana','Alasan Belum Jelas','Temuan Pada Tingkat Lain','Jumlah Rekomendasi Ditampilkan',
              'Rekomendasi 1 Nama','Rekomendasi 1 Lokasi','Rekomendasi 1 ID Salesforce','Rekomendasi 1 Status',
              'Rekomendasi 1 Catatan','Keputusan Tim Daikin','Id Target Final Tim Daikin','Nama Final Tim Daikin',
              'Id Parent Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']
HEADERS=['Objek','Id Data','Nama Data','Jenis Parent','Id Parent Sekarang','Nama Parent Dalam Ekspor',
         'Lokasi Parent Dari Pencocokan','Id Parent Usulan','Nama Parent Usulan','Id Kota Langsung Sekarang',
         'Lokasi Kota Dari Pencocokan','Id Kota Langsung Usulan','Nama Kota Langsung Usulan','Lokasi Rekomendasi Untuk Review',
         'Jenis Perbaikan','Status Review','Catatan Perbaikan','Temuan Pada Tingkat Lain','Keputusan Tim Daikin',
         'Id Parent Final Tim Daikin','Id Kota Langsung Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']
STATUS='Menunggu konfirmasi Tim Daikin'
OBJECTS={'Kecamatan':'Kecamatan__c','Kelurahan':'Kelurahan__c'}
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};TAG='{'+NS['m']+'}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
APP={'a':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties',
     'v':'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'}


def assess(row,candidates,targets):
    """Return a proposal only; ID equality never approves a repair or selects a new ID."""
    rid=row['Id Sumber']
    if not rid or row['Rekomendasi 1 ID Salesforce']!=rid:return None,'different_or_missing_id'
    matching=[c for c in candidates if (c['Id_Target_Kandidat'] or c['ID_Master_Perlu_Verifikasi'])==rid
              and c['Hierarki_Kandidat']==row['Rekomendasi 1 Lokasi']]
    if not matching:raise ValueError(f'{rid}: pipeline and workbook recommendations differ')
    candidate=matching[0]
    path=tuple(candidate['Hierarki_Kandidat'].split(' | '))
    if (row['Objek'] not in OBJECTS or candidate['Objek']!=OBJECTS[row['Objek']]
            or len(path)!={'Kecamatan':3,'Kelurahan':4}[row['Objek']]):return None,'different_level'
    assert candidate['Nama_Kandidat']==row['Rekomendasi 1 Nama']==path[-1]
    multiple=len({c['Hierarki_Kandidat'] for c in candidates})>1
    name_changed=row['Nama Sumber']!=candidate['Nama_Kandidat']
    # Ambiguous locations move to the same-ID queue, without selecting a Parent.
    parent='' if multiple else targets.get(path[:-1],'')
    city='' if multiple else targets.get(path[:2],'') if len(path)==4 else ''
    unknown=not parent or (len(path)==4 and not city)
    current=row['Id Parent Sekarang'] or '';direct=row['Id Kota Langsung Sekarang'] or ''
    actions=[]
    if multiple:actions.append('Konfirmasi lokasi dan Parent')
    else:
        if not parent:actions.append('Konfirmasi ID Parent')
        elif current!=parent:actions.append('Lengkapi Parent' if not current else 'Ubah Parent')
        if len(path)==4:
            if not city:actions.append('Konfirmasi ID kabupaten/kota langsung')
            elif direct!=city:
                actions.append('Lengkapi kabupaten/kota langsung' if not direct else 'Ubah kabupaten/kota langsung')
    if name_changed:actions.append('Konfirmasi nama data')
    if not actions:actions.append('Periksa hubungan Parent')
    if any(row[h] not in (None,'') for h in DATA_HEADERS[17:]):return None,'existing_review_input'
    if multiple:status='Lokasi dan Parent masih perlu dikonfirmasi';reason='multiple_locations'
    elif unknown:
        status='Nama dan Parent masih perlu dikonfirmasi' if name_changed else 'Parent masih perlu dikonfirmasi'
        reason='parent_id_unknown'
    elif name_changed:status='Nama masih perlu dikonfirmasi';reason='name_also_changes'
    elif actions==['Periksa hubungan Parent']:status='Parent masih perlu dikonfirmasi';reason='no_parent_change'
    else:status=STATUS;reason='eligible'
    return {'source_id':rid,'path':path,'parent_id':parent,'city_id':city,'actions':actions,
            'multiple':multiple,'name_changed':name_changed,
            'candidate_count':len({c['Hierarki_Kandidat'] for c in candidates}),'status':status},reason


def proposal_values(row,plan):
    path=plan['path'];note=row['Rekomendasi 1 Catatan'] or ''
    prefix='ID ini sama dengan ID sumber. Hubungan wilayah masih perlu diperiksa.'
    if note.startswith(prefix):note=note[len(prefix):].lstrip()
    remarks=['ID data diusulkan tetap. Perubahan menunggu keputusan Tim Daikin.']
    if plan['multiple']:
        remarks.append(f"Ada {plan['candidate_count']} rekomendasi lokasi. Lokasi pada kolom sebelah adalah rekomendasi pertama dan masih perlu dikonfirmasi. ID serta nama Parent usulan dikosongkan sampai lokasi dipastikan. Rincian seluruh pilihan tersedia pada PILIHAN MAPPING. ID dalam catatan lama hanya untuk pemeriksaan.")
    elif not plan['parent_id'] or (len(path)==4 and not plan['city_id']):
        remarks.append('ID Parent yang belum dapat dipastikan dibiarkan kosong. Pastikan hubungan wilayah sebelum mengisi ID final.')
    if plan['name_changed']:
        remarks.append(f"Nama saat ini: {row['Nama Sumber']}. Nama pada rekomendasi pertama: {row['Rekomendasi 1 Nama']}. Konfirmasi sebelum mengubah nama.")
    if note:remarks.append('Catatan rekomendasi pertama (perlu dikonfirmasi):\n'+note)
    note='\n\n'.join(remarks)
    return [row['Objek'],row['Id Sumber'],row['Nama Sumber'],
            'Kecamatan' if len(path)==4 else 'Kabupaten/kota',row['Id Parent Sekarang'],
            row['Nama Parent Dalam Ekspor'],row['Hierarki Parent Yang Teridentifikasi'],plan['parent_id'] or None,
            None if plan['multiple'] else path[-2],
            row['Id Kota Langsung Sekarang'],row['Hierarki Kota Langsung'],plan['city_id'] or None,
            path[1] if len(path)==4 and not plan['multiple'] else None,' | '.join(path),'; '.join(plan['actions']),plan['status'],
            note,row['Temuan Pada Tingkat Lain'],None,None,None,None,None,None]


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Choose a new backup path'
    groups=defaultdict(list)
    for c in read_csv(pipeline/'03_Manual_Review'/'Review_candidates.csv'):
        if c['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':groups[c['Id_Sumber']].append(c)
    inventory=read_csv(pipeline/'04_Master_Targets'/'Master_target_inventory.csv')
    targets={tuple(r['Hierarki_Master'].split(' | ')):r['Id_Target'] for r in inventory}
    sources={r['Id_Sumber']:r for prefix in ['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']
             for r in read_csv(pipeline/'05_All_Records'/f'{prefix}_all_records.csv')}
    before_hash=hashlib.sha256(workbook.read_bytes()).hexdigest()
    shutil.copy2(workbook,backup)
    with ZipFile(backup) as z:
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));strings=[''.join(si.itertext()) for si in shared]
        def val(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            s=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(s)]
            return int(s) if s and s.isdigit() and c.get('t') is None else s
        def put(c,value):
            for child in list(c):c.remove(child)
            c.attrib.pop('t',None)
            if value is None or value=='':return
            if isinstance(value,int):E.SubElement(c,TAG+'v').text=str(value)
            else:
                c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t');t.text=value
                if value!=value.strip():t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        def col(c):return column_index_from_string(re.sub(r'\d','',c.get('r')))
        wb=E.fromstring(z.read('xl/workbook.xml'));sheet_list=wb.find('m:sheets',NS)
        names=[s.get('name') for s in sheet_list]
        existing=TITLE in names
        assert len(names)==(15 if existing else 14) and 'PERIKSA SEBELUM INSERT' not in names
        insert_at=names.index(TITLE) if existing else names.index('DATA BELUM JELAS')
        rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        byrel={r.get('Id'):r for r in rels}
        old_data_rel=byrel[sheet_list[names.index('DATA BELUM JELAS')].get(REL+'id')]
        data_entry='xl/'+old_data_rel.get('Target');assert data_entry=='xl/worksheets/sheet14.xml'
        types=E.fromstring(z.read('[Content_Types].xml'))
        if existing:new_entry='xl/'+byrel[sheet_list[insert_at].get(REL+'id')].get('Target')
        else:
            new_number=max(int(re.search(r'sheet(\d+)\.xml',p).group(1)) for p in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',p))+1
            new_entry=f'xl/worksheets/sheet{new_number}.xml'
            rid='rId'+str(max(int(r.get('Id')[3:]) for r in rels)+1)
            new_sheet=E.Element(TAG+'sheet',name=TITLE,sheetId=str(max(int(s.get('sheetId')) for s in sheet_list)+1))
            new_sheet.set(REL+'id',rid);sheet_list.insert(insert_at,new_sheet)
            E.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                         Id=rid,Type=REL[1:-1]+'/worksheet',Target=f'worksheets/sheet{new_number}.xml')
            E.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',
                         PartName='/'+new_entry,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
        styles=E.fromstring(z.read('xl/styles.xml'));xfs=styles.find('m:cellXfs',NS)
        inputs=deepcopy(xfs[5]);alignment=inputs.find('m:alignment',NS)
        if alignment is None:alignment=E.SubElement(inputs,TAG+'alignment')
        alignment.set('vertical','top');alignment.set('wrapText','1');inputs.set('applyAlignment','1')
        input_style=17 if existing else len(xfs)
        if not existing:xfs.append(inputs)
        date=deepcopy(inputs);date.set('numFmtId','14');date.set('applyNumberFormat','1')
        date_style=18 if existing else len(xfs)
        if not existing:xfs.append(date);xfs.set('count',str(len(xfs)))
        new=E.Element(TAG+'worksheet',nsmap={None:NS['m']})
        dimension=E.SubElement(new,TAG+'dimension',ref='A1:X1')
        views=E.SubElement(new,TAG+'sheetViews');view=E.SubElement(views,TAG+'sheetView',workbookViewId='0')
        E.SubElement(view,TAG+'pane',xSplit='3',ySplit='1',topLeftCell='D2',activePane='bottomRight',state='frozen')
        E.SubElement(view,TAG+'selection',pane='bottomRight',activeCell='D2',sqref='D2')
        E.SubElement(new,TAG+'sheetFormatPr',defaultRowHeight='15')
        cols=E.SubElement(new,TAG+'cols')
        widths=[18,24,34,22,26,32,60,26,34,26,55,26,34,65,48,35,100,85,26,28,30,85,22,24]
        for i,width in enumerate(widths,1):
            style=date_style if i==24 else input_style if i>=19 else 2 if i in {8,9,12,13} else 6
            E.SubElement(cols,TAG+'col',min=str(i),max=str(i),width=str(width),customWidth='1',style=str(style))
        new_rows=E.SubElement(new,TAG+'sheetData')
        existing_count=0
        if existing:
            # Keep existing proposals, answers, formats, filters and pane settings.
            new=E.fromstring(z.read(new_entry));new_rows=new.find('m:sheetData',NS)
            dimension=new.find('m:dimension',NS);existing_count=len(new_rows)-1
            header_cells={col(c):c for c in new_rows[0]}
            previous=[val(header_cells.get(i)) for i in range(1,25)]
            assert previous[:13]+previous[14:]==HEADERS[:13]+HEADERS[14:]
            put(header_cells[14],HEADERS[13])
        def append(values):
            number=len(new_rows)+1;row=E.SubElement(new_rows,TAG+'row',r=str(number),spans='1:24')
            if number==1:row.set('ht','60');row.set('customHeight','1')
            for i,value in enumerate(values,1):
                style=3 if number==1 else date_style if i==24 else input_style if i>=19 else 2 if i in {8,9,12,13} else 6
                c=E.SubElement(row,TAG+'c',r=get_column_letter(i)+str(number),s=str(style));put(c,value)
        if not existing:append(HEADERS)
        raw=z.read(data_entry);assert re.search(rb'<f(?:\s|>)',raw) is None
        start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        metadata=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);kept=BytesIO()
        moved=[];reasons=Counter();counts=Counter();statuses=Counter();remaining=0;before_rows=0
        with z.open(data_entry) as f:
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                cells={col(c):c for c in row};number=int(row.get('r'))
                values=[val(cells.get(i)) for i in range(1,25)]
                if number==1:assert values==DATA_HEADERS;take=False
                else:
                    before_rows+=1;record=dict(zip(DATA_HEADERS,values))
                    plan,reason=assess(record,groups[record['Id Sumber']],targets);reasons[reason]+=1;take=plan is not None
                    if take:
                        source=sources[record['Id Sumber']]
                        assert source['Nama_Sumber']==record['Nama Sumber']
                        assert source['Id_Induk_Sumber']==(record['Id Parent Sekarang'] or '')
                        assert source['Id_Kota_Langsung_Sumber']==(record['Id Kota Langsung Sekarang'] or '')
                        for path,pid in [(plan['path'][:-1],plan['parent_id'])]+([(plan['path'][:2],plan['city_id'])] if len(plan['path'])==4 else []):
                            if not pid:continue
                            parent=sources[pid]
                            actual=tuple(parent[k] for k in ['Provinsi_Target','KotaKabupaten_Target','Kecamatan_Target','Kelurahan_Target'] if parent[k])
                            assert actual==path
                        append(proposal_values(record,plan));moved.append(plan);counts[record['Objek']]+=1;statuses[plan['status']]+=1
                if not take:
                    if number!=1:remaining+=1
                    newnum=1 if number==1 else remaining+1;row.set('r',str(newnum))
                    for c in row:c.set('r',re.sub(r'\d','',c.get('r'))+str(newnum))
                    serialized=E.tostring(row)
                    for decl in [b' xmlns="'+NS['m'].encode()+b'"',b' xmlns:r="'+REL[1:-1].encode()+b'"']:
                        serialized=serialized.replace(decl,b'',1)
                    kept.write(serialized)
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
        assert before_rows==remaining+len(moved) and len(moved)==len({m['source_id'] for m in moved})
        assert moved,'No records meet the proposed criteria'
        for key in ['dimension','autoFilter']:metadata.find('m:'+key,NS).set('ref',f'A1:X{remaining+1}')
        for dv in metadata.findall('m:dataValidations/m:dataValidation',NS):
            assert dv.get('sqref')==f'R2:R{before_rows+1}';dv.set('sqref',f'R2:R{remaining+1}')
        new_end=existing_count+len(moved)+1;dimension.set('ref',f'A1:X{new_end}')
        if existing:
            new.find('m:autoFilter',NS).set('ref',f'A1:X{new_end}')
            for dv in new.findall('m:dataValidations/m:dataValidation',NS):dv.set('sqref',f'S2:S{new_end}')
        else:
            E.SubElement(new,TAG+'autoFilter',ref=f'A1:X{new_end}')
            dvs=E.SubElement(new,TAG+'dataValidations',count='1')
            dv=E.SubElement(dvs,TAG+'dataValidation',type='list',allowBlank='1',showInputMessage='1',showErrorMessage='1',sqref=f'S2:S{new_end}')
            E.SubElement(dv,TAG+'formula1').text='"SETUJU_UBAH,TOLAK_PERUBAHAN,PERLU_DISKUSI"'
            E.SubElement(new,TAG+'pageMargins',left='0.7',right='0.7',top='0.75',bottom='0.75',header='0.3',footer='0.3')
        summary=E.fromstring(z.read('xl/worksheets/sheet2.xml'));srows=summary.find('m:sheetData',NS)
        expected_headers=['Objek','Jumlah Master','Sudah Benar','Perlu Diubah','Calon Data Baru','Duplikat','Data Lain Belum Jelas','Valid Menunggu ID Utama']
        assert [val(c) for c in srows[0]]==expected_headers+(['Perbaikan Parent ID Tetap'] if existing else [])
        if not existing:
            h=E.SubElement(srows[0],TAG+'c',r='I1',s='13');put(h,'Perbaikan Parent ID Tetap')
        for row in list(srows)[1:]:
            cells={col(c):c for c in row};obj=val(cells[1]);n=counts[obj]
            if n:put(cells[7],int(val(cells[7]))-n)
            if existing:put(cells[9],int(val(cells[9]))+n)
            else:
                cell=E.SubElement(row,TAG+'c',r='I'+row.get('r'),s='1');put(cell,n)
            row.set('spans','1:9')
        srows[0].set('spans','1:9')
        if not existing:E.SubElement(summary.find('m:cols',NS),TAG+'col',min='9',max='9',width='30',customWidth='1',style='6')
        for key in ['dimension','autoFilter']:summary.find('m:'+key,NS).set('ref','A1:I5')
        instructions=E.fromstring(z.read('xl/worksheets/sheet1.xml'));irows=instructions.find('m:sheetData',NS)
        put(irows[3][1],'Konfirmasi usulan pada lembar PERUBAHAN dan PERBAIKAN PARENT - ID TETAP. Pada sheet ID tetap, baca Status Review dan Catatan Perbaikan: Parent, lokasi, atau nama dapat masih perlu dipastikan. ID Parent usulan yang belum pasti dibiarkan kosong. Periksa usulan berwarna hijau, lalu isi keputusan dan kolom kuning setelah pemeriksaan. Perubahan menunggu persetujuan Tim Daikin.')
        put(irows[6][1],'DATA BELUM JELAS memuat kasus yang ID tujuannya berbeda atau belum tersedia. Semua kasus dengan ID rekomendasi sama dengan ID sumber dipisahkan ke PERBAIKAN PARENT - ID TETAP, termasuk bila Parent atau lokasi belum pasti. Ini bukan berarti datanya sudah valid. Rincian semua pilihan tetap tersedia pada PILIHAN MAPPING untuk kedua sheet. Workbook ini tidak menjalankan perubahan otomatis.')
        glossary=E.fromstring(z.read('xl/worksheets/sheet3.xml'));grow=glossary.find('m:sheetData',NS)[8]
        for c,value in zip(grow,['Perbaikan Parent ID Tetap','ID rekomendasi sama dengan ID sumber. Parent, lokasi, dan nama masih perlu diperiksa sesuai Status Review; belum otomatis valid.','Contoh: Hutagurgur (Huta Gurgur) diusulkan memakai ID yang sama, tetapi ID Parent Dolok Sanggul masih kosong sampai hubungan ke Kab. Humbang Hasundutan dipastikan.'],strict=True):put(c,value)
        defined=wb.find('m:definedNames',NS)
        for name in defined:
            index=int(name.get('localSheetId','-1'))
            if not existing and index>=insert_at:name.set('localSheetId',str(index+1))
            if name.get('name')=='_xlnm._FilterDatabase':
                if name.get('localSheetId')=='1':name.text="'RINGKASAN'!$A$1:$I$5"
                elif name.text.startswith("'DATA BELUM JELAS'!"):name.text=f"'DATA BELUM JELAS'!$A$1:$X${remaining+1}"
                elif existing and name.text.startswith(f"'{TITLE}'!"):name.text=f"'{TITLE}'!$A$1:$X${new_end}"
        if not existing:
            nf=E.SubElement(defined,TAG+'definedName',name='_xlnm._FilterDatabase',localSheetId=str(insert_at),hidden='1')
            nf.text=f"'{TITLE}'!$A$1:$X${new_end}"
        for view in wb.findall('m:bookViews/m:workbookView',NS):
            for attr in ['activeTab','firstSheet']:
                if not existing and view.get(attr) is not None and int(view.get(attr))>=insert_at:view.set(attr,str(int(view.get(attr))+1))
        app=E.fromstring(z.read('docProps/app.xml'));titles=app.find('a:TitlesOfParts/v:vector',APP)
        if not existing:
            item=E.Element('{'+APP['v']+'}lpstr');item.text=TITLE;titles.insert(insert_at,item);titles.set('size',str(len(titles)))
        heading=app.find('a:HeadingPairs/v:vector',APP)
        for i,item in enumerate(heading):
            if item.findtext('v:lpstr',namespaces=APP)=='Worksheets':heading[i+1].find('v:i4',APP).text=str(len(titles))
        replacements={data_entry:E.tostring(metadata).replace(b'<sheetData/>',b'<sheetData>'+kept.getvalue()+b'</sheetData>'),
                      new_entry:E.tostring(new),'xl/worksheets/sheet1.xml':E.tostring(instructions),
                      'xl/worksheets/sheet2.xml':E.tostring(summary),'xl/worksheets/sheet3.xml':E.tostring(glossary),
                      'xl/workbook.xml':E.tostring(wb),'xl/_rels/workbook.xml.rels':E.tostring(rels),
                      '[Content_Types].xml':E.tostring(types),'docProps/app.xml':E.tostring(app),'xl/styles.xml':E.tostring(styles)}
        shared_refs=0
        for entry in {n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n)}|{new_entry}:
            raw=replacements[entry] if entry in replacements else z.read(entry)
            shared_refs+=len(re.findall(rb'<c\b[^>]*\bt="s"',raw))
        shared.set('count',str(shared_refs));replacements['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(prefix='daikin-parent-',suffix='.xlsx',dir=workbook.parent,delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
                if not existing:out.writestr(new_entry,replacements[new_entry],compress_type=8)
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'backup':str(backup),'before_sha256':before_hash,'moved':len(moved),'moved_ids':[m['source_id'] for m in moved],
            'moved_by_object':dict(counts),'remaining_data_rows':remaining,'new_sheet':TITLE,'new_entry':new_entry,
            'screening_counts':dict(reasons),'new_headers':HEADERS,'new_status_counts':dict(statuses),
            'previous_parent_rows':existing_count,'total_parent_rows':existing_count+len(moved),'mapping_details_preserved':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',required=True,type=Path);parser.add_argument('--pipeline',required=True,type=Path)
    parser.add_argument('--backup',required=True,type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args();result=apply(args.workbook,args.pipeline,args.backup)
    if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='moved_ids'},ensure_ascii=False,indent=2))
