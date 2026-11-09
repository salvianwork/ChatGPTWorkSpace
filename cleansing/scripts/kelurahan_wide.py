"""One review row per kelurahan, with independently approved change sections."""
from collections import defaultdict
from io import BytesIO
import re
from lxml import etree as E
from openpyxl.utils import get_column_letter
from daikin_review_readability import NS,TAG,put,encode,layout,row_height,rules,ranges
from merge_daikin_changes import can_accept,needs_location,OPTIONS
from regional_note_compaction import compact_recommendation_note

KINDS=['Parent Kecamatan','Kabupaten/Kota Langsung','Nama']
COMMON=['Objek','Id Data','Nama Data','Perubahan yang Perlu Direview','Relasi Master yang Seharusnya',
        'Temuan Pada Tingkat Lain','Panduan Review']
GUIDE=('ID data tetap. Review hanya bagian yang tercantum pada Perubahan yang Perlu Direview. '
       'Keputusan setiap bagian berdiri sendiri. Setujui usulan jika nilai dan lokasi sudah jelas; '
       'jika perlu koreksi, pilih Gunakan nilai final dan isi nilai final pada bagian tersebut. '
       'Lokasi yang belum pasti memerlukan lokasi final. Lengkapi catatan jika menolak/perlu diskusi, PIC, dan tanggal per bagian. '
       'Usulan berlaku setelah Tim Daikin menyetujui.')


def fields(kind):
    if kind=='Nama':
        return [(7,'Nama Usulan',32),(6,'Konteks Data Sekarang untuk Nama',65),(10,'Status Konfirmasi Nama',38),
                (11,'Penjelasan Usulan Nama',75),(13,'Keputusan Nama',28),(14,'Nama Final',32),
                (15,'Lokasi Final untuk Nama',75),(16,'Catatan Review Nama',55),(17,'PIC Nama',22),(18,'Tanggal Nama',22)]
    label='Kecamatan' if kind=='Parent Kecamatan' else 'Kabupaten/Kota Langsung'
    return [(4,'ID '+label+' Sekarang',24),(5,'Nama '+label+' Sekarang',32),(6,'Konteks '+label+' Sekarang',65),
            (7,'ID '+label+' Usulan',24),(8,'Nama '+label+' Usulan',32),(10,'Status Konfirmasi '+label,38),
            (11,'Penjelasan Usulan '+label,75),(13,'Keputusan '+label,28),(14,'ID '+label+' Final',28),
            (15,'Lokasi Final '+label,75),(16,'Catatan Review '+label,55),(17,'PIC '+label,22),(18,'Tanggal '+label,22)]


HEADERS=COMMON+[label for k in KINDS for _,label,_ in fields(k)]
WIDTHS=[17,24,34,35,85,75,90]+[width for k in KINDS for _,_,width in fields(k)]
COLS={};offset=len(COMMON)
for kind in KINDS:
    COLS[kind]={old:offset+j for j,(old,_,_) in enumerate(fields(kind),1)};offset+=len(fields(kind))


def section_note(note,kind):
    if not note:return note
    generic={'• ID data tetap.',f'• ID data tetap. Baris ini memeriksa {kind}.',
             '• Periksa juga baris perubahan lain dengan Id Data yang sama. Keputusan diisi per baris.',
             '• Usulan berlaku setelah Tim Daikin menyetujui. Lengkapi PIC dan tanggal.'}
    lines=[line for line in note.splitlines() if line not in generic]
    text='\n'.join(lines).replace('Baris Nama','Bagian Nama').replace('baris Nama','bagian Nama')
    text=text.replace('Baris Parent','Bagian Parent').replace('baris hubungan','bagian hubungan')
    return compact_recommendation_note(text.strip()) or None


def master_cell(group):
    byvalue=defaultdict(list)
    for v in group:byvalue[v[9]].append(v[3])
    if len(byvalue)==1:return group[0][9]
    return 'Acuan master per bagian:'+''.join('\n\n['+'; '.join(kinds)+']\n'+value for value,kinds in byvalue.items())


def master_for(value,kind):
    if not value.startswith('Acuan master per bagian:'):return value
    sections=re.split(r'\n\n\[([^\]]+)\]\n',value)
    for labels,text in zip(sections[1::2],sections[2::2]):
        if kind in labels.split('; '):return text
    raise AssertionError('Missing master context for '+kind)


def flatten(group):
    assert len({tuple(v[:3]) for v in group})==1
    assert len({v[3] for v in group})==len(group) and all(v[3] in KINDS for v in group)
    assert len({v[12] for v in group})==1,'Cross-level evidence needs its own section if contexts differ'
    bykind={v[3]:v for v in group}
    result=group[0][:3]+['; '.join(k for k in KINDS if k in bykind),master_cell(group),group[0][12],GUIDE]
    for kind in KINDS:
        v=bykind.get(kind)
        if kind=='Nama' and v:assert v[4]==v[2] and not v[5] and not v[8]
        result.extend(section_note(v[old],kind) if old==11 and v else v[old] if v else None for old,_,_ in fields(kind))
    assert len(result)==len(HEADERS)
    return result


def unflatten(row):
    """Recover the separate change records, including scoped inputs and dates."""
    result=[]
    for kind in row[3].split('; '):
        v=row[:3]+[kind]+[None]*15;v[9]=master_for(row[4],kind);v[12]=row[5]
        for old,col in COLS[kind].items():v[old]=row[col-1]
        if kind=='Nama':v[4]=row[2]
        result.append(v)
    return result


def format_sheet(meta,groups):
    rows=[flatten(group) for group in groups];last=len(rows)+1
    decision_groups=[];checks=[];idrefs=[]
    for kind in KINDS:
        cols=COLS[kind];d,f,p,s,c,pic,date,loc=[get_column_letter(cols[k]) for k in [13,14,7,10,16,17,18,15]]
        known=[];unknown=[];locations=[]
        for n,group in enumerate(groups,2):
            v=next((v for v in group if v[3]==kind),None)
            if v:
                (known if can_accept(v) else unknown).append(n)
                if needs_location(v):locations.append(n)
        decision_groups.extend([(ranges(known,d),OPTIONS),(ranges(unknown,d),OPTIONS[1:])])
        checks.extend([(f'{f}2:{f}{last}',f'AND(${d}2="Gunakan nilai final",${f}2="")'),
                       (f'{d}2:{d}{last}',f'AND(${d}2="Setujui usulan",OR(${p}2="",ISNUMBER(SEARCH("lokasi",${s}2))'+
                        (f',ISNUMBER(SEARCH(";",${p}2))' if kind!='Nama' else '')+'))'),
                       (f'{c}2:{c}{last}',f'AND(OR(${d}2="Tolak usulan",${d}2="Perlu diskusi"),${c}2="")'),
                       (f'{pic}2:{date}{last}',f'AND(${d}2<>"",OR(${pic}2="",${date}2=""))')])
        for token in ranges(locations,loc).split():
            first=re.search(r'\d+',token)[0]
            checks.append((token,f'AND(OR(${d}{first}="Setujui usulan",${d}{first}="Gunakan nilai final"),${loc}{first}="")'))
        if kind!='Nama':idrefs.append(f'{f}2:{f}{last}')
    rules(meta,decision_groups,checks,idrefs)
    layout(meta,WIDTHS)
    for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:{get_column_letter(len(HEADERS))}{last}')
    body=BytesIO()
    for n,v in enumerate([HEADERS]+rows,1):
        node=E.Element(TAG+'row',r=str(n),spans=f'1:{len(HEADERS)}')
        active=set(v[3].split('; ')) if n>1 else set()
        input_cols={col for k in active for old,col in COLS[k].items() if old>=13}
        dates={COLS[k][18] for k in active}
        for col,value in enumerate(v,1):put(node,col,value,3 if n==1 else 18 if col in dates else 17 if col in input_cols else 6)
        if n==1:node.set('ht','88');node.set('customHeight','1')
        else:row_height(node,v,WIDTHS,360)
        body.write(encode(node))
    return E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>'),rows
