"""Apply text-supported review candidates and one-row kelurahan change review."""
import argparse,csv,hashlib,json,re,tempfile
from collections import Counter,defaultdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import get_column_letter
from daikin_review_readability import Package,NS,put,encode,row_height,MORE_ID_NOTE
from daikin_identity_review import Context,view,format_data,sheet_xml
from regional_client_display import INFORMATIONAL_STATUSES
from regional_location_text import TEXT_REASON,LocationTextIndex
from regional_note_compaction import compact_recommendation_note
from kelurahan_wide import format_sheet,HEADERS


def source_note(raw,ctx):
    lines=[]
    for label,level,rid in [('Parent Kecamatan',2,raw.get('Kecamatan__c')),
                            ('Kabupaten/kota langsung',1,raw.get('Kota_Kabupaten__c')),
                            ('Kecamatan lama',2,raw.get('Kecamatans__c'))]:
        if not rid or rid=='0':continue
        if not re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?',rid):
            lines.append('• '+label+' pada sumber (teks): '+rid+'.');continue
        record=ctx.records[level].get(rid)
        location=' | '.join(record['_path']) if record and record['_path'] else record['Source_Name'] if record else 'nama/lokasi belum diketahui'
        lines.append('• '+label+' pada sumber: '+location+' (ID '+rid+').')
    return '\n'.join(lines)


def apply(workbook,pipeline,source_dir,backup):
    assert not backup.exists(),'Choose a fresh backup path'
    backup.write_bytes(workbook.read_bytes());ctx=Context(pipeline);text_index=LocationTextIndex(ctx.paths[3]);stats=Counter()
    with (source_dir/'Kelurahan.csv').open(encoding='cp1252',newline='') as f:source={r['Id']:r for r in csv.DictReader(f)}
    with ZipFile(backup) as z:
        a=Package(z);replacement={};groups=defaultdict(list)
        assert a.values(next(a.rows(10)),19)[3]=='Bagian yang Diubah','Already grouped or unexpected schema'
        for row in a.rows(10):
            if row.get('r')!='1':
                v=a.values(row,19);groups[v[1]].append(v)
        replacement['xl/worksheets/sheet10.xml'],wide=format_sheet(a.metadata(10),list(groups.values()))
        stats.update(kelurahan_rows_before=sum(len(g) for g in groups.values()),kelurahan_rows_after=len(wide),
                     kelurahan_source_ids=len(groups),scoped_master_contexts=sum(len({v[9] for v in g})>1 for g in groups.values()))
        data=[a.values(r,23) for r in a.rows(14)];updates={}
        for v in data[1:]:
            if v[0]!='Kelurahan' or any(v[16:]):continue
            raw=source[v[1]];hits=text_index.candidates(v[2],raw)
            if len(hits)!=1:continue
            path,reason=hits[0]
            matches=[c for c in ctx.candidates[v[1]] if c['Reason'].startswith(TEXT_REASON) and c['Candidate_Path']==' | '.join(path)]
            if not matches:continue
            display=view(matches[0]);display[4]+='\n\n'+source_note(raw,ctx)
            # Keeping the current record requires a separate Parent decision;
            # do not present its own ID as a destination in DATA BELUM JELAS.
            if display[2]==v[1]:
                display[2]=None;display[4]+='\n\nID sumber dapat dipertahankan jika lokasi dikonfirmasi; perbaikan Parent perlu direview. ID tujuan belum ditetapkan.'
                stats['same_id_kept_out_of_destination']+=1
            if not display[2] and any((c['Candidate_Target_Id'] or c['Unverified_Master_ID']) and c['Candidate_Path']!=' | '.join(path) for c in ctx.candidates[v[1]]):
                display[4]+='\n\n'+MORE_ID_NOTE
            display=[x or None for x in display];display[4]=compact_recommendation_note(display[4])
            if v[12]!=display[1]:stats['changed_primary_location']+=1
            v[8]='Lokasi dari teks; perlu konfirmasi'
            v[9]='Nama dan teks lokasi cocok dengan satu struktur master. Relasi sumber berbeda atau belum lengkap; konfirmasikan lokasi dan Parent sebelum memilih ID akhir.'
            v[11:16]=display;updates[v[1]]=display;stats['text_supported_sources']+=1
        replacement['xl/worksheets/sheet14.xml']=format_data(a.metadata(14),data)
        mapping=[];emitted=set();order=Counter();identities={v[1]:v[:3] for v in data[1:]}
        for row in a.rows(15):
            v=a.values(row,12)
            if row.get('r')=='1':mapping.append(v);continue
            rid=v[1];display=updates.get(rid)
            if display and rid not in emitted:
                mapping.append(identities[rid]+[0]+display+['Master','Kelurahan',1]);emitted.add(rid)
            if display and v[5]==display[1] and v[7] not in INFORMATIONAL_STATUSES:continue
            mapping.append(v)
        for rid,display in updates.items():
            if rid not in emitted:mapping.append(identities[rid]+[0]+display+['Master','Kelurahan',1])
        for v in mapping[1:]:
            if v[1] in updates:order[v[1]]+=1;v[3]=order[v[1]]
        meta=a.metadata(15)
        widths=[float(c.get('width','25')) for c in meta.findall('m:cols/m:col',NS) for _ in range(int(c.get('min')),int(c.get('max'))+1)]
        replacement['xl/worksheets/sheet15.xml']=sheet_xml(meta,mapping,widths)
        stats['mapping_rows']=len(mapping)-1
        instructions={
            3:'PERUBAHAN KOTA dan KECAMATAN: satu baris per perubahan. PERUBAHAN KELURAHAN: satu baris per ID dengan bagian Parent Kecamatan, Kabupaten/Kota Langsung, dan Nama. Lihat Perubahan yang Perlu Direview; bagian kosong tidak perlu diisi.',
            4:'Pada PERUBAHAN KELURAHAN, baca acuan master sekali lalu bandingkan nilai sekarang dan usulan pada setiap bagian. Jika acuan berbeda antarbagian, baca label bagiannya. Keputusan satu bagian tidak menyetujui bagian lainnya. ID data tetap.',
            5:'Isi keputusan, nilai final bila diperlukan, lokasi final yang belum pasti, catatan, PIC, dan tanggal pada masing-masing bagian. Nilai final Nama berisi nama; nilai final hubungan berisi satu ID Salesforce. Kolom kuning diisi hanya untuk bagian yang perlu direview.',
            6:'DATA BELUM JELAS untuk nama/lokasi/ID yang belum pasti. Lokasi dari teks ekspor hanya kandidat jika seluruh struktur cocok dengan satu lokasi master; relasi yang berbeda tetap perlu dikonfirmasi. Baca PILIHAN MAPPING untuk alternatif, DATA DUPLIKAT untuk usulan penggabungan, dan CALON DATA BARU untuk lokasi yang perlu dicari data lamanya.',
            7:'Kolom kuning diisi Tim Daikin; sel merah menandai isian wajib yang belum lengkap. Pada PERUBAHAN KELURAHAN, filter Perubahan yang Perlu Direview sesuai bagian, lalu filter keputusan bagian itu yang kosong. Bagian yang tidak tercantum tidak perlu diisi. Pada sheet lain, filter keputusan kosong seperti biasa. File upload disiapkan setelah review dan persetujuan.'}
        for i,width in [(1,2),(3,3)]:
            meta=a.metadata(i);body=BytesIO()
            for row in a.rows(i):
                v=a.values(row,width)
                if i==1 and v[0] in instructions:put(row,2,instructions[v[0]],6)
                if i==3 and v[0]=='Baris perubahan':
                    put(row,2,'Kota/kecamatan: satu baris per perubahan. Kelurahan: satu baris per ID, dengan keputusan terpisah untuk Nama, Parent Kecamatan, dan Kabupaten/Kota Langsung.',6)
                    put(row,3,'Taman Sari memiliki satu baris dengan dua bagian hubungan yang direview terpisah.',6)
                if i==3 and v[0]=='Parent':put(row,3,'Parent Kelurahan adalah Kecamatan; periksa bagian Parent Kecamatan pada PERUBAHAN KELURAHAN.',6)
                if row.get('r')!='1':row_height(row,a.values(row,width),[12,110] if i==1 else [30,75,65],300)
                body.write(encode(row))
            replacement[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        wb=E.fromstring(z.read('xl/workbook.xml'))
        for d in wb.findall('m:definedNames/m:definedName',NS):
            if d.text.startswith("'PERUBAHAN KELURAHAN'!"):d.text=f"'PERUBAHAN KELURAHAN'!$A$1:${get_column_letter(len(HEADERS))}${len(wide)+1}"
            if d.text.startswith("'PILIHAN MAPPING'!"):d.text=f"'PILIHAN MAPPING'!$A$1:$L${len(mapping)}"
        replacement['xl/workbook.xml']=E.tostring(wb)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for name in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):refs+=len(re.findall(rb'<(?:\w+:)?c\b[^>]*\bt="s"',replacement.get(name,z.read(name))))
        shared.set('count',str(refs));replacement['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacement.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'counts':dict(stats),'updated_source_ids':sorted(updates),
            'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','pipeline','source_dir','backup','report']:p.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    a=p.parse_args();r=apply(a.workbook,a.pipeline,a.source_dir,a.backup);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print(json.dumps(r['counts'],ensure_ascii=False,indent=2))
