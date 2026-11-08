"""Independent whole-workbook invariants for the readability/evidence stage."""
import argparse,csv,json,re,sys
from collections import Counter,defaultdict
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_valid_region_reclassification import Archive,NS
from regional_matching import normalize,conflicting_region_words


def pad(v,n):return tuple(v)+(None,)*(n-len(v))


def dropdowns(meta):
    result={}
    for dv in meta.findall('m:dataValidations/m:dataValidation',NS):
        assert dv.get('showErrorMessage')=='1' and dv.get('errorStyle')=='stop'
        if dv.get('type')!='list':continue
        options=dv.findtext('m:formula1',namespaces=NS).strip('"').split(',')
        for ref in dv.get('sqref').split():
            start,end=(ref.split(':')+[ref])[:2] if ':' not in ref else ref.split(':')
            col=re.sub(r'\d','',start);lo=int(re.sub(r'\D','',start));hi=int(re.sub(r'\D','',end))
            for row in range(lo,hi+1):
                assert (col,row) not in result;result[col,row]=options
    return result


def check(before,after,pipeline):
    inv=defaultdict(set)
    with (pipeline/'04_Master_Targets/Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            p=r['Master_Path'].split(' | ');inv[len(p)-1,normalize(p[-1],len(p)-1)].add(r['Master_Path'])
    stats=Counter();source_ids=Counter();counts={};removed_first=[];later=[];evidence={}
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist() and bz.testzip() is None
        a,b=Archive(az),Archive(bz)
        names=lambda z:[s.get('name') for s in E.fromstring(z.read('xl/workbook.xml')).find('m:sheets',NS)]
        assert names(az)==names(bz) and len(names(bz))==15
        for i,width in [(4,12),(5,12),(6,12),(7,17),(8,20),(9,20),(10,20),(11,14),(13,15),(14,23),(16,19)]:
            count=0
            for old,new in zip_longest(a.rows(i),b.rows(i)):
                assert old is not None and new is not None,'Record row count changed'
                ov=pad(old[0],width);nv=pad(new[0],width)
                if ov[0]=='Objek':continue
                count+=1
                if i in [4,5,6]:assert old==new
                elif i==7:
                    assert ov[:12]==nv[:12] and not any(nv[12:])
                    stats['valid_pending']+='Penetapan ID utama' in (nv[9] or '')
                elif i in [8,9,10,11,13]:assert ov==nv,'Data or answers changed while styling'
                elif i==16:
                    assert ov[:9]==nv[:9] and ov[10:12]==nv[10:12] and ov[13:]==nv[13:],'Parent relationship or client answers changed'
                    if ov[9]!=nv[9]:
                        old_paths=[line[2:] for line in ov[9].splitlines() if line.startswith('• ')]
                        new_paths=[line[2:] for line in nv[9].splitlines() if line.startswith('• ')]
                        assert new_paths and set(new_paths)<set(old_paths)
                        assert all(conflicting_region_words(ov[2],p.split(' | ')[-1]) for p in set(old_paths)-set(new_paths))
                        stats['parent_master_options_removed']+=len(old_paths)-len(new_paths)
                    assert 'Catatan data sebelum pemisahan baris' not in nv[12]
                    stats['parent_notes']+=ov[12]!=nv[12]
                elif i==14:
                    for c in range(23):
                        if c not in {4,8,9,11,12,13,14,15}:assert ov[c]==nv[c],('Source or answers changed',ov[1],c)
                    if ov[4]!=nv[4]:assert ov[4] in {0,'0'} and nv[4]=='Belum diketahui'
                    if ov[11:16]!=nv[11:16] and ov[13]!=nv[13]:
                        assert (ov[15] or '').startswith('Nama mirip') and conflicting_region_words(ov[2],ov[11])
                        assert not any(nv[11:16]);removed_first.append(nv[1])
                    if nv[15] and 'Pilihan lain pada PILIHAN MAPPING memiliki ID' in nv[15]:later.append(nv[1])
                    if nv[8]=='Nama ada di master; lokasi perlu konfirmasi':
                        p=sorted(inv[['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan'].index(nv[0]),normalize(nv[2],['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan'].index(nv[0]))])
                        assert p and not nv[13] and not nv[11];evidence[nv[1]]=p
                        assert all(path in nv[9] for path in p[:3])
                        assert ('+'+str(len(p)-3)+' lokasi lainnya' in nv[9]) if len(p)>3 else True
                    assert not nv[13] or nv[13]!=nv[1],'Self recommendation reintroduced'
                    stats['id_available' if nv[13] else 'id_blank']+=1
                    if not nv[13]:stats['location_without_id' if nv[12] else 'no_recommendation']+=1
                if i!=11 and i!=16:source_ids[nv[1]]+=1
            counts[i]=count
        parent_ids={v[1] for v,_ in b.rows(16) if v[0]!='Objek'};source_ids.update(parent_ids)
        assert len(source_ids)==91306 and set(source_ids.values())=={1}
        assert len(removed_first)==7 and len(later)==424 and len(evidence)==855
        assert stats['id_available']==11485 and stats['id_blank']==5632
        assert stats['location_without_id']==3604 and stats['no_recommendation']==2028
        oldmap=[pad(v,12) for v,_ in a.rows(15)];newmap=[pad(v,12) for v,_ in b.rows(15)]
        assert len(newmap)==len(oldmap)+857
        for ov,nv in zip(oldmap,newmap):
            if ov==nv:continue
            assert ov[:6]==nv[:6] and ov[9:]==nv[9:]
            assert (ov[8] or '').startswith('Nama mirip') and conflicting_region_words(ov[2],ov[4])
            assert nv[6] is None and nv[7]=='Nama berbeda; perlu konfirmasi';stats['unsafe_options']+=1
        assert stats['unsafe_options']==97
        appended=newmap[len(oldmap):];extra=[r for r in appended if r[7]=='Nama berbeda; perlu konfirmasi'];assert len(extra)==2
        assert {r[1] for r in appended if r[7]=='Nama sama; lokasi perlu dikonfirmasi'}==set(evidence)
        for v in appended:
            if v[7]=='Nama berbeda; perlu konfirmasi':
                assert not v[6] and v[1] in removed_first
                assert all(line[2:] in set().union(*inv.values()) for line in v[5].splitlines() if line.startswith('• '))
                continue
            paths=evidence[v[1]];assert not v[6] and int(v[11])==len(paths)
            actual=[line[2:] for line in v[5].splitlines() if line.startswith('• ')]
            assert actual==paths[:3] and v[9]=='Master' and v[7]=='Nama sama; lokasi perlu dikonfirmasi'
        # The first candidate remains in place; no alternative is promoted simply
        # because it has an ID. All 424 missing-first-ID records keep their fields.
        beforedata={v[1]:pad(v,23) for v,_ in a.rows(14)}
        afterdata={v[1]:pad(v,23) for v,_ in b.rows(14)}
        for rid in later:assert beforedata[rid][11:15]==afterdata[rid][11:15]
        for i in [7,8,9,10,11,13,14,15,16]:
            meta=b.metadata(i);pane=meta.find('m:sheetViews/m:sheetView/m:pane',NS)
            assert pane.get('topLeftCell')=='D2'
        dm=dropdowns(b.metadata(14));pm=dropdowns(b.metadata(16));vm=dropdowns(b.metadata(7))
        for row,(v,_) in enumerate(b.rows(14),1):
            if row==1:continue
            v=pad(v,23);opts=dm['Q',row]
            assert ('Gunakan rekomendasi 1' in opts)==bool(v[13] and ';' not in v[13])
        for row,(v,_) in enumerate(b.rows(16),1):
            if row==1:continue
            v=pad(v,19);opts=pm['O',row]
            assert ('Setujui usulan' in opts)==bool(v[7])
            assert 'Gunakan ID final' in opts
        assert len(vm)==1059 and stats['valid_pending']==1059
        for i in [7,8,9,10,11,13,14,16]:assert b.metadata(i).find('m:conditionalFormatting',NS) is not None
        for name in bz.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):assert re.search(rb'<f(?:\s|>)',bz.read(name)) is None
        # Check all review-input styles (yellow), not just selected samples.
        for i,lo,hi in [(8,14,20),(9,14,20),(10,14,20),(11,7,13),(13,11,15),(14,17,23),(16,15,19)]:
            with bz.open(f'xl/worksheets/sheet{i}.xml') as f:
                for _,row in E.iterparse(f,events=('end',),tag='{'+NS['m']+'}row'):
                    if row.get('r')!='1':
                        cells={openpyxl.utils.column_index_from_string(re.sub(r'\d','',c.get('r'))):c for c in row}
                        assert all(cells[c].get('s')==('18' if c==hi else '17') for c in range(lo,hi+1))
                        assert float(row.get('ht'))>=36
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
    wb=openpyxl.load_workbook(after,read_only=True);assert len(wb.sheetnames)==15
    assert wb['VALID KELURAHAN'].max_column==17 and wb['DATA BELUM JELAS'].max_column==23
    assert wb['PILIHAN MAPPING'].max_row==59405;wb.close()
    result={'counts':dict(stats),'sheet_records':counts,'source_ids':len(source_ids),'blocked_first':len(removed_first),
            'master_evidence_sources':len(evidence),'later_id_notes':len(later),'checks':'PASS'}
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['before','after','pipeline']:p.add_argument(name,type=Path)
    args=p.parse_args();check(args.before,args.after,args.pipeline)
