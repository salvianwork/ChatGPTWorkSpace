"""Move verified comma-qualified names to same-ID rename proposals in Daikin."""
import argparse,csv,hashlib,json,re,shutil,tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string,get_column_letter,range_boundaries
from daikin_parent_review import NS,TAG


def rename_values(v,path):
    assert len(v)==23 and not any(v[16:])
    parts=path.split(' | ')
    return [v[0],v[1],v[2],parts[-1],v[4],v[3],parts[-2],v[3],v[6],v[6],path,'Nama',
            'Nama sebelum koma sesuai master dan keterangan setelah koma cocok dengan Parent yang tercatat. '
            'Pertahankan ID ini; cukup ubah nama menjadi '+parts[-1]+'. Parent sudah sesuai. '
            'Usulan menunggu konfirmasi Tim Daikin.',None,None,None,None,None,None,None]


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    with (pipeline/'03_Manual_Review/Review_candidates.csv').open(encoding='utf-8-sig',newline='') as f:
        choices=[r for r in csv.DictReader(f) if r['ID_Explanation'].startswith('Nama sebelum koma sesuai master')]
    candidates={r['Source_Id']:r for r in choices}
    assert len(choices)==len(candidates)
    with (pipeline/'04_Master_Targets/Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        inventory={r['Master_Path']:r for r in csv.DictReader(f)}
    before_hash=hashlib.sha256(workbook.read_bytes()).hexdigest();shutil.copy2(workbook,backup)
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
            if value is None:return
            if isinstance(value,int):E.SubElement(c,TAG+'v').text=str(value)
            else:c.set('t','inlineStr');E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t').text=value
        def col(c):return column_index_from_string(re.sub(r'\d','',c.get('r')))
        def values(row,width):
            cells={col(c):c for c in row}
            return [val(cells.get(i)) for i in range(1,width+1)]
        def iterrows(index):
            with z.open(f'xl/worksheets/sheet{index}.xml') as f:
                for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                    yield row
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        protected_paths=set()
        for row in iterrows(11):
            v=values(row,14)
            if row.get('r')!='1' and any(v[6:13]):protected_paths.add(v[2])
        moved={};deferred=[]
        for row in iterrows(14):
            v=values(row,23);rid=v[1]
            if rid not in candidates:continue
            c=candidates[rid];path=c['Candidate_Path'];inv=inventory[path]
            assert c['Candidate_Target_Id']==rid and c['ID_Verification']=='ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'
            assert v[2]==c['Source_Name'] and v[12]==path and v[11]==c['Candidate_Name']
            assert not inv['Target_Id'] and not inv['Master_Sheet_Id']
            assert inv['Parent_Target_Id']==v[3] and v[3]
            if any(v[16:]) or path in protected_paths:deferred.append(rid);continue
            moved[rid]=v
        assert 'a1pJ40000008X0WIAU' in moved
        paths={candidates[rid]['Candidate_Path'] for rid in moved};counts=Counter(v[0] for v in moved.values())
        replacements={};lengths={};removed_new=Counter();removed_mapping=0
        for index,width,lastcol in [(14,23,'W'),(11,14,'N'),(15,12,'L')]:
            entry=f'xl/worksheets/sheet{index}.xml';raw=z.read(entry)
            start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
            meta=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);body=BytesIO();n=0
            for row in iterrows(index):
                v=values(row,width);header=row.get('r')=='1'
                remove=not header and ((index in (14,15) and v[1] in moved) or (index==11 and v[2] in paths))
                if remove:
                    if index==11:assert not any(v[6:13]);removed_new[v[0]]+=1
                    if index==15:removed_mapping+=1
                    continue
                n+=1;row.set('r',str(n))
                for c in row:c.set('r',get_column_letter(col(c))+str(n))
                serialized=E.tostring(row)
                for decl in [b' xmlns="'+NS['m'].encode()+b'"',b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"']:
                    serialized=serialized.replace(decl,b'',1)
                body.write(serialized)
            for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:{lastcol}{n}')
            for dv in meta.findall('m:dataValidations/m:dataValidation',NS):
                areas=[]
                for area in dv.get('sqref').split():
                    minc,minr,maxc,maxr=range_boundaries(area)
                    areas.append(f'{get_column_letter(minc)}{minr}:{get_column_letter(maxc)}{n}')
                dv.set('sqref',' '.join(areas))
            replacements[entry]=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
            lengths[index]=n
        for label,index in [('Kecamatan',9),('Kelurahan',10)]:
            adds=[rename_values(v,candidates[rid]['Candidate_Path']) for rid,v in moved.items() if v[0]==label]
            if not adds:continue
            entry=f'xl/worksheets/sheet{index}.xml';root=E.fromstring(z.read(entry));rows=root.find('m:sheetData',NS)
            assert len(values(rows[0],20))==20 and val(rows[0][1])=='Id Salesforce'
            for fields in adds:
                number=len(rows)+1;row=E.SubElement(rows,TAG+'row',r=str(number),spans='1:20')
                for i,value in enumerate(fields,1):
                    style=18 if i==20 else 17 if i>=14 else 2 if i in {4,7,8,10} else 6
                    cell=E.SubElement(row,TAG+'c',r=get_column_letter(i)+str(number),s=str(style));put(cell,value)
            n=len(rows)
            for key in ['dimension','autoFilter']:root.find('m:'+key,NS).set('ref',f'A1:T{n}')
            for dv in root.findall('m:dataValidations/m:dataValidation',NS):
                areas=[]
                for area in dv.get('sqref').split():
                    minc,minr,maxc,maxr=range_boundaries(area)
                    areas.append(f'{get_column_letter(minc)}{minr}:{get_column_letter(maxc)}{n}')
                dv.set('sqref',' '.join(areas))
            replacements[entry]=E.tostring(root);lengths[index]=n
        summary=E.fromstring(z.read('xl/worksheets/sheet2.xml'))
        for row in list(summary.find('m:sheetData',NS))[1:]:
            cells={col(c):c for c in row};obj=val(cells[1]);n=counts[obj]
            if n:put(cells[4],val(cells[4])+n);put(cells[7],val(cells[7])-n)
            if removed_new[obj]:put(cells[5],val(cells[5])-removed_new[obj])
        replacements['xl/worksheets/sheet2.xml']=E.tostring(summary)
        wb=E.fromstring(z.read('xl/workbook.xml'));names=[s.get('name') for s in wb.find('m:sheets',NS)]
        assert len(names)==15
        endpoints={'DATA BELUM JELAS':('W',14),'CALON DATA BARU':('N',11),'PILIHAN MAPPING':('L',15),
                   'PERUBAHAN KECAMATAN':('T',9),'PERUBAHAN KELURAHAN':('T',10)}
        for d in wb.findall('m:definedNames/m:definedName',NS):
            name=names[int(d.get('localSheetId'))]
            if d.get('name')=='_xlnm._FilterDatabase' and name in endpoints:
                endcol,index=endpoints[name]
                if index in lengths:d.text=f"'{name}'!$A$1:${endcol}${lengths[index]}"
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
    return {'before_sha256':before_hash,'moved_ids':list(moved),'rename_count':len(moved),
            'by_object':dict(counts),'deferred_review_inputs':deferred,'removed_new_locations':dict(removed_new),
            'removed_mapping_rows':removed_mapping,'sheet_data_rows':{str(i):n-1 for i,n in lengths.items()}}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['workbook','pipeline','backup']:p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--report',type=Path);args=p.parse_args();r=apply(args.workbook,args.pipeline,args.backup)
    if args.report:args.report.write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print(json.dumps(r,ensure_ascii=False,indent=2))
