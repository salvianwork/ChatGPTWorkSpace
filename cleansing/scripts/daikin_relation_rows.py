"""Present the Daikin same-ID review as one row per relationship, with master paths."""
import argparse
from collections import Counter,defaultdict
import csv,hashlib,json,re,shutil,tempfile
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import get_column_letter
from daikin_parent_review import TITLE,HEADERS as BEFORE_HEADERS,NS,TAG

HEADERS=['Objek','Id Data','Nama Data','Hubungan yang Diperiksa','Id Relasi Sekarang',
         'Nama Relasi Sekarang','Lokasi Relasi Dari Pencocokan','Id Relasi Usulan',
         'Nama Relasi Usulan','Relasi Master yang Seharusnya','Jenis Perbaikan','Status Review',
         'Catatan Perbaikan','Temuan Pada Tingkat Lain','Keputusan Tim Daikin',
         'Id Relasi Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']
PRIMARY='Parent Kecamatan';CITY_PARENT='Parent Kabupaten/Kota';DIRECT='Kabupaten/Kota Langsung'


def master_relation(first,choices,master_paths):
    paths=list(dict.fromkeys(c['Hierarki_Kandidat'] for c in choices))
    if first not in paths or not paths or any(p not in master_paths for p in paths):
        raise ValueError('Recommendation must match actual master paths')
    paths=[first]+[p for p in paths if p!=first]
    if len(paths)==1:return paths[0]
    return 'Lokasi masih perlu dikonfirmasi. Pilihan pada master:\n'+'\n'.join('• '+p for p in paths)


def relation_rows(v,master,current_names=None):
    """Keep all source IDs and proposals; split only relationships needing review."""
    assert len(v)==24 and v[0] in {'Kecamatan','Kelurahan'}
    kinds=[]
    if not v[7] or v[4]!=v[7] or v[19]:kinds.append('primary')
    if v[0]=='Kelurahan' and (not v[11] or v[9]!=v[11] or v[20]):kinds.append('direct')
    # A future name-only case keeps one review row, with no implied Parent change.
    if not kinds:kinds=['primary']
    result=[]
    for kind in kinds:
        primary=kind=='primary'
        label=(PRIMARY if v[0]=='Kelurahan' else CITY_PARENT) if primary else DIRECT
        current,name,location,proposal,proposed_name=(v[4],v[5],v[6],v[7],v[8]) if primary else (v[9],None,v[10],v[11],v[12])
        # The old sheet has no exported city-name column. Look it up by the
        # actual source ID, without deriving the current name from a suggestion.
        if not primary:name=(current_names or {}).get(current)
        if not proposal:action='Konfirmasi ID relasi dan lokasi'
        elif not current:action='Lengkapi relasi'
        elif current!=proposal:action='Ubah relasi'
        else:action='Konfirmasi data; relasi sudah sesuai'
        if 'Konfirmasi nama data' in (v[14] or ''):action+='; konfirmasi nama data'
        note='Baris ini memeriksa '+label+'. ID data diusulkan tetap; perubahan menunggu keputusan Tim Daikin.'
        if v[15].startswith('Lokasi dan Parent'):
            note+=' Lokasi belum dipilih; ID relasi usulan tetap kosong.'
        if len(kinds)>1:note+=' Hubungan lainnya diperiksa pada baris terpisah dengan ID data yang sama.'
        elif v[0]=='Kelurahan':
            other=('Parent kecamatan',v[4],v[5],v[6],v[7],v[8]) if not primary else ('Kabupaten/kota langsung',v[9],None,v[10],v[11],v[12])
            if other[1] and other[1]==other[4]:
                note+='\n\nHubungan lain sudah sesuai: '+other[0]+', '+(other[5] or '')+' (ID '+other[1]+').'
                if other[3]:note+=' Lokasi dari pencocokan: '+other[3]+'.'
        if v[16]:note+='\n\nCatatan data sebelum pemisahan baris:\n'+v[16]
        result.append([v[0],v[1],v[2],label,current,name,location,proposal,proposed_name,master,
                       action,v[15],note,v[17],v[18],v[19] if primary else v[20],v[21],v[22],v[23]])
    return result


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    groups=defaultdict(list)
    for c in csv_rows(pipeline/'03_Manual_Review'/'Review_candidates.csv'):
        if c['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':groups[c['Id_Sumber']].append(c)
    master_paths={r['Hierarki_Master'] for r in csv_rows(pipeline/'04_Master_Targets'/'Master_target_inventory.csv')}
    current_names={r['Id_Sumber']:r['Nama_Sumber'] for r in csv_rows(pipeline/'05_All_Records'/'KotaKabupaten_all_records.csv')}
    sha=hashlib.sha256(workbook.read_bytes()).hexdigest();shutil.copy2(workbook,backup)
    with ZipFile(backup) as z:
        strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))]
        def val(c):
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            s=c.findtext('m:v',namespaces=NS)
            if c.get('t')=='s':return strings[int(s)]
            if s is None:return None
            return float(s) if '.' in s and c.get('t') is None else int(s) if s.isdigit() and c.get('t') is None else s
        def put(c,value):
            for child in list(c):c.remove(child)
            c.attrib.pop('t',None)
            if value is None or value=='':return
            if isinstance(value,(int,float)):E.SubElement(c,TAG+'v').text=str(value)
            else:
                c.set('t','inlineStr');E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t').text=value
        entry='xl/worksheets/sheet16.xml';root=E.fromstring(z.read(entry))
        data=root.find('m:sheetData',NS);assert [val(c) for c in data[0]]==BEFORE_HEADERS
        rows=[];unique=set();counts=Counter();multi=0
        for row in list(data)[1:]:
            v=[val(c) for c in row];assert len(v)==24
            assert v[1] not in unique;unique.add(v[1])
            master=master_relation(v[13],groups[v[1]],master_paths)
            selected=[c for c in groups[v[1]] if c['Hierarki_Kandidat']==v[13]
                      and (c['Id_Target_Kandidat'] or c['ID_Master_Perlu_Verifikasi'])==v[1]]
            assert selected,'Source ID must still match its displayed recommendation'
            if master.startswith('Lokasi masih'):multi+=1
            converted=relation_rows(v,master,current_names);rows.extend(converted)
            counts.update(r[3] for r in converted)
        assert len({(r[1],r[3]) for r in rows})==len(rows)
        for child in list(data):data.remove(child)
        widths=[18,25,33,30,26,42,65,26,34,100,44,42,110,95,28,28,85,23,25]
        cols=root.find('m:cols',NS)
        for child in list(cols):cols.remove(child)
        for i,width in enumerate(widths,1):
            style=18 if i==19 else 17 if i>=15 else 2 if i in {8,9} else 6
            E.SubElement(cols,TAG+'col',min=str(i),max=str(i),width=str(width),customWidth='1',style=str(style))
        for number,values in enumerate([HEADERS]+rows,1):
            row=E.SubElement(data,TAG+'row',r=str(number),spans='1:19')
            if number==1:row.set('ht','48');row.set('customHeight','1')
            for i,value in enumerate(values,1):
                style=3 if number==1 else 18 if i==19 else 17 if i>=15 else 2 if i in {8,9} else 6
                c=E.SubElement(row,TAG+'c',r=get_column_letter(i)+str(number),s=str(style));put(c,value)
        last=len(rows)+1
        for key in ['dimension','autoFilter']:root.find('m:'+key,NS).set('ref',f'A1:S{last}')
        dvs=root.findall('m:dataValidations/m:dataValidation',NS);assert len(dvs)==1
        assert dvs[0].findtext('m:formula1',namespaces=NS)=='"SETUJU_UBAH,TOLAK_PERUBAHAN,PERLU_DISKUSI"'
        dvs[0].set('sqref',f'O2:O{last}')
        wb=E.fromstring(z.read('xl/workbook.xml'));names=[s.get('name') for s in wb.find('m:sheets',NS)]
        assert len(names)==15 and names[12]==TITLE
        for defined in wb.findall('m:definedNames/m:definedName',NS):
            if defined.get('name')=='_xlnm._FilterDatabase' and defined.get('localSheetId')=='12':
                defined.text=f"'{TITLE}'!$A$1:$S${last}"
        summary=E.fromstring(z.read('xl/worksheets/sheet2.xml'))
        srows=summary.find('m:sheetData',NS);assert val(srows[0][-1])=='Perbaikan Parent ID Tetap'
        put(srows[0][-1],'Perbaikan Parent ID Tetap (ID Unik)')
        assert sum(int(val(r[-1])) for r in list(srows)[1:])==len(unique)
        instructions=E.fromstring(z.read('xl/worksheets/sheet1.xml'));irows=instructions.find('m:sheetData',NS)
        put(irows[3][1],'Konfirmasi usulan pada lembar PERUBAHAN dan PERBAIKAN PARENT - ID TETAP. Sheet Parent memakai satu baris per hubungan yang perlu diperbaiki atau dikonfirmasi. Satu ID data dapat muncul dua kali untuk Parent kecamatan dan kabupaten/kota langsung. Baca Relasi Master yang Seharusnya, Status Review, dan catatan. Lokasi yang belum pasti ditampilkan sebagai pilihan master; ID relasi yang belum pasti tetap kosong. Isi keputusan serta ID relasi final pada baris hubungan yang sesuai.')
        nids=f'{len(unique):,}'.replace(',','.');nrows=f'{len(rows):,}'.replace(',','.')
        put(irows[6][1],f'DATA BELUM JELAS memuat ID tujuan berbeda atau belum tersedia. Kasus ID rekomendasi sama dengan ID sumber ada pada PERBAIKAN PARENT - ID TETAP: {nids} ID unik dalam {nrows} baris hubungan. RINGKASAN menghitung ID unik, bukan jumlah baris hubungan. Rincian pilihan tersedia pada PILIHAN MAPPING. Data belum otomatis valid atau disetujui; perubahan menunggu keputusan Tim Daikin.')
        glossary=E.fromstring(z.read('xl/worksheets/sheet3.xml'));grow=glossary.find('m:sheetData',NS)[8]
        put(grow[1],'ID rekomendasi sama dengan ID sumber. Satu baris memeriksa satu hubungan; ID data bisa berulang. Ringkasan tetap menghitung ID unik. Relasi master menunjukkan urutan provinsi hingga data, dengan penanda bila lokasi masih perlu dikonfirmasi.')
        put(grow[2],'Hutagurgur (Huta Gurgur) mempunyai baris Parent Kecamatan dan Kabupaten/Kota Langsung. ID Parent Dolok Sanggul tetap kosong sampai dipastikan. Relasi master: Sumatra Utara | Kab. Humbang Hasundutan | Dolok Sanggul | Hutagurgur (Huta Gurgur).')
        replacements={entry:E.tostring(root),'xl/workbook.xml':E.tostring(wb),
                      'xl/worksheets/sheet1.xml':E.tostring(instructions),'xl/worksheets/sheet2.xml':E.tostring(summary),
                      'xl/worksheets/sheet3.xml':E.tostring(glossary)}
        # All rewritten cells use inline strings; preserve shared string contents/indices.
        for name in replacements:
            assert len(re.findall(rb'<c\b[^>]*\bt="s"',z.read(name)))==len(re.findall(rb'<c\b[^>]*\bt="s"',replacements[name]))
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'before_sha256':sha,'unique_source_ids':len(unique),'relation_rows':len(rows),
            'rows_by_relationship':dict(counts),'multiple_master_location_ids':multi,'headers':HEADERS}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['workbook','pipeline','backup']:parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=apply(args.workbook,args.pipeline,args.backup)
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
