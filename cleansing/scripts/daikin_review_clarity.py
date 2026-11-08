"""Apply province/parenthesized-name corrections and clarify review wording/statuses."""
import argparse,csv,hashlib,json,re,shutil,tempfile
from collections import Counter,defaultdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string,get_column_letter
from daikin_parent_review import NS,TAG
from daikin_relation_rows import relationship_status
from regional_matching import normalize,province_name_forms
from regional_client_display import client_candidate,NO_EXACT_WITH_CANDIDATES


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def candidate_view(r):
    fields={'ID_Verification':'Status_Verifikasi_ID','Candidate_Target_Id':'Id_Target_Kandidat',
            'Unverified_Master_ID':'ID_Master_Perlu_Verifikasi','Candidate_Name':'Nama_Kandidat',
            'Candidate_Path':'Hierarki_Kandidat','Reason':'Alasan','Review_Kind':'Jenis_Rekomendasi',
            'Source_Id':'Id_Sumber','Parent_Action_Note':'Petunjuk_Perbaikan_Wilayah',
            'Parent_Action_Required':'Perlu_Perbaikan_Wilayah','Client_ID_Note':'Penjelasan_ID_Client',
            'ID_Explanation':'Alasan_Verifikasi_ID'}
    d={out:r.get(key,'') for key,out in fields.items()}
    d.update(Jenis_Bukti='KANDIDAT_OBJEK_SAMA',Tingkat_Ditemukan='Kecamatan' if r['Object']=='Kecamatan__c' else 'Kelurahan')
    return [v.replace('Client','Tim Daikin').replace('client','Tim Daikin') if isinstance(v,str) else v for v in client_candidate(d)]


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    raw=csv_rows(pipeline/'03_Manual_Review/Review_candidates.csv')
    bysource=defaultdict(list);aliases={}
    for r in raw:
        bysource[r['Source_Id']].append(r)
        if 'alias dalam tanda kurung' in r['Reason']:
            assert r['Source_Id'] not in aliases;aliases[r['Source_Id']]=r
    province_names=[r['Master_Path'] for r in csv_rows(pipeline/'04_Master_Targets/Master_target_inventory.csv') if r['Object']=='Provinsi__c']
    sf_provinces=csv_rows(pipeline/'05_All_Records/Provinsi_all_records.csv')
    before_sha=hashlib.sha256(workbook.read_bytes()).hexdigest();shutil.copy2(workbook,backup)
    with ZipFile(backup) as z:
        strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))]
        def val(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            v=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(v)]
            return int(v) if v and v.isdigit() and c.get('t') is None else v
        def put(c,value):
            for child in list(c):c.remove(child)
            c.attrib.pop('t',None)
            if value is None or value=='':return
            if isinstance(value,int):E.SubElement(c,TAG+'v').text=str(value)
            else:c.set('t','inlineStr');E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t').text=value
        def col(c):return column_index_from_string(re.sub(r'\d','',c.get('r')))
        def values(row,width):
            cells={col(c):c for c in row};return [val(cells.get(i)) for i in range(1,width+1)]
        def rows(index):
            with z.open(f'xl/worksheets/sheet{index}.xml') as f:
                for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                    yield row
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        def encode(row):
            raw=E.tostring(row)
            for decl in [b' xmlns="'+NS['m'].encode()+b'"',b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"']:
                raw=raw.replace(decl,b'',1)
            return raw
        def metadata(index):
            raw=z.read(f'xl/worksheets/sheet{index}.xml');start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
            return E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:])
        replacements={};alias_views={};province_hits={};source_values={};data_changes=0
        body=BytesIO()
        for row in rows(14):
            if row.get('r')!='1':
                v=values(row,23);rid=v[1];cells={col(c):c for c in row}
                if rid in aliases:
                    r=aliases[rid];assert r['Source_Name']==v[2]
                    assert r['Candidate_Path'].rsplit(' | ',1)[0]==v[5]
                    assert not any(v[16:]),'Protect existing review answers before changing a recommendation'
                    view=candidate_view(r);assert view[2]!=rid,'Do not introduce self-recommendations into DATA BELUM JELAS'
                    alias_views[rid]=view;source_values[rid]=v[:3]
                    for i,new in enumerate(view,12):
                        if val(cells.get(i))!=(new or None):data_changes+=1
                        if i not in cells:cells[i]=E.SubElement(row,TAG+'c',r=get_column_letter(i)+row.get('r'),s='6')
                        put(cells[i],new)
                    row[:]=sorted(list(row),key=col)
                elif v[0]=='Kota/Kabupaten' and (v[11] or v[13]) and not bysource.get(rid):
                    matched=[name for name in province_names if normalize(v[2],0) in province_name_forms(name)]
                    if len(matched)==1:
                        assert not any(v[16:]);province=matched[0]
                        sf=[r['Source_Name'] for r in sf_provinces if r['Target_Provinsi']==province]
                        assert len(sf)==1
                        province_hits[rid]=(province,sf[0]);source_values[rid]=v[:3]
                        for i in range(12,17):
                            if i in cells:put(cells[i],None)
                        put(cells[10],f'Nama {v[2]} sesuai nama provinsi {province}. Konfirmasikan tingkat wilayah dan lokasi sebelum memilih ID kota/kabupaten.')
                        cross=v[10] or '• Hasil Master:\n\n• Hasil Salesforce:\n\n• Tindak Lanjut:\n  Pastikan tingkat wilayah, lokasi, dan provinsinya sebelum memilih ID akhir.'
                        for title,line in [('• Hasil Master:',f'  - Provinsi: {province}'),('• Hasil Salesforce:',f'  - Provinsi: {sf[0]} — perlu dikonfirmasi')]:
                            if line not in cross:cross=cross.replace(title+'\n',title+'\n'+line+'\n',1)
                        if 11 not in cells:cells[11]=E.SubElement(row,TAG+'c',r='K'+row.get('r'),s='6')
                        put(cells[11],cross);row[:]=sorted(list(row),key=col)
            body.write(encode(row))
        assert 'a1pJ40000008XNrIAM' in alias_views and 'a1ofC000000MuErQAK' in province_hits
        meta=metadata(14);replacements['xl/worksheets/sheet14.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        samelevel_sources=set(alias_views)
        for row in rows(15):
            if row.get('r')=='1':continue
            v=values(row,12)
            if v[1] not in province_hits and v[5] and v[7]!='Nama ditemukan di tingkat lain':samelevel_sources.add(v[1])
        body=BytesIO();n=0;orders=Counter();inserted=set();removed=0;labels=0
        affected=set(alias_views)|set(province_hits)
        def append_new(fields):
            nonlocal n
            n+=1;row=E.Element(TAG+'row',r=str(n),spans='1:12')
            for i,value in enumerate(fields,1):
                c=E.SubElement(row,TAG+'c',r=get_column_letter(i)+str(n),s='6');put(c,value)
            body.write(encode(row))
        for row in rows(15):
            header=row.get('r')=='1';v=values(row,12);rid=v[1]
            if not header and rid in affected and rid not in inserted:
                inserted.add(rid);identity=source_values[rid]
                if rid in alias_views:
                    orders[rid]+=1
                    append_new(identity+[str(orders[rid])]+alias_views[rid]+['Master',identity[0],None])
                else:
                    province,sfname=province_hits[rid]
                    for origin,name in [('Master',province),('Ekspor Salesforce',sfname)]:
                        orders[rid]+=1
                        append_new(identity+[str(orders[rid]),name,name,None,'Nama ditemukan di tingkat lain',
                                   f'Nama {identity[2]} sesuai nama inti provinsi {province}. Tingkat wilayah dan lokasi perlu dikonfirmasi.',origin,'Provinsi','1'])
            samelevel=not header and v[5] and v[7]!='Nama ditemukan di tingkat lain'
            if not header and rid in affected and samelevel:removed+=1;continue
            cells={col(c):c for c in row}
            if not header and rid in samelevel_sources and v[7] in {'Nama belum ditemukan',NO_EXACT_WITH_CANDIDATES[0]}:
                put(cells[8],NO_EXACT_WITH_CANDIDATES[0]);put(cells[9],NO_EXACT_WITH_CANDIDATES[1].replace('Client','Tim Daikin').replace('client','Tim Daikin'));labels+=1
            if not header and rid in affected:
                orders[rid]+=1;put(cells[4],str(orders[rid]))
            n+=1;row.set('r',str(n))
            for c in row:c.set('r',get_column_letter(col(c))+str(n))
            body.write(encode(row))
        assert inserted==affected
        meta=metadata(15)
        for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:L{n}')
        replacements['xl/worksheets/sheet15.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        parent_body=BytesIO();statuses=Counter();dependency=0
        for row in rows(16):
            if row.get('r')!='1':
                v=values(row,19);cells={col(c):c for c in row};new=relationship_status(v[7],v[11]);put(cells[12],new);statuses[new]+=1
                if v[7] and v[11]=='Parent masih perlu dikonfirmasi':
                    dependency+=1
                    put(cells[13],'ID relasi usulan pada baris ini sudah tersedia. Hubungan lain pada ID data yang sama masih perlu dikonfirmasi; periksa baris terkait.\n\n'+v[12])
            parent_body.write(encode(row))
        replacements['xl/worksheets/sheet16.xml']=E.tostring(metadata(16)).replace(b'<sheetData/>',b'<sheetData>'+parent_body.getvalue()+b'</sheetData>')
        wb=E.fromstring(z.read('xl/workbook.xml'))
        for d in wb.findall('m:definedNames/m:definedName',NS):
            if d.text.startswith("'PILIHAN MAPPING'!"):d.text=f"'PILIHAN MAPPING'!$A$1:$L${n}"
        replacements['xl/workbook.xml']=E.tostring(wb)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for entry in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):refs+=len(re.findall(rb'<c\b[^>]*\bt="s"',replacements.get(entry,z.read(entry))))
        if int(shared.get('count'))!=refs:shared.set('count',str(refs));replacements['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'before_sha256':before_sha,'alias_ids':list(alias_views),'province_ids':list(province_hits),
            'alias_record_count':len(alias_views),'alias_changed_cells':data_changes,'province_records':len(province_hits),
            'removed_mapping_candidates':removed,'mapping_rows':n-1,'clarified_no_exact_rows':labels,
            'parent_status_counts':dict(statuses),'parent_dependency_notes':dependency}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['workbook','pipeline','backup']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--report',type=Path);args=p.parse_args();r=apply(args.workbook,args.pipeline,args.backup)
    if args.report:args.report.write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print(json.dumps(r,ensure_ascii=False,indent=2))
