"""Compare every retained cell after the counter removal and Madura correction."""
import argparse
from collections import Counter
from itertools import zip_longest
from pathlib import Path
import re,sys,json
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from finalize_daikin_review import SOURCE_ID,REJECTED,COUNTER,REASON
from check_valid_region_reclassification import Archive,NS,TAG,signature


def styled_rows(archive,index):
    with archive.z.open(f'xl/worksheets/sheet{index}.xml') as f:
        for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
            cells={openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
            yield (tuple(archive.value(cells[i]) if i in cells else None for i in range(1,max(cells)+1)),
                   {i:signature(c) for i,c in cells.items()})
            row.clear()
            while row.getprevious() is not None:del row.getparent()[0]


def check(before,after):
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist() and bz.testzip() is None
        changed={n for n in az.namelist() if az.read(n)!=bz.read(n)}
        assert changed<={'xl/worksheets/sheet14.xml','xl/worksheets/sheet15.xml','xl/workbook.xml','xl/sharedStrings.xml'}
        a,b=Archive(az),Archive(bz);ids=Counter();stats=Counter();n=0;madura=0
        for old,new in zip_longest(styled_rows(a,14),styled_rows(b,14)):
            assert old is not None and new is not None
            ov,os=old;nv,ns=new;ov=ov+(None,)*(24-len(ov));nv=nv+(None,)*(23-len(nv))
            expected=list(ov[:11]+ov[12:]);special=ov[1]==SOURCE_ID
            if n==0:
                assert ov[11]==COUNTER and nv==tuple(expected) and COUNTER not in nv
            elif special:
                madura+=1;expected[9]=REASON
                expected[11:16]=[None]*5
            assert nv==tuple(expected),(n,ov[1])
            # Cell signatures omit their addresses, so shifted IDs/client cells
            # still retain their exact formatting and stored representation.
            kept={i-1 if i>12 else i:s for i,s in os.items() if i!=12}
            assert kept.keys()==ns.keys()
            for index,x in kept.items():
                y=ns[index]
                if special and index in {10,12,13,14,15,16}:
                    assert dict(x[1]).get('s')==dict(y[1]).get('s');continue
                assert x==y,('Unrelated cell format changed',n,index)
            if n:
                ids[nv[1]]+=1
                stats['ID available' if nv[13] else 'ID blank']+=1
                stats['Recommendation present' if nv[11] else 'No recommendation']+=1
            n+=1
        assert n==17129 and madura==1 and len(ids)==17128 and all(v==1 for v in ids.values())
        assert stats['ID blank']==5635 and stats['No recommendation']==2020
        removed=set();order=0;mapping_count=0
        def remaining():
            nonlocal order
            for v,s in a.rows(15):
                if v[1]==SOURCE_ID:
                    if v[6] in REJECTED:removed.add(v[6]);continue
                    assert not v[6];order+=1;values=list(v);values[3]=order;v=tuple(values)
                    yield v,s,True
                else:yield v,s,False
        for previous,current in zip_longest(remaining(),b.rows(15)):
            assert previous is not None and current is not None and previous[0]==current[0]
            if previous[2]:
                for i,(x,y) in enumerate(zip(previous[1][-1],current[1][-1],strict=True)):
                    if i!=3:assert x==y
            else:assert previous[1]==current[1]
            mapping_count+=1
        assert removed==REJECTED and order==2 and mapping_count==58588
        oldmeta,newmeta=a.metadata(14),b.metadata(14)
        assert newmeta.find('m:dimension',NS).get('ref')=='A1:W17129'
        assert newmeta.find('m:autoFilter',NS).get('ref')=='A1:W17129'
        dv=newmeta.find('m:dataValidations/m:dataValidation',NS)
        assert dv.get('sqref')=='Q2:Q17129'
        assert dv.findtext('m:formula1',namespaces=NS)==oldmeta.findtext('m:dataValidations/m:dataValidation/m:formula1',namespaces=NS)
        oc=list(oldmeta.find('m:cols',NS));nc=list(newmeta.find('m:cols',NS));assert len(nc)==23
        del oc[11]
        for i,(x,y) in enumerate(zip(oc,nc,strict=True),1):
            x.set('min',str(i));x.set('max',str(i));assert E.tostring(x)==E.tostring(y)
        aw,bw=E.fromstring(az.read('xl/workbook.xml')),E.fromstring(bz.read('xl/workbook.xml'))
        for x,y in zip(aw.findall('m:definedNames/m:definedName',NS),bw.findall('m:definedNames/m:definedName',NS),strict=True):
            if x.text.startswith("'DATA BELUM JELAS'!"):assert y.text=="'DATA BELUM JELAS'!$A$1:$W$17129";y.text=x.text
            elif x.text.startswith("'PILIHAN MAPPING'!"):assert y.text=="'PILIHAN MAPPING'!$A$1:$L$58588";y.text=x.text
        assert E.tostring(aw)==E.tostring(bw)
        for entry in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',entry):assert not re.search(rb'<f(?:\s|>)',bz.read(entry))
        report={'data_rows':n-1,'data_columns':23,'mapping_rows':mapping_count-1,'removed_madura_candidates':len(removed),
                'other_worksheets_unchanged':13,'data_counts':dict(stats),'changed_parts':sorted(changed)}
    wb=openpyxl.load_workbook(after,read_only=True)
    assert len(wb.sheetnames)==15 and wb['DATA BELUM JELAS'].max_column==23
    assert wb['PERBAIKAN PARENT - ID TETAP'].max_row==12571;wb.close()
    print(json.dumps(report,indent=2));print('PASS: all retained values/styles/IDs, client inputs, unchanged sheets, dropdown and workbook integrity.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    args=p.parse_args();check(args.before,args.after)
