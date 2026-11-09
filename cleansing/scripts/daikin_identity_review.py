"""Review-only name/context fixes and high-evidence duplicate proposals.

No Salesforce changes, no canonical-ID rewrite, and no approval is generated.
"""
import argparse,csv,hashlib,json,re,tempfile
from collections import Counter,defaultdict
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import get_column_letter
from regional_matching import normalize,unique_identity_paths,name_identity_kind
from regional_review_context import legacy_parent_context,one_edit_typo
from regional_client_display import client_candidate
from daikin_review_readability import Package,NS,TAG,put,encode,layout,row_height,rules,ranges
from merge_daikin_changes import HEADERS as CHANGE_HEADERS,format_review

LABELS=['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan']
OBJECTS=['Provinsi__c','Kota_Kabupaten__c','Kecamatan__c','Kelurahan__c']
DUP_HEADERS=['Objek','Id Duplikat','Nama Duplikat','Id Yang Dipertahankan','Nama Yang Dipertahankan','Hierarki Master',
             'Status Konfirmasi','Alasan Usulan','Jumlah Kecamatan Terdampak','Jumlah Kelurahan Terdampak',
             'Jumlah Data Anak Terdampak Dalam Paket','Catatan Dampak','Keputusan Tim Daikin',
             'Id Tujuan Final Tim Daikin','Catatan Tim Daikin','PIC Tim Daikin','Tanggal Konfirmasi']


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def view(c):
    mapping={'ID_Verification':'Status_Verifikasi_ID','Candidate_Target_Id':'Id_Target_Kandidat','Unverified_Master_ID':'ID_Master_Perlu_Verifikasi',
             'Candidate_Name':'Nama_Kandidat','Candidate_Path':'Hierarki_Kandidat','Reason':'Alasan','Review_Kind':'Jenis_Rekomendasi','Source_Id':'Id_Sumber',
             'Parent_Action_Note':'Petunjuk_Perbaikan_Wilayah','Parent_Action_Required':'Perlu_Perbaikan_Wilayah','Client_ID_Note':'Penjelasan_ID_Client','ID_Explanation':'Alasan_Verifikasi_ID'}
    d={out:c.get(key,'') for key,out in mapping.items()};d.update(Jenis_Bukti='KANDIDAT_OBJEK_SAMA',Tingkat_Ditemukan=LABELS[OBJECTS.index(c['Object'])])
    return [x.replace('Client','Tim Daikin').replace('client','Tim Daikin') if isinstance(x,str) else x for x in client_candidate(d)]


class Context:
    def __init__(self,pipeline):
        self.inventory={};self.paths=[set() for _ in range(4)];self.children=[defaultdict(list) for _ in range(4)]
        for r in read_csv(pipeline/'04_Master_Targets/Master_target_inventory.csv'):
            p=tuple(r['Master_Path'].split(' | '));self.inventory[p]=r;self.paths[len(p)-1].add(p);self.children[len(p)-1][p[:-1]].append(p)
        self.city_children=defaultdict(list)
        for p in self.paths[3]:self.city_children[p[:2]].append(p)
        self.records=[]
        for level,prefix in enumerate(['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']):
            rows={}
            for r in read_csv(pipeline/f'05_All_Records/{prefix}_all_records.csv'):
                p=tuple(r[k] for k in ['Target_Provinsi','Target_KotaKabupaten','Target_Kecamatan','Target_Kelurahan'][:level+1])
                r['_path']=p if all(p) else None;r['_blocked']=r['Status']=='REVIEW_PARENT_CONFLICT'
                r['_requires_review']=bool(level and r['Parent_Evidence']!='PARENT_LOOKUP_ID')
                rows[r['Source_Id']]=r
            self.records.append(rows)
        self.candidates=defaultdict(list)
        for r in read_csv(pipeline/'03_Manual_Review/Review_candidates.csv'):self.candidates[r['Source_Id']].append(r)
        for rows in self.candidates.values():rows.sort(key=lambda r:int(r['Rank']))
        self.kec_refs=Counter();self.kel_refs=Counter();self.legacy_refs=Counter()
        for r in self.records[2].values():self.kec_refs[r['Source_Parent_Id']]+=1
        for r in self.records[3].values():
            self.kel_refs[r['Source_Parent_Id']]+=1;self.kel_refs[r['Source_Direct_City_Id']]+=1
            if r['Source_Legacy_Kecamatans'] in self.records[2]:self.legacy_refs[r['Source_Legacy_Kecamatans']]+=1

    def city(self,rid):
        c=self.records[1].get(rid)
        if not c or c['_blocked'] or c['Parent_Evidence']!='PARENT_LOOKUP_ID' or not c['_path']:return None
        province=self.records[0].get(c['Source_Parent_Id'])
        if not province or province['_path']!=c['_path'][:1]:return None
        return c['_path']

    def district(self,rid):
        r=self.records[2].get(rid)
        if not r or r['_blocked']:return None
        city=self.city(r['Source_Parent_Id'])
        if not city:return None
        hits=unique_identity_paths(2,r['Source_Name'],city,self.children[2][city])
        return next(iter(hits)) if len(hits)==1 else None

    def parent(self,level,r):
        if r['_blocked']:return None,''
        if level==1:
            p=self.records[0].get(r['Source_Parent_Id']);return (p['_path'],'') if p else (None,'')
        if level==2:return self.city(r['Source_Parent_Id']),''
        if level!=3:return None,''
        direct=self.city(r['Source_Direct_City_Id'])
        if r['Source_Direct_City_Id'] and not direct:return None,''
        if r['Source_Parent_Id']:
            p=self.district(r['Source_Parent_Id'])
            if p and (not direct or p[:2]==direct):return p,''
            return None,''
        raw={'Kecamatan__c':'','Kecamatans__c':r['Source_Legacy_Kecamatans'],'Kecamatan__r.Name':r['Source_Parent_Display']}
        context=legacy_parent_context(raw,direct,self.records[2],self.records[1],self.paths[2])
        return context if context else (None,'')

    def strong(self,level,r,parent):
        if parent is None:return {}
        eligible=self.children[level][parent]
        found=unique_identity_paths(level,r['Source_Name'],parent,eligible)
        if found:return found
        if level==3:
            # A name/alias elsewhere in the same city outranks an unrelated
            # one-letter neighbour inside a possibly incorrect district.
            if any(name_identity_kind(r['Source_Name'],p[-1],level,p[:-1]) for p in self.city_children[parent[:2]]):return {}
        typo={p:'one_letter' for p in eligible if one_edit_typo(r['Source_Name'],p[-1],level)}
        return typo if len(typo)==1 else {}


def self_rows(v,path,ctx):
    level=len(path)-1;r=ctx.records[level][v[1]];result=[]
    base=[v[0],v[1],v[2],None,None,None,None,None,None,' | '.join(path),None,None,v[10],None,None,None,None,None,None]
    if v[2]!=path[-1]:
        row=base.copy();row[3]='Nama';row[4]=v[2];row[7]=path[-1];row[10]='Nama usulan tersedia; menunggu konfirmasi'
        row[11]='• ID data tetap. Nama sumber cocok dengan nama inti/alias master dalam lokasi yang sama.\n• Konfirmasikan penulisan nama yang akan digunakan. ID final tidak dipilih otomatis.';result.append(row)
    relations=[({1:'Parent Provinsi',2:'Parent Kabupaten/Kota',3:'Parent Kecamatan'}[level],r['Source_Parent_Id'],path[:-1])]
    if level==3:relations.append(('Kabupaten/Kota Langsung',r['Source_Direct_City_Id'],path[:2]))
    for label,current,p in relations:
        expected=ctx.inventory[p]['Target_Id']
        if current and current==expected:continue
        row=base.copy();row[3]=label;row[4]=current or None;row[7]=expected or None;row[8]=p[-1]
        old=ctx.records[len(p)-1].get(current)
        row[5]=old['Source_Name'] if old else None
        row[6]=' | '.join(old['_path']) if old and old['_path'] else 'Lokasi lengkap belum diketahui'
        row[10]='ID usulan tersedia; menunggu konfirmasi' if expected else 'ID usulan belum tersedia'
        row[11]='• ID data tetap. '+('Lengkapi' if not current else 'Periksa perubahan')+' '+label.lower()+'.\n• Baca relasi master dan konfirmasikan ID yang digunakan; tidak ada perubahan otomatis.'
        result.append(row)
    return result


def plan(ctx,data):
    plans={};stats=Counter()
    for v in data:
        rid=v[1];level=LABELS.index(v[0]);r=ctx.records[level][rid]
        if any(v[16:]):stats['existing_answers_kept']+=1;continue
        parent,context=ctx.parent(level,r);strong=ctx.strong(level,r,parent)
        if len(strong)==1:
            p,kind=next(iter(strong.items()));inv=ctx.inventory[p]
            supplied=r['Supplied_Name_Changes']
            if supplied and normalize(supplied,level)!=normalize(p[-1],level):stats['conflicting_supplied_name_kept']+=1;continue
            candidates=[c for c in ctx.candidates[rid] if c['Candidate_Path']==' | '.join(p)]
            if not candidates:stats['strong_candidate_not_in_pipeline']+=1;continue
            c=candidates[0];tid=inv['Target_Id']
            if tid and c['Candidate_Target_Id']==tid and c['ID_Verification']=='ID_TERVERIFIKASI':
                action='repair' if tid==rid else 'duplicate'
                plans[rid]={'action':action,'path':p,'kind':kind,'candidate':c,'parent_context':context}
                stats[action]+=1;continue
            prefs=set(filter(None,inv['Master_Sheet_Id'].split(';')))
            if prefs=={rid} and not tid and c['Unverified_Master_ID']==rid and level in (2,3):
                changes=self_rows(v,p,ctx)
                if changes:
                    plans[rid]={'action':'repair','path':p,'kind':kind,'candidate':c,'parent_context':context,'rows':changes}
                    stats['repair']+=1;continue
            # A safer name/location can still be shown while its target ID is
            # unresolved. Do not move it to duplicate review or borrow another ID.
            if (v[11],v[12],v[13])!=(c['Candidate_Name'],c['Candidate_Path'],c['Candidate_Target_Id'] or c['Unverified_Master_ID'] or None):
                plans[rid]={'action':'recommendation','path':p,'kind':kind,'candidate':c,'parent_context':context};stats['recommendation']+=1
        else:
            # Only a unique name/alias inside the recorded city can add an
            # unknown-district recommendation; this remains DATA BELUM JELAS.
            city=ctx.city(r['Source_Direct_City_Id']) if level==3 else None
            hits=[c for c in ctx.candidates[rid] if city and tuple(c['Candidate_Path'].split(' | '))[:2]==city
                  and name_identity_kind(r['Source_Name'],c['Candidate_Name'],level,tuple(c['Candidate_Path'].split(' | '))[:-1])]
            paths={c['Candidate_Path'] for c in hits}
            if len(paths)==1 and not r['_blocked']:
                c=hits[0]
                if (v[11],v[12],v[13])!=(c['Candidate_Name'],c['Candidate_Path'],c['Candidate_Target_Id'] or c['Unverified_Master_ID'] or None):
                    plans[rid]={'action':'recommendation','path':tuple(c['Candidate_Path'].split(' | ')),'kind':'city_only','candidate':c,'parent_context':''};stats['recommendation']+=1
    return plans,stats


def inspect_plan(pipeline,workbook,report_path):
    ctx=Context(pipeline)
    with ZipFile(workbook) as z:
        a=Package(z);data=[a.values(r,23) for r in a.rows(14) if r.get('r')!='1']
    plans,stats=plan(ctx,data)
    report_path.write_text(json.dumps({'counts':dict(stats),'plans':{rid:{k:v for k,v in item.items() if k!='candidate'} for rid,item in plans.items()}},ensure_ascii=False,indent=2))
    return ctx,data,plans,stats


def proposal_note(v,item,ctx,changed_ids):
    """Explain identity and actual source relationships without prescribing two actions."""
    p=item['path'];level=len(p)-1;r=ctx.records[level][v[1]];tid=item['candidate']['Candidate_Target_Id']
    reasons={'exact':'Nama dan lokasi sama dengan master.',
             'spelling_alias':'Nama cocok dengan nama inti atau variasi ejaan yang tertulis pada master.',
             'qualified':'Nama cocok setelah keterangan kabupaten/kota setelah koma diperiksa.',
             'registered_alias':'Nama singkat cocok dengan alias yang sudah didaftarkan.',
             'city_core':'Nama cocok setelah awalan administratif diperiksa.',
             'one_letter':'Nama berbeda satu huruf dalam lokasi yang sama. Pastikan kedua nama merujuk data yang sama.'}
    lines=['• Dasar usulan: '+reasons[item['kind']]]
    if item['parent_context']:
        # This source will retire if approved; do not ask to fill its Parent as
        # another action alongside the proposed merge.
        lines.append('• Konteks lokasi: '+item['parent_context'].split(' Kolom kecamatan utama',1)[0])
    if v[3]:lines.append('• Parent pada sumber: '+v[3]+(' — '+str(v[4]) if v[4] else '')+'.')
    else:lines.append('• Parent utama pada sumber: kosong.')
    if r['Source_Legacy_Kecamatans']:
        lines.append('• Relasi kecamatan lama pada sumber: '+r['Source_Legacy_Kecamatans']+'.')
    if v[6]:lines.append('• Kabupaten/kota langsung pada sumber: '+v[6]+'.')
    if v[5]:lines.append('• Konteks Parent sumber: '+str(v[5])+'.')
    if v[7]:lines.append('• Konteks kabupaten/kota langsung: '+str(v[7])+'.')
    expected_parent=ctx.inventory[p[:-1]]['Target_Id']
    target_parent=ctx.records[level][tid]['Source_Parent_Id']
    if expected_parent and target_parent==expected_parent:
        lines.append('• Parent ID tujuan sudah '+p[-2]+' ('+expected_parent+'), sesuai master.')
    if tid in changed_ids:
        lines.append('• ID tujuan juga ada pada PERUBAHAN. Selesaikan review nama/Parent tujuan sebelum penggabungan.')
    else:lines.append('• ID tujuan sesuai lokasi master; periksa kembali relasi tujuan sebelum penggabungan.')
    lines.append('• Tindakan: konfirmasikan ID yang dipertahankan dan referensi data anak. Jika digabung, tidak perlu memperbaiki Parent sumber yang akan dinonaktifkan. Tidak ada penggabungan otomatis.')
    if v[10]:lines.extend(['','Temuan pada tingkat lain (bukti tambahan):',v[10]])
    return '\n'.join(lines)


def duplicate_row(v,item,ctx,changed_ids):
    rid=v[1];c=item['candidate'];level=LABELS.index(v[0]);kind=item['kind']
    status=('Dugaan duplikat — konfirmasi ejaan' if kind=='one_letter' else
            'Usulan duplikat — nama dan lokasi sama' if kind=='exact' else 'Usulan duplikat — variasi nama')
    districts=ctx.kec_refs[rid] if level==1 else 0
    villages=ctx.kel_refs[rid] if level in (1,2) else 0
    impact='Hitungan hanya mencakup relasi langsung pada ekspor regional; periksa juga referensi pada objek Salesforce lain.'
    if ctx.legacy_refs[rid]:impact+=f' Ada {ctx.legacy_refs[rid]} kelurahan yang menyebut ID ini pada relasi kecamatan lama; periksa terpisah dari hitungan relasi utama.'
    return [v[0],rid,v[2],c['Candidate_Target_Id'],c['Candidate_Name'],' | '.join(item['path']),status,
            proposal_note(v,item,ctx,changed_ids),districts,villages,districts+villages,impact,None,None,None,None,None]


def sheet_xml(meta,rows,widths,input_start=None,date_col=None):
    body=BytesIO()
    for n,values in enumerate(rows,1):
        row=E.Element(TAG+'row',r=str(n),spans=f'1:{len(widths)}')
        for col,value in enumerate(values,1):
            style=3 if n==1 else 18 if col==date_col else 17 if input_start and col>=input_start else 6
            put(row,col,value,style)
        if n==1:row.set('ht','62');row.set('customHeight','1')
        else:row_height(row,values,widths,360)
        body.write(encode(row))
    layout(meta,widths)
    for key in ['dimension','autoFilter']:
        node=meta.find('m:'+key,NS)
        if node is not None:node.set('ref',f'A1:{get_column_letter(len(widths))}{len(rows)}')
    return E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')


def format_data(meta,rows):
    last=len(rows);known=[n for n,v in enumerate(rows[1:],2) if v[13] and ';' not in v[13]]
    unknown=sorted(set(range(2,last+1))-set(known))
    options=['Gunakan rekomendasi','Gunakan ID lain','Buat data baru','Di luar master','Perlu diskusi']
    rules(meta,[(ranges(known,'Q'),options),(ranges(unknown,'Q'),options[1:])],
          [(f'Q2:R{last}','AND(OR($Q2="Gunakan ID lain",$Q2="MASUKKAN_ID_LAIN"),$R2="")'),
           (f'S2:T{last}','AND(OR($Q2="Buat data baru",$Q2="BUAT_DATA_BARU"),OR($S2="",$T2=""))'),
           (f'Q2:Q{last}','AND(OR($Q2="Gunakan rekomendasi",$Q2="PILIH_KANDIDAT_1"),OR($N2="",ISNUMBER(SEARCH(";",$N2))))'),
           (f'V2:W{last}','AND($Q2<>"",OR($V2="",$W2=""))')],
          [f'R2:R{last}',f'T2:T{last}'])
    widths=[17,24,32,24,32,65,24,65,35,75,80,35,75,28,38,90,28,28,35,28,60,22,22]
    return sheet_xml(meta,rows,widths,17,23)


def format_duplicates(meta,rows):
    last=len(rows)
    rules(meta,[(f'M2:M{last}',['Gabungkan ke usulan','Bukan duplikat','Gunakan ID lain','Perlu diskusi'])],
          [(f'N2:N{last}','AND(OR($M2="Gunakan ID lain",$M2="GUNAKAN_ID_TUJUAN_LAIN"),$N2="")'),
           (f'P2:Q{last}','AND($M2<>"",OR($P2="",$Q2=""))')],[f'N2:N{last}'])
    return sheet_xml(meta,rows,[17,24,34,24,35,80,42,100,22,22,24,75,28,28,65,22,22],13,17)


def apply(workbook,pipeline,backup,report_path):
    assert not backup.exists(),'Choose a fresh backup path'
    backup.write_bytes(workbook.read_bytes())
    ctx,data,plans,stats=inspect_plan(pipeline,backup,report_path)
    byid={v[1]:v for v in data}
    # No silent self-reference: same-ID work must have an explicit field-level
    # repair. Fail before writing if this safety condition changes in future data.
    for rid,item in plans.items():
        if item['action']=='repair':
            item.setdefault('rows',self_rows(byid[rid],item['path'],ctx))
            assert item['rows'],'Same-ID match has no repair; reclassify as valid separately'
    with ZipFile(backup) as z:
        a=Package(z);replacements={};changes={}
        changed_ids=set()
        for i in [8,9,10]:
            changes[i]=[a.values(r,19) for r in a.rows(i) if r.get('r')!='1']
            changed_ids.update(v[1] for v in changes[i])
        moved=Counter();dups=[DUP_HEADERS]
        assert a.values(next(a.rows(13)),17)[15:]==[None,None],'This stage expects the 15-column duplicate review'
        for row in a.rows(13):
            if row.get('r')=='1':continue
            v=a.values(row,15)
            dups.append(v[:6]+['Usulan duplikat — pemeriksaan sebelumnya',
                'Indikasi duplikat dari pemeriksaan sebelumnya. Konfirmasikan lokasi master, ID yang dipertahankan, dan semua referensi data anak; tidak ada penggabungan otomatis.']+v[6:])
        data_out=[a.values(next(a.rows(14)),23)]
        for v in data:
            item=plans.get(v[1])
            if item and item['action']=='duplicate':
                dups.append(duplicate_row(v,item,ctx,changed_ids));moved[v[0]]+=1;continue
            if item and item['action']=='repair':
                changes[{'Kota/Kabupaten':8,'Kecamatan':9,'Kelurahan':10}[v[0]]].extend(item['rows']);continue
            if item:
                display=view(item['candidate']);v=v.copy();v[11:16]=[x or None for x in display]
                v[8]='Lokasi rekomendasi perlu dikonfirmasi'
                v[9]=('Nama cocok dalam kabupaten/kota yang tercatat. Kecamatan sumber belum lengkap atau berbeda dari lokasi master; '
                      'pastikan kecamatan sebelum memilih ID tujuan.' if item['kind']=='city_only' else
                      'Nama dan lokasi rekomendasi sudah dicocokkan dengan master. Baca status ID dan konfirmasikan relasinya sebelum memilih ID tujuan.')
            data_out.append(v)
        replacements['xl/worksheets/sheet13.xml']=format_duplicates(a.metadata(13),dups)
        replacements['xl/worksheets/sheet14.xml']=format_data(a.metadata(14),data_out)
        for i in [8,9,10]:
            if any(p['action']=='repair' and LABELS.index(byid[rid][0])+7==i for rid,p in plans.items()):
                replacements[f'xl/worksheets/sheet{i}.xml']=format_review(a.metadata(i),changes[i])
        # Keep cross-level and other informational evidence intact. Replace
        # same-level alternatives only for sources whose proposal changed.
        from regional_client_display import INFORMATIONAL_STATUSES
        duplicate_by_id={v[1]:v for v in dups[1:]}
        def mapping_display(rid,item):
            if item['action']=='duplicate':
                d=duplicate_by_id[rid]
                return [d[4],d[5],d[3],d[6],d[7]]
            return view(item['candidate'])
        mapping=[];emitted=set();order=Counter()
        for row in a.rows(15):
            v=a.values(row,12)
            if row.get('r')=='1':mapping.append(v);continue
            rid=v[1];item=plans.get(rid)
            if item and rid not in emitted:
                source=byid[rid]
                display=mapping_display(rid,item)
                mapping.append([source[0],rid,source[2],0]+[x or None for x in display]+['Master',source[0],1]);emitted.add(rid)
            if item and v[7] not in INFORMATIONAL_STATUSES:continue
            mapping.append(v)
        for rid,item in plans.items():
            if rid not in emitted:
                v=byid[rid];mapping.append([v[0],rid,v[2],0]+[x or None for x in mapping_display(rid,item)]+['Master',v[0],1])
        for v in mapping[1:]:
            if v[1] in plans:order[v[1]]+=1;v[3]=order[v[1]]
        replacements['xl/worksheets/sheet15.xml']=sheet_xml(a.metadata(15),mapping,[17,24,34,10,38,85,28,42,100,20,22,18])
        # Summary follows ID groups, not the number of relationship-review rows.
        for i,width in [(1,2),(2,8),(3,3)]:
            meta=a.metadata(i);body=BytesIO()
            for row in a.rows(i):
                v=a.values(row,width)
                if i==2 and row.get('r')!='1':
                    v[5]+=moved[v[0]];v[6]-=moved[v[0]]
                    repaired=sum(p['action']=='repair' and byid[rid][0]==v[0] for rid,p in plans.items())
                    v[3]+=repaired;v[6]-=repaired
                    for col,value in enumerate(v,1):put(row,col,value)
                if i==1 and row.get('r')=='7':
                    put(row,2,'DATA DUPLIKAT berisi usulan dengan kecocokan kuat. Baca Status Konfirmasi, Alasan Usulan, dan Hierarki Master. Pilih keputusan pada M–Q; periksa referensi anak sebelum penggabungan. Jika ID sumber digabung ke ID lain, tidak perlu membuat perbaikan Parent untuk sumber yang akan dinonaktifkan. DATA BELUM JELAS tetap untuk nama/lokasi/ID yang belum pasti. PERUBAHAN untuk perbaikan dengan ID data tetap. Tidak ada persetujuan otomatis.')
                if i==3 and v[0]=='Duplikat':
                    put(row,2,'Usulan penggabungan dengan kecocokan kuat, bukan persetujuan otomatis. Status membedakan nama sama, variasi nama, dan dugaan beda satu huruf. Baca alasan dan lokasi; konfirmasikan ejaan, ID tujuan, serta referensi data anak.')
                body.write(encode(row))
            replacements[f'xl/worksheets/sheet{i}.xml']=E.tostring(meta).replace(b'<sheetData/>',b'<sheetData>'+body.getvalue()+b'</sheetData>')
        wb=E.fromstring(z.read('xl/workbook.xml'))
        sizes={'DATA DUPLIKAT':('Q',len(dups)),'DATA BELUM JELAS':('W',len(data_out)),'PILIHAN MAPPING':('L',len(mapping))}
        for d in wb.findall('m:definedNames/m:definedName',NS):
            for title,(end,n) in sizes.items():
                if d.text.startswith("'"+title+"'!"):d.text=f"'{title}'!$A$1:${end}${n}"
        replacements['xl/workbook.xml']=E.tostring(wb)
        shared=E.fromstring(z.read('xl/sharedStrings.xml'));refs=0
        for name in z.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):
                refs+=len(re.findall(rb'<(?:\w+:)?c\b[^>]*\bt="s"',replacements.get(name,z.read(name))))
        shared.set('count',str(refs));replacements['xl/sharedStrings.xml']=E.tostring(shared)
        with tempfile.NamedTemporaryFile(dir=workbook.parent,suffix='.xlsx',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w') as out:
                for info in z.infolist():out.writestr(info,replacements.get(info.filename,z.read(info.filename)))
            with ZipFile(temp) as check:assert check.testzip() is None
            temp.replace(workbook)
        finally:temp.unlink(missing_ok=True)
    result={'counts':dict(stats),'moved_by_object':dict(moved),'data_duplicate':len(dups)-1,'data_unclear':len(data_out)-1,
            'mapping_rows':len(mapping)-1,'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(workbook.read_bytes()).hexdigest(),
            'plans':{rid:{k:v for k,v in item.items() if k!='candidate'} for rid,item in plans.items()}}
    report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['workbook','pipeline','backup','report']:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();result=apply(args.workbook,args.pipeline,args.backup,args.report)
    print(json.dumps({k:v for k,v in result.items() if k!='plans'},ensure_ascii=False,indent=2))
