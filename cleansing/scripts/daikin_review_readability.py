"""Add missing master evidence and make the Daikin review workbook easier to use.

Review-only stage after daikin_review_clarity. Uses streaming OOXML updates to
preserve source IDs, existing answers, workbook parts and source files.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
from io import BytesIO
import json
from math import ceil
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string, get_column_letter
from regional_matching import normalize, conflicting_region_words

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
TAG='{'+NS['m']+'}'
LEVELS=['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan']
INFO_STATUS='Nama sama; lokasi perlu dikonfirmasi'
DIRECTION_STATUS='Nama berbeda; perlu konfirmasi'
MORE_ID_NOTE=('ID rekomendasi pertama belum tersedia. Pilihan lain pada PILIHAN MAPPING memiliki ID, '
              'tetapi mewakili kandidat yang berbeda. Pastikan lokasi terlebih dahulu; jangan memilih hanya karena ID tersedia.')
VALID_INPUTS=['Keputusan Tim Daikin','Id Utama Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']
DATA_OPTIONS=['Gunakan rekomendasi 1','Gunakan ID lain','Buat data baru','Di luar master','Perlu diskusi']
PARENT_OPTIONS=['Setujui usulan','Tolak usulan','Perlu diskusi']


def master_locations(name, level, index):
    return sorted(index.get((level,normalize(name,level)),set()))


def master_evidence(paths):
    """Show at most three actual full locations and an exact remainder count."""
    return '\n'.join(['• '+p for p in paths[:3]]+([f'+{len(paths)-3} lokasi lainnya'] if len(paths)>3 else []))


def direction_note(source,target):
    return (f'Nama sumber “{source}” dan nama master “{target}” memiliki penanda wilayah yang berbeda. '
            'Kemiripan ejaan belum cukup untuk memilih ID. Pastikan nama, lokasi, dan provinsinya.')


def parent_note(v, related):
    lines=['• ID data tetap. Baris ini memeriksa '+v[3]+'.']
    if v[7]:
        lines.append('• Tindakan: cocokkan usulan dengan lokasi master. Setujui, tolak, atau pilih Gunakan ID final untuk memakai ID lain.')
    elif 'Lokasi dan ID' in v[11]:
        lines.append('• Tindakan: konfirmasikan lokasi pada Relasi Master yang Seharusnya. Cari ID relasinya, lalu isi Id Relasi Final.')
    else:
        lines.append('• Tindakan: lokasi master sudah ditampilkan; cari ID relasi yang sesuai, lalu isi Id Relasi Final.')
        # Keep the specific reason for missing IDs instead of replacing it with
        # a generic warning. Discard old instructions tied to a first option.
        old=v[12] or ''
        reason=re.search(r'(Alasan ID .*?)(?=\n\nSetelah Tim Daikin|\Z)',old,re.S)
        if reason:lines.append(reason[1].strip())
    if 'nama data' in v[11].lower() or 'Nama saat ini:' in (v[12] or ''):
        lines.append('• Nama data juga perlu dikonfirmasi. Bandingkan Nama Data dengan nama terakhir pada relasi master.')
    if related>1:
        lines.append('• Periksa juga baris hubungan lain dengan Id Data yang sama. Keputusan diisi per baris.')
    lines.append('• Usulan berlaku setelah Tim Daikin menyetujui. Lengkapi PIC dan tanggal.')
    return '\n'.join(lines)


def compact_note(text):
    """Remove only repeated boilerplate; retain all case-specific ID explanations."""
    if not text:return text
    text=text.replace('Hubungan wilayah untuk lokasi rekomendasi:\n','')
    text=text.replace('Hubungan wilayah pada data sumber untuk pilihan ini:\n','')
    text=text.replace('• Tidak perlu mengubah hubungan wilayah pada data sumber untuk pilihan ini.','')
    text=text.replace('• Tidak perlu mengubah hubungan wilayah.','')
    text=text.replace('Jika rekomendasi ini dipilih setelah Tim Daikin memastikan lokasi:',
                      'Setelah lokasi dipastikan:')
    text=text.replace('Induk','Parent').replace('induk','Parent')
    return re.sub(r'\n{3,}','\n\n',text).strip()


class Package:
    def __init__(self,z):
        self.z=z
        self.strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))]
    def val(self,c):
        if c is None:return None
        if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
        value=c.findtext('m:v',namespaces=NS)
        if c.get('t')=='s':return self.strings[int(value)]
        return int(value) if value and value.isdigit() and c.get('t') is None else value
    def rows(self,i):
        with self.z.open(f'xl/worksheets/sheet{i}.xml') as f:
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                yield row
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
    def cells(self,row):return {column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
    def values(self,row,width):
        cells=self.cells(row);return [self.val(cells.get(i)) for i in range(1,width+1)]
    def metadata(self,i):
        raw=self.z.read(f'xl/worksheets/sheet{i}.xml');start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        return E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:])


def put(row,col,value,style=None):
    ref=get_column_letter(col)+row.get('r')
    c=next((c for c in row if c.get('r')==ref),None)
    if c is None:c=E.SubElement(row,TAG+'c',r=ref,s=str(style or 6))
    for child in list(c):c.remove(child)
    c.attrib.pop('t',None)
    if style is not None:c.set('s',str(style))
    if value is None or value=='':
        # Excel expects cells in address order even when a new cell is blank.
        row[:]=sorted(row,key=lambda c:column_index_from_string(re.sub(r'\d','',c.get('r'))))
        return
    if isinstance(value,int):E.SubElement(c,TAG+'v').text=str(value)
    else:
        c.set('t','inlineStr');node=E.SubElement(E.SubElement(c,TAG+'is'),TAG+'t');node.text=str(value)
    row[:]=sorted(row,key=lambda c:column_index_from_string(re.sub(r'\d','',c.get('r'))))


def encode(row):
    raw=E.tostring(row)
    for decl in [b' xmlns="'+NS['m'].encode()+b'"',b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"']:
        raw=raw.replace(decl,b'',1)
    return raw


def append_meta(meta,node):
    # All new rules belong after autoFilter and before pageMargins.
    margins=meta.find('m:pageMargins',NS)
    meta.insert(list(meta).index(margins) if margins is not None else len(meta),node)


def ranges(numbers,col):
    result=[]
    for n in sorted(numbers):
        if result and n==result[-1][1]+1:result[-1][1]=n
        else:result.append([n,n])
    return ' '.join(f'{col}{a}:{col}{b}' if a!=b else f'{col}{a}' for a,b in result)


def list_rule(container,refs,options):
    if not refs:return
    # Split large disjoint selections to stay well below Excel sqref limits.
    tokens=refs.split()
    for start in range(0,len(tokens),300):
        node=E.SubElement(container,TAG+'dataValidation',type='list',allowBlank='1',errorStyle='stop',
             showInputMessage='1',showErrorMessage='1',sqref=' '.join(tokens[start:start+300]),
             promptTitle='Keputusan Tim Daikin',prompt='Baca bukti lokasi. Isi ID final jika diminta; sel merah berarti isian belum lengkap.',
             errorTitle='Pilih keputusan dari daftar',error='Gunakan salah satu pilihan yang tersedia pada baris ini.')
        E.SubElement(node,TAG+'formula1').text='"'+','.join(options)+'"'


def red_rule(meta,refs,formula,priority):
    cf=E.Element(TAG+'conditionalFormatting',sqref=refs)
    rule=E.SubElement(cf,TAG+'cfRule',type='expression',dxfId='0',priority=str(priority))
    E.SubElement(rule,TAG+'formula').text=formula
    append_meta(meta,cf)


def rules(meta,groups,checks,id_refs=()):
    for old in meta.findall('m:dataValidations',NS):meta.remove(old)
    for old in meta.findall('m:conditionalFormatting',NS):meta.remove(old)
    for priority,(refs,formula) in enumerate(checks,1):red_rule(meta,refs,formula,priority)
    dv=E.Element(TAG+'dataValidations')
    for refs,options in groups:list_rule(dv,refs,options)
    for ref in id_refs:
        first=ref.split(':')[0]
        node=E.SubElement(dv,TAG+'dataValidation',type='custom',allowBlank='1',errorStyle='stop',
             showInputMessage='1',showErrorMessage='1',sqref=ref,
             promptTitle='Satu ID Salesforce',prompt='Isi satu ID Salesforce berisi 15 atau 18 karakter. Kosongkan jika belum dipastikan.',
             errorTitle='Periksa ID final',error='Masukkan satu ID Salesforce (15 atau 18 karakter), tanpa spasi atau tanda titik koma.')
        E.SubElement(node,TAG+'formula1').text=f'OR({first}="",AND(OR(LEN({first})=15,LEN({first})=18),ISERROR(SEARCH(";",{first})),ISERROR(SEARCH(" ",{first}))))'
    if len(dv):dv.set('count',str(len(dv)));append_meta(meta,dv)


def layout(meta,widths,freeze=True):
    if freeze:
        view=meta.find('m:sheetViews/m:sheetView',NS)
        for c in list(view):view.remove(c)
        E.SubElement(view,TAG+'pane',xSplit='3',ySplit='1',topLeftCell='D2',activePane='bottomRight',state='frozen')
        E.SubElement(view,TAG+'selection',pane='bottomRight',activeCell='D2',sqref='D2')
    if widths:
        cols=meta.find('m:cols',NS)
        for c in list(cols):cols.remove(c)
        for i,width in enumerate(widths,1):E.SubElement(cols,TAG+'col',min=str(i),max=str(i),width=str(width),customWidth='1')


def row_height(row,values,widths,limit=300):
    lines=max((sum(max(1,ceil(len(line)/max(8,width-3))) for line in str(value or '').split('\n'))
               for value,width in zip(values,widths)),default=1)
    row.set('ht',str(min(409,max(36,min(limit,lines*15+8)))))
    row.set('customHeight','1')


def apply(workbook,pipeline,backup):
    assert not backup.exists(),'Use a fresh backup path'
    backup.write_bytes(workbook.read_bytes())
    index=defaultdict(set)
    with (pipeline/'04_Master_Targets/Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            path=r['Master_Path'];parts=path.split(' | ');level=len(parts)-1
            index[(level,normalize(parts[-1],level))].add(path)
    report=Counter();examples={}
    with ZipFile(backup) as z:
        a=Package(z);replacement={}
        data={v[1]:v for row in a.rows(14) if (v:=a.values(row,23))[0]!='Objek'}
        assert a.values(next(a.rows(7)),17)[12:] == [None]*5,'This stage expects the workbook before structured ID-primary inputs'
        mapping=[a.values(row,12) for row in a.rows(15)]
        existing=defaultdict(list)
        for v in mapping[1:]:existing[v[1]].append(v)
        related=Counter(a.values(r,19)[1] for r in a.rows(16) if r.get('r')!='1')
        missing={rid:master_locations(v[2],LEVELS.index(v[0]),index)
                 for rid,v in data.items() if not v[11]}
        missing={rid:p for rid,p in missing.items() if p}
        bad={rid for rid,v in data.items() if (v[15] or '').startswith('Nama mirip') and conflicting_region_words(v[2],v[11])}
        later={rid for rid,v in data.items() if not v[13] and any(r[6] and r[7]!='Nama ditemukan di tingkat lain' for r in existing[rid])}
        report.update(master_evidence_sources=len(missing),previously_missing_detail=sum(not existing[rid] for rid in missing),
                      blocked_first_recommendations=len(bad),later_id_explanations=len(later))
        # Convert unsafe fuzzy alternatives to explicit evidence, retaining the
        # real master location but never presenting its ID as a recommendation.
        unsafe_paths=defaultdict(set)
        for v in mapping[1:]:
            if (v[8] or '').startswith('Nama mirip') and conflicting_region_words(v[2],v[4]):
                unsafe_paths[v[1]].add(v[5])
                v[6]=None;v[7]=DIRECTION_STATUS;v[8]=direction_note(v[2],v[4]);report['blocked_mapping_options']+=1
        orders=Counter(v[1] for v in mapping[1:])
        for rid,paths in missing.items():
            v=data[rid];orders[rid]+=1
            mapping.append(v[:3]+[str(orders[rid]),v[2],master_evidence(paths),None,INFO_STATUS,
               'Nama ditemukan di master, tetapi lokasi dan Parent data sumber belum cocok atau belum lengkap. '
               'Konfirmasikan kecamatan, kabupaten/kota, dan provinsi sebelum memilih ID tujuan.', 'Master',v[0],str(len(paths))])
        # A historical name in parentheses may have an exact base name in the
        # same master Parent. Show that evidence without silently dropping the
        # directional qualifier or assigning the base name's ID.
        for rid in sorted(bad):
            v=data[rid];match=re.fullmatch(r'\s*([^()]+)\s*\([^()]+\)\s*',v[2])
            if not match:continue
            level=LEVELS.index(v[0])
            paths=[p for p in master_locations(match[1].strip(),level,index) if p.rsplit(' | ',1)[0]==v[5]]
            if not paths:continue
            orders[rid]+=1
            mapping.append(v[:3]+[str(orders[rid]),match[1].strip(),master_evidence(paths),None,DIRECTION_STATUS,
                'Nama sebelum tanda kurung ada pada master dalam Parent yang sama. Keterangan arah/wilayah dalam tanda kurung perlu dikonfirmasi; ID tujuan belum ditentukan.',
                'Master',v[0],str(len(paths))])
            report['parenthesized_base_evidence']+=1
        for rid in bad:
            v=data[rid]
            assert not any(v[16:]),'Keep decisions intact; resolve an answered row explicitly'
            v[8]='Nama wilayah perlu dikonfirmasi'
            v[9]=direction_note(v[2],v[11])+' Bukti lokasi tersedia pada PILIHAN MAPPING.'
            v[11:16]=[None]*5
        for rid,paths in missing.items():
            v=data[rid]
            v[8]='Nama ada di master; lokasi perlu konfirmasi'
            v[9]=('• Masalah: nama ada di master, tetapi lokasi atau Parent pada data sumber belum cocok atau belum lengkap.'
                  '\n\n• Bukti Master:\n'+master_evidence(paths)+
                  '\n\n• Tindakan: pastikan lokasi, Parent, dan provinsi. Lihat PILIHAN MAPPING untuk rincian. ID tujuan belum dapat dipilih.')
            v[15]=None
        for rid in later-bad:
            v=data[rid]
            if MORE_ID_NOTE not in (v[15] or ''):v[15]='\n\n'.join(x for x in [v[15],MORE_ID_NOTE] if x)
        for rid,v in data.items():
            if v[4] in ('0',0):v[4]='Belum diketahui';report['unknown_parent_display']+=1
            v[15]=compact_note(v[15])
            if ';' in (v[13] or ''):
                v[15]=(v[15] or '')+'\n\n• Ada beberapa ID untuk lokasi ini. Pilih satu setelah dikonfirmasi: gunakan keputusan Gunakan ID lain, lalu isi satu ID pada Id Target Final.'
                report['multiple_id_choice_explanations']+=1
        for rid in ['a1pJ40000008XY0IAM','a1nJ4000000KWLNIA4','a1pJ40000008XDhIAM']:examples[rid]=data[rid]
        # Styles: consistent yellow inputs, grey inapplicable cells, red incomplete inputs.
        styles=E.fromstring(z.read('xl/styles.xml'));fills=styles.find('m:fills',NS)
        grey_fill=len(fills);fill=E.SubElement(fills,TAG+'fill');pattern=E.SubElement(fill,TAG+'patternFill',patternType='solid');E.SubElement(pattern,TAG+'fgColor',rgb='FFF0F2F4');fills.set('count',str(len(fills)))
        xfs=styles.find('m:cellXfs',NS);grey_style=len(xfs);xf=deepcopy(xfs[17]);xf.set('fillId',str(grey_fill));xfs.append(xf);xfs.set('count',str(len(xfs)))
        dxfs=styles.find('m:dxfs',NS);assert len(dxfs)==0
        dxf=E.SubElement(dxfs,TAG+'dxf');fill=E.SubElement(dxf,TAG+'fill');pattern=E.SubElement(fill,TAG+'patternFill',patternType='solid');E.SubElement(pattern,TAG+'fgColor',rgb='FFFFC7CE');dxfs.set('count','1')
        replacement['xl/styles.xml']=E.tostring(styles)
        known=[];unknown=[];pending=[];parent_known=[];parent_unknown=[]
        widths={
           7:[14,24,32,32,58,24,28,24,45,55,48,55,28,26,55,22,22],
           14:[17,24,32,24,30,55,24,50,35,60,70,30,60,26,32,75,28,26,30,26,55,22,22],
           16:[17,24,32,28,24,30,55,24,30,75,30,38,75,70,28,26,55,22,22],
           15:[17,24,32,10,32,75,26,35,75,24,20,15],
           1:[12,110],2:[20,22,20,20,24,20,24,32,32],3:[30,75,65]}
        for i in [1,2,3,7,8,9,10,11,13,14,15,16]:
            meta=a.metadata(i);body=BytesIO();last=0
            if i in [8,9,10]:
                widths[i]=[17,24,32,32,30,24,30,24,24,24,60,30,65,28,32,26,26,55,22,22]
            if i==11:widths[i]=[17,32,65,26,26,20,28,26,32,26,55,22,22,65]
            if i==13:widths[i]=[17,24,32,26,32,65,20,20,25,65,28,26,55,22,22]
            width=len(widths[i])
            rows=a.rows(i)
            if i==15:
                # Build mapping rows anew; preserve order of all old evidence.
                def mapping_nodes():
                    for n,v in enumerate(mapping,1):
                        row=E.Element(TAG+'row',r=str(n))
                        for c,value in enumerate(v,1):put(row,c,value,3 if n==1 else 6)
                        yield row
                rows=mapping_nodes()
            for row in rows:
                n=int(row.get('r'));last=n
                old=a.values(row,width);v=list(old)
                if n==1:
                    if i==7:
                        for c,h in enumerate(VALID_INPUTS,13):put(row,c,h,3)
                        v[12:]=VALID_INPUTS
                    elif i==2:
                        for c,h in {2:'Jumlah Master (Lokasi)',5:'Calon Data Baru (Lokasi)',8:'Menunggu ID Utama (Bagian dari Sudah Benar)'}.items():put(row,c,h,3);v[c-1]=h
                    row.set('ht','62');row.set('customHeight','1')
                else:
                    if i==14:
                        v=data[v[1]]
                        for c in [5,9,10,12,13,14,15,16]:
                            if old[c-1]!=v[c-1]:put(row,c,v[c-1]);report['data_changed_cells']+=1
                        (known if v[13] and ';' not in v[13] else unknown).append(n)
                    elif i==16:
                        if v[1] in unsafe_paths:
                            lines=(v[9] or '').splitlines()
                            kept=[line for line in lines if line.removeprefix('• ').strip() not in unsafe_paths[v[1]]]
                            report['parent_master_options_removed']+=len(lines)-len(kept)
                            if len(kept)!=len(lines):
                                assert any(line.startswith('• ') for line in kept),'Keep valid master evidence'
                                kept[0]='Lokasi master untuk dikonfirmasi:'
                                v[9]='\n'.join(kept);put(row,10,v[9],6)
                        v[12]=parent_note(v,related[v[1]]);put(row,13,v[12],6)
                        report['parent_notes_simplified']+=1
                        (parent_known if v[7] else parent_unknown).append(n)
                    elif i==7:
                        is_pending='Penetapan ID utama' in (v[9] or '')
                        if is_pending:pending.append(n)
                        for c in range(13,18):put(row,c,None,(18 if c==17 else 17) if is_pending else grey_style)
                    elif i==1:
                        instructions={
                         2:'Mulai dari RINGKASAN. Kelompok Salesforce dihitung per ID unik. Jumlah Master dan Calon Data Baru dihitung per lokasi; jangan ditambahkan ke total Salesforce. Menunggu ID Utama sudah termasuk Sudah Benar.',
                         3:'VALID menjadi acuan lokasi. Khusus VALID KELURAHAN: filter Alasan Dinyatakan Sesuai berisi “Penetapan ID utama”. Isi lima kolom kuning di bagian kanan untuk menetapkan ID utama.',
                         4:'PERUBAHAN: bandingkan nama dan Parent saat ini dengan usulan. PERBAIKAN PARENT - ID TETAP: satu baris untuk satu hubungan; periksa semua baris dengan ID data yang sama. Baca relasi master sebelum menyetujui.',
                         7:'DATA BELUM JELAS: pastikan tingkat wilayah, lokasi, Parent, dan provinsi. Hanya rekomendasi pertama ditampilkan. Nama sama di lokasi lain adalah bukti untuk diperiksa, bukan ID tujuan. Lihat PILIHAN MAPPING untuk rinciannya.',
                         8:'Kolom kuning diisi Tim Daikin. Sel merah berarti isian wajib belum lengkap setelah keputusan dipilih.\n• Gunakan ID lain / Gunakan ID final / Tetapkan ID utama: isi ID final.\n• Buat data baru pada DATA BELUM JELAS: isi nama dan ID Parent final.\n• Lengkapi PIC dan tanggal. Sel panjang dapat dibaca lengkap melalui formula bar atau tombol F2.\nFile ini untuk review. Tim cleansing menyiapkan file upload setelah persetujuan.'}
                        if n in instructions:v[1]=instructions[n];put(row,2,v[1],6)
                    elif i==3:
                        if v[0]=='Canonical':v=['ID utama','Satu ID yang dipilih untuk mewakili sebuah lokasi.','Gunakan satu ID utama setelah dikonfirmasi.']
                        elif v[0]=='Lookup':v=['Hubungan antar data','Kolom yang menyimpan ID Parent atau data terkait.','Kecamatan menyimpan ID kota/kabupatennya.']
                        elif v[0]=='Data tujuan':v[2]='Id Target adalah ID data tujuan.'
                        elif v[0]=='Gap analysis':v[0]='Perbandingan data'
                        for c,x in enumerate(v,1):
                            if x!=old[c-1]:put(row,c,x,6)
                    # Uniform inputs on each review sheet. Never change values.
                    inputs={8:(14,20),9:(14,20),10:(14,20),11:(7,13),13:(11,15),14:(17,23),16:(15,19)}
                    if i in inputs:
                        start,end=inputs[i]
                        for c in range(start,end+1):put(row,c,v[c-1],18 if c==end else 17)
                    for c in row:
                        if c.get('s') not in {'17','18',str(grey_style)}:c.set('s','6')
                    row_height(row,v,widths[i],360 if i in [14,16] else 240)
                body.write(encode(row))
            layout(meta,widths[i],freeze=i not in [1,2,3])
            if i==7:
                meta.find('m:dimension',NS).set('ref',f'A1:Q{last}');meta.find('m:autoFilter',NS).set('ref',f'A1:Q{last}')
                checks=[(f'M2:N{last}','AND($M2="Tetapkan ID utama",$N2="")'),
                        (f'P2:Q{last}','AND($M2<>"",OR($P2="",$Q2=""))')]
                rules(meta,[(ranges(pending,'M'),['Tetapkan ID utama','Perlu diskusi'])],checks,[f'N2:N{last}'])
            elif i==14:
                checks=[(f'Q2:R{last}','AND(OR($Q2="Gunakan ID lain",$Q2="MASUKKAN_ID_LAIN"),$R2="")'),
                        (f'S2:T{last}','AND(OR($Q2="Buat data baru",$Q2="BUAT_DATA_BARU"),OR($S2="",$T2=""))'),
                        (f'Q2:Q{last}','AND(OR($Q2="Gunakan rekomendasi 1",$Q2="PILIH_KANDIDAT_1"),OR($N2="",ISNUMBER(SEARCH(";",$N2))))'),
                        (f'V2:W{last}','AND($Q2<>"",OR($V2="",$W2=""))')]
                rules(meta,[(ranges(known,'Q'),DATA_OPTIONS),(ranges(unknown,'Q'),DATA_OPTIONS[1:])],checks,[f'R2:R{last}',f'T2:T{last}'])
            elif i==16:
                checks=[(f'O2:P{last}','AND($O2="Gunakan ID final",$P2="")'),
                        (f'O2:O{last}','AND(OR($O2="Setujui usulan",$O2="SETUJU_UBAH"),$H2="")'),
                        (f'R2:S{last}','AND($O2<>"",OR($R2="",$S2=""))')]
                rules(meta,[(ranges(parent_known,'O'),PARENT_OPTIONS[:1]+['Gunakan ID final']+PARENT_OPTIONS[1:]),
                            (ranges(parent_unknown,'O'),['Gunakan ID final']+PARENT_OPTIONS[1:])],checks,[f'P2:P{last}'])
            elif i in [8,9,10]:
                rules(meta,[(f'N2:N{last}',PARENT_OPTIONS)],[(f'S2:T{last}','AND($N2<>"",OR($S2="",$T2=""))')],[f'P2:P{last}',f'Q2:Q{last}'])
            elif i==11:
                rules(meta,[(f'G2:G{last}',['Buat data baru','Gunakan data lama','Tidak perlu dibuat','Perlu diskusi'])],
                      [(f'H2:H{last}','AND(OR($G2="Gunakan data lama",$G2="DATA_SUDAH_ADA"),$H2="")'),
                       (f'L2:M{last}','AND($G2<>"",OR($L2="",$M2=""))')],[f'H2:H{last}',f'J2:J{last}'])
            elif i==13:
                rules(meta,[(f'K2:K{last}',['Gabungkan ke usulan','Bukan duplikat','Gunakan ID lain','Perlu diskusi'])],
                      [(f'L2:L{last}','AND(OR($K2="Gunakan ID lain",$K2="GUNAKAN_ID_TUJUAN_LAIN"),$L2="")'),
                       (f'N2:O{last}','AND($K2<>"",OR($N2="",$O2=""))')],[f'L2:L{last}'])
            if i==15:
                for key in ['dimension','autoFilter']:meta.find('m:'+key,NS).set('ref',f'A1:L{last}')
                report['mapping_rows']=last-1
            replacement[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        report['valid_pending_structured_inputs']=len(pending)
        # Defined print/filter ranges follow the expanded VALID / evidence sheets.
        wb=E.fromstring(z.read('xl/workbook.xml'))
        for d in wb.findall('m:definedNames/m:definedName',NS):
            if d.text.startswith("'PILIHAN MAPPING'!"):d.text=f"'PILIHAN MAPPING'!$A$1:$L${report['mapping_rows']+1}"
            if d.text.startswith("'VALID KELURAHAN'!"):d.text="'VALID KELURAHAN'!$A$1:$Q$47306"
        replacement['xl/workbook.xml']=E.tostring(wb)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for name in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):refs+=len(re.findall(rb'<c\b[^>]*\bt="s"',replacement.get(name,z.read(name))))
        shared.set('count',str(refs));replacement['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacement.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    return {'counts':dict(report),'blocked_first_ids':sorted(bad),'master_evidence_ids':sorted(missing),
            'later_id_note_ids':sorted(later-bad),'examples':examples,
            'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','pipeline','backup','report']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();result=apply(args.workbook,args.pipeline,args.backup);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result['counts'],ensure_ascii=False,indent=2))
