"""Validate the simple client layout without changing matching decisions or client input."""
import argparse
from copy import deepcopy
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
from regional_client_display import CHOICE_HEADERS,MAPPING_HEADERS,client_candidate,mapping_row,source_text
from reclassify_valid_regions import existing_pending_ids

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};TAG='{'+NS['m']+'}'


def signature(node, ignore_ref=False):
    return (node.tag,tuple(sorted((k,v) for k,v in node.attrib.items() if not (ignore_ref and k=='r'))),node.text,node.tail,
            tuple(signature(c) for c in node))


def check(before,after,candidates):
    with ZipFile(before) as a,ZipFile(after) as b:
        strings=[''.join(si.itertext()) for si in E.fromstring(a.read('xl/sharedStrings.xml'))]
        def value(c):
            if c is None:return None
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            v=c.findtext('m:v',namespaces=NS)
            return strings[int(v)] if c.get('t')=='s' else v
        already_valid=existing_pending_ids(a,value)
        assert a.namelist()==b.namelist();assert b.testzip() is None
        changed={n for n in a.namelist() if a.read(n)!=b.read(n)}
        assert changed<={'xl/worksheets/sheet14.xml','xl/worksheets/sheet15.xml','xl/styles.xml','xl/workbook.xml'},changed
        ar=E.fromstring(a.read('xl/worksheets/sheet14.xml'));br=E.fromstring(b.read('xl/worksheets/sheet14.xml'))
        oldrows=ar.find('m:sheetData',NS);newrows=br.find('m:sheetData',NS);assert len(oldrows)==len(newrows)
        old_client=28 if ar.find('m:dimension',NS).get('ref').split(':')[-1].startswith('AI') else 25
        colnum=lambda c:openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r')))
        for old,new in zip(oldrows,newrows,strict=True):
            assert {k:v for k,v in old.attrib.items() if k!='spans'}=={k:v for k,v in new.attrib.items() if k!='spans'}
            oc={colnum(c):c for c in old};nc={colnum(c):c for c in new}
            for col in range(1,9):
                assert (col in oc)==(col in nc)
                if col in oc:assert signature(oc[col])==signature(nc[col]),oc[col].get('r')
            for offset in range(8):
                oldc=oc.get(old_client+offset);newc=nc.get(28+offset)
                assert (oldc is None)==(newc is None)
                if oldc is not None:
                    assert signature(oldc,True)==signature(newc,True),oldc.get('r')
        print('PASS: every source ID/name and client input cell is preserved after moving the client columns.')
        assert not br.findall('.//m:f',NS)
        xfs=E.fromstring(b.read('xl/styles.xml')).find('m:cellXfs',NS)
        wrapped={i for i,xf in enumerate(xfs) if xf.find('m:alignment',NS) is not None and xf.find('m:alignment',NS).get('wrapText')=='1'}
        for row in newrows:
            for c in row:
                if 12<=colnum(c)<=27:assert int(c.get('s','0')) in wrapped
        print('PASS: recommendation text wraps correctly.')
        def settings(tree):
            return {i:{k:v for k,v in c.attrib.items() if k not in ['min','max']} for c in tree.find('m:cols',NS) for i in range(int(c.get('min')),int(c.get('max'))+1)}
        os,ns=settings(ar),settings(br)
        for col in range(1,12):assert os[col]==ns[col]
        for offset in range(8):assert os[old_client+offset]==ns[28+offset]
        od=ar.find('m:dataValidations',NS);nd=br.find('m:dataValidations',NS)
        assert len(od)==len(nd)
        for old,new in zip(od,nd,strict=True):
            expected=[]
            for area in old.get('sqref').split():
                minc,minr,maxc,maxr=openpyxl.utils.range_boundaries(area)
                assert old_client<=minc<=maxc<old_client+8
                expected.append(f'{openpyxl.utils.get_column_letter(minc-old_client+28)}{minr}:{openpyxl.utils.get_column_letter(maxc-old_client+28)}{maxr}')
            assert new.get('sqref')==' '.join(expected)
            cp=deepcopy(new);cp.set('sqref',old.get('sqref'));assert E.tostring(deepcopy(old))==E.tostring(cp)
        def metadata(raw):
            assert re.search(rb'<f(?:\s|>)',raw) is None
            start=raw.index(b'<sheetData>');end=raw.index(b'</sheetData>')+len(b'</sheetData>')
            tree=E.fromstring(raw[:start]+b'<sheetData/>'+raw[end:]);tree.remove(tree.find('m:cols',NS));return tree
        arm=metadata(a.read('xl/worksheets/sheet14.xml'));brm=metadata(b.read('xl/worksheets/sheet14.xml'))
        for tree in [arm,brm]:tree.remove(tree.find('m:dataValidations',NS))
        for key in ['dimension','autoFilter']:brm.find('m:'+key,NS).set('ref',arm.find('m:'+key,NS).get('ref'))
        assert E.tostring(arm)==E.tostring(brm)
        print('PASS: sheet layout, client formats, dropdown options and adjusted dropdown positions are correct.')
        am=metadata(a.read('xl/worksheets/sheet15.xml'));bm=metadata(b.read('xl/worksheets/sheet15.xml'))
        for key in ['dimension','autoFilter']:bm.find('m:'+key,NS).set('ref',am.find('m:'+key,NS).get('ref'))
        assert E.tostring(am)==E.tostring(bm)
        aw=E.fromstring(a.read('xl/workbook.xml'));bw=E.fromstring(b.read('xl/workbook.xml'))
        an=aw.find('m:definedNames',NS);bn=bw.find('m:definedNames',NS)
        for old,new in zip(an,bn,strict=True):
            if old.get('name')=='_xlnm._FilterDatabase' and old.get('localSheetId') in {'13','14'}:new.text=old.text
        assert E.tostring(aw)==E.tostring(bw)
        ast=E.fromstring(a.read('xl/styles.xml'));bst=E.fromstring(b.read('xl/styles.xml'))
        ax=ast.find('m:cellXfs',NS);bx=bst.find('m:cellXfs',NS);assert len(bx)>=len(ax)
        assert all(E.tostring(x)==E.tostring(y) for x,y in zip(ax,bx))
        for extra in list(bx)[len(ax):]:
            assert extra.find('m:alignment',NS).get('wrapText')=='1';bx.remove(extra)
        bx.set('count',ax.get('count'));assert E.tostring(ast)==E.tostring(bst)
    print('PASS: source IDs/names, client values/styles, dropdown choices and 13 other sheets unchanged; dropdown positions updated correctly; no new formulas.')
    with candidates.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    records=[r for r in records if r['Id_Sumber'] not in already_valid]
    from collections import defaultdict
    groups=defaultdict(list)
    for d in records:
        if d['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':groups[d['Id_Sumber']].append(d)
    old=openpyxl.load_workbook(before,read_only=True);w=openpyxl.load_workbook(after,read_only=True)
    assert w.sheetnames==old.sheetnames
    for sheet in w:
        if sheet.title!='PILIHAN MAPPING':assert sheet.max_row==old[sheet.title].max_row
        if sheet.title not in ['DATA BELUM JELAS','PILIHAN MAPPING']:assert sheet.max_column==old[sheet.title].max_column
    assert w['DATA BELUM JELAS'].max_column==35 and w['PILIHAN MAPPING'].max_column==12
    it=w['PILIHAN MAPPING'].values;assert list(next(it))==MAPPING_HEADERS
    for row,expected in zip(it,records,strict=True):assert [v if v is not None else '' for v in row]==mapping_row(expected)
    oldit=old['DATA BELUM JELAS'].values;oldheaders=next(oldit);it=w['DATA BELUM JELAS'].values;headers=next(it)
    assert headers[:11]==oldheaders[:11]
    assert list(headers[11:27])==['Jumlah_Rekomendasi']+CHOICE_HEADERS
    assert headers[27:35]==oldheaders[old_client-1:old_client+7]
    samples=[];watched={'a1pJ40000008XVWIA2','a1nJ4000000KUKFIA4','a1pJ40000008XDhIAM','a1nfC00000VF9PmQAL','a1ofC000001vBcaQAE','a1pJ40000008X4aIAE','a1ofC0000004iFaQAI','a1pJ40000008X21IAE','a1ofC000002XjI9QAK','a1nJ4000000Kc2yIAC'}
    banned=re.compile(r'\b(record|lookup|hierarki|leluhur|pemulihan|verifikasi|canonical|deterministik|hipotesis|ambigu)\b',re.I)
    for row,oldrow in zip(it,oldit,strict=True):
        cs=groups[row[1]];assert row[11]==len(cs)
        assert row[:8]==oldrow[:8]
        assert tuple(row[8:11])==source_text(oldrow[8],oldrow[9],oldrow[5],oldrow[7],oldrow[10])
        assert not banned.search(' '.join(str(v) for v in row[8:10] if v))
        assert row[27:35]==oldrow[old_client-1:old_client+7]
        for i in range(3):
            values=[v or '' for v in row[12+i*5:17+i*5]]
            assert values==(client_candidate(cs[i]) if i<len(cs) else ['']*5)
            assert not banned.search(' '.join(values[3:5]))
        options=[tuple(v or '' for v in row[12+i*5:15+i*5]) for i in range(3) if row[12+i*5] is not None]
        assert len(options)==len(set(options)),row[1]
        if row[1] in watched:samples.append({'Nama':row[2],'Rekomendasi':row[12:17]})
        if row[1] in {'a1oJ40000009gGfIAI','a1oJ40000009VymIAE','a1ofC00000504n7QAA'}:
            assert row[11]==0 and not any(row[12:27]),row[1]
            assert 'Provinsi:' in row[10] and row[10]==oldrow[10]
    print('PASS: one ID/status/note per choice; names, paths, ranks and all candidate IDs agree with source CSV; pending IDs remain labelled; input values preserved.')
    print(json.dumps(samples,ensure_ascii=False,indent=2));old.close();w.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path);parser.add_argument('after',type=Path);parser.add_argument('candidates',type=Path)
    args=parser.parse_args();check(args.before,args.after,args.candidates)
