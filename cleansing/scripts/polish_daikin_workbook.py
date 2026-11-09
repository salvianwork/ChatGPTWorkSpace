"""Complete master evidence, simplify headers and repair Excel cell order/styles.

Post-merge stage. All source/target IDs, records, decisions and candidate order
stay intact. Cross-level evidence never assigns destination IDs automatically.
"""
import argparse,csv,hashlib,json,re,tempfile
from collections import Counter,defaultdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string,get_column_letter,range_boundaries
from daikin_review_readability import Package,NS,TAG,put,encode,row_height
from regional_matching import normalize
from regional_evidence import LEVELS,candidate_proof,rename_recommendation_label

SOURCE_LABELS={'Master':'• Hasil Master:','Ekspor Salesforce':'• Hasil Salesforce:'}
LEVEL_PREFIX=re.compile(r'^(Provinsi|Kota/Kabupaten|Kecamatan|Kelurahan):\s*')
STEP='Nama ditemukan pada tingkat wilayah yang berbeda. Pastikan tingkat wilayah, lokasi, dan provinsinya sebelum memilih ID akhir.'


def cross_sections(text):
    result=defaultdict(list);current=None
    for line in (text or '').splitlines():
        line=line.strip()
        if line in SOURCE_LABELS.values():current=next(k for k,v in SOURCE_LABELS.items() if v==line)
        elif line.startswith('• Tindak Lanjut:'):current=None
        elif current and line.startswith('- '):result[current].append(line[2:])
    return result


def master_part(path):
    clean=LEVEL_PREFIX.sub('',path).removesuffix(' — perlu dikonfirmasi')
    if clean.startswith('+') or clean=='Lokasi lengkap belum tersedia':return None
    return tuple(clean.split(' | '))


def clean_cross(text,master,variant_names=(),priority=()):
    """Keep Salesforce evidence as exported; render master paths without level prefixes."""
    sections=cross_sections(text);lines=[]
    if master:
        lines.append('• Hasil Master:')
        priorities={p:i for i,p in enumerate(priority)}
        for level in sorted(master):
            paths=sorted(master[level],key=lambda p:(priorities.get(p,10**6),p))
            for p in paths[:3]:lines.append('  - '+' | '.join(p))
            if len(paths)>3:lines.append(f'  - +{len(paths)-3} lokasi lainnya')
        if variant_names:lines.append('  Keterangan: variasi nama '+ '; '.join(variant_names)+'.')
    elif sections.get('Master'):
        lines.append('• Hasil Master:')
        lines.extend('  - '+LEVEL_PREFIX.sub('',v) for v in sections['Master'])
    if sections.get('Ekspor Salesforce'):
        if lines:lines.append('')
        lines.append('• Hasil Salesforce:')
        lines.extend('  - '+v for v in dict.fromkeys(LEVEL_PREFIX.sub('',v) for v in sections['Ekspor Salesforce']))
    if not lines:return None
    lines+=['','• Tindak Lanjut:','  '+STEP]
    return '\n'.join(lines)


def evidence_note(old,paths,source_level,target_name):
    """Show the full supporting hierarchy while keeping every ID-specific warning."""
    paths=list(dict.fromkeys(paths));lines=['• Struktur pada master:']
    bylevel=defaultdict(list)
    for p in paths:bylevel[len(p)-1].append(p)
    for level,items in sorted(bylevel.items()):
        lines.extend('  - '+' | '.join(p) for p in items[:3])
        if len(items)>3:lines.append(f'  - +{len(items)-3} lokasi lainnya')
    relation=LEVELS[source_level].lower()
    lines+=['','• Alasan rekomendasi:']
    if len(paths)==1:lines.append(f'  {paths[0][-1]} pada master merupakan {LEVELS[len(paths[0])-1].lower()}.')
    lines.append(f'  Data sumber tercatat sebagai {relation}. Rekomendasi {target_name} diambil dari {relation} pada struktur master tersebut.')
    # The old first paragraph repeats the same relationship in prose. Specific
    # ID warnings and instructions after that paragraph must remain intact.
    rest=old or ''
    if rest.startswith('• Struktur pada master:'):
        blocks=rest.split('\n\n',2)
        if len(blocks)>1 and blocks[1].startswith('• Alasan rekomendasi:'):
            rest=blocks[2] if len(blocks)>2 else ''
    marker='tingkat wilayahnya perlu diperbaiki.'
    if rest.startswith('Di master, ') and marker in rest:
        rest=rest.split(marker,1)[1].lstrip()
    if rest:lines+=['',rest]
    return '\n'.join(lines)


def load_inventory(pipeline):
    paths=set();index=[defaultdict(set) for _ in range(4)]
    with (pipeline/'04_Master_Targets/Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            p=tuple(r['Master_Path'].split(' | '));paths.add(p);index[len(p)-1][normalize(p[-1],len(p)-1)].add(p)
    proofs=defaultdict(list)
    with (pipeline/'03_Manual_Review/Review_candidates.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            p=candidate_proof(r)
            if p:
                assert p in paths,'Master proof must exist in the inventory'
                item=(p,tuple(r['Candidate_Path'].split(' | ')))
                if item not in proofs[r['Source_Id']]:proofs[r['Source_Id']].append(item)
    return paths,index,proofs


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Use a fresh backup path'
    all_master,index,proofs=load_inventory(pipeline);backup.write_bytes(workbook.read_bytes())
    report=Counter();replacement={};rows_by_sheet={};identity={};cross_old={};new_cross={};master_evidence={};variants={};note_proofs={}
    with ZipFile(backup) as z:
        a=Package(z);wb=E.fromstring(z.read('xl/workbook.xml'));sheets=wb.find('m:sheets',NS)
        assert len(sheets)==14 and 'PERBAIKAN PARENT - ID TETAP' not in [s.get('name') for s in sheets]
        # Physical sheet IDs remain stable after removing the old Parent sheet.
        for i in [8,9,10,14]:
            width=23 if i==14 else 19;source_rows=[]
            for row in a.rows(i):
                v=a.values(row,width)
                if row.get('r')=='1':continue
                rid=v[1];source_rows.append(v);identity.setdefault(rid,v[:3])
                text=v[10] if i==14 else v[12]
                if text:cross_old.setdefault(rid,text)
                if i==14:
                    destination=tuple((v[12] or '').split(' | '))
                    selected=[p for p,target in proofs.get(rid,[]) if target==destination]
                    if selected:note_proofs[rid]=selected
            rows_by_sheet[i]=source_rows
        # Reuse all actual master locations for exact names, plus supporting
        # paths the candidate engine already used (for example Buntok Kota).
        for rid,v in identity.items():
            if rid not in cross_old and rid not in proofs:continue
            source_level=LEVELS.index(v[0]);old_sections=cross_sections(cross_old.get(rid));found=defaultdict(set);priority=list(note_proofs.get(rid,[]))
            for value in old_sections.get('Master',[]):
                p=master_part(value)
                if p:
                    assert p in all_master,('Old master evidence absent from inventory',rid,p)
                    found[len(p)-1].add(p)
                    if p not in priority:priority.append(p)
            for level in range(4):
                if level!=source_level:found[level].update(index[level].get(normalize(v[2],level),set()))
            alias=[]
            for p,target in proofs.get(rid,[]):
                if len(p)-1==source_level:continue
                found[len(p)-1].add(p)
                if p not in priority:priority.append(p)
                if normalize(v[2],len(p)-1)!=normalize(p[-1],len(p)-1):
                    phrase=f'“{v[2]}” → “{p[-1]}”'
                    if phrase not in alias:alias.append(phrase)
            found={k:s for k,s in found.items() if s}
            if not found and not cross_old.get(rid):continue
            master_evidence[rid]=found;variants[rid]=alias
            new_cross[rid]=clean_cross(cross_old.get(rid),found,alias,priority)
            if proofs.get(rid):report['sources_with_supporting_master_proof']+=1
        # Update existing mapping evidence rather than duplicating the same
        # source/level, and append only missing informational Master rows.
        mapping=[];master_row_keys=set();orders=Counter()
        for row in a.rows(15):
            v=a.values(row,12);mapping.append(v)
            if row.get('r')=='1':continue
            rid=v[1];orders[rid]=max(orders[rid],int(v[3]))
            if v[9]=='Master' and v[7]=='Nama ditemukan di tingkat lain':
                level=LEVELS.index(v[10]);master_row_keys.add((rid,level))
                if rid in proofs and rid in master_evidence and level in master_evidence[rid]:
                    actual=master_evidence[rid][level]
                    old_examples=[tuple(p.split(' | ')) for p in (v[5] or '').split('; ') if p]
                    ordered=list(dict.fromkeys(old_examples+sorted(actual)))
                    assert set(old_examples)<=actual
                    v[5]='; '.join(' | '.join(p) for p in ordered[:5]);v[11]=str(len(actual))
                    if variants[rid]:
                        addition=' Variasi nama: '+'; '.join(variants[rid])+'.'
                        if addition not in v[8]:v[8]+=addition
        for rid in sorted(proofs):
            if rid not in master_evidence:continue
            for level,actual in master_evidence[rid].items():
                if (rid,level) in master_row_keys:continue
                orders[rid]+=1;names=sorted({p[-1] for p in actual})
                mapping.append(identity[rid]+[str(orders[rid]),names[0] if len(names)==1 else identity[rid][2],
                   '; '.join(' | '.join(p) for p in sorted(actual)[:5]),None,'Nama ditemukan di tingkat lain',
                   'Struktur master ini mendukung rekomendasi pada tingkat wilayah lain. ID tujuan tidak ditetapkan dari temuan ini.'+
                   (' Variasi nama: '+'; '.join(variants[rid])+'.' if variants[rid] else ''),
                   'Master',LEVELS[level],str(len(actual))])
                report['added_mapping_evidence_rows']+=1
        # Repair row/cell order everywhere and contain all formatting within the
        # table. Keep column widths, individual styles and validation behavior.
        for sheet in sheets:
            i=int(sheet.get('sheetId'));meta=a.metadata(i)
            original_cols=meta.findall('m:cols/m:col',NS);column_styles={}
            for col in original_cols:
                if col.get('style'):
                    for c in range(int(col.get('min')),int(col.get('max'))+1):column_styles[c]=col.get('style')
                    col.attrib.pop('style',None);report['cleared_whole_column_styles']+=1
            body=BytesIO();header_width=None;lastrow=0
            if i==15:
                def mapping_nodes():
                    for n,v in enumerate(mapping,1):
                        r=E.Element(TAG+'row',r=str(n))
                        for c,value in enumerate(v,1):put(r,c,value,3 if n==1 else 6)
                        yield r
                source=mapping_nodes()
            else:source=a.rows(i)
            for row in source:
                n=int(row.get('r'));lastrow=n
                if n==1:header_width=max(a.cells(row))
                rowstyle=row.get('s')
                if rowstyle:report['cleared_whole_row_styles']+=1
                row.attrib.pop('s',None);row.attrib.pop('customFormat',None)
                cells=a.cells(row);old_order=list(cells)
                if old_order!=sorted(old_order):report['repaired_cell_order_rows']+=1
                for cnum,cell in list(cells.items()):
                    assert int(re.search(r'\d+',cell.get('r'))[0])==n,'Cell belongs to a different row'
                    if cnum>header_width:
                        assert a.val(cell) in (None,''),'Do not remove data outside the table'
                        row.remove(cell);report['removed_outside_cells']+=1;continue
                    if cell.get('s') is None and (rowstyle or column_styles.get(cnum)):
                        cell.set('s',rowstyle or column_styles[cnum])
                    value=a.val(cell);renamed=rename_recommendation_label(value)
                    if renamed!=value:put(row,cnum,renamed);report['renamed_label_cells']+=1
                if i in [8,9,10,14] and n>1:
                    width=23 if i==14 else 19;v=a.values(row,width);rid=v[1];cross_col=11 if i==14 else 13
                    if rid in new_cross and v[cross_col-1]!=(new_cross[rid] or None):
                        put(row,cross_col,new_cross[rid],6);report['updated_cross_level_cells']+=1
                    if i==14 and rid in note_proofs:
                        note=evidence_note(v[15],note_proofs[rid],LEVELS.index(v[0]),v[11])
                        if note!=v[15]:
                            put(row,16,note,6);report['updated_recommendation_notes']+=1
                    widths=[float(c.get('width','25')) for c in meta.findall('m:cols/m:col',NS) for _ in range(int(c.get('min')),int(c.get('max'))+1)]
                    row_height(row,a.values(row,width),widths,360)
                row[:]=sorted(row,key=lambda c:column_index_from_string(re.sub(r'\d','',c.get('r'))))
                row.set('spans',f'1:{header_width}')
                body.write(encode(row))
            # Rename the matching dropdown/conditional-format option as well.
            for node in meta.iter():
                if E.QName(node).localname in {'formula','formula1','formula2'} and node.text:
                    node.text=rename_recommendation_label(node.text)
            if i==15:
                for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:L{lastrow}')
                report['mapping_rows']=lastrow-1
            replacement[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        for d in wb.findall('m:definedNames/m:definedName',NS):
            if d.text.startswith("'PILIHAN MAPPING'!"):d.text=f"'PILIHAN MAPPING'!$A$1:$L${report['mapping_rows']+1}"
        replacement['xl/workbook.xml']=E.tostring(wb)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));count=0
        for name,data in replacement.items():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):count+=len(re.findall(rb'<(?:\w+:)?c\b[^>]*\bt="s"',data))
        shared.set('count',str(count));replacement['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as result:
                for info in z.infolist():result.writestr(info,replacement.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as result:assert result.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'counts':dict(report),'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','pipeline','backup','report']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();r=apply(args.workbook,args.pipeline,args.backup);args.report.write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
