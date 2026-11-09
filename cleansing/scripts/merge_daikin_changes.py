"""Merge same-ID Parent review into PERUBAHAN, one row per field or relationship.

All source and proposed IDs remain review values. No Salesforce connection and
no target selection from an ambiguous location or an unrelated recommendation.
"""
import argparse
from collections import Counter, defaultdict
import csv, hashlib, json, re, tempfile
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from daikin_review_readability import Package,NS,TAG,put,encode,layout,row_height,rules,ranges

OLD_PARENT='PERBAIKAN PARENT - ID TETAP'
HEADERS=['Objek','Id Data','Nama Data','Bagian yang Diubah','Nilai Sekarang',
         'Nama Relasi Sekarang','Konteks Lokasi Sekarang','Nilai Usulan','Nama Relasi Usulan',
         'Relasi Master yang Seharusnya','Status Konfirmasi','Penjelasan dan Tindakan',
         'Temuan Pada Tingkat Lain','Keputusan Tim Daikin','Nilai Final Tim Daikin',
         'Lokasi Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']
WIDTHS=[17,24,32,28,32,30,60,32,30,75,40,80,70,28,32,75,55,22,22]
PRIMARY={'Kota/Kabupaten':'Parent Provinsi','Kecamatan':'Parent Kabupaten/Kota','Kelurahan':'Parent Kecamatan'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
APP={'a':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties',
     'v':'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'}
OPTIONS=['Setujui usulan','Gunakan nilai final','Tolak usulan','Perlu diskusi']


def master_paths(value):
    if not value:return []
    if '\n' not in value:return [value]
    return [line[2:] for line in value.splitlines() if line.startswith('• ')]


def master_display(paths):
    paths=list(dict.fromkeys(paths));assert paths
    return paths[0] if len(paths)==1 else 'Lokasi master untuk dikonfirmasi:\n'+'\n'.join('• '+p for p in paths)


def needs_location(row):
    return len(master_paths(row[9]))>1 or 'lokasi' in row[10].casefold()


def can_accept(row):
    return bool(row[7]) and not needs_location(row) and (row[3]=='Nama' or ';' not in row[7])


def decision(value):
    return {'SETUJU_UBAH':'Setujui usulan','TOLAK_PERUBAHAN':'Tolak usulan','PERLU_DISKUSI':'Perlu diskusi',
            'Gunakan ID final':'Gunakan nilai final'}.get(value,value)


def status(value,kind,paths,location_pending=False):
    if location_pending or len(paths)>1:
        return 'Nama dan lokasi perlu dikonfirmasi' if kind=='Nama' else 'Lokasi dan ID usulan perlu dikonfirmasi'
    if not value:return 'Nama usulan perlu dikonfirmasi' if kind=='Nama' else 'ID usulan belum tersedia'
    return ('Nama' if kind=='Nama' else 'ID')+' usulan tersedia; menunggu konfirmasi'


def source_context(root):
    """Read only identity/Parent columns; use actual FKs, without name recovery."""
    records={};parents={};names={}
    for filename,parent_key in [('Provinsi.csv',None),('Kota Kabupaten.csv','Provinsi__c'),('Kecamatan.csv','Kota_Kabupaten__c')]:
        text=(root/filename).read_bytes()
        try:text=text.decode('utf-8-sig')
        except UnicodeDecodeError:text=text.decode('cp1252')
        for r in csv.DictReader(StringIO(text)):
            rid=r['Id'];names[rid]=r['Name'];parents[rid]=r.get(parent_key) if parent_key else None
            records[rid]=parent_key is None
    def path(rid,seen=None):
        seen=set() if seen is None else seen
        if not rid or rid not in names or rid in seen:return None
        if records[rid]:return names[rid]
        prefix=path(parents[rid],seen|{rid})
        return prefix+' | '+names[rid] if prefix else None
    return names,{rid:path(rid) for rid in names}


def base_row(v,kind,current,proposal,current_name,proposed_name,current_context,final_value,note,cross=None):
    p=master_paths(v[10])
    return [v[0],v[1],v[2],kind,current,current_name,current_context,proposal,proposed_name,
            v[10],status(proposal,kind,p),note,cross,decision(v[13]),final_value,None,v[17],v[18],v[19]]


def wide_changes(v,names=None,contexts=None):
    """Split every proposed/answered field, including combined name/Parent fixes."""
    assert len(v)==20;names=names or {};contexts=contexts or {};rows=[]
    common='• ID data tetap.\n• '+(v[12] or 'Cocokkan perubahan dengan lokasi master.')
    action='\n• Baca Nilai Sekarang dan Nilai Usulan. Setujui atau isi Nilai Final yang benar; lengkapi PIC dan tanggal.'
    for kind,current,proposed,current_name,proposed_name,final_value,rid in [
        ('Nama',v[2],v[3],None,None,v[14],v[5]),
        (PRIMARY[v[0]],v[5],v[7],v[4],v[6],v[15],v[5]),
        ('Kabupaten/Kota Langsung',v[8],v[9],names.get(v[8]),v[10].split(' | ')[1] if v[0]=='Kelurahan' else None,v[16],v[8])]:
        if kind=='Kabupaten/Kota Langsung' and v[0]!='Kelurahan':continue
        if (current or '')==(proposed or '') and final_value in (None,''):continue
        context=contexts.get(rid)
        context='Dari relasi Salesforce: '+context if context else 'Lokasi lengkap belum diketahui'
        rows.append(base_row(v,kind,current,proposed,current_name,proposed_name,context,final_value,common+action))
    assert rows,'Do not drop an existing source record with no changed fields'
    return rows


def parent_change(v):
    assert len(v)==19
    paths=master_paths(v[9]);assert paths
    note=(v[12] or '').replace('Gunakan ID final','Gunakan nilai final').replace('Id Relasi Final','Nilai Final')
    note=note.replace('baris hubungan lain','baris perubahan lain')
    note=re.sub(r'• Nama data juga perlu dikonfirmasi\.[^\n]*',
                '• Periksa juga baris Nama pada ID data yang sama.',note)
    return [v[0],v[1],v[2],v[3],v[4],v[5],
            'Dari pencocokan: '+v[6] if v[6] else 'Lokasi lengkap belum diketahui',
            v[7],v[8],v[9],status(v[7],v[3],paths,v[11].startswith('Lokasi')),note,
            v[13],decision(v[14]),v[15],None,v[16],v[17],v[18]]


def name_confirmation(group):
    """Move the existing name confirmation to its own row; never choose an alias."""
    first=group[0];paths=list(dict.fromkeys(p for v in group for p in master_paths(v[9])))
    names=list(dict.fromkeys(p.split(' | ')[-1] for p in paths))
    if first[2] in names:return None
    # Multiple master spellings/locations must remain a client decision.
    proposed=names[0] if len(names)==1 else None
    note=('• ID data tetap. Nama juga perlu dikonfirmasi pada data ini.\n'
          '• Bandingkan nama saat ini dengan nama terakhir pada relasi master. '
          'Jika ada beberapa lokasi, pastikan lokasinya terlebih dahulu.\n'
          '• Isi Nilai Final untuk nama yang disepakati. Baris Parent diputuskan terpisah.')
    return [first[0],first[1],first[2],'Nama',first[2],None,None,proposed,None,
            master_display(paths),status(proposed,'Nama',paths),note,first[13],None,None,None,None,None,None]


def format_review(meta,rows):
    body=BytesIO();known=[];unknown=[];loc=[]
    for n,v in enumerate([HEADERS]+rows,1):
        row=E.Element(TAG+'row',r=str(n))
        for c,value in enumerate(v,1):put(row,c,value,3 if n==1 else 18 if c==19 else 17 if c>=14 else 6)
        if n==1:row.set('ht','62');row.set('customHeight','1')
        else:
            row_height(row,v,WIDTHS,360)
            (known if can_accept(v) else unknown).append(n)
            if needs_location(v):loc.append(n)
        body.write(encode(row))
    last=len(rows)+1
    layout(meta,WIDTHS)
    for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:S{last}')
    checks=[(f'N2:O{last}','AND($N2="Gunakan nilai final",$O2="")'),
            (f'N2:N{last}','AND($N2="Setujui usulan",OR($H2="",ISNUMBER(SEARCH("lokasi",$K2)),AND($D2<>"Nama",ISNUMBER(SEARCH(";",$H2)))))'),
            (f'Q2:Q{last}','AND(OR($N2="Tolak usulan",$N2="Perlu diskusi"),$Q2="")'),
            (f'R2:S{last}','AND($N2<>"",OR($R2="",$S2=""))')]
    for token in ranges(loc,'P').split():
        first=re.search(r'\d+',token)[0]
        checks.append((token,f'AND(OR($N{first}="Setujui usulan",$N{first}="Gunakan nilai final"),$P{first}="")'))
    rules(meta,[(ranges(known,'N'),OPTIONS),(ranges(unknown,'N'),OPTIONS[1:])],checks)
    dvs=meta.find('m:dataValidations',NS)
    dv=E.SubElement(dvs,TAG+'dataValidation',type='custom',allowBlank='1',errorStyle='stop',showInputMessage='1',showErrorMessage='1',
                   sqref=f'O2:O{last}',promptTitle='Nama atau satu ID',prompt='Baris Nama: isi nama final. Baris hubungan: isi satu ID Salesforce (15 atau 18 karakter).',
                   errorTitle='Periksa nilai final',error='Untuk hubungan wilayah, isi satu ID Salesforce 15 atau 18 karakter tanpa spasi/titik koma.')
    E.SubElement(dv,TAG+'formula1').text='OR($D2="Nama",O2="",AND(OR(LEN(O2)=15,LEN(O2)=18),ISERROR(SEARCH(";",O2)),ISERROR(SEARCH(" ",O2))))'
    dvs.set('count',str(len(dvs)))
    # Make a long location field explain what should be entered without a list
    # whose literal values could exceed Excel's 255-character validation limit.
    return E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')


def apply(workbook,source_dir,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    names,contexts=source_context(source_dir)
    backup.write_bytes(workbook.read_bytes());report=Counter();out={};old_ids=set();parent_ids=set()
    with ZipFile(backup) as z:
        a=Package(z);wb=E.fromstring(z.read('xl/workbook.xml'));sheets=wb.find('m:sheets',NS)
        titles=[s.get('name') for s in sheets];assert len(titles)==15 and titles[12]==OLD_PARENT
        old=[]
        for i in [8,9,10]:
            rows=a.rows(i);header=a.values(next(rows),20);assert header[:3]==['Objek','Id Salesforce','Nama Sekarang']
            old.extend(a.values(row,20) for row in rows)
        groups=defaultdict(list)
        for row in a.rows(16):
            if row.get('r')!='1':
                v=a.values(row,19);groups[v[1]].append(v);parent_ids.add(v[1]);report['original_parent_relationships']+=1
        assert not {v[1] for v in old}&parent_ids
        out={8:[],9:[],10:[]};index={'Kota/Kabupaten':8,'Kecamatan':9,'Kelurahan':10}
        for v in old:
            assert v[1] not in old_ids;old_ids.add(v[1]);new=wide_changes(v,names,contexts);out[index[v[0]]].extend(new)
            report['original_change_rows']+=1;report['normalized_original_changes']+=len(new)
        for rid,group in groups.items():
            out[index[group[0][0]]].extend(parent_change(v) for v in group)
            row=name_confirmation(group)
            if row is not None:
                out[index[row[0]]].append(row);report['separate_name_confirmations']+=1
        replacement={}
        for i,rows in out.items():
            assert len({(v[1],v[3]) for v in rows})==len(rows),'Duplicate field/relationship on one source ID'
            replacement[f'xl/worksheets/sheet{i}.xml']=format_review(a.metadata(i),rows)
            report[f'sheet_{i}_rows']=len(rows);report[f'sheet_{i}_source_ids']=len({v[1] for v in rows})
        # Keep unrelated sheets byte-identical; update the three user guides.
        instruction={
           1:'Baca RINGKASAN. Kelompok Salesforce dihitung per ID unik, bukan jumlah baris perubahan. Jumlah Master dan Calon Data Baru dihitung per lokasi; Menunggu ID Utama sudah termasuk Sudah Benar.',
           2:'VALID menjadi acuan lokasi. Khusus VALID KELURAHAN, filter Alasan Dinyatakan Sesuai berisi “Penetapan ID utama”. Isi lima kolom kuning di kanan untuk menetapkan ID utama.',
           3:'Semua usulan perbaikan ada pada PERUBAHAN KOTA, PERUBAHAN KECAMATAN, atau PERUBAHAN KELURAHAN. Satu baris memeriksa satu perubahan/hubungan. ID yang sama bisa muncul pada beberapa baris; putuskan setiap baris secara terpisah.',
           4:'Pada PERUBAHAN, baca Bagian yang Diubah, Nilai Sekarang, Nilai Usulan, Relasi Master yang Seharusnya, dan Status Konfirmasi. Baris Nama berisi nama; baris Parent atau Kabupaten/Kota Langsung berisi ID relasi. ID data pada kolom B tetap.',
           5:'Jika nilai usulan tersedia dan lokasi sudah satu, pilih Setujui usulan. Jika usulan kosong atau perlu dikoreksi, pilih Gunakan nilai final lalu isi Nilai Final. Untuk lokasi yang belum pasti, isi juga Lokasi Final dengan urutan provinsi hingga data. Jangan memilih ID berdasarkan nama saja.',
           6:'DATA BELUM JELAS untuk menentukan ID tujuan berbeda atau yang belum diketahui. Lihat PILIHAN MAPPING untuk bukti. Periksa juga DATA DUPLIKAT dan CALON DATA BARU sesuai kasusnya; cari data lama sebelum membuat data baru.',
           7:'Kolom kuning diisi Tim Daikin. Sel merah berarti isian wajib belum lengkap. Lengkapi keputusan, nilai final jika diminta, catatan, PIC, dan tanggal. Filter keputusan kosong untuk melihat baris yang belum direview. Sel panjang dapat dibaca melalui formula bar atau F2. File upload disiapkan tim cleansing setelah persetujuan.'}
        for i,width in [(1,2),(2,8),(3,3)]:
            meta=a.metadata(i);body=BytesIO()
            for row in a.rows(i):
                n=int(row.get('r'));v=a.values(row,9 if i==2 else width)
                if i==1 and n>1:put(row,2,instruction[int(v[0])],6)
                if i==2:
                    if n==1:put(row,4,'Perubahan untuk Direview (ID Unik)',3)
                    else:
                        obj=v[0];count=len({r[1] for r in out[index[obj]]}) if obj in index else 0
                        put(row,4,count,6)
                    for cell in list(row):
                        if re.sub(r'\d','',cell.get('r'))=='I':row.remove(cell)
                    for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref','A1:H5')
                    cols=meta.find('m:cols',NS)
                    for col in list(cols):
                        if int(col.get('min'))>8:cols.remove(col)
                if i==3:
                    if v[0]=='Perbaikan Parent ID Tetap':
                        put(row,1,'Baris perubahan',6)
                        put(row,2,'Satu baris memeriksa satu nama atau hubungan wilayah. ID data tetap; keputusan diberikan per baris.',6)
                        put(row,3,'Hutagurgur memiliki baris Parent Kecamatan dan Kabupaten/Kota Langsung pada PERUBAHAN KELURAHAN.',6)
                    elif v[0]=='Perlu diperbaiki':put(row,2,'Data sudah ada dan mempunyai usulan perubahan nama atau hubungan Parent yang perlu direview.',6)
                    elif v[0]=='Parent':put(row,3,'Parent Kelurahan adalah Kecamatan; ID Parent ditulis pada baris Parent Kecamatan.',6)
                values=a.values(row,width)
                if n==1:row.set('ht','62');row.set('customHeight','1')
                else:row_height(row,values,[12,110] if i==1 else [20,22,20,32,24,20,24,32] if i==2 else [30,75,65],300)
                body.write(encode(row))
            replacement[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        removed=sheets[12];rid=removed.get(REL+'id');sheets.remove(removed)
        defined=wb.find('m:definedNames',NS)
        for d in list(defined):
            local=int(d.get('localSheetId')) if d.get('localSheetId') is not None else None
            if local==12 or OLD_PARENT in (d.text or ''):defined.remove(d);continue
            if local is not None and local>12:d.set('localSheetId',str(local-1))
            for i in [8,9,10]:
                title=titles[i-1]
                if d.text.startswith("'"+title+"'!"):d.text=f"'{title}'!$A$1:$S${len(out[i])+1}"
            if d.text.startswith("'RINGKASAN'!"):d.text="'RINGKASAN'!$A$1:$H$5"
        replacement['xl/workbook.xml']=E.tostring(wb)
        rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        match=[r for r in rels if r.get('Id')==rid];assert len(match)==1 and match[0].get('Target')=='worksheets/sheet16.xml'
        rels.remove(match[0]);replacement['xl/_rels/workbook.xml.rels']=E.tostring(rels)
        ct=E.fromstring(z.read('[Content_Types].xml'))
        for node in list(ct):
            if node.get('PartName')=='/xl/worksheets/sheet16.xml':ct.remove(node)
        replacement['[Content_Types].xml']=E.tostring(ct)
        app=E.fromstring(z.read('docProps/app.xml'))
        parts=app.find('a:TitlesOfParts/v:vector',APP)
        for part in list(parts):
            if part.text==OLD_PARENT:parts.remove(part)
        parts.set('size','14');app.find('a:HeadingPairs/v:vector/v:variant/v:i4',APP).text='14'
        replacement['docProps/app.xml']=E.tostring(app)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for entry in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry) and entry!='xl/worksheets/sheet16.xml':
                refs+=len(re.findall(rb'<c\b[^>]*\bt="s"',replacement.get(entry,z.read(entry))))
        shared.set('count',str(refs));replacement['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as result:
                for info in z.infolist():
                    if info.filename not in {'xl/worksheets/sheet16.xml','xl/worksheets/_rels/sheet16.xml.rels'}:
                        result.writestr(info,replacement.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as result:assert result.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    report.update(unique_changes=len(old_ids|parent_ids),all_change_rows=sum(map(len,out.values())),
                  pending_value_rows=sum(not r[7] for rows in out.values() for r in rows),
                  pending_location_rows=sum(needs_location(r) for rows in out.values() for r in rows))
    return {'counts':dict(report),'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','source-dir','backup','report']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();r=apply(args.workbook,args.source_dir,args.backup);args.report.write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
