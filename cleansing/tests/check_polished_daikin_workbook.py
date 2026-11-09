"""Audit every cell/value plus XLSX structure after evidence/format repair."""
import argparse,csv,json,re,sys,posixpath
from collections import Counter,defaultdict
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from openpyxl.utils import column_index_from_string,range_boundaries
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_valid_region_reclassification import Archive,NS,TAG
from regional_evidence import rename_recommendation_label

PHYSICAL=[1,2,3,4,5,6,7,8,9,10,11,13,14,15]


def pad(v,n):return tuple(v)+(None,)*(n-len(v))


def package_audit(path):
    result=Counter()
    with ZipFile(path) as z:
        assert len(set(z.namelist()))==len(z.namelist()) and z.testzip() is None
        a=Archive(z);styles=E.fromstring(z.read('xl/styles.xml'));xfs=styles.find('m:cellXfs',NS)
        strings=a.strings;shared_refs=0
        assert int(xfs.get('count'))==len(xfs)
        assert int(E.fromstring(z.read('xl/sharedStrings.xml')).get('uniqueCount'))==len(strings)
        for name in z.namelist():
            if name.endswith('.rels'):
                tree=E.fromstring(z.read(name));seen=set()
                base='' if name=='_rels/.rels' else posixpath.dirname(posixpath.dirname(name))
                for r in tree:
                    assert r.get('Id') not in seen;seen.add(r.get('Id'))
                    if r.get('TargetMode')=='External':continue
                    target=r.get('Target');resolved=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(base,target))
                    assert resolved in z.namelist(),('Missing package target',name,resolved)
        for i in PHYSICAL:
            meta=a.metadata(i);bounds=range_boundaries(meta.find('m:dimension',NS).get('ref'));last=0;maxcol=0;header=None
            for col in meta.findall('m:cols/m:col',NS):assert col.get('style') is None,'Whole-column formatting outside table'
            with z.open(f'xl/worksheets/sheet{i}.xml') as f:
                for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                    n=int(row.get('r'));assert n>last;last=n
                    assert row.get('s') is None and row.get('customFormat') is None,'Whole-row formatting outside table'
                    cols=[]
                    for c in row:
                        assert c.tag==TAG+'c';ref=c.get('r');col=column_index_from_string(re.sub(r'\d','',ref));cols.append(col)
                        assert int(re.search(r'\d+',ref)[0])==n
                        assert 0<=int(c.get('s','0'))<len(xfs)
                        assert c.find('m:f',NS) is None,'New cell formulas'
                        if c.get('t')=='s':assert 0<=int(c.findtext('m:v',namespaces=NS))<len(strings);shared_refs+=1
                    assert cols==sorted(set(cols)),('Excel cell address order',i,n,cols)
                    if header is None:header=max(cols)
                    assert max(cols)<=header and n<=bounds[3]
                    maxcol=max(maxcol,max(cols));result['rows']+=1;result['cells']+=len(cols)
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
            assert maxcol==bounds[2] and last==bounds[3]
            for node in meta.findall('m:dataValidations/m:dataValidation',NS)+meta.findall('m:conditionalFormatting',NS):
                for ref in node.get('sqref').split():
                    lo,top,hi,bot=range_boundaries(ref);assert lo>=1 and top>=1 and hi<=header and bot<=last
            dv=meta.find('m:dataValidations',NS)
            if dv is not None:
                assert int(dv.get('count'))==len(dv)
                for node in dv:
                    assert len(node.get('sqref'))<=32767
                    for attr in ['prompt','error']:assert len(node.get(attr,''))<=255
                    for attr in ['promptTitle','errorTitle']:assert len(node.get(attr,''))<=32
                    formula=node.findtext('m:formula1',namespaces=NS) or ''
                    if node.get('type')=='list' and formula.startswith('"'):assert len(formula[1:-1])<=255
            result['sheets']+=1
        sst=E.fromstring(z.read('xl/sharedStrings.xml'));assert int(sst.get('count'))==shared_refs
        wb=E.fromstring(z.read('xl/workbook.xml'));titles=[n.get('name') for n in wb.find('m:sheets',NS)]
        assert len(titles)==14 and len(set(titles))==14
        for d in wb.findall('m:definedNames/m:definedName',NS):
            assert titles[int(d.get('localSheetId'))] in d.text
        ct=E.fromstring(z.read('[Content_Types].xml'))
        for node in ct:
            if node.get('PartName'):assert node.get('PartName').lstrip('/') in z.namelist()
        result['shared_string_references']=shared_refs
    return dict(result)


def check(before,after,pipeline):
    with (pipeline/'04_Master_Targets/Master_target_inventory.csv').open(encoding='utf-8-sig',newline='') as f:
        master={r['Master_Path'] for r in csv.DictReader(f)}
    stats=Counter();examples={};source_ids=set();data_ids=set();counts={};cross_changes=set()
    with ZipFile(before) as az,ZipFile(after) as bz:
        assert az.namelist()==bz.namelist()
        a,b=Archive(az),Archive(bz)
        for i in PHYSICAL:
            if i==15:continue
            n=0
            for old,new in zip_longest(a.rows(i),b.rows(i)):
                assert old is not None and new is not None,('Changed record count',i)
                ov,nv=old[0],new[0];width=max(len(ov),len(nv));ov=pad(ov,width);nv=pad(nv,width);n+=1
                for c,(x,y) in enumerate(zip(ov,nv)):
                    if i in [8,9,10] and n>1 and c==12:
                        if x!=y:stats['cross_cells']+=1;cross_changes.add(ov[1])
                        continue
                    if i==14 and n>1 and c in [10,15]:
                        if x!=y:stats['cross_cells' if c==10 else 'recommendation_notes']+=1
                        if c==10 and x!=y:cross_changes.add(ov[1])
                        if c==15 and x!=y and x:
                            marker='tingkat wilayahnya perlu diperbaiki.'
                            tail=x.split(marker,1)[1].lstrip() if x.startswith('Di master, ') and marker in x else x
                            assert tail in y,'Lost an ID-specific warning while adding master structure'
                        continue
                    assert rename_recommendation_label(x)==y,('Unexpected value/ID/answer change',i,n,c,x,y)
                if n==1:
                    if i==14:assert nv[11:16]==('Rekomendasi Nama','Rekomendasi Lokasi','Rekomendasi ID Salesforce','Rekomendasi Status','Rekomendasi Catatan')
                    continue
                if i in [4,5,6,7,8,9,10,13,14]:source_ids.add(nv[1])
                if i==14:
                    data_ids.add(nv[1]);assert ov[11:15]==nv[11:15],'Recommendation identity changed'
                    if nv[1] in {'a1pJ40000008X4aIAE','a1pJ40000008XNrIAM','a1pJ40000008X0WIAU'}:examples[nv[1]]=nv
                if i in [8,9,10,14]:
                    col=10 if i==14 else 12;text=nv[col] or ''
                    if ov[col]:assert text,'Lost existing cross-level evidence'
                    if '• Hasil Salesforce:' in (ov[col] or ''):
                        oldsf=ov[col].split('• Hasil Salesforce:',1)[1].split('• Tindak Lanjut:',1)[0]
                        newsf=text.split('• Hasil Salesforce:',1)[1].split('• Tindak Lanjut:',1)[0]
                        for line in oldsf.splitlines():
                            if line.strip().startswith('- '):
                                location=re.sub(r'^- (Provinsi|Kota/Kabupaten|Kecamatan|Kelurahan):\s*','- ',line.strip())
                                assert location in newsf,'Lost Salesforce evidence'
                    assert not re.search(r'^\s*- (Provinsi|Kota/Kabupaten|Kecamatan|Kelurahan):',text,re.M)
                    # Verify every displayed Master location against the real
                    # inventory. Salesforce evidence is never filled from Master.
                    section=None
                    for line in text.splitlines():
                        if line=='• Hasil Master:':section='master'
                        elif line=='• Hasil Salesforce:':section='sf'
                        elif line=='• Tindak Lanjut:':section=None
                        elif section=='master' and line.strip().startswith('- '):
                            path=line.strip()[2:]
                            assert path.startswith('+') or path=='Lokasi lengkap belum tersedia' or path in master,('Invented master evidence',nv[1],path)
            counts[i]=n-1
        assert len(source_ids)==91306 and len(data_ids)==17117
        assert [v for v,_ in a.rows(2)]==[v for v,_ in b.rows(2)]
        oldmap=[pad(v,12) for v,_ in a.rows(15)];newmap=[pad(v,12) for v,_ in b.rows(15)]
        assert len(newmap)==len(oldmap)+1
        for old,new in zip(oldmap,newmap):
            assert old[:5]==new[:5] and old[6:8]==new[6:8] and old[9:11]==new[9:11],'Candidate IDs/order/status changed'
            if old[5]!=new[5]:
                assert old[9]=='Master' and old[7]=='Nama ditemukan di tingkat lain'
                assert set(old[5].split('; '))<=set(new[5].split('; '))
            if old[8]!=new[8]:assert new[8].startswith(old[8]) and 'Variasi nama:' in new[8]
        extra=newmap[-1]
        assert extra[1]=='a1pJ40000008X4aIAE' and extra[6] is None and extra[9]=='Master' and extra[10]=='Kelurahan'
        expected='Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota'
        assert extra[5]==expected
        buntok=examples['a1pJ40000008X4aIAE'];assert expected in buntok[10] and expected in buntok[15]
        assert 'variasi nama “Buntok” → “Buntok Kota”' in buntok[10]
        assert buntok[13]=='a1pfC00000DcGqWQAV' and buntok[12]=='Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan'
        sf=buntok[10].split('• Hasil Salesforce:',1)[1].split('• Tindak Lanjut:',1)[0]
        assert 'Buntok Kota' not in sf and 'Lokasi lengkap belum tersedia — perlu dikonfirmasi' in sf
        assert counts=={1:7,2:4,3:29,4:38,5:54,6:6081,7:47305,8:458,9:830,10:20039,11:20511,13:3105,14:17117}
        # The open-error regression is visible in the old archive and absent now.
        with az.open('xl/worksheets/sheet11.xml') as f:
            bad=0
            for _,row in E.iterparse(f,events=('end',),tag=TAG+'row'):
                cols=[column_index_from_string(re.sub(r'\d','',c.get('r'))) for c in row]
                bad+=cols!=sorted(cols)
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
            assert bad==20511;stats['repaired_cell_order_rows']=bad
    audit=package_audit(after)
    wb=openpyxl.load_workbook(after,read_only=True);assert len(wb.sheetnames)==14
    assert wb['PILIHAN MAPPING'].max_row==59406;wb.close()
    result={'checks':'PASS','source_ids':len(source_ids),'sheet_count':14,'sheet_record_counts':counts,
            'new_mapping_evidence':1,**dict(stats),'package_audit':audit}
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['before','after','pipeline']:p.add_argument(key,type=Path)
    args=p.parse_args();check(args.before,args.after,args.pipeline)
