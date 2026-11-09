"""Two editable English slides: master hierarchy and Salesforce review findings.

Read-only inputs. Counts are reconciled against the reference master, source
CSVs and current Daikin workbook before any presentation is written.
"""
import argparse,csv,hashlib,json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import openpyxl
from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches,Pt
from zipfile import ZipFile
from daikin_review_readability import Package

LEVELS=['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan']
LABELS=['Province','City / regency','District','Village']
STEM='Daikin_Master_and_Salesforce_Summary_2_Slides'
COLORS={'ink':'153447','muted':'59707E','bg':'F3F7FA','white':'FFFFFF','line':'DCE7EE',
        'blue':'0075BA','teal':'138D83','purple':'7763A8','amber':'AF7313','coral':'C65B43','pale':'E6F2FA'}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def get_counts(workbook,root):
    sha=digest(workbook)
    with ZipFile(workbook) as z:
        a=Package(z);summary=[a.values(r,8) for r in a.rows(2)][1:]
        assert [r[0] for r in summary]==LEVELS
        master=[r[1] for r in summary];source=[sum(r[i] for i in [2,3,5,6]) for r in summary]
        totals={key:sum(r[i] for r in summary) for key,i in [('master',1),('valid',2),('changes',3),('new',4),('duplicates',5),('unclear',6),('pending_primary',7)]}
        seen=set();counts={}
        for sheet in [4,5,6,7,8,9,10,13,14]:
            local=set()
            for row in a.rows(sheet):
                if row.get('r')=='1':continue
                cells=a.cells(row);rid=a.val(cells[2]);assert rid
                assert rid not in local or sheet in [8,9],'Unexpected duplicate review row'
                local.add(rid)
            assert not seen&local,'Source ID belongs to multiple review groups'
            seen.update(local);counts[sheet]=len(local)
        assert sum(counts[i] for i in [4,5,6,7])==totals['valid']
        assert sum(counts[i] for i in [8,9,10])==totals['changes']
        assert counts[13]==totals['duplicates'] and counts[14]==totals['unclear']
        detail=Counter()
        for row in a.rows(14):
            if row.get('r')=='1':continue
            v=a.values(row,23)
            if v[13]:
                detail['id_available']+=1
                detail['multiple_ids']+=';' in v[13]
            else:detail['location_only' if v[12] else 'no_recommendation']+=1
        assert sum(detail[k] for k in ['id_available','location_only','no_recommendation'])==totals['unclear']
        new_counts=Counter(a.values(r,14)[0] for r in a.rows(11) if r.get('r')!='1')
        assert [new_counts[l] for l in LEVELS]==[r[4] for r in summary]
    reference=root/'Service Territory MASTER FIX.xlsx';wb=openpyxl.load_workbook(reference,read_only=True,data_only=True)
    paths=[set() for _ in range(4)];raw_rows=0
    for r in wb['Service Territory'].iter_rows(min_row=2,values_only=True):
        if not any(v is not None for v in r):continue
        p=(r[0],r[1],r[3],r[5]);assert all(p);raw_rows+=1
        for level in range(4):paths[level].add(p[:level+1])
    wb.close();assert list(map(len,paths))==master
    csv_counts=[];csv_ids=set();csv_hashes={}
    for filename in ['Provinsi.csv','Kota Kabupaten.csv','Kecamatan.csv','Kelurahan.csv']:
        path=root/filename;ids=set()
        with path.open(encoding='cp1252',newline='') as f:
            for r in csv.DictReader(f):
                assert r['Id'] not in ids and r['IsDeleted'].upper()=='FALSE';ids.add(r['Id'])
        assert not csv_ids&ids;csv_ids.update(ids);csv_counts.append(len(ids));csv_hashes[filename]=digest(path)
    assert csv_counts==source and csv_ids==seen
    total_source=sum(source);assert sum(totals[k] for k in ['valid','changes','duplicates','unclear'])==total_source
    assert totals['pending_primary']<=totals['valid'];assert sha==digest(workbook)
    return dict(totals,source=total_source,master_by_level=master,source_by_level=source,
                new_by_level=[new_counts[l] for l in LEVELS],unclear_detail=dict(detail),
                raw_master_rows=raw_rows,workbook_sha256=sha,reference_sha256=digest(reference),csv_sha256=csv_hashes)


def build(workbook,root,out,ref):
    c=get_counts(workbook,root);out.mkdir(exist_ok=True,parents=True)
    sha=c['workbook_sha256'];stamp=datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%d %b %Y')
    url='https://github.com/salvianwork/ChatGPTWorkSpace/blob/'+ref+'/cleansing/client_review/Mandatory%20for%20Client/Daikin_Cleansing_Data_Regional.xlsx'
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    prs.core_properties.title='Daikin | Master and Salesforce Regional Data Summary'
    prs.core_properties.author='Tim Daikin | Regional Data Review'
    prs.core_properties.subject='Reference locations, Salesforce review groups, and required decisions'
    prs.core_properties.comments='Source workbook SHA-256 '+sha
    text_shapes=[]
    def rgb(color):return RGBColor.from_string(COLORS.get(color,color))
    def rect(s,x,y,w,h,color):
        shape=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
        shape.fill.solid();shape.fill.fore_color.rgb=rgb(color);shape.line.fill.background()
        for e in shape._element.xpath('./p:style/a:effectRef'):e.set('idx','0')
    def text(s,x,y,w,h,value,size=13,color='ink',bold=False,align=None):
        shape=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=shape.text_frame
        tf.clear();tf.word_wrap=True;tf.margin_top=tf.margin_bottom=tf.margin_left=tf.margin_right=0
        for i,line in enumerate(value.split('\n')):
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.line_spacing=1.08;p.space_after=Pt(2)
            if align is not None:p.alignment=align
            for run in p.runs:
                run.font.name='DejaVu Sans';run.font.size=Pt(size);run.font.bold=bold;run.font.color.rgb=rgb(color)
                run._r.get_or_add_rPr().set('lang','en-US')
        text_shapes.append(shape);return shape
    def base(n,title,subtitle):
        s=prs.slides.add_slide(prs.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=rgb('bg')
        rect(s,0,0,13.333,.07,'blue')
        text(s,.55,.25,12.1,.22,'DAIKIN  /  REGIONAL DATA REVIEW',10,'blue',True)
        text(s,.55,.64,12.2,.55,title,26,'ink',True)
        text(s,.55,1.30,12.2,.36,subtitle,12,'muted')
        rect(s,.55,7.07,12.23,.012,'line')
        sh=text(s,.55,7.19,11.4,.16,'Source: Daikin_Cleansing_Data_Regional.xlsx  |  '+sha[:10]+'  |  '+stamp,8.5,'muted')
        for p in sh.text_frame.paragraphs:
            for r in p.runs:r.hyperlink.address=url
        text(s,12.05,7.17,.72,.20,f'{n:02} / 02',9,'blue',True,PP_ALIGN.RIGHT)
        return s
    def donut(s,x,y,w,h,labels,values,colors):
        data=ChartData();data.categories=labels;data.add_series('Count',values)
        chart=s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT,Inches(x),Inches(y),Inches(w),Inches(h),data).chart
        chart.has_legend=False;chart.has_title=False;plot=chart.plots[0];plot.has_data_labels=False
        chart._chartSpace.xpath('.//c:holeSize')[0].set('val','77')
        chart._chartSpace.xpath('.//c:firstSliceAng')[0].set('val','270')
        for point,color in zip(chart.series[0].points,colors):
            point.format.fill.solid();point.format.fill.fore_color.rgb=rgb(color);point.format.line.fill.background()
    def notes(s,value):s.notes_slide.notes_text_frame.text=value+'\n\nSource: '+url+'\nWorkbook SHA-256: '+sha
    fmt=lambda n:f'{n:,}'
    s=base(1,'Master data | Location hierarchy & comparison',
           'Use the full location hierarchy: Province → City / Regency → District → Village.')
    rect(s,.55,1.86,3.10,1.21,'white')
    text(s,.76,2.02,2.68,.22,'MASTER REFERENCE LOCATIONS',10,'blue',True)
    text(s,.76,2.36,2.68,.40,fmt(c['master']),29,'ink',True)
    text(s,.76,2.88,2.68,.18,'38 provinces  •  4 regional levels',10.5,'muted')
    rect(s,.55,3.25,3.10,2.45,'white')
    donut(s,.68,3.36,2.84,2.13,LABELS,c['master_by_level'],['purple','amber','blue','teal'])
    text(s,1.21,4.12,1.78,.34,f"{c['master_by_level'][3]/c['master']:.1%}",17.5,'teal',True,PP_ALIGN.CENTER)
    text(s,1.21,4.52,1.78,.21,'villages',9,'muted',False,PP_ALIGN.CENTER)
    rect(s,3.88,1.86,8.90,.47,'ink')
    for x,w,label,align in [(4.08,2.14,'REGIONAL LEVEL',None),(6.43,1.55,'MASTER',PP_ALIGN.RIGHT),
                             (8.30,1.80,'SALESFORCE',PP_ALIGN.RIGHT),(10.39,2.16,'CHECK BEFORE CREATE',PP_ALIGN.RIGHT)]:
        text(s,x,2.00,w,.20,label,9.5,'white',True,align)
    level_colors=['purple','amber','blue','teal']
    for i in range(5):
        y=2.33+i*.62;total=i==4;bg='ink' if total else 'white';color='white' if total else 'ink'
        rect(s,3.88,y,8.90,.59,bg)
        if not total:rect(s,3.88,y,.045,.59,level_colors[i])
        values=[c['master'],c['source'],c['new']] if total else [c['master_by_level'][i],c['source_by_level'][i],c['new_by_level'][i]]
        text(s,4.08,y+.18,2.15,.26,'TOTAL' if total else LABELS[i],12,color,total)
        for x,w,value in zip([6.43,8.30,10.39],[1.55,1.80,2.16],values):text(s,x,y+.17,w,.28,fmt(value),15,color,True,PP_ALIGN.RIGHT)
    text(s,3.91,5.59,8.84,.24,'Master = distinct location paths. Salesforce = record IDs.',10.5,'muted')
    text(s,3.91,5.87,8.84,.24,'Differences between totals do not measure missing locations or duplicates.',10.2,'muted')
    rect(s,.55,6.24,12.23,.62,'pale')
    text(s,.75,6.37,1.75,.30,fmt(c['new']),21,'blue',True)
    text(s,2.66,6.34,9.82,.44,'Locations flagged for an existing-record check (CALON DATA BARU).\nConfirm old records and Parent IDs before approving creation.',11.2,'ink')
    notes(s,'The master count is the sum of distinct hierarchy paths at all four levels, reconciled to Service Territory MASTER FIX.xlsx. '
          f"There are {c['raw_master_rows']:,} source rows and {c['master_by_level'][3]:,} unique village paths. "
          'Master counts are locations; Salesforce counts are exported record IDs. A row-count difference is not a missing-data or duplicate count. '
          f"The {c['new']:,} locations on CALON DATA BARU are proposals to check before creation: {c['new_by_level'][1]:,} cities/regencies, "
          f"{c['new_by_level'][2]:,} districts, and {c['new_by_level'][3]:,} villages. Existing records may need Parent repairs or ID confirmation. "
          'Creating a new record requires confirming that an existing record cannot be reused. No workbook data was changed.')

    s=base(2,'Salesforce data | Findings & required decisions',
           f"{fmt(c['source'])} record IDs  •  {fmt(c['valid'])} match master locations  •  {fmt(c['source']-c['valid'])} in other review groups")
    rect(s,.55,1.86,3.60,3.64,'white')
    text(s,.77,2.03,3.16,.22,'CURRENT REVIEW GROUPS',10,'muted',True,PP_ALIGN.CENTER)
    groups=['Location matches master','Proposed changes','Duplicate proposals','Location / ID unclear']
    vals=[c['valid'],c['changes'],c['duplicates'],c['unclear']];colors=['teal','blue','coral','amber']
    donut(s,.75,2.40,3.20,2.53,groups,vals,colors)
    text(s,1.27,3.34,2.17,.40,fmt(c['source']),18,'ink',True,PP_ALIGN.CENTER)
    text(s,1.27,3.83,2.17,.22,'source records',10.5,'muted',False,PP_ALIGN.CENTER)
    text(s,.77,5.05,3.15,.23,'Each ID is counted in one group.',10,'muted',False,PP_ALIGN.CENTER)
    rect(s,4.36,1.86,8.42,.46,'ink')
    text(s,4.55,2.00,2.40,.20,'REVIEW GROUP',9.5,'white',True)
    text(s,6.90,2.00,1.18,.20,'RECORDS',9.5,'white',True,PP_ALIGN.RIGHT)
    text(s,8.29,2.00,4.22,.20,'ACTION FOR TIM DAIKIN',9.5,'white',True)
    actions=[f"Keep location; select primary IDs for\n{fmt(c['pending_primary'])} records still awaiting confirmation.",
             'Confirm name and Parent edits;\nreview each active section separately.',
             'Choose the record to retain;\ncheck child references before merging.',
             'Confirm location, regional level,\nand the Salesforce ID to use.']
    for i,(label,value,color,action) in enumerate(zip(groups,vals,colors,actions)):
        y=2.32+i*.795;rect(s,4.36,y,8.42,.765,'white');rect(s,4.36,y,.045,.765,color)
        text(s,4.55,y+.19,2.32,.29,label,11.7,color,True)
        text(s,6.89,y+.12,1.20,.29,fmt(value),16.5,color,True,PP_ALIGN.RIGHT)
        text(s,6.89,y+.47,1.20,.19,f'{value/c["source"]:.1%}',9.5,'muted',False,PP_ALIGN.RIGHT)
        text(s,8.29,y+.19,4.27,.46,action,11.3,'ink')
    d=c['unclear_detail'];rect(s,.55,5.73,12.23,.99,'pale')
    text(s,.74,5.91,2.23,.53,'LOCATION / ID UNCLEAR\n'+fmt(c['unclear'])+' records',11.5,'blue',True)
    for x,key,label,color in [(3.10,'id_available','Proposed ID available','blue'),(6.36,'location_only','Location found; ID pending','amber'),(9.62,'no_recommendation','No recommendation yet','coral')]:
        text(s,x,5.86,2.97,.32,fmt(d[key]),20,color,True);text(s,x,6.26,2.97,.22,label,10.6,'ink')
    text(s,3.10,6.54,9.45,.16,f"{fmt(d['multiple_ids'])} records have several proposed IDs; confirm one final ID.",8.9,'muted')
    text(s,.58,6.86,12.19,.16,f"Blank recommended IDs: {fmt(d['location_only']+d['no_recommendation'])} = {fmt(d['location_only'])} + {fmt(d['no_recommendation'])}. All proposals require confirmation; no Salesforce updates applied.",9.4,'muted')
    notes(s,f"All {c['source']:,} Salesforce source IDs reconcile to the four original CSV files and belong to exactly one main workbook review group. "
          f"The {c['pending_primary']:,} records awaiting primary-ID selection are already included in {c['valid']:,} records whose locations match master. "
          f"The {c['changes']:,} proposed-change IDs are distinct records; PERUBAHAN KELURAHAN has one row per ID and independent decisions for Name, Parent Kecamatan and Kabupaten/Kota Langsung. "
          'Review groups are proposals and location classifications, not evidence of an upload approval. Duplicate proposals require checking child references and selecting the retained record. '
          f"DATA BELUM JELAS has {d['id_available']:,} records with a proposed ID, {d['location_only']:,} with a location but no ID, and {d['no_recommendation']:,} with no recommendation. "
          f"A blank ID filter returns {d['location_only']+d['no_recommendation']:,}, not only the no-recommendation group. "
          'Current review limitations remain open: alternative-name confirmation, source ID appearing among multiple candidates, and lengthy notes. The slides do not implement changes to those workflows.')
    assert len(prs.slides)==2
    for shape in text_shapes:
        assert shape.left>=0 and shape.top>=0 and shape.left+shape.width<=prs.slide_width and shape.top+shape.height<=prs.slide_height
    path=out/(STEM+'.pptx');prs.save(path)
    assert digest(workbook)==sha,'Workbook changed during summary generation'
    (out/'source_and_counts.json').write_text(json.dumps(dict(c,workbook=str(workbook),source_ref=ref,language='en',slides=2),ensure_ascii=False,indent=2))
    print(path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',type=Path,required=True);p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--source-ref',default='854873192b9c8cf52c3f04a1b17baefa2c3daabd')
    a=p.parse_args();build(a.workbook,a.source_dir,a.output_dir,a.source_ref)
