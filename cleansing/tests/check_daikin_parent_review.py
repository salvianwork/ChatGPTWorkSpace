"""Compare a Parent-queue split with its backup, including every remaining cell."""
import argparse
from collections import Counter,defaultdict
import csv
from itertools import zip_longest
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile
from lxml import etree as E
import openpyxl

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from daikin_parent_review import TITLE,HEADERS,STATUS
from check_valid_region_reclassification import Archive,NS,TAG


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def check(before,after,pipeline):
    candidates=defaultdict(list)
    for c in csv_rows(pipeline/'03_Manual_Review'/'Review_candidates.csv'):
        if c['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':candidates[c['Id_Sumber']].append(c)
    targets={tuple(r['Hierarki_Master'].split(' | ')):r['Id_Target']
             for r in csv_rows(pipeline/'04_Master_Targets'/'Master_target_inventory.csv')}
    sources={r['Id_Sumber']:r for prefix in ['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']
             for r in csv_rows(pipeline/'05_All_Records'/f'{prefix}_all_records.csv')}

    def expected(v):
        # Independently derive the complete eligible set from the original rows.
        if v[0] not in {'Kecamatan','Kelurahan'} or not v[1] or v[1]!=v[14]:return None
        choices=candidates[v[1]]
        if len(choices)!=1 or any(v[17:]):return None
        c=choices[0];path=tuple(c['Hierarki_Kandidat'].split(' | '))
        if len(path)!={'Kecamatan':3,'Kelurahan':4}[v[0]] or c['Objek']!=v[0]+'__c':return None
        assert (c['Id_Target_Kandidat'] or c['ID_Master_Perlu_Verifikasi'])==v[1]
        assert c['Hierarki_Kandidat']==v[13]
        if not v[2]==c['Nama_Kandidat']==path[-1]:return None
        parent=targets.get(path[:-1]);city=targets.get(path[:2]) if len(path)==4 else None
        if not parent or (len(path)==4 and not city):return None
        actions=[]
        if (v[3] or '')!=parent:actions.append('Ubah Parent' if v[3] else 'Lengkapi Parent')
        if len(path)==4 and v[6]!=city:
            actions.append('Ubah kabupaten/kota langsung' if v[6] else 'Lengkapi kabupaten/kota langsung')
        return (path,parent,city,actions) if actions else None

    with ZipFile(before) as az,ZipFile(after) as bz:
        assert bz.testzip() is None
        added=set(bz.namelist())-set(az.namelist())
        assert added=={'xl/worksheets/sheet16.xml'}
        assert set(az.namelist())<=set(bz.namelist())
        changed={n for n in az.namelist() if az.read(n)!=bz.read(n)}
        allowed={f'xl/worksheets/sheet{i}.xml' for i in [1,2,3,14]}|{
            'xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml',
            'docProps/app.xml','xl/styles.xml','xl/sharedStrings.xml'}
        assert changed<=allowed,changed-allowed
        for i in [4,5,6,7,8,9,10,11,13,15]:
            entry=f'xl/worksheets/sheet{i}.xml';assert az.read(entry)==bz.read(entry)
        a,b=Archive(az),Archive(bz)
        moved={};plans={};old_ids=Counter();new_ids=Counter();counts=Counter()

        def data_rows(archive,index):
            for values,sig in archive.rows(index):yield values+(None,)*(24-len(values)),sig

        def remaining():
            for values,sig in data_rows(a,14):
                if values[0]=='Objek':yield values,sig;continue
                old_ids[values[1]]+=1;plan=expected(values)
                if plan:
                    assert values[1] not in moved
                    moved[values[1]]=values;plans[values[1]]=plan;counts[values[0]]+=1
                else:yield values,sig

        remaining_count=0
        for previous,current in zip_longest(remaining(),data_rows(b,14)):
            assert previous is not None and previous==current,'Remaining data, style or order changed'
            if current[0][0]!='Objek':
                remaining_count+=1;new_ids[current[0][1]]+=1
        assert moved,'No expected proposals'
        new_rows=b.rows(16);assert next(new_rows)[0]==tuple(HEADERS)
        actual_ids=[]
        for v,_ in new_rows:
            rid=v[1];assert rid in moved;actual_ids.append(rid);new_ids[rid]+=1
            old=moved[rid];path,parent,city,actions=plans[rid]
            assert v[:3]==old[:3]
            assert v[3]==('Kecamatan' if len(path)==4 else 'Kabupaten/kota')
            assert v[4:7]==old[3:6]
            assert v[7:9]==(parent,path[-2])
            assert v[9:11]==old[6:8]
            assert v[11:14]==(city,path[1] if city else None,' | '.join(path))
            assert v[14]=='; '.join(actions) and v[15]==STATUS
            oldnote=old[16] or ''
            prefix='ID ini sama dengan ID sumber. Hubungan wilayah masih perlu diperiksa.'
            if oldnote.startswith(prefix):oldnote=oldnote[len(prefix):].lstrip()
            assert v[16]=='ID data dipertahankan. Usulan perubahan menunggu keputusan Tim Daikin.'+('\n\n'+oldnote if oldnote else '')
            assert v[17]==old[10] and all(x is None for x in v[18:])
            assert not any(old[17:]),'Existing Tim Daikin inputs lost'
            source=sources[rid]
            assert (source['Nama_Sumber'],source['Id_Induk_Sumber'],source['Id_Kota_Langsung_Sumber'])==(old[2],old[3] or '',old[6] or '')
            for pid,ppath in [(parent,path[:-1])]+([(city,path[:2])] if city else []):
                record=sources[pid]
                actual=tuple(record[k] for k in ['Provinsi_Target','KotaKabupaten_Target','Kecamatan_Target','Kelurahan_Target'] if record[k])
                assert actual==ppath,'Proposed Parent ID belongs to another location'
        assert actual_ids==list(moved),'Moved rows were duplicated or reordered'
        for index in [4,5,6,7,8,9,10,13]:
            for v,_ in a.rows(index):
                if v[0]!='Objek':old_ids[v[1]]+=1;new_ids[v[1]]+=1
        assert old_ids==new_ids and all(n==1 for n in new_ids.values())
        summary_before=[v for v,_ in a.rows(2)];summary_after=[v for v,_ in b.rows(2)]
        assert summary_after[0]==summary_before[0]+('Perbaikan Parent ID Tetap',)
        for old,new in zip(summary_before[1:],summary_after[1:],strict=True):
            values=list(old);values[6]-=counts[old[0]];values.append(counts[old[0]])
            assert new==tuple(values)
        assert sum(v[2]+v[3]+v[5]+v[6]+v[8] for v in summary_after[1:])==len(new_ids)
        am,bm=a.metadata(14),b.metadata(14)
        for key in ['dimension','autoFilter']:
            assert bm.find('m:'+key,NS).get('ref')==f'A1:X{remaining_count+1}'
            bm.find('m:'+key,NS).set('ref',am.find('m:'+key,NS).get('ref'))
        ad,bd=am.find('m:dataValidations',NS),bm.find('m:dataValidations',NS)
        assert len(ad)==len(bd)==1 and bd[0].get('sqref')==f'R2:R{remaining_count+1}'
        bd[0].set('sqref',ad[0].get('sqref'));assert E.tostring(am)==E.tostring(bm)
        nm=b.metadata(16);last=len(moved)+1
        assert nm.find('m:dimension',NS).get('ref')==f'A1:X{last}'
        assert nm.find('m:autoFilter',NS).get('ref')==f'A1:X{last}'
        dv=nm.find('m:dataValidations/m:dataValidation',NS)
        assert dv.get('sqref')==f'S2:S{last}' and dv.get('type')=='list'
        assert dv.findtext('m:formula1',namespaces=NS)=='"SETUJU_UBAH,TOLAK_PERUBAHAN,PERLU_DISKUSI"'
        assert nm.find('m:sheetViews/m:sheetView/m:pane',NS).get('topLeftCell')=='D2'
        ast,bst=E.fromstring(az.read('xl/styles.xml')),E.fromstring(bz.read('xl/styles.xml'))
        ax,bx=ast.find('m:cellXfs',NS),bst.find('m:cellXfs',NS)
        assert len(bx)==len(ax)+2
        for x,y in zip(ax,bx):assert E.tostring(x)==E.tostring(y)
        for xf in list(bx)[len(ax):]:
            assert xf.find('m:alignment',NS).get('wrapText')=='1'
            assert xf.get('fillId')==ax[5].get('fillId')
        # Every new body cell wraps, including the blank review inputs.
        for col in nm.findall('m:cols/m:col',NS):
            assert bx[int(col.get('style'))].find('m:alignment',NS).get('wrapText')=='1'
        ash,bsh=E.fromstring(az.read('xl/sharedStrings.xml')),E.fromstring(bz.read('xl/sharedStrings.xml'))
        bsh.set('count',ash.get('count'));assert E.tostring(ash)==E.tostring(bsh)
        aw,bw=E.fromstring(az.read('xl/workbook.xml')),E.fromstring(bz.read('xl/workbook.xml'))
        oldnames=[s.get('name') for s in aw.find('m:sheets',NS)]
        newnames=[s.get('name') for s in bw.find('m:sheets',NS)]
        inserted=oldnames.index('DATA BELUM JELAS')
        assert newnames==oldnames[:inserted]+[TITLE]+oldnames[inserted:]
        for name in bw.findall('m:definedNames/m:definedName',NS):
            index=int(name.get('localSheetId'))
            assert name.text.startswith(("'"+newnames[index]+"'!",newnames[index]+'!')),(index,name.text)
        assert not any('_' in h for h in HEADERS)
        for entry in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):
                assert re.search(rb'<f(?:\s|>)',bz.read(entry)) is None
        for rid in ['a1nJ4000000KcG8IAK','a1nJ4000000KcG4IAK','a1nJ4000000Kc2yIAC']:
            assert rid in moved
        for rid in ['a1nfC00000VFAI6QAP','a1pJ40000008XEvIAM','a1oJ40000009gGfIAI']:
            assert rid in new_ids and rid not in moved
        assert plans['a1nJ4000000KcG8IAK'][1]=='a1pJ40000008Xi7IAE'
        assert plans['a1nJ4000000KcG4IAK'][1]=='a1pJ40000008Xi7IAE'
        result={'moved':len(moved),'moved_by_object':dict(counts),'remaining_data_rows':remaining_count,
                'total_unique_source_ids':len(new_ids),'changed_parts':sorted(changed),
                'added_parts':sorted(added),'all_review_decisions_blank':True}
    workbook=openpyxl.load_workbook(after,read_only=True)
    assert workbook.sheetnames==newnames and len(workbook.sheetnames)==15
    assert workbook[TITLE].max_row==last and workbook[TITLE].max_column==24
    assert workbook['DATA BELUM JELAS'].max_row==remaining_count+1
    assert workbook['PILIHAN MAPPING'].max_row==58590
    assert workbook['RINGKASAN'].max_column==9
    workbook.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('PASS: every source ID, remaining cell/style/order, proposals, pending decisions, summaries, dropdowns, unaffected sheets and formulas.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['before','after','pipeline']:parser.add_argument(arg,type=Path)
    args=parser.parse_args();check(args.before,args.after,args.pipeline)
