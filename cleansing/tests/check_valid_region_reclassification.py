"""Check region reclassification against the previous workbook and pipeline data."""
import argparse
from collections import Counter
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
from regional_validity import PENDING_REGION,PENDING_PRIMARY,OBJECT_LABELS,valid_client_row

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
TAG='{'+NS['m']+'}'


def signature(node):
    return (node.tag,tuple(sorted((k,v) for k,v in node.attrib.items() if k not in {'r','spans'})),
            node.text,node.tail,tuple(signature(c) for c in node))


class Archive:
    def __init__(self,z):
        self.z=z
        self.strings=[''.join(si.itertext()) for si in E.fromstring(z.read('xl/sharedStrings.xml'))]

    def value(self,c):
        if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
        v=c.findtext('m:v',namespaces=NS)
        if c.get('t')=='s':return self.strings[int(v)]
        return int(v) if v and v.isdigit() and c.get('t') is None else v

    def rows(self,index):
        with self.z.open(f'xl/worksheets/sheet{index}.xml') as f:
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                cells={openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
                values=tuple(self.value(cells[i]) if i in cells else None for i in range(1,max(cells)+1))
                yield values,signature(row)
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]

    def metadata(self,index):
        raw=self.z.read(f'xl/worksheets/sheet{index}.xml')
        assert re.search(rb'<f(?:\s|>)',raw) is None,'New worksheet formulas'
        start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
        return E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:])


def check(before,after,root):
    pending={}
    for level,prefix in enumerate(['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']):
        with (root/'05_All_Records'/f'{prefix}_all_records.csv').open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                if row['Status_Validasi_Wilayah']==PENDING_REGION:
                    assert row['Status_Penetapan_ID_Utama']==PENDING_PRIMARY
                    assert row['Status']=='COCOK_MASTER_ID_TARGET_BELUM_TERVERIFIKASI'
                    pending[row['Id_Sumber']]=(level,dict(row,Objek=list(OBJECT_LABELS)[level]))
    with (root/'04_Master_Targets'/'Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        inventory={r['Hierarki_Master']:r['Id_Target'] for r in csv.DictReader(f)}
    for level,source in pending.values():
        path=[source[k] for k in ['Provinsi_Target','KotaKabupaten_Target','Kecamatan_Target','Kelurahan_Target'] if source[k]]
        assert source['Nama_Sumber']==path[-1]
        assert source['Metode_Pencocokan']=='COCOK_PERSIS_DALAM_HIERARKI'
        if level:
            assert source['Id_Induk_Sumber']==inventory[' | '.join(path[:-1])]
            assert source['Id_Induk_Sumber'] and source['Bukti_Induk']=='ID_LOOKUP_INDUK'
        if level==3:
            assert source['Id_Kota_Langsung_Sumber']==inventory[' | '.join(path[:2])]
            assert source['Id_Kota_Langsung_Sumber']
    with ZipFile(before) as oldzip,ZipFile(after) as newzip:
        assert oldzip.namelist()==newzip.namelist() and newzip.testzip() is None
        changed={n for n in oldzip.namelist() if oldzip.read(n)!=newzip.read(n)}
        allowed={f'xl/worksheets/sheet{i}.xml' for i in [2,4,5,6,7,14,15]}|{'xl/workbook.xml','xl/styles.xml'}
        assert changed<=allowed,changed
        a,b=Archive(oldzip),Archive(newzip)
        previous_ids=Counter();current_ids=Counter();moved={};deferred=set();existing_pending=set()
        for level in range(4):
            for values,_ in a.rows(level+4):
                if values[0]=='Objek':continue
                previous_ids[values[1]]+=1
                if values[9]=='Data wilayah sudah sesuai. Penetapan ID utama masih menunggu konfirmasi client.':
                    existing_pending.add(values[1])

        def remaining():
            for values,sig in a.rows(14):
                if values[0]=='Objek':yield values,sig;continue
                previous_ids[values[1]]+=1
                if values[1] in pending and not any(values[27:35]):
                    moved[values[1]]=values
                else:
                    if values[1] in pending:deferred.add(values[1])
                    yield values,sig
        for old,new in zip_longest(remaining(),b.rows(14)):
            assert old is not None and new is not None and old==new,'Remaining review record changed'
            if new[0][0]!='Objek':current_ids[new[0][1]]+=1
        counts=Counter(pending[rid][0] for rid in moved)
        for level in range(4):
            newrows=b.rows(level+4)
            for expected in a.rows(level+4):
                actual=next(newrows)
                assert expected==actual,'Existing valid record changed'
                if actual[0][0]!='Objek':current_ids[actual[0][1]]+=1
            for rid,oldvalues in moved.items():
                lev,source=pending[rid]
                if lev!=level:continue
                actual=next(newrows)[0]
                assert actual==tuple(valid_client_row(source)),rid
                assert actual[1:3]==oldvalues[1:3]
                assert (actual[5] or '')==(oldvalues[3] or '')
                current_ids[rid]+=1
            assert next(newrows,None) is None
        assert previous_ids==current_ids and all(n==1 for n in current_ids.values())
        assert set(pending)==set(moved)|existing_pending|deferred
        hidden=set(moved)|existing_pending
        expected_mapping=(row for row in a.rows(15) if row[0][1] not in hidden)
        mapping_count=0
        for old,new in zip_longest(expected_mapping,b.rows(15)):
            assert old==new,'Unrelated mapping record changed'
            mapping_count+=1
        assert all(not any(values[27:35]) for values in moved.values())
        oldsummary=[r[0] for r in a.rows(2)];newsummary=[r[0] for r in b.rows(2)]
        assert newsummary[0]==oldsummary[0][:8]+('Valid_Menunggu_ID_Utama',)
        labels=list(OBJECT_LABELS.values())
        for old,new in zip(oldsummary[1:],newsummary[1:],strict=True):
            level=labels.index(old[0]);expected=list(old[:8])
            expected[2]+=counts[level];expected[7]-=counts[level]
            expected.append(sum(pending[rid][0]==level for rid in hidden))
            assert tuple(expected)==new
        for index in [4,5,6,7,14,15]:
            am,bm=a.metadata(index),b.metadata(index)
            for key in ['dimension','autoFilter']:
                av,bv=am.find('m:'+key,NS),bm.find('m:'+key,NS)
                if av is not None:bv.set('ref',av.get('ref'))
            ad,bd=am.find('m:dataValidations',NS),bm.find('m:dataValidations',NS)
            if ad is not None:
                assert len(ad)==len(bd)
                last=sum(1 for _ in b.rows(index))
                for av,bv in zip(ad,bd,strict=True):
                    areas=[]
                    for area in av.get('sqref').split():
                        minc,minr,maxc,_=openpyxl.utils.range_boundaries(area)
                        areas.append(f'{openpyxl.utils.get_column_letter(minc)}{minr}:{openpyxl.utils.get_column_letter(maxc)}{last}')
                    assert bv.get('sqref')==' '.join(areas)
                    bv.set('sqref',av.get('sqref'))
            assert E.tostring(am)==E.tostring(bm),'Worksheet settings changed'
        aw,bw=E.fromstring(oldzip.read('xl/workbook.xml')),E.fromstring(newzip.read('xl/workbook.xml'))
        for av,bv in zip(aw.find('m:definedNames',NS),bw.find('m:definedNames',NS),strict=True):
            if av.get('name')=='_xlnm._FilterDatabase' and int(av.get('localSheetId')) in [1,3,4,5,6,13,14]:bv.text=av.text
        assert E.tostring(aw)==E.tostring(bw),'Workbook settings or sheet order changed'
        ast,bst=E.fromstring(oldzip.read('xl/styles.xml')),E.fromstring(newzip.read('xl/styles.xml'))
        ax,bx=ast.find('m:cellXfs',NS),bst.find('m:cellXfs',NS)
        assert len(bx)>=len(ax)
        assert all(E.tostring(x)==E.tostring(y) for x,y in zip(ax,bx))
        for extra in list(bx)[len(ax):]:
            assert extra.find('m:alignment',NS).get('wrapText')=='1';bx.remove(extra)
        bx.set('count',ax.get('count'));assert E.tostring(ast)==E.tostring(bst)
        for i in range(1,16):
            assert re.search(rb'<f(?:\s|>)',newzip.read(f'xl/worksheets/sheet{i}.xml')) is None
        lawang='a1nJ4000000Kc3PIAS'
        assert lawang in hidden|deferred and 'a1nJ4000000KYnfIAG' not in hidden
        assert 'a1nJ4000000Kc2yIAC' not in hidden,'Missing parent still needs review'
        assert 'a1nJ4000000KUKFIA4' not in hidden,'Conflicting city still needs review'
        print(json.dumps({'moved':len(moved),'pending_primary':len(hidden),'deferred_client_inputs':len(deferred),
                          'mapping_rows_after':mapping_count-1,'changed_parts':sorted(changed)},indent=2))
    old=openpyxl.load_workbook(before,read_only=True);new=openpyxl.load_workbook(after,read_only=True)
    assert old.sheetnames==new.sheetnames and len(new.sheetnames)==15
    assert new['DATA BELUM JELAS'].max_row==old['DATA BELUM JELAS'].max_row-len(moved)
    assert new['DATA BELUM JELAS'].max_column==35
    assert new['PILIHAN MAPPING'].max_row==mapping_count and new['PILIHAN MAPPING'].max_column==12
    for level,name in enumerate(['VALID PROVINSI','VALID KOTA','VALID KECAMATAN','VALID KELURAHAN']):
        assert new[name].max_row==old[name].max_row+counts[level]
        assert new[name].max_column==old[name].max_column==12
    old.close();new.close()
    print('PASS: source IDs, exact relationships, client values/styles/dropdowns, remaining rows/order, summary, sheet order, ZIP integrity and formulas.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['before','after','records_root']:parser.add_argument(name,type=Path)
    args=parser.parse_args();check(args.before,args.after,args.records_root)
