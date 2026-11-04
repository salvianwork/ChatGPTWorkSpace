"""Verify workbook changes against the original and the validated candidate CSV."""
import argparse
from collections import defaultdict
import csv
import gc
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_regional_client_workbook import EXTRA_HEADERS,METADATA,MAPPING_KEYS,PURPOSES

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
TAG='{'+NS['m']+'}'


def check(before,after,candidates):
    with ZipFile(before) as a,ZipFile(after) as b:
        assert a.namelist()==b.namelist();assert b.testzip() is None
        changed={n for n in a.namelist() if a.read(n)!=b.read(n)}
        assert changed<= {'xl/worksheets/sheet14.xml','xl/worksheets/sheet15.xml','xl/styles.xml'},changed
        ar=E.fromstring(a.read('xl/worksheets/sheet14.xml'));br=E.fromstring(b.read('xl/worksheets/sheet14.xml'))
        oldrows=ar.find('m:sheetData',NS);newrows=br.find('m:sheetData',NS)
        assert len(oldrows)==len(newrows)
        style_tree=E.fromstring(b.read('xl/styles.xml'));xfs=style_tree.find('m:cellXfs',NS)
        for old,new in zip(oldrows,newrows,strict=True):
            assert {k:v for k,v in old.attrib.items() if k!='spans'}=={k:v for k,v in new.attrib.items() if k!='spans'}
            if old.get('spans') is None:new.attrib.pop('spans',None)
            else:new.set('spans',old.get('spans'))
            for row in [old,new]:
                for c in list(row):
                    col=openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r')))
                    if 12<=col<=24 or col>=33:
                        assert not c.findall('m:f',NS)
                        if row is new and col>=33:
                            assert xfs[int(c.get('s','0'))].find('m:alignment',NS).get('wrapText')=='1'
                        row.remove(c)
        for key in ['dimension','autoFilter']:br.find('m:'+key,NS).set('ref',ar.find('m:'+key,NS).get('ref'))
        cols=br.find('m:cols',NS)
        for c in list(cols):
            if int(c.get('min'))>=33:cols.remove(c)
        oldcols=ar.find('m:cols',NS)
        for c in list(oldcols):
            if int(c.get('min'))>=33:oldcols.remove(c)
        assert E.tostring(ar)==E.tostring(br),'Protected source/client cells or sheet settings changed'
        del ar,br,oldrows,newrows;gc.collect()
        def metadata(raw):
            assert b'<f' not in raw
            start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
            return E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:])
        am=metadata(a.read('xl/worksheets/sheet15.xml'));bm=metadata(b.read('xl/worksheets/sheet15.xml'))
        for key in ['dimension','autoFilter']:bm.find('m:'+key,NS).set('ref',am.find('m:'+key,NS).get('ref'))
        for tree in [am,bm]:
            cols=tree.find('m:cols',NS)
            for c in list(cols):
                if int(c.get('min'))>=17:cols.remove(c)
        assert E.tostring(am)==E.tostring(bm)
        ast=E.fromstring(a.read('xl/styles.xml'));bst=E.fromstring(b.read('xl/styles.xml'))
        ax=ast.find('m:cellXfs',NS);bx=bst.find('m:cellXfs',NS)
        assert len(bx)>=len(ax)
        assert all(E.tostring(x)==E.tostring(y) for x,y in zip(ax,bx))
        for extra in list(bx)[len(ax):]:
            assert extra.find('m:alignment',NS).get('wrapText')=='1';bx.remove(extra)
        bx.set('count',ax.get('count'));assert E.tostring(ast)==E.tostring(bst)
    print('PASS: protected original cells, IDs, inputs, dropdowns, formulas, row order and 13 other sheets unchanged.')
    with candidates.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    old=openpyxl.load_workbook(before,read_only=True);w=openpyxl.load_workbook(after,read_only=True)
    assert w.sheetnames==old.sheetnames
    for s in w:
        if s.title not in ['DATA BELUM JELAS','PILIHAN MAPPING']:
            assert (s.max_row,s.max_column)==(old[s.title].max_row,old[s.title].max_column)
    assert w['DATA BELUM JELAS'].max_row==old['DATA BELUM JELAS'].max_row
    assert w['DATA BELUM JELAS'].max_column==44
    it=w['PILIHAN MAPPING'].values;headers=next(it)
    assert headers==tuple(['Kegunaan']+MAPPING_KEYS+METADATA)
    groups=defaultdict(list)
    for row,expected in zip(it,records,strict=True):
        actual=dict(zip(headers,row));assert actual['Kegunaan']==PURPOSES[expected['Jenis_Bukti']]
        assert all((actual[k] or '')==v for k,v in expected.items())
        if actual['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':groups[actual['Id_Sumber']].append(actual)
        else:assert not actual['Id_Target_Kandidat']
    it=w['DATA BELUM JELAS'].values;headers=next(it)
    assert headers[:32]==next(old['DATA BELUM JELAS'].values)[:32]
    assert list(headers[32:])==EXTRA_HEADERS
    samples={};names={'a1ofC000001vBcaQAE','a1pJ40000008X4aIAE','a1pJ40000008XDhIAM','a1pJ40000008XVWIA2','a1nJ4000000KUKFIA4','a1nfC00000VF9PmQAL'}
    for row in it:
        d=dict(zip(headers,row));cs=groups[d['Id_Sumber']]
        assert d['Jumlah_Pilihan_Mapping']==len(cs)
        for i in range(3):
            for suffix,key in [('Nama','Nama_Kandidat'),('Hierarki','Hierarki_Kandidat'),('Id_Target','Id_Target_Kandidat'),('Alasan','Alasan')]+[(key,key) for key in METADATA]:
                assert d[f'Pilihan_{i+1}_{suffix}']==(cs[i][key] if i<len(cs) else None)
        if d['Id_Sumber'] in names:
            assert d['Id_Target_Final_Client'] is None
            samples[d['Nama_Sumber']]={k:d[k] for k in headers if k.startswith('Pilihan_1_')}
    assert len(samples)==6
    print('PASS: every mapping row, visible choice, count and metadata field matches validated script output; no automatic final IDs.')
    print(json.dumps(samples,ensure_ascii=False,indent=2))
    old.close();w.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path);parser.add_argument('after',type=Path);parser.add_argument('candidates',type=Path)
    args=parser.parse_args();check(args.before,args.after,args.candidates)
