"""Independently validate the Parent-to-PERUBAHAN merge against every old row."""
import argparse,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_valid_region_reclassification import Archive,NS
from check_daikin_review_readability import dropdowns

OLD_PARENT='PERBAIKAN PARENT - ID TETAP'

def pad(v,n):return tuple(v)+(None,)*(n-len(v))

def paths(value):
    return [line[2:] for line in value.splitlines() if line.startswith('• ')] if '\n' in value else [value]

def converted_decision(value):
    return {'SETUJU_UBAH':'Setujui usulan','TOLAK_PERUBAHAN':'Tolak usulan','PERLU_DISKUSI':'Perlu diskusi',
            'Gunakan ID final':'Gunakan nilai final'}.get(value,value)


def check(before,after):
    stats=Counter();expected={};names={};parent_groups=defaultdict(list);before_ids=set();unchanged_ids=set()
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert bz.testzip() is None
        a,b=Archive(az),Archive(bz)
        old_titles=[s.get('name') for s in E.fromstring(az.read('xl/workbook.xml')).find('m:sheets',NS)]
        new_wb=E.fromstring(bz.read('xl/workbook.xml'));new_titles=[s.get('name') for s in new_wb.find('m:sheets',NS)]
        assert len(new_titles)==14 and new_titles==[s for s in old_titles if s!=OLD_PARENT]
        assert set(az.namelist())-set(bz.namelist())=={'xl/worksheets/sheet16.xml'}
        assert not(set(bz.namelist())-set(az.namelist()))
        changed={n for n in bz.namelist() if az.read(n)!=bz.read(n)}
        assert changed<={'xl/workbook.xml','xl/_rels/workbook.xml.rels','[Content_Types].xml','docProps/app.xml',
                        'xl/sharedStrings.xml',*[f'xl/worksheets/sheet{i}.xml' for i in [1,2,3,8,9,10]]}
        for i in [4,5,6,7,11,13,14,15]:
            assert az.read(f'xl/worksheets/sheet{i}.xml')==bz.read(f'xl/worksheets/sheet{i}.xml')
            if i in [4,5,6,7,13,14]:
                for v,_ in a.rows(i):
                    if v[0]!='Objek':assert v[1] not in unchanged_ids;unchanged_ids.add(v[1])
        allowed_paths=defaultdict(set)
        for i in [8,9,10]:
            for ov,_ in a.rows(i):
                if ov[0]=='Objek':continue
                v=pad(ov,20);assert v[1] not in before_ids;before_ids.add(v[1]);names[v[1]]=v[2];allowed_paths[v[1]].add(v[10])
                primary={'Kota/Kabupaten':'Parent Provinsi','Kecamatan':'Parent Kabupaten/Kota','Kelurahan':'Parent Kecamatan'}[v[0]]
                fields=[('Nama',v[2],v[3],v[14]),(primary,v[5],v[7],v[15])]
                if v[0]=='Kelurahan':fields.append(('Kabupaten/Kota Langsung',v[8],v[9],v[16]))
                for field,cur,proposed,final in fields:
                    if (cur or '')==(proposed or '') and not final:continue
                    key=(v[1],field);assert key not in expected
                    expected[key]={'identity':v[:3],'current':cur,'proposal':proposed,'master':v[10],
                                   'answers':(converted_decision(v[13]),final,None,v[17],v[18],v[19]),
                                   'old_reason':v[12],'old_kind':'wide'}
        assert len(before_ids)==8606 and len(expected)==8625
        for ov,_ in a.rows(16):
            if ov[0]=='Objek':continue
            v=pad(ov,19);parent_groups[v[1]].append(v);names[v[1]]=v[2];allowed_paths[v[1]].update(paths(v[9]))
            key=(v[1],v[3]);assert key not in expected
            expected[key]={'identity':v[:3],'current':v[4],'proposal':v[7],'master':v[9],
                           'answers':(converted_decision(v[14]),v[15],None,v[16],v[17],v[18]),
                           'old_reason':v[12],'old_kind':'parent','old':v}
        assert len(parent_groups)==9000 and not before_ids&set(parent_groups)
        before_ids.update(parent_groups)
        # A name row is needed only when none of the previously displayed master
        # names is exactly the current Salesforce name. Never guess one of several.
        new_names={}
        for rid,group in parent_groups.items():
            candidate_names={p.split(' | ')[-1] for p in allowed_paths[rid]}
            if group[0][2] not in candidate_names:new_names[rid]=candidate_names
        assert len(new_names)==132
        actual={};sheet_counts={};source_counts={};known_count=0
        for i in [8,9,10]:
            meta=b.metadata(i);options=dropdowns(meta);header=None;n=0;sheet_ids=set()
            for rownum,(nv,_) in enumerate(b.rows(i),1):
                v=pad(nv,19)
                if rownum==1:
                    assert len(nv)==19 and all('_' not in h for h in nv);header=nv;continue
                assert v[1] in before_ids and v[2]==names[v[1]]
                n+=1;sheet_ids.add(v[1]);key=v[1],v[3];assert key not in actual;actual[key]=v
                if key in expected:
                    e=expected[key];assert v[:3]==e['identity'] and v[4]==e['current'] and v[7]==e['proposal']
                    assert v[9]==e['master'] and v[13:]==e['answers'],'IDs, master evidence or answers changed'
                    if e['old_kind']=='wide':assert e['old_reason'] in v[11]
                    else:
                        old=e['old'];assert v[5]==old[5] and v[8]==old[8] and v[12]==old[13]
                        if old[6]:assert v[6]=='Dari pencocokan: '+old[6]
                        # Preserve detailed missing-ID explanations, not boilerplate.
                        reason=re.search(r'(Alasan ID .*?)(?=\n• Periksa juga|\n• Usulan berlaku|\Z)',old[12],re.S)
                        if reason:assert reason[1].replace('Id Relasi Final','Nilai Final') in v[11]
                else:
                    assert v[3]=='Nama' and v[1] in new_names and v[4]==v[2]
                    target_names=new_names[v[1]];assert v[7]==(next(iter(target_names)) if len(target_names)==1 else None)
                    assert set(paths(v[9]))==allowed_paths[v[1]] and not any(v[13:]),'New name confirmation must not inherit approval'
                assert set(paths(v[9]))<=allowed_paths[v[1]],'Invented master location'
                needs_location=len(paths(v[9]))>1 or 'lokasi' in v[10].lower()
                can_accept=bool(v[7]) and not needs_location and (v[3]=='Nama' or ';' not in v[7])
                assert ('Setujui usulan' in options['N',rownum])==can_accept
                known_count+=can_accept
                stats['pending_value_rows']+=not v[7];stats['pending_location_rows']+=needs_location
                if v[7] is None and v[3]!='Nama':stats['blank_relation_proposals']+=1
            sheet_counts[i]=n;source_counts[i]=len(sheet_ids)
            assert meta.find('m:dimension',NS).get('ref')==f'A1:S{n+1}'
            assert meta.find('m:autoFilter',NS).get('ref')==f'A1:S{n+1}'
            assert meta.find('m:sheetViews/m:sheetView/m:pane',NS).get('topLeftCell')=='D2'
            custom=meta.findall('m:dataValidations/m:dataValidation',NS)
            assert any(d.get('type')=='custom' and '$D2="Nama"' in d.findtext('m:formula1',namespaces=NS) for d in custom)
            rules=meta.findall('m:conditionalFormatting/m:cfRule/m:formula',NS)
            assert any('Gunakan nilai final' in r.text and '$O2=""' in r.text for r in rules)
            with bz.open(f'xl/worksheets/sheet{i}.xml') as f:
                for _,row in E.iterparse(f,events=('end',),tag='{'+NS['m']+'}row'):
                    if row.get('r')!='1':
                        cells={openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
                        assert all(cells[c].get('s')==('18' if c==19 else '17') for c in range(14,20))
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        assert set(expected)<=set(actual)
        assert set(actual)-set(expected)=={(rid,'Nama') for rid in new_names}
        assert set(rid for rid,kind in actual)==before_ids and not before_ids&unchanged_ids
        assert len(before_ids|unchanged_ids)==91306
        assert sheet_counts=={8:458,9:830,10:20039} and source_counts=={8:458,9:819,10:16329}
        assert stats['blank_relation_proposals']==7310 and stats['pending_value_rows']==7333 and stats['pending_location_rows']==6128
        # Summary counts distinct data IDs; the number of review rows is separate.
        oldsum=[pad(v,9) for v,_ in a.rows(2)];newsum=[v for v,_ in b.rows(2)]
        for ov,nv in zip(oldsum[1:],newsum[1:]):
            assert len(nv)==8 and nv[:3]==ov[:3] and nv[4:]==ov[4:8]
            assert nv[3]==ov[3]+ov[8]
        assert sum(v[3] for v in newsum[1:])==17606
        for d in new_wb.findall('m:definedNames/m:definedName',NS):
            assert OLD_PARENT not in d.text
            local=int(d.get('localSheetId'));assert 0<=local<14
            assert new_titles[local] in d.text
        rels=E.fromstring(bz.read('xl/_rels/workbook.xml.rels'))
        assert not any(r.get('Target')=='worksheets/sheet16.xml' for r in rels)
        app=E.fromstring(bz.read('docProps/app.xml'));ns={'a':app.nsmap[None],'v':app.nsmap['vt']}
        titles=app.find('a:TitlesOfParts/v:vector',ns);assert titles.get('size')=='14' and [n.text for n in titles]==new_titles
        for name in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):
                assert re.search(rb'<f(?:\s|>)',bz.read(name)) is None,'New cell formulas'
        # No active cell may direct the client to the removed sheet.
        for i in [1,2,3,8,9,10]:
            assert not any(OLD_PARENT in str(value).upper() for v,_ in b.rows(i) for value in v)
        # Familiar examples: both Hutagurgur relationships remain independent;
        # the approved Belimbing proposal stays a same-ID, name-only review.
        h=[v for (rid,kind),v in actual.items() if rid=='a1nfC00000VF9uNQAT']
        assert {v[3] for v in h}=={'Parent Kecamatan','Kabupaten/Kota Langsung'}
        assert next(v for v in h if v[3]=='Parent Kecamatan')[7] is None
        assert next(v for v in h if v[3]=='Kabupaten/Kota Langsung')[7]=='a1oJ40000009JMgIAM'
        bel=actual['a1pJ40000008X0WIAU','Nama'];assert bel[7]=='Belimbing' and bel[1]=='a1pJ40000008X0WIAU'
    wb=openpyxl.load_workbook(after,read_only=True);assert wb.sheetnames==new_titles
    assert wb['DATA BELUM JELAS'].max_row==17118 and wb['PILIHAN MAPPING'].max_row==59405;wb.close()
    result={'checks':'PASS','sheet_count':14,'source_ids':91306,'unique_changes':len(before_ids),'change_rows':len(actual),
            'extra_name_confirmations':len(new_names),'sheet_rows':sheet_counts,'sheet_source_ids':source_counts,
            'rows_with_accept_option':known_count,**dict(stats),'unchanged_other_sheets':8}
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    args=p.parse_args();check(args.before,args.after)
